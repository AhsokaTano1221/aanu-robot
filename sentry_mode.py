import time
import sys
import os
import threading

# Add path to hardware libraries
project_dir = os.path.dirname(os.path.abspath(__file__))
local_path = os.path.join(project_dir, 'freenove-kit', 'Code', 'Server')
if os.path.exists(local_path):
    sys.path.insert(0, local_path)
else:
    sys.path.insert(0, '/home/eera/robot/freenove-kit/Code/Server')

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
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)

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
      - If face is detected, sound buzzer + flash Red LEDs.
      - If no face, flash Yellow briefly and continue.
    """
    detector = FaceDetector()
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
                        trigger_alarm(1.0)
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
