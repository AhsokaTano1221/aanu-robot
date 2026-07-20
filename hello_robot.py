import time

print('🤖 Hello! I am your robot!')
print('I am alive and running on THIS Raspberry Pi!')
print()

# Countdown to prove we're running live
for i in range(5, 0, -1):
   print(f'  Launching in {i}...')
   time.sleep(1)

print()
print('🚗 VROOM! Robot is ready!')
print('(Next step: we make the LEDs blink!)')
