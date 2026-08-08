import os
import sys
import time
import math
import random
import argparse
from datetime import datetime

# Setup paths to import sentry_mode
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_dir)

# ==========================================================
# CONFIGURATION: Choose default companion personality.
# Options: "rob" (Grumpy/Sassy) or "bob" (Happy/Friendly)
DEFAULT_MODE = "rob"
# ==========================================================

import sentry_mode
sentry_mode.DISABLE_LEDS = False

try:
    from led import Led
    sentry_mode.led = Led()
    print("💡 Physical LEDs enabled for companion feedback.")
except Exception as e:
    print(f"⚠️ Failed to enable physical LEDs: {e}")

from sentry_mode import (
    car, ultrasonic, buzzer, servo,
    speak, IS_REAL_HARDWARE, set_all_leds
)

# Helper to write safety motor values
def safe_set_motor(duty1, duty2, duty3, duty4):
    try:
        car.set_motor_model(duty1, duty2, duty3, duty4)
        return True
    except Exception as e:
        print(f"⚠️ Motor error: {e}")
        return False

# Smooth servo pan helper
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

# Happy wiggle dance (for Bob)
def perform_happy_wiggle():
    print("🕺 Companion: Performing happy Bob wiggle!")
    for _ in range(3):
        safe_set_motor(-800, -800, 800, 800)
        time.sleep(0.1)
        safe_set_motor(800, 800, -800, -800)
        time.sleep(0.1)
    safe_set_motor(0, 0, 0, 0)

# Grumpy reverse grumble (for Rob)
def perform_grumpy_shake():
    print("💢 Companion: Performing grumpy Rob shake!")
    # Sharp backward reverse and quick stop
    safe_set_motor(-900, -900, -900, -900)
    time.sleep(0.2)
    safe_set_motor(0, 0, 0, 0)
    time.sleep(0.1)
    # Annoyed quick twist
    safe_set_motor(700, 700, -700, -700)
    time.sleep(0.12)
    safe_set_motor(-700, -700, 700, 700)
    time.sleep(0.12)
    safe_set_motor(0, 0, 0, 0)

# Rainbow color flash
def flash_rainbow_colors(duration=1.5):
    start = time.time()
    colors = ['Red', 'Orange', 'Yellow', 'Green', 'Blue', 'Indigo', 'Purple']
    i = 0
    while time.time() - start < duration:
        set_all_leds(colors[i % len(colors)])
        time.sleep(0.1)
        i += 1
    set_all_leds('Green')

PERSONALITIES = {
    "rob": {
        "name": "Rob",
        "startup": "Grumpy Rob is active. Don't expect me to be happy about this.",
        "lost": ["Ugh, where did you wander off to now?", "Great, left behind again."],
        "found": ["Oh, there you are. Stop moving so fast.", "I suppose I have to follow you now."],
        "startled_led": "Red",
        "startled_speak": "Hey! Back off! Personal space!",
        "pet_led": "Orange",
        "pet_speak": "Stop touching me! I'm not a dog!",
        "wiggle": perform_grumpy_shake
    },
    "bob": {
        "name": "Bob",
        "startup": "Hi! I'm Bob, your best friend! Let's play!",
        "lost": ["Oh no! Where did my best friend go?", "Come back, let's play!"],
        "found": ["Yay! I found you! Let's go!", "Woohoo! Back together!"],
        "startled_led": "Magenta",
        "startled_speak": "Oops, watch out buddy!",
        "pet_led": "Rainbow",
        "pet_speak": "Oh boy! I love pets! This is the best day ever!",
        "wiggle": perform_happy_wiggle
    }
}

