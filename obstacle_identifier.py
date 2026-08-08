import os
import sys
import time
import json
import random
from datetime import datetime

# Import components from sentry_mode.py
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

import sentry_mode
sentry_mode.DISABLE_LEDS = False
try:
    from led import Led
    sentry_mode.led = Led()
    print("💡 Physical LEDs enabled for classification feedback.")
except Exception as e:
    print(f"⚠️ Failed to enable physical LEDs: {e}")

from sentry_mode import (
    car, ultrasonic, camera, buzzer, servo,
    speak, IS_REAL_HARDWARE
)

# Initialize logging directory
run_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
log_dir = f"/tmp/{run_timestamp}"
os.makedirs(log_dir, exist_ok=True)
log_filepath = os.path.join(log_dir, "log")

print(f"📝 Obstacle Identifier run started. Logging into: {log_filepath}")
try:
    with open(log_filepath, "w") as f:
        f.write(f"=== OBSTACLE IDENTIFICATION RUN STARTED AT {datetime.now().isoformat()} ===\n\n")
except Exception as e:
    print(f"⚠️ Failed to write to log file: {e}")

# Safe I2C motor control wrapper
i2c_error_count = 0

def safe_set_motor(duty1, duty2, duty3, duty4):
    global i2c_error_count
    try:
        car.set_motor_model(duty1, duty2, duty3, duty4)
        i2c_error_count = 0
        return True
    except OSError as e:
        i2c_error_count += 1
        print(f"⚠️ Hardware: I2C error writing to motors ({i2c_error_count}/3): {e}")
        return False
    except Exception as e:
        print(f"⚠️ Hardware: Error writing to motors: {e}")
        return False

current_pan_angle = 90

def set_servo_angle_smooth(target_angle):
    global current_pan_angle
    if not servo:
        current_pan_angle = target_angle
        return
    
    target_angle = int(target_angle)
    if abs(current_pan_angle - target_angle) <= 2:
        try:
            servo.set_servo_pwm('0', target_angle)
        except Exception:
            pass
        current_pan_angle = target_angle
        return

    step = 3 if target_angle > current_pan_angle else -3
    for angle in range(int(current_pan_angle), target_angle, step):
        try:
            servo.set_servo_pwm('0', angle)
        except Exception:
            pass
        time.sleep(0.015)
    
    try:
        servo.set_servo_pwm('0', target_angle)
    except Exception:
        pass
    current_pan_angle = target_angle

def identify_obstacle(image_path: str) -> str:
    """Sends Bedrock vision request to identify the obstacle blocking the path."""
    from sentry_mode import set_all_leds
    set_all_leds('Purple')

    if not IS_REAL_HARDWARE:
        # Simulate local mock vision candidates
        time.sleep(1.0)
        candidates = [
            "wooden chair leg", 
            "plastic waste basket", 
            "cardboard shipping box", 
            "backpack on the floor", 
            "tennis shoe",
            "white wall",
            "wooden closet door"
        ]
        set_all_leds('Green')
        return random.choice(candidates)

    import base64
    import boto3
    
    try:
        with open(image_path, "rb") as f:
            base64_data = base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"⚠️ Vision: Failed to read image for analysis: {e}")
        set_all_leds('Green')
        return "unknown obstacle"

    system_prompt = (
        "You are a ground-level robot camera. Look at the bottom-center and center of the frame "
        "to identify the physical object directly blocking the robot's wheels.\n"
        "If the obstacle is a structural boundary of the room (such as a wall, door, floor, door frame, baseboard), "
        "respond exactly with the word 'wall'.\n"
        "Do NOT classify items lying on the floor (such as books, book covers, papers, boxes, boards, mats, or toys) as walls. "
        "These are discrete movable obstacles. If the object is a book or book cover, identify it with a specific distinguishing "
        "feature such as its main color, cover design, or title (e.g. 'blue book cover with white title', 'book with yellow cat cover', 'math textbook').\n"
        "Otherwise, if it is a discrete movable obstacle (e.g. 'wooden chair leg', 'backpack', 'cardboard box', 'tennis shoe'), "
        "respond with a short, descriptive name in 2 to 4 words.\n"
        "Do not include any explanations, sentences, or markdown formatting. Return raw text only."
    )

    try:
        from botocore.config import Config
        config = Config(connect_timeout=4.0, read_timeout=8.0, retries={'max_attempts': 1})
        bedrock = boto3.client(service_name='bedrock-runtime', region_name='us-east-1', config=config)
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "system": system_prompt,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": base64_data
                            }
                        },
                        {
                            "type": "text",
                            "text": "Identify the obstacle directly in front."
                        }
                    ]
                }
            ]
        }
        response = bedrock.invoke_model(
            modelId='us.anthropic.claude-sonnet-5',
            body=json.dumps(payload)
        )
        response_body = json.loads(response.get('body').read())
        raw_text = response_body['content'][0]['text'].strip().lower()
        set_all_leds('Green')
        return raw_text
    except Exception as e:
        print(f"⚠️ Vision: Bedrock vision call failed: {e}")
        set_all_leds('Green')
        return "unidentified object"

