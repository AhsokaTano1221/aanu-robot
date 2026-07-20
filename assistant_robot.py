import os
import sys
import json
import time
from datetime import datetime

# AWS SDK imports
try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None

# Hardware library path (support both local Mac workspace and absolute Pi paths)
project_dir = os.path.dirname(os.path.abspath(__file__))
local_path = os.path.join(project_dir, 'freenove-kit', 'Code', 'Server')
if os.path.exists(local_path):
    sys.path.append(local_path)
else:
    sys.path.append('/home/eera/robot/freenove-kit/Code/Server')

# Mock classes for testing on Mac
class MockLed:
    def ledIndex(self, index, r, g, b):
        pass  # Silent on Mac to avoid flooding output

class MockBuzzer:
    def set_state(self, state):
        pass

class MockUltrasonic:
    def get_distance(self) -> float:
        return 42.5
    def close(self):
        pass

# Try importing hardware libraries, otherwise fallback to mocks
try:
    from led import Led
    from buzzer import Buzzer
    from ultrasonic import Ultrasonic
    led = Led()
    buzzer = Buzzer()
    ultrasonic = Ultrasonic()
    IS_REAL_HARDWARE = True
except ImportError:
    led = MockLed()
    buzzer = MockBuzzer()
    ultrasonic = MockUltrasonic()
    IS_REAL_HARDWARE = False
    print("⚠️ Hardware libraries not found. Running in MOCK mode (perfect for Mac testing).")

REGION_NAME = os.getenv("AWS_REGION", "us-east-1")
MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")

# Color dictionary matching led_tests.py
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

def set_colour(color_name):
    # Normalize color name to title case (e.g. "red" -> "Red")
    normalized = color_name.strip().title()
    if normalized not in COLORS:
        print(f"⚠️ Warning: Unknown color '{color_name}'. Available colors: {list(COLORS.keys())}")
        return False
    rgb = COLORS[normalized]
    for i in range(8):
        led.ledIndex(i, rgb[0], rgb[1], rgb[2])
    return True

def beep_buzzer(duration):
    if duration <= 0:
        return
    buzzer.set_state(True)
    time.sleep(duration)
    buzzer.set_state(False)

def turn_off_everything():
    for i in range(8):
        led.ledIndex(i, 0, 0, 0)
    buzzer.set_state(False)
    try:
        ultrasonic.close()
    except Exception:
        pass

