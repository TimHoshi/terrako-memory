import time
import sys
import supervisor

print("Step 1 - basic imports done")

from leds import test_pixels, startup_sequence
print("Step 2 - leds imported")

# Presence engine: one ring, one language. Falls back to plain blue breathing
# if presence.py is missing, so a half-copied card still boots.
try:
    import presence
    presence_ok = True
    print("Step 2b - presence imported")
except Exception as e:
    presence_ok = False
    from leds import set_color, breathe
    print(f"Step 2b - presence FAILED: {e}")

try:
    from movement import wake_up, stand, servos
    movement_ok = True
    print("Step 3 - movement imported")
except Exception as e:
    movement_ok = False
    servos = [None] * 9
    print(f"Step 3 - movement FAILED: {e}")

print("Step 4 - sensor skipped")


# -- Serial helpers --
def serial_send(msg):
    sys.stdout.write(msg + '\n')


def serial_read():
    if supervisor.runtime.serial_bytes_available:
        line = sys.stdin.readline().strip()
        return line if line else None
    return None


def show(name, timed=None):
    """Set a presence state, legacy fallback if the engine is missing."""
    if not presence_ok:
        legacy = {'idle': 'blue', 'talking': 'green', 'alert': 'red',
                  'working': 'red', 'asleep': 'off', 'happy': 'green'}
        set_color(legacy.get(name, 'blue'))
        return True
    if timed:
        return presence.set_state_timed(name, timed)
    return presence.set_state(name)


def animate():
    if presence_ok:
        presence.tick()
    else:
        breathe()


# -- Boot sequence --
print("Step 5 - testing pixels")
pixel_ok = test_pixels()
if not pixel_ok:
    serial_send('WARNING_PIXEL')
else:
    startup_sequence()

print("Step 6 - waiting for Orange Pi HELLO")
show('working')
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
    animate()
    if idle_count >= 300:  # every 30 seconds
        serial_send('WAITING')
        idle_count = 0

print("Step 7 - running wakeup")
if movement_ok and not calibrate_mode:
    wake_up()
else:
    print("Step 7 - skipping wakeup, movement not available")

# Legs came back under their own power; the ring says I'm here.
show('here')

print("Step 8 - sending READY")
serial_send('READY')

print("Step 9 - entering main loop")

while True:
    cmd = serial_read()

    if cmd:
        if cmd == 'STOP':
            if movement_ok:
                stand()
            show('asleep')
        elif cmd == 'STAND':
            if movement_ok:
                stand()
            show('here')
        # --- presence states (new) ---
        elif cmd.startswith('STATE'):
            try:
                name = cmd.split(None, 1)[1]
                serial_send(f'OK STATE {name}' if show(name) else f'ERROR unknown state {name}')
            except Exception as e:
                serial_send(f'ERROR {e}')
        elif cmd.startswith('BRIGHT'):
            try:
                pct = int(cmd.split()[1])
                if presence_ok:
                    presence.set_brightness(pct)
                serial_send(f'OK BRIGHT {pct}')
            except Exception as e:
                serial_send(f'ERROR {e}')
        elif cmd.startswith('EYE '):
            # EYE <r> <g> <b> - raw, held steady until the next STATE
            try:
                _, r, g, b = cmd.split()
                if presence_ok:
                    presence.set_rgb(int(r), int(g), int(b))
                serial_send(f'OK EYE {r} {g} {b}')
            except Exception as e:
                serial_send(f'ERROR {e}')
        # --- legacy EYE_* names, mapped to states ---
        elif cmd == 'EYE_RED':
            show('alert')
        elif cmd == 'EYE_BLUE':
            show('idle')
        elif cmd == 'EYE_GREEN':
            show('talking')
        elif cmd == 'EYE_OFF':
            show('asleep')
        elif cmd == 'HAPPY':
            show('happy', timed=2.5)
        elif cmd == 'THINK':
            think_start = time.monotonic()
            show('working')
            while True:
                if presence_ok:
                    presence.tick()
                else:
                    from leds import think_pulse
                    think_pulse()
                if supervisor.runtime.serial_bytes_available:
                    cmd = sys.stdin.readline().strip()
                    if cmd:
                        break
                if time.monotonic() - think_start > 60:
                    break
                time.sleep(0.05)
            show('idle')
        elif cmd == 'SLEEP':
            show('asleep')
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
        animate()