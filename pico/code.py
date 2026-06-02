import time
import sys
import supervisor

print("Step 1 - basic imports done")

from leds import test_pixels, startup_sequence
from leds import set_color, breathe, think_pulse, sleep_fade
print("Step 2 - leds imported")

try:
    from movement import wake_up, stand, servos
    movement_ok = True
    print("Step 3 - movement imported")
except Exception as e:
    movement_ok = False
    servos = [None] * 9
    print(f"Step 3 - movement FAILED: {e}")

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
idle_count = 0
while True:
    cmd = serial_read()
    if cmd == 'HELLO':
        break
    time.sleep(0.1)
    idle_count += 1
    if idle_count >= 300:  # every 30 seconds
        serial_send('WAITING')
        idle_count = 0

print("Step 7 - running wakeup")
if movement_ok:
    wake_up()
else:
    print("Step 7 - skipping wakeup, movement not available")

print("Step 8 - sending READY")
serial_send('READY')
set_color('blue')

print("Step 9 - entering main loop")

# ── MAIN LOOP ──
while True:
    cmd = serial_read()

    if cmd:
        if cmd == 'STOP':
            if movement_ok:
                stand()
        elif cmd == 'STAND':
            if movement_ok:
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
        elif cmd == 'THINK':
            while True:
                think_pulse()
                time.sleep(0.05)
                cmd = serial_read()
                if cmd:
                    break
                # Timeout after 60 seconds — return to normal
                if time.monotonic() - think_start > 60:
                    break
        elif cmd == 'SLEEP':
            sleep_fade()
            serial_send('SLEEPING')
        elif cmd == 'RELEASE':
            if movement_ok and any(s is not None for s in servos):
                from movement import pca
                for i in range(9):
                    pca.channels[i].duty_cycle = 0
            serial_send('RELEASED')
        elif cmd.startswith('SERVO'):
            try:
                parts = cmd.split()
                ch = int(parts[1])
                ang = int(parts[2])
                if servos[ch] is not None:
                    servos[ch].angle = max(0, min(180, ang))
                    serial_send(f'OK {ch} {ang}')
                else:
                    serial_send(f'ERROR servo {ch} not available')
            except Exception as e:
                serial_send(f'ERROR {e}')
    else:
        breathe()

    time.sleep(0.02)