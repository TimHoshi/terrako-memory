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
calibrate_mode = False
while True:
    cmd = serial_read()
    if cmd == 'HELLO':
        break
    if cmd == 'CALIBRATE':
        calibrate_mode = True
        break
    time.sleep(0.1)
    idle_count += 1
    if idle_count >= 300:  # every 30 seconds
        serial_send('WAITING')
        idle_count = 0

print("Step 7 - running wakeup")
if movement_ok and not calibrate_mode:
    wake_up()
else:
    print("Step 7 - skipping wakeup, movement not available")

print("Step 8 - sending READY")
serial_send('READY')
set_color('blue')

print("Step 9 - entering main loop")

# ── Color hold timer ──
# After an EYE_* command, hold that color for this many seconds
# before resuming the breathing animation.
COLOR_HOLD_SECONDS = 2.5
color_hold_until = 0

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
            color_hold_until = time.monotonic() + COLOR_HOLD_SECONDS
        elif cmd == 'EYE_BLUE':
            set_color('blue')
            color_hold_until = time.monotonic() + COLOR_HOLD_SECONDS
        elif cmd == 'EYE_GREEN':
            set_color('green')
            color_hold_until = time.monotonic() + COLOR_HOLD_SECONDS
        elif cmd == 'EYE_OFF':
            set_color('off')
            color_hold_until = time.monotonic() + COLOR_HOLD_SECONDS
        elif cmd == 'HAPPY':
            set_color('green')
            color_hold_until = time.monotonic() + COLOR_HOLD_SECONDS
            time.sleep(0.5)
            set_color('blue')
        elif cmd == 'THINK':
            think_start = time.monotonic()
            while True:
                think_pulse()
                if supervisor.runtime.serial_bytes_available:
                    cmd = sys.stdin.readline().strip()
                    if cmd:
                        break
                if time.monotonic() - think_start > 60:
                    break
                time.sleep(0.05)
            # Process the breaking command
            if cmd == 'EYE_BLUE':
                set_color('blue')
                color_hold_until = time.monotonic() + COLOR_HOLD_SECONDS
            elif cmd == 'EYE_GREEN':
                set_color('green')
                color_hold_until = time.monotonic() + COLOR_HOLD_SECONDS
            elif cmd == 'EYE_OFF':
                set_color('off')
                color_hold_until = time.monotonic() + COLOR_HOLD_SECONDS
        elif cmd == 'SLEEP':
            sleep_fade()
            serial_send('SLEEPING')
            # Hold sleep state indefinitely - don't resume breathing
            color_hold_until = time.monotonic() + 999999
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
        if time.monotonic() > color_hold_until:
            breathe()

    time.sleep(0.02)