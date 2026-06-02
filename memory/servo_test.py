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

print('\nServo Test Mode!')
print('Commands:')
print('  SERVO [ch] [angle] — move specific servo e.g. "SERVO 0 90"')
print('  STAND              — move all to standing position')
print('  RELEASE            — release all servos')
print('  CENTER             — move all to 90 degrees')
print('  q                  — quit')
print()

while True:
    cmd = input('> ').strip().upper()
    
    if cmd == 'Q':
        break
    elif cmd == 'CENTER':
        for i in range(9):
            ser.write(f'SERVO {i} 90\n'.encode())
            time.sleep(0.1)
        print('All servos centered at 90°')
    elif cmd == 'STAND':
        ser.write(b'STAND\n')
        time.sleep(0.5)
        print('Standing position')
    elif cmd == 'RELEASE':
        ser.write(b'RELEASE\n')
        time.sleep(0.5)
        print('Servos released')
    else:
        ser.write((cmd + '\n').encode())
        time.sleep(0.3)
        while ser.in_waiting:
            line = ser.readline().decode().strip()
            if line:
                print(f'Pico: {line}')

ser.close()