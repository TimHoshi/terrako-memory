import serial
import time

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
time.sleep(1)

# Send HELLO and wait for boot
print('Sending HELLO...')
ser.write(b'HELLO\n')

# Wait for READY
start = time.time()
while time.time() - start < 30:
    if ser.in_waiting:
        line = ser.readline().decode().strip()
        if line:
            print(f'Pico: {line}')
            if 'READY' in line:
                break

print('\nTerrako ready! Enter commands (or q to quit):')
print('Options: EYE_RED, EYE_BLUE, EYE_GREEN, EYE_OFF, HAPPY, STOP, SLEEP')

while True:
    cmd = input('> ').strip().upper()
    if cmd == 'Q':
        break
    ser.write((cmd + '\n').encode())
    time.sleep(0.5)
    while ser.in_waiting:
        line = ser.readline().decode().strip()
        if line:
            print(f'Pico: {line}')

ser.close()
