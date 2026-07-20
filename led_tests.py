import time
import sys

import os

# Point to your actual username 'eera' and folder 'freenove-kit'
project_dir = os.path.dirname(os.path.abspath(__file__))
local_path = os.path.join(project_dir, 'freenove-kit', 'Code', 'Server')
if os.path.exists(local_path):
    sys.path.append(local_path)
else:
    sys.path.append('/home/eera/robot/freenove-kit/Code/Server')

# Import the Led class (note the capitalization)
from led import Led
from buzzer import Buzzer

# Initialize the LED strip on the car
led = Led()
buzzer = Buzzer()


def set_colour(color):
   for i in range(8):
      led.ledIndex(i, colors[color][0], colors[color][1], colors[color][2])
      

name = input("What color would you like to see? ")

colors = {
   'Red' : [255, 0, 0],
   'Green' : [0, 255, 0],
   'Blue' : [0, 0, 255],
   'Yellow' : [255, 255, 0],
   'Purple' : [255, 0, 255],
   'Cyan' : [0, 255, 255],
   'White' : [255, 255, 255],
   'Off' : [0, 0, 0],
}

set_colour(name)         
buzzer.set_state(True)         
time.sleep(2)
buzzer.set_state(False)  
for i in range(8):
      led.ledIndex(i, 0,0,0)
   
print()
print(f'🌈 LED test with color {name} complete!')