class RobotAssistant:
    def __init__(self):
        if boto3 is None:
            raise RuntimeError("boto3 is not installed. Please install it using: pip install boto3")
        self.client = boto3.client("bedrock-runtime", region_name=REGION_NAME)
        self.messages = []
        
    def chat(self, user_message):
        self.messages.append({
            'role': 'user',
            'content': [{'text': user_message}]
        })
        
        # Define the control tool configuration using Bedrock Converse API Schema
        tools = [
            {
                'toolSpec': {
                    'name': 'control_robot_hardware',
                    'description': "Controls the physical robot's LED strip and buzzer.",
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {
                                'led_color': {
                                    'type': 'string',
                                    'enum': list(COLORS.keys()),
                                    'description': 'The color to set the LED strip to. Use "Off" to turn off the LEDs.'
                                },
                                'beep_duration': {
                                    'type': 'number',
                                    'description': 'Number of seconds to sound the buzzer. Use 0 or omit if you do not want to make a sound.'
                                }
                            }
                        }
                    }
                }
            },
            {
                'toolSpec': {
                    'name': 'get_distance',
                    'description': "Measures the distance from the robot's ultrasonic sensor to the nearest obstacle (like a person or wall) in centimeters.",
                    'inputSchema': {
                        'json': {
                            'type': 'object',
                            'properties': {}
                        }
                    }
                }
            }
        ]
        
        try:
            # First converse call to allow tool use
            response = self.client.converse(
                modelId=MODEL_ID,
                messages=self.messages,
                system=[{
                    'text': "You are an intelligent robot assistant. You have access to tools to control the physical robot's LED lights/buzzer and to measure distances using an ultrasonic sensor. "
                            "When the user asks to change colors, blink, beep, or turn off the lights, ALWAYS invoke the control_robot_hardware tool. "
                            "When the user asks about the distance to a person, object, wall, or how far something is, ALWAYS invoke the get_distance tool. "
                            "If the user asks a general question, just reply normally. "
                            "Be friendly, helpful, and a bit robotic."
                }],
                toolConfig={'tools': tools}
            )
            
            output_message = response['output']['message']
            self.messages.append(output_message)
            
            # Check for tool use request
            tool_calls = [c['toolUse'] for c in output_message.get('content', []) if 'toolUse' in c]
            
            if tool_calls:
                tool_results_content = []
                for tool in tool_calls:
                    name = tool['name']
                    input_data = tool['input']
                    tool_use_id = tool['toolUseId']
                    
                    if name == 'control_robot_hardware':
                        led_color = input_data.get('led_color')
                        beep_duration = input_data.get('beep_duration', 0)
                        
                        actions = []
                        if led_color:
                            if set_colour(led_color):
                                actions.append(f"Set LED color to {led_color}")
                        if beep_duration > 0:
                            beep_buzzer(beep_duration)
                            actions.append(f"Beeped buzzer for {beep_duration} seconds")
                            
                        result_text = ", ".join(actions) if actions else "No action performed."
                        print(f"🤖 [Hardware Action Executed: {result_text}]")
                        
                        tool_results_content.append({
                            'toolResult': {
                                'toolUseId': tool_use_id,
                                'status': 'success',
                                'content': [{'text': f"Successfully executed: {result_text}"}]
                            }
                        })
                    elif name == 'get_distance':
                        distance = ultrasonic.get_distance()
                        if distance is not None:
                            result_text = f"Successfully measured distance: {distance} cm"
                        else:
                            result_text = "Failed to measure distance."
                        print(f"🤖 [Hardware Action Executed: {result_text}]")
                        
                        tool_results_content.append({
                            'toolResult': {
                                'toolUseId': tool_use_id,
                                'status': 'success',
                                'content': [{'text': result_text}]
                            }
                        })
                
                if tool_results_content:
                    self.messages.append({
                        'role': 'user',
                        'content': tool_results_content
                    })
                
                # Make a follow-up converse call with the tool results to get the final response
                followup_response = self.client.converse(
                    modelId=MODEL_ID,
                    messages=self.messages,
                    system=[{
                        'text': "You are an intelligent robot assistant. You just successfully ran the hardware tools. Confirm the results of the execution to the user."
                    }],
                    toolConfig={'tools': tools}
                )
                final_message = followup_response['output']['message']
                self.messages.append(final_message)
                text_response = "".join([c['text'] for c in final_message.get('content', []) if 'text' in c])
                return text_response
            else:
                # Just text response, no tool called
                text_response = "".join([c['text'] for c in output_message.get('content', []) if 'text' in c])
                return text_response
                
        except Exception as e:
            return f"❌ Error contacting Bedrock: {e}"

def main():
    print("====================================================")
    print("🤖 Starting AI Robot Assistant CLI...")
    print("Press Ctrl+C or type 'exit' / 'quit' to shut down.")
    print("====================================================")
    
    try:
        assistant = RobotAssistant()
        print("Connected to AWS Bedrock successfully.")
    except Exception as e:
        print(f"Failed to initialize assistant: {e}")
        return

    try:
        while True:
            user_input = input("\nYou: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ('exit', 'quit'):
                break
                
            print("AI: thinking...")
            reply = assistant.chat(user_input)
            print(f"\nAI: {reply}")
            
    except KeyboardInterrupt:
        pass
    finally:
        turn_off_everything()
        print("\nGoodbye! 🤖")

if __name__ == "__main__":
    main()
