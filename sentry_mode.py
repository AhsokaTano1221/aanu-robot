import time
import sys
import os
import threading
import subprocess
import json
import boto3
from datetime import datetime

# Add path to hardware libraries
project_dir = os.path.dirname(os.path.abspath(__file__))
local_path = os.path.join(project_dir, 'freenove-kit', 'Code', 'Server')
if os.path.exists(local_path):
    sys.path.insert(0, local_path)
else:
    sys.path.insert(0, '/home/eera/robot/freenove-kit/Code/Server')

try:
    from dotenv import load_dotenv
    dotenv_path = os.path.join(project_dir, '.env')
    load_dotenv(dotenv_path)
except ImportError:
    pass

def speak(text: str):
    """Speaks the given text using the system's text-to-speech tool in a non-blocking background process."""
    if not text:
        return
    print(f"🔊 Speaking: \"{text}\"")
    try:
        if sys.platform == "darwin":
            # On macOS, use the native 'say' command
            subprocess.Popen(["say", text])
        else:
            # On Linux (Raspberry Pi), use 'espeak'
            subprocess.Popen(
                ["espeak", "-s", "150", "-a", "200", "-p", "40", text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
    except Exception as e:
        print(f"⚠️ Error running text-to-speech: {e}")

def generate_threat_response(personality: str, distance_cm: float) -> str:
    """Queries Amazon Bedrock to generate a threat response based on personality and distance.
    Falls back to local responses if the API call fails.
    """
    fallbacks = {
        "aggressive": "Intruder detected! Step back immediately or face consequences.",
        "polite": "Excuse me, you are trespassing in a restricted area. Please leave.",
        "paranoid": "Ah! A human! Don't look at me, stay away!",
        "snarky": "Oh look, another intruder. How original. Please leave before I get bored.",
        "cute": "Hello human! You are not supposed to be here, please go away.",
    }
    
    try:
        # Create Bedrock Runtime client
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        
        system_prompt = (
            f"You are a sentry robot. You have detected a human intruder's face at a distance of {distance_cm}cm. "
            f"Your current personality mode is: {personality}. "
            "Generate a short, menacing, humorous, or alert response matching your personality (1-2 sentences max). "
            "Speak directly to the intruder. Do not include any meta-text, introductions, markdown, or quotes. "
            "Only output the spoken text."
        )
        
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": "React to the intruder."
                }
            ],
            "temperature": 0.7,
        })
        
        response = bedrock.invoke_model(
            modelId='anthropic.claude-3-haiku-20240307-v1:0',
            body=body
        )
        
        response_body = json.loads(response.get('body').read())
        text = response_body['content'][0]['text'].strip()
        # Clean quotes if any are returned
        text = text.replace('"', '').replace("'", "")
        return text
    except Exception as e:
        print(f"\n⚠️ Bedrock API call failed ({e}). Using offline fallback response.")
        # Try to get matching fallback, otherwise construct a generic one with distance
        p_lower = personality.lower()
        if p_lower in fallbacks:
            return fallbacks[p_lower]
        return f"Intruder detected at {distance_cm} centimeters! Please step away."

log_lock = threading.Lock()

def log_intrusion(distance_cm: float, photo_name: str, ai_response: str):
    """Logs the intrusion event details to a local JSON file."""
    log_file = os.path.join(project_dir, 'sentry_log.json')
    new_entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "distance_cm": distance_cm,
        "photo_name": photo_name,
        "ai_response": ai_response
    }
    
    with log_lock:
        try:
            log_data = []
            if os.path.exists(log_file):
                try:
                    with open(log_file, 'r') as f:
                        log_data = json.load(f)
                    if not isinstance(log_data, list):
                        log_data = []
                except Exception:
                    log_data = []
            
            log_data.append(new_entry)
            
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=4)
            print(f"\n📝 Event logged to {log_file}")
        except Exception as e:
            print(f"\n⚠️ Failed to write to log file: {e}")

def generate_and_speak(personality: str, distance_cm: float, photo_name: str):
    """Generates the speech response, speaks it in the background, and logs the event."""
    speech_text = generate_threat_response(personality, distance_cm)
    speak(speech_text)
    log_intrusion(distance_cm, photo_name, speech_text)

# Predefined colors for LED strip
COLORS = {
   'Red' : [255, 0, 0],
   'Green' : [0, 255, 0],
   'Blue' : [0, 0, 255],
   'Yellow' : [255, 255, 0],
   'Purple' : [255, 0, 255],
   'Cyan' : [0, 255, 255],
   'White' : [255, 255, 255],
   'Off' : [0, 0, 0],
}