def main(mode: str):
    global current_pan_angle
    mode = mode.lower()
    if mode not in PERSONALITIES:
        mode = "rob"
    
    p = PERSONALITIES[mode]
    print(f"🐶 Starting Rob's Follow-Me Companion Mode in [{p['name'].upper()}] personality...")
    print("Press Ctrl+C to terminate.")

    # Speak startup personality info
    speak(p["startup"])

    # Init beep
    try:
        buzzer.set_state(True)
        time.sleep(0.15)
        buzzer.set_state(False)
    except Exception:
        pass

    set_servo_angle_smooth(90)
    if servo:
        try:
            servo.set_servo_pwm('1', 90)  # Tilt centered
        except Exception:
            pass

    pet_timer_start = None
    last_state = "searching"
    
    try:
        while True:
            # 1. Read distance
            try:
                dist = ultrasonic.get_distance()
            except Exception:
                dist = None

            # Print telemetry log
            print(f"[{p['name']}] State: {last_state} | Distance: {f'{dist:.1f} cm' if dist is not None else 'None'} | Pan: {current_pan_angle}°")

            # 2. State Machine
            if dist is None or dist > 80.0:
                if last_state != "searching":
                    print(f"🔍 Lost connection. Entering search mode.")
                    speak(random.choice(p["lost"]))
                    last_state = "searching"
                    safe_set_motor(0, 0, 0, 0)
                
                set_all_leds('Blue')

                # Slow head pan sweep to locate target (60 to 120 degrees)
                sweep_angle = int(90 + 30 * math.sin(time.time() * 2))
                set_servo_angle_smooth(sweep_angle)
                time.sleep(0.05)
                continue

            # Target detected!
            if last_state == "searching":
                print("🎯 Target located! Locking on...")
                speak(random.choice(p["found"]))
                try:
                    buzzer.set_state(True)
                    time.sleep(0.1)
                    buzzer.set_state(False)
                except Exception:
                    pass
                last_state = "locked"

            # Align chassis if head is panned off-center
            if abs(current_pan_angle - 90) > 8:
                turn_direction = 1 if current_pan_angle > 90 else -1
                print(f"↪️ Aligning chassis to head angle ({current_pan_angle}°)...")
                safe_set_motor(turn_direction * 850, turn_direction * 850, -turn_direction * 850, -turn_direction * 850)
                time.sleep(0.15)
                safe_set_motor(0, 0, 0, 0)
                set_servo_angle_smooth(90)
                time.sleep(0.1)
                continue

            # Check for close-range petting / handshake
            if dist < 8.0:
                safe_set_motor(0, 0, 0, 0)
                if pet_timer_start is None:
                    pet_timer_start = time.time()
                elif time.time() - pet_timer_start >= 1.5:
                    speak(p["pet_speak"])
                    try:
                        buzzer.set_state(True)
                        time.sleep(0.08)
                        buzzer.set_state(False)
                        if mode == "bob":
                            time.sleep(0.08)
                            buzzer.set_state(True)
                            time.sleep(0.08)
                            buzzer.set_state(False)
                    except Exception:
                        pass
                    
                    if p["pet_led"] == "Rainbow":
                        flash_rainbow_colors(1.5)
                    else:
                        set_all_leds(p["pet_led"])
                        time.sleep(1.0)
                        
                    p["wiggle"]()
                    pet_timer_start = None
                time.sleep(0.05)
                continue
            else:
                pet_timer_start = None

            # Startled warning
            if dist < 15.0:
                print(f"⚠️ Startled! Target is too close!")
                set_all_leds(p["startled_led"])
                speak(p["startled_speak"])
                safe_set_motor(-1000, -1000, -1000, -1000)
                time.sleep(0.35)
                safe_set_motor(0, 0, 0, 0)
                time.sleep(0.1)
                continue

            # Following control thresholds
            if dist < 25.0:
                set_all_leds('Green')
                safe_set_motor(-500, -500, -500, -500)
            elif dist > 35.0:
                set_all_leds('Green')
                safe_set_motor(600, 600, 600, 600)
            else:
                set_all_leds('Green')
                safe_set_motor(0, 0, 0, 0)

            time.sleep(0.05)

    except KeyboardInterrupt:
        print(f"\n👋 Companion mode [{p['name']}] interrupted by user.")
    finally:
        safe_set_motor(0, 0, 0, 0)
        set_all_leds('Green')
        try:
            set_servo_angle_smooth(90)
        except Exception:
            pass
        print(f"🛑 Companion mode [{p['name']}] terminated safely.")

def select_mode_interactively():
    print("\n==================================================")
    print("🐾 Select Companion Personality Mode:")
    print("  [1] Grumpy Rob (Sassy & easily annoyed)")
    print("  [2] Happy Bob  (Friendly & loves playing)")
    print("==================================================")
    while True:
        try:
            choice = input("Enter choice (1 or 2, default '1'): ").strip()
            if not choice or choice == "1" or choice.lower() == "r" or choice.lower() == "rob":
                return "rob"
            elif choice == "2" or choice.lower() == "b" or choice.lower() == "bob":
                return "bob"
            else:
                print("⚠️ Invalid choice. Please enter 1 or 2.")
        except (KeyboardInterrupt, EOFError):
            print("\n👋 Defaulting to Grumpy Rob.")
            return "rob"

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Rob vs Bob Companion Follow-Me Script")
    parser.add_argument("--mode", type=str, choices=["rob", "bob"], default=None,
                        help="Select companion personality: rob (grumpy) or bob (happy)")
    args = parser.parse_args()
    
    selected_mode = args.mode
    if selected_mode is None:
        selected_mode = select_mode_interactively()
        
    main(selected_mode)
