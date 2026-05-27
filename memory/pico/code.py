import time
import sys
import supervisor

print("Step 1 - basic imports done")

from leds import test_pixels, startup_sequence
from leds import set_color, breathe
print("Step 2 - leds imported")

from movement import wake_up, stand, servos
print("Step 3 - movement imported")

print("Step 4 - sensor skipped")

# ── Serial helpers ──
def serial_send(msg):
    sys.stdout.write(msg + '\n')

def serial_read():
    if supervisor.runtime.serial_bytes_available:
        line = sys.stdin.readline().strip()
        return line if line else None
    return None

# ── Boot sequence ──
print("Step 5 - testing pixels")
pixel_ok = test_pixels()
if not pixel_ok:
    serial_send('WARNING_PIXEL')
else:
    startup_sequence()

print("Step 6 - waiting for Orange Pi HELLO")
set_color('orange')
while True:
    cmd = serial_read()
    if cmd == 'HELLO':
        break
    time.sleep(0.1)

print("Step 7 - running wakeup")
wake_up()

print("Step 8 - sending READY")
serial_send('READY')
set_color('blue')

print("Step 9 - entering main loop")

# ── MAIN LOOP ──
while True:
    cmd = serial_read()

    if cmd:
        if cmd == 'STOP':
            stand()
        elif cmd == 'STAND':
            stand()
        elif cmd == 'EYE_RED':
            set_color('red')
        elif cmd == 'EYE_BLUE':
            set_color('blue')
        elif cmd == 'EYE_GREEN':
            set_color('green')
        elif cmd == 'EYE_OFF':
            set_color('off')
        elif cmd == 'HAPPY':
            set_color('green')
            time.sleep(0.5)
            set_color('blue')
        elif cmd == 'SLEEP':
            sleep_fade()
            serial_send('SLEEPING')
        elif cmd.startswith('SERVO'):
            try:
                parts = cmd.split()
                ch = int(parts[1])
                ang = int(parts[2])
                servos[ch].angle = max(0, min(180, ang))
                serial_send(f'OK {ch} {ang}')
            except Exception as e:
                serial_send(f'ERROR {e}')
        elif cmd == 'THINK':
            while True:
                think_pulse()
                time.sleep(0.05)
                cmd = serial_read()
                if cmd:
                    break
        elif cmd == 'SLEEP':
            sleep_fade()
            serial_send('SLEEPING')
    else:
        breathe()
    time.sleep(0.02)