# Try importing hardware classes, otherwise define simulated/mock fallbacks for macOS/development
try:
    from led import Led
    from ultrasonic import Ultrasonic
    from buzzer import Buzzer
    from camera import Camera
    
    led = Led()
    ultrasonic = Ultrasonic()
    buzzer = Buzzer()
    camera = Camera()
    IS_REAL_HARDWARE = True
except Exception as e:
    import random

    class MockLed:
        def __init__(self):
            pass
        def ledIndex(self, index, r, g, b):
            pass

    class MockUltrasonic:
        def __init__(self):
            self.base = 42.5
        def get_distance(self) -> float:
            # Simulate a realistic fluctuating distance reading
            self.base += random.uniform(-1.5, 1.5)
            self.base = max(2.0, min(self.base, 300.0))
            return round(self.base, 1)
        def close(self):
            pass

    class MockBuzzer:
        def __init__(self):
            self.state = False
        def set_state(self, state: bool) -> None:
            self.state = state
            print(f"[Mock Buzzer] State set to: {self.state}")
        def close(self) -> None:
            pass

    class MockCamera:
        def save_image(self, filename: str) -> dict:
            print(f"[Mock Camera] Simulating capture: Saved mock image to {filename}")
            with open(filename, 'wb') as f:
                f.write(b'MOCK_IMAGE_DATA')
            return {"mock": True}
        def close(self):
            pass

    led = MockLed()
    ultrasonic = MockUltrasonic()
    buzzer = MockBuzzer()
    camera = MockCamera()
    IS_REAL_HARDWARE = False
    print("⚠️ Running in MOCK Mode (Simulated hardware for Mac OS / Development)")

# Try loading OpenCV for face detection
try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

class FaceDetector:
    def __init__(self):
        # Locate the xml file inside freenove-kit/Code/Client
        self.cascade_path = os.path.join(project_dir, 'freenove-kit', 'Code', 'Client', 'haarcascade_frontalface_default.xml')
        self.face_cascade = None
        if HAS_OPENCV:
            if os.path.exists(self.cascade_path):
                self.face_cascade = cv2.CascadeClassifier(self.cascade_path)
                print(f"👤 Face detection initialized using Haar Cascade: {self.cascade_path}")
            else:
                print(f"⚠️ Warning: Cascade file not found at {self.cascade_path}. Face detection will be mocked.")
        else:
            print("💡 OpenCV (cv2) not installed. Face detection will run in Mock/Simulated mode.")

    def detect_faces(self, image_path: str) -> tuple:
        """
        Detects faces in the image at image_path.
        Returns:
            (has_face: bool, number_of_faces: int, processed_image_path: str or None)
        """
        if not HAS_OPENCV or not self.face_cascade:
            # Mock mode: 40% chance of detecting a face for testing/demo
            has_face = random.choice([True, False, False])
            num_faces = 1 if has_face else 0
            if has_face:
                print("[Mock Face Detection] Simulated detecting 1 face.")
            else:
                print("[Mock Face Detection] No faces simulated.")
            return has_face, num_faces, None

        try:
            img = cv2.imread(image_path)
            if img is None:
                print(f"❌ Error: Could not read image at {image_path}")
                return False, 0, None

            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            # Enhance image contrast using histogram equalization to improve detection in poor/varying lighting
            gray = cv2.equalizeHist(gray)
            
            # Tune parameters for more sensitive detection:
            # - scaleFactor=1.1: scans smaller increments of image size scaling for distant/close faces
            # - minNeighbors=3: less restrictive, catches faces under poorer illumination or angled poses
            # - minSize=(30, 30): sets a minimum search window size to catch smaller/further faces
            faces = self.face_cascade.detectMultiScale(
                gray, 
                scaleFactor=1.1, 
                minNeighbors=3, 
                minSize=(30, 30)
            )

            if len(faces) > 0:
                print(f"👤 Detected {len(faces)} face(s)!")
                for (x, y, w, h) in faces:
                    # Draw a green circle around each face
                    face_x = int(x + w / 2.0)
                    face_y = int(y + h / 2.0)
                    radius = int((w + h) / 4)
                    cv2.circle(img, (face_x, face_y), radius, (0, 255, 0), 2)
                
                # Save the processed image with circles drawn on it
                processed_path = "intruder_face_detected.jpg"
                cv2.imwrite(processed_path, img)
                return True, len(faces), processed_path
            else:
                return False, 0, None
        except Exception as e:
            print(f"❌ Error during face detection: {e}")
            return False, 0, None

