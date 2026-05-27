import serial
import time

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
time.sleep(1)

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

print('\nCalibration mode!')
print('Enter: channel angle (e.g. "0 150")')
print('Enter: save — to print final STAND array')
print('Enter: q — to quit')

current = [150, 90, 90, 90, 90, 45, 50, 120, 90]

# Set current standing position first
for i, angle in enumerate(current):
    ser.write(f'SERVO {i} {angle}\n'.encode())
    time.sleep(0.1)

while True:
    val = input('> ').strip()
    
    if val.lower() == 'q':
        break
    elif val.lower() == 'save':
        print(f'\nFinal STAND array:')
        print(f'STAND = {current}')
        print('\nCopy this into movement.py on the Pico!')
    else:
        try:
            ch, ang = val.split()
            ch = int(ch)
            ang = int(ang)
            current[ch] = ang
            ser.write(f'SERVO {ch} {ang}\n'.encode())
            time.sleep(0.1)
            while ser.in_waiting:
                line = ser.readline().decode().strip()
                if line:
                    print(f'Pico: {line}')
            print(f'Channel {ch} → {ang}°')
        except:
            print('Format: channel angle (e.g. "0 150")')

ser.close()
