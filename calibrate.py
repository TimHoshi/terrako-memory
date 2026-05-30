import serial
import time

ser = serial.Serial('/dev/ttyACM0', 115200, timeout=2)
time.sleep(2)

print('Sending HELLO...')
# Send HELLO multiple times to make sure it gets through
for _ in range(5):
    ser.write(b'HELLO\n')
    time.sleep(0.5)

print('Listening for READY...')
start = time.time()
ready = False
while time.time() - start < 30:
    if ser.in_waiting:
        line = ser.readline().decode().strip()
        if line:
            print(f'Pico: {line}')
            if 'READY' in line:
                ready = True
                break

if not ready:
    print('Pico did not respond - check connection')
    ser.close()
    exit()

print('\nCalibration mode!')
print('Enter: channel angle (e.g. "0 90")')
print('Enter: save — to print final STAND array')
print('Enter: q — to quit')

current = [90, 90, 90, 90, 90, 90, 90, 90, 90]

while True:
    val = input('> ').strip()
    
    if val.lower() == 'q':
        break
    elif val.lower() == 'save':
        print(f'\nFinal STAND array:')
        print(f'STAND = {current}')
        print('\nCopy this into movement.py!')
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
            print('Format: channel angle (e.g. "0 90")')

ser.close()