def set_all_leds(color_name: str) -> bool:
    """Sets all 8 LEDs to the specified color name."""
    normalized = color_name.strip().title()
    if normalized not in COLORS:
        print(f"⚠️ Warning: Unknown color '{color_name}'. Available colors: {list(COLORS.keys())}")
        return False
    rgb = COLORS[normalized]
    
    # Set all 8 LEDs. In the Freenove Led library, ledIndex uses a bitmask.
    # To light up all LEDs, we pass index=255 (binary 11111111).
    led.ledIndex(255, rgb[0], rgb[1], rgb[2])
    return True

def trigger_alarm(duration: float = 0.5):
    """Beeps the buzzer and blinks LEDs to indicate alarm/alert."""
    print("🚨 Alarm Triggered!")
    buzzer.set_state(True)
    set_all_leds('Red')
    time.sleep(duration)
    
    buzzer.set_state(False)
    set_all_leds('Off')

def cleanup():
    """Release all hardware resources and turn off lights/buzzers."""
    print("\n🧹 Cleaning up resources...")
    try:
        set_all_leds('Off')
    except Exception:
        pass
        
    try:
        buzzer.set_state(False)
        buzzer.close()
    except Exception:
        pass
        
    try:
        ultrasonic.close()
    except Exception:
        pass

    try:
        camera.close()
    except Exception:
        pass

def run_sentry_mode(threshold_cm: float = 30.0):
    """
    Sentry Mode Loop:
    - Green LED means area is clear.
    - Continuously measures distance using the ultrasonic sensor.
    - If an object is detected closer than threshold_cm:
      - Turn LEDs Blue (Scanning).
      - Capture an image from the camera.
      - Check for a human face.
      - If face is detected, sound buzzer + flash Red LEDs and speak threat response.
      - If no face, flash Yellow briefly and continue.
    """
    detector = FaceDetector()
    
    print("\n🤖 Welcome to Sentry Mode!")
    print("Choose a personality for your sentry robot:")
    print("  - Aggressive (Threatening & defensive)")
    print("  - Polite     (Formal & polite)")
    print("  - Paranoid   (Terrified of humans)")
    print("  - Snarky     (Sarcastic & bored)")
    print("  - Cute       (Sweet & friendly)")
    print("  - Or type any custom personality you want!")
    
    try:
        personality = input("Enter robot personality [default: Snarky]: ").strip()
        if not personality:
            personality = "Snarky"
    except (EOFError, KeyboardInterrupt):
        personality = "Snarky"
        print("\nUsing default personality: Snarky")
        
    print(f"🧠 Personality set to: '{personality}'\n")
    
    print(f"🛡️ Sentry Mode activated! Threshold: {threshold_cm} cm. Press Ctrl+C to exit.")
    
    # Indicate armed state (Green LED)
    set_all_leds('Green')
    
    try:
        while True:
            distance = ultrasonic.get_distance()
            if distance is not None:
                print(f"\r🔍 Monitoring... Distance: {distance} cm", end="", flush=True)
                
                if distance < threshold_cm:
                    print(f"\n⚠️ Motion detected at {distance} cm! Scanning for intruders...")
                    
                    # Blue LED indicates scanning
                    set_all_leds('Blue')
                    
                    # Capture image
                    capture_filename = "sentry_scan.jpg"
                    camera.save_image(capture_filename)
                    
                    # Detect face
                    has_face, num_faces, face_image_path = detector.detect_faces(capture_filename)
                    
                    if has_face:
                        if face_image_path:
                            print(f"🚨 Intruder verified! Face image saved to {face_image_path}")
                        else:
                            print("🚨 Intruder verified!")
                        
                        # Generate response and speak in background thread to prevent blocking main alarms
                        threading.Thread(
                            target=generate_and_speak,
                            args=(personality, distance, face_image_path or capture_filename),
                            daemon=True
                        ).start()
                        
                        trigger_alarm(1.0)
                        
                        # Cool-down to prevent spamming Bedrock/Speech
                        print("⏳ Cooldown active for 5 seconds...")
                        time.sleep(5.0)
                    else:
                        print("🟡 False alarm: No face detected. Warning alert triggered.")
                        set_all_leds('Yellow')
                        time.sleep(0.5)
                        set_all_leds('Off')
                        
                    # Reset back to armed status
                    set_all_leds('Green')
            else:
                print("\r⚠️ Error reading sensor values.", end="", flush=True)
                
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛡️ Sentry Mode deactivated by user.")
    finally:
        cleanup()

if __name__ == "__main__":
    run_sentry_mode()
