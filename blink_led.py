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
    from infrared import Infrared
    from camera import Camera
    led = Led()
    ultrasonic = Ultrasonic()
    infrared = Infrared()
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

    class MockInfrared:
        def read_one_infrared(self, channel: int) -> int:
            return random.choice([0, 1])
        def read_all_infrared(self) -> int:
            return (self.read_one_infrared(1) << 2) | (self.read_one_infrared(2) << 1) | self.read_one_infrared(3)
        def read_sensor_values(self) -> list:
            return [self.read_one_infrared(1), self.read_one_infrared(2), self.read_one_infrared(3)]
        def close(self):
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
    infrared = MockInfrared()
    camera = MockCamera()
    IS_REAL_HARDWARE = False
    print("⚠️ Running in MOCK Mode (Simulated hardware for Mac OS / Development)")

def set_colour(color_name: str) -> bool:
    """Sets all 8 LEDs to the specified color name."""
    normalized = color_name.strip().title()
    if normalized not in COLORS:
        print(f"⚠️ Warning: Unknown color '{color_name}'. Available colors: {list(COLORS.keys())}")
        return False
    rgb = COLORS[normalized]
    for i in range(8):
        led.ledIndex(i, rgb[0], rgb[1], rgb[2])
    print(f"🎨 LED color set to: {normalized} {rgb}")
    return True

def cleanup():
    """Turn off LEDs and close sensor objects to release resources."""
    # Set all LEDs to Off
    for i in range(8):
        led.ledIndex(i, 0, 0, 0)
    # Close classes if real hardware/applicable
    try:
        infrared.close()
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

def test_led():
    print(f"\n--- LED Test Mode ---")
    print(f"Available colors: {', '.join(COLORS.keys())}")
    print("Type 'back' or 'quit' to return to the main menu.")
    while True:
        color = input("Enter color: ").strip()
        if color.lower() in ('back', 'quit'):
            break
        set_colour(color)

def test_infrared():
    stop_event = threading.Event()

    def print_loop():
        while not stop_event.is_set():
            values = infrared.read_sensor_values()
            print(f"\rInfrared Sensor Readings (L, C, R): {values} ", end="", flush=True)
            time.sleep(0.5)
        print() # Move to new line when stopped

    thread = threading.Thread(target=print_loop)
    thread.daemon = True
    thread.start()

    print("\n--- Continuously printing Infrared Sensor values ---")
    print("Type 'quit' and press Enter to return to the main menu.")
    while True:
        user_input = input().strip().lower()
        if user_input == 'quit':
            stop_event.set()
            thread.join()
            break

def test_ultrasonic():
    stop_event = threading.Event()

    def print_loop():
        while not stop_event.is_set():
            distance = ultrasonic.get_distance()
            if distance is not None:
                print(f"\rUltrasonic Distance: {distance} cm ", end="", flush=True)
            else:
                print(f"\rUltrasonic Distance: Error reading sensor ", end="", flush=True)
            time.sleep(0.5)
        print() # Move to new line when stopped

    thread = threading.Thread(target=print_loop)
    thread.daemon = True
    thread.start()

    print("\n--- Continuously printing Ultrasonic Distance ---")
    print("Type 'quit' and press Enter to return to the main menu.")
    while True:
        user_input = input().strip().lower()
        if user_input == 'quit':
            stop_event.set()
            thread.join()
            break

def test_camera():
    print(f"\n--- Camera Test Mode ---")
    filename = input("Enter output filename (default: test_image.jpg): ").strip()
    if not filename:
        filename = "test_image.jpg"
    print(f"Capturing image to {filename}...")
    metadata = camera.save_image(filename)
    if metadata is not None:
        print(f"📸 Image successfully captured and saved as {filename}!")
    else:
        print("❌ Error: Failed to capture/save image.")

def main():
    print("🤖 Welcome to Robot Sensor and LED Tester!")
    try:
        while True:
            print("\n===============================")
            print("🤖 Main Selection Menu")
            print("===============================")
            print("1. LED (Test LED colors)")
            print("2. Infrared (Read IR sensors)")
            print("3. Ultrasonic (Read Distance)")
            print("4. Camera (Capture Live Image)")
            print("5. Quit")
            choice = input("Select an option (1-5): ").strip()

            if choice == '1':
                test_led()
            elif choice == '2':
                test_infrared()
            elif choice == '3':
                test_ultrasonic()
            elif choice == '4':
                test_camera()
            elif choice in ('5', 'quit'):
                break
            else:
                print("Invalid option. Please select 1, 2, 3, 4, or 5.")
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    finally:
        cleanup()
        print("Goodbye! 🤖")

if __name__ == "__main__":
    main()