def main():
    global i2c_error_count
    print("🚀 Starting Rob's Obstacle Identifier Test Loop...")
    print("🔋 Run terminates after 60 seconds or after identifying 5 obstacles.")
    
    # Sound startup beep
    try:
        buzzer.set_state(True)
        time.sleep(0.15)
        buzzer.set_state(False)
    except Exception:
        pass

    # Servos center
    try:
        set_servo_angle_smooth(90)
        if servo:
            servo.set_servo_pwm('1', 90)
        time.sleep(0.2)
    except Exception:
        pass

    max_duration = 60.0
    max_obstacles = 5
    obstacle_count = 0
    spotted_count = 0
    logged_objects = set()
    start_time = time.time()

    pan_angles = [90, 60, 90, 75, 90, 105, 90, 120]
    pan_index = 0

    try:
        while time.time() - start_time < max_duration and obstacle_count < max_obstacles:
            if i2c_error_count >= 3:
                print("🛑 Critical: I2C connection lost. Exiting run...")
                break

            # 1. Step head to current discrete angle
            target_angle = pan_angles[pan_index]
            set_servo_angle_smooth(target_angle)
            
            # Wait for physical servo stabilization (discrete scan pause)
            time.sleep(0.12)

            # 2. Measure distance while head is stable
            try:
                dist = ultrasonic.get_distance()
            except Exception:
                dist = None
            print(f"[Scan] Angle: {target_angle}° | Distance: {f'{dist:.1f} cm' if dist is not None else 'None'}")

            # Move to next index for the next loop iteration
            pan_index = (pan_index + 1) % len(pan_angles)

            if dist is not None:
                # Trigger target approach if we see something in close range (dist < 38.0)
                if dist < 38.0:
                    # Double-consecutive measurement check to reject single-frame bounces
                    time.sleep(0.03)
                    try:
                        dist2 = ultrasonic.get_distance()
                    except Exception:
                        dist2 = None
                    print(f"[Scan Confirm] Angle: {target_angle}° | Distance: {f'{dist2:.1f} cm' if dist2 is not None else 'None'}")
                    
                    if dist2 is not None and dist2 < 38.0:
                        spotted_count += 1
                        spotted_angle = target_angle
                        print(f"\n🎯 Target spotted at angle {spotted_angle:.1f}° (distance: {dist2:.1f} cm)!")
                        safe_set_motor(0, 0, 0, 0)
                        time.sleep(0.15)
                        
                        # Align chassis with object direction
                        if spotted_angle < 80.0:
                            print("↪️ Aligning chassis to the right...")
                            safe_set_motor(900, 900, -900, -900)
                            time.sleep(0.2)
                        elif spotted_angle > 100.0:
                            print("↩️ Aligning chassis to the left...")
                            safe_set_motor(-900, -900, 900, 900)
                            time.sleep(0.2)
                            
                        safe_set_motor(0, 0, 0, 0)
                        
                        # Point head straight for approach sensor readings
                        set_servo_angle_smooth(90)
                        time.sleep(0.15)
                        
                        # Get closer to the object (until dist <= 20.0 cm)
                        # Dynamically compute max allowed drive time to prevent runaway bumping
                        max_approach_time = max(0.2, (dist2 - 20.0) / 35.0 + 0.2)
                        print(f"🐾 Getting closer to the object... (Max time: {max_approach_time:.2f}s)")
                        approach_start = time.time()
                        consecutive_none = 0
                        while time.time() - approach_start < max_approach_time:
                            try:
                                d = ultrasonic.get_distance()
                            except Exception:
                                d = None
                            print(f"[Approach] Distance: {f'{d:.1f} cm' if d is not None else 'None'}")
                            
                            if d is None:
                                consecutive_none += 1
                                if consecutive_none >= 2:
                                    print("⚠️ Sensor went blind (proximity/contact). Stopping approach to prevent crash.")
                                    break
                            else:
                                consecutive_none = 0
                                if d <= 20.0:
                                    break
                                    
                            safe_set_motor(600, 600, 600, 600)
                            time.sleep(0.05)
                        
                        # Stop and stabilize
                        safe_set_motor(0, 0, 0, 0)
                        time.sleep(0.15)
                        
                        # Point head back to original spotted angle for snapshot target framing
                        set_servo_angle_smooth(int(spotted_angle))
                        time.sleep(0.3)  # Wait for head to settle
                        
                        # Capture image
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        filename = f"static/logs/obstacle_{spotted_count}_{timestamp}.jpg"
                        filepath = os.path.join(project_dir, filename)
                        os.makedirs(os.path.dirname(filepath), exist_ok=True)
                        
                        description = "unknown obstacle"
                        try:
                            camera.save_image(filepath)
                            print(f"📸 Image captured and saved to: {filename}")
                            
                            # Identify obstacle via Bedrock
                            print("🤖 Identifying obstacle...")
                            description = identify_obstacle(filepath)
                        except Exception as e:
                            print(f"⚠️ Camera/Vision capture failed: {e}")
                        
                        # Center head
                        set_servo_angle_smooth(90)
                        
                        # Check structural boundaries or duplicate classification
                        cleaned_desc = description.strip().lower()
                        is_wall = any(w in cleaned_desc for w in ["wall", "door", "floor", "baseboard", "doorframe", "door frame"])
                        
                        if is_wall:
                            # Structural boundary spotted!
                            alert_message = "Wall detected. Steering away."
                            print(f"🔊 Rob says: '{alert_message}'")
                            speak(alert_message)
                        elif cleaned_desc in logged_objects:
                            # Duplicate object spotted!
                            alert_message = f"I see the {description} again. Steering away."
                            print(f"🔊 Rob says: '{alert_message}'")
                            speak(alert_message)
                        else:
                            # Unique object!
                            logged_objects.add(cleaned_desc)
                            obstacle_count += 1
                            
                            alert_message = f"Obstacle detected. I see a {description}."
                            print(f"🔊 Rob says: '{alert_message}'")
                            speak(alert_message)
                            
                            # Log to /tmp/<datetime>/log file
                            log_entry = f"[{datetime.now().isoformat()}] Obstacle #{obstacle_count} | Angle: {spotted_angle:.1f}° | Distance: {dist2:.1f} cm | Object: {description} | Image: {filename}\n"
                            try:
                                with open(log_filepath, "a") as f:
                                    f.write(log_entry)
                            except Exception as log_err:
                                print(f"⚠️ Failed to write entry to log file: {log_err}")
                        
                        # Back up away from obstacle
                        safe_set_motor(-900, -900, -900, -900)
                        time.sleep(0.4)
                        safe_set_motor(0, 0, 0, 0)
                        time.sleep(0.15)
                        
                        # Spin randomly until path is clear (d > 70 cm), enforcing 0.3s min duration and 2 consecutive clear readings
                        direction = random.choice([-1, 1])
                        safe_set_motor(direction * 1150, direction * 1150, -direction * 1150, -direction * 1150)
                        
                        consecutive_clear = 0
                        spin_start = time.time()
                        while time.time() - spin_start < 2.5:
                            time.sleep(0.05)
                            try:
                                d = ultrasonic.get_distance()
                            except Exception:
                                d = None
                            print(f"[Spin Clear] Distance: {f'{d:.1f} cm' if d is not None else 'None'}")
                            if d is not None and d > 70.0:
                                consecutive_clear += 1
                            else:
                                consecutive_clear = 0
                                
                            if consecutive_clear >= 2 and (time.time() - spin_start > 0.3):
                                break
                                
                        safe_set_motor(0, 0, 0, 0)
                        pan_index = 2  # Reset sweep to center
                        continue
                else:
                    # Move forward at calibrated search speed (550)
                    safe_set_motor(550, 550, 550, 550)
            else:
                safe_set_motor(0, 0, 0, 0)

    except KeyboardInterrupt:
        print("\n🛡️ Run interrupted by user.")
    finally:
        # Ensure motors are stopped and LEDs are off
        safe_set_motor(0, 0, 0, 0)
        try:
            from sentry_mode import set_all_leds
            set_all_leds('Off')
        except Exception:
            pass

    # Run summary report
    elapsed_run_time = time.time() - start_time
    summary_text = (
        f"\n=== OBSTACLE RUN SUMMARY ===\n"
        f"Duration: {elapsed_run_time:.1f} seconds\n"
        f"Obstacles Spotted: {obstacle_count}/{max_obstacles}\n"
    )
    print(summary_text)
    try:
        with open(log_filepath, "a") as f:
            f.write(summary_text)
    except Exception:
        pass
        
    speak(f"Run completed. I successfully identified {obstacle_count} obstacles.")

if __name__ == "__main__":
    main()
