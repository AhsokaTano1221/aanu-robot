# Rob's Omnidirectional Robot Control

This repository houses the scripts and utilities to control Rob (and his happy alter-ego Bob), an omnidirectional Raspberry Pi 4/3 mobile robot equipped with Mecanum wheels, a pan-tilt head, status LEDs, a speaker, and an ultrasonic distance sensor.

---

## Core Scripts & Applications

### 1. 🐶 Follow-Me Companion Mode (`follow_me.py`)
Turns Rob into an interactive companion that tracks you using real-time ultrasonic telemetry and pan servo sweep scans:
* **Interactive Startup Prompt**: Prompts you to pick your robot's personality on boot.
* **Rob Mode (Grumpy/Sassy)**: Irritable personality. Grumbles when followed, demands personal space, and performs grumpy shakes when petted.
* **Bob Mode (Happy/Friendly)**: Enthusiastic companion. Loves being followed, does happy wiggles, and wiggles/double-beeps with rainbow lights when petted (< 8 cm for 1.5s).
* **Startled Proximity Alerts**: Backs up quickly and displays warning colors if you walk too close (< 15 cm).

### 2. 🎯 Sweeping Obstacle Identifier (`obstacle_identifier.py`)
Discrete scanning sequence where Rob:
* Rotates his head continuously check path angles `[90, 60, 90, 75, 90, 105, 90, 120]` to prevent front blindness.
* Smoothly approaches objects without bumping (automatically stops if the sensor goes blind within proximity dead zones).
* Captures a snapshot, queries Amazon Bedrock (Claude 5 Sonnet) with detailed prompts to distinguish book covers or items uniquely, and speaks the description aloud.

### 3. 🚨 Sentry Mode (`sentry_mode.py`)
Provides autonomous guarding, movement, and face/object threat-detection algorithms:
* Integrates text-to-speech voice notifications.
* Computes real-time threat scores based on proximity and visual detections (e.g. face spotting).
* Controls status lighting modes and sequences.

### 4. 🎙️ Voice Assistant Robot (`assistant_robot.py`)
An interactive LLM voice assistant:
* Captures live microphone audio commands.
* Sends queries to Bedrock to parse natural language intent.
* Automatically triggers physical actions (like moving, beeping, speaking, or looking around) based on your spoken instructions.

### 5. 🌐 Web Control Server (`web_server.py`)
A Flask-based web interface server:
* Streams the real-time camera feed to your web browser.
* Exposes on-screen joystick overlays to drive the Mecanum wheels.
* Allows manual servo pan-tilt adjustments, buzzer toggling, and remote diagnostics.

### 6. 💡 LED Strip Diagnostic (`blink_led.py`)
A standalone script to test and verify status light signals:
* Displays custom colors and animations (blink, follow, wipe, rainbow cycle).

---

## Secure AWS Credentials Setup (Option B)

Amazon Bedrock requests require AWS credentials. To prevent committing access keys to your Git repository, credentials are excluded from the repository.

### Configuration on the Raspberry Pi:
To set them up permanently on your Raspberry Pi:
1. Create the credentials config directory for root (since script runs with `sudo` permissions):
   ```bash
   sudo mkdir -p /root/.aws
   ```
2. Create the credentials file:
   ```bash
   sudo nano /root/.aws/credentials
   ```
3. Paste the following configuration structure:
   ```ini
   [default]
   aws_access_key_id = YOUR_ACTUAL_ACCESS_KEY_ID
   aws_secret_access_key = YOUR_ACTUAL_SECRET_ACCESS_KEY
   region = us-east-1
   ```
4. Save and close (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

## How to Run

### 1. Run Companion Mode (Rob vs Bob)
```bash
sudo python3 follow_me.py
```
*Follow the interactive console menu to choose your personality mode on startup.*

To force a personality directly and bypass the startup prompt:
```bash
sudo python3 follow_me.py --mode bob
```

### 2. Run Obstacle Identifier Mode
```bash
sudo python3 obstacle_identifier.py
```

### 3. Start the Web Control Panel
```bash
sudo python3 web_server.py
```
*Open `http://<your-pi-ip>:8000` in any browser to control Rob remotely.*
