#!/usr/bin/env python3
"""
Terrako servo calibration tool.
Connects to the Pico WITHOUT triggering the wake animation,
then lets you adjust each servo interactively.

Usage:
    python3 calibrate.py

Commands inside the tool:
    <channel> <angle>   Set servo to angle       e.g.  2 95
    all <angle>         Set all leg servos 0-7   e.g.  all 90
    head <angle>        Set head servo 8         e.g.  head 90
    release             Release all servos (go limp)
    stand               All leg servos to 90
    list                Show channel map
    quit                Exit (releases servos first)
"""

import serial
import time
import os

CHANNEL_MAP = """
Channel map:
  0 = Rear Left  HIP      4 = Rear Left  KNEE
  1 = Front Right HIP     5 = Front Left KNEE
  2 = Front Left  HIP     6 = Rear Right KNEE
  3 = Rear Right  HIP     7 = Front Right KNEE
  8 = HEAD (be careful - limited range)
"""

def find_pico():
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2']:
        if os.path.exists(port):
            return port
    return None

def main():
    port = find_pico()
    if not port:
        print("No Pico found!")
        return

    print(f"Connecting to Pico on {port}...")
    ser = serial.Serial(port, 115200, timeout=1)
    time.sleep(3)  # let Pico finish booting

    # CALIBRATE handshake - skips wake animation
    ser.write(b'CALIBRATE\n')
    time.sleep(1)
    print("Connected in CALIBRATE mode - no wake animation.")
    print(CHANNEL_MAP)
    print("Type a command (or 'help'):")

    while True:
        try:
            cmd = input("> ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            cmd = 'quit'

        if not cmd:
            continue

        if cmd in ('quit', 'exit', 'q'):
            print("Releasing servos and exiting...")
            ser.write(b'RELEASE\n')
            time.sleep(0.5)
            ser.close()
            break

        elif cmd == 'help':
            print(__doc__)

        elif cmd == 'list':
            print(CHANNEL_MAP)

        elif cmd == 'release':
            ser.write(b'RELEASE\n')
            print("Servos released.")

        elif cmd == 'stand':
            for ch in range(8):
                ser.write(f'SERVO {ch} 90\n'.encode())
                time.sleep(0.15)
            print("All leg servos set to 90.")

        elif cmd.startswith('all '):
            try:
                angle = int(cmd.split()[1])
                for ch in range(8):
                    ser.write(f'SERVO {ch} {angle}\n'.encode())
                    time.sleep(0.15)
                print(f"All leg servos set to {angle}.")
            except (ValueError, IndexError):
                print("Usage: all <angle>   e.g.  all 90")

        elif cmd.startswith('head '):
            try:
                angle = int(cmd.split()[1])
                if angle < 45 or angle > 135:
                    print("Head limited to 45-135 for safety.")
                    continue
                ser.write(f'SERVO 8 {angle}\n'.encode())
                print(f"Head set to {angle}.")
            except (ValueError, IndexError):
                print("Usage: head <angle>   e.g.  head 90")

        else:
            # Try to parse "<channel> <angle>"
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    ch = int(parts[0])
                    angle = int(parts[1])
                    if ch < 0 or ch > 8:
                        print("Channel must be 0-8.")
                        continue
                    if ch == 8 and (angle < 45 or angle > 135):
                        print("Head limited to 45-135 for safety.")
                        continue
                    ser.write(f'SERVO {ch} {angle}\n'.encode())
                    print(f"Servo {ch} -> {angle}")
                except ValueError:
                    print("Unknown command. Type 'help'.")
            else:
                print("Unknown command. Type 'help'.")

if __name__ == "__main__":
    main()