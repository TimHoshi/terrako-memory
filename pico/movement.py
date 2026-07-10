import board
import busio
import time
import math
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685

# ── PCA9685 initialization with retry ──
def init_pca():
    """Initialize PCA9685 with retry."""
    for attempt in range(3):
        try:
            i2c = busio.I2C(board.GP1, board.GP0)
            pca = PCA9685(i2c)
            pca.frequency = 50
            print(f"PCA9685 initialized on attempt {attempt + 1}")
            return pca
        except Exception as e:
            print(f"PCA9685 init attempt {attempt + 1} failed: {e}")
            time.sleep(1)
    return None

pca = init_pca()
servos = []
if pca:
    for i in range(9):
        s = servo.Servo(pca.channels[i], min_pulse=500, max_pulse=2500)
        servos.append(s)
else:
    print("WARNING: PCA9685 not available — servos disabled")
    servos = [None] * 9

# ── Calibrated standing angles ──
STAND = [90, 90, 90, 90, 90, 90, 90, 90, 90]

# ── Servo channel assignments ──
FL_HIP  = 2;  FL_KNEE = 5
FR_HIP  = 1;  FR_KNEE = 7
RL_HIP  = 0;  RL_KNEE = 4
RR_HIP  = 3;  RR_KNEE = 6
HEAD    = 8

def _set(channel, angle):
    if servos[channel] is not None:
        servos[channel].angle = max(0, min(180, angle))

def stand():
    """Stand up in stages - diagonal pairs, ramped, to limit current draw."""
    if not any(s is not None for s in servos):
        return

    # Pair 1: Front Left + Rear Right (hips then knees, ramped)
    for ch in (FL_HIP, RR_HIP, FL_KNEE, RR_KNEE):
        slow_set(ch, STAND[ch], steps=15, delay=0.02)

    time.sleep(0.3)  # let current settle

    # Pair 2: Front Right + Rear Left
    for ch in (FR_HIP, RL_HIP, FR_KNEE, RL_KNEE):
        slow_set(ch, STAND[ch], steps=15, delay=0.02)

    time.sleep(0.3)

def slow_set(channel, target, steps=20, delay=0.02):
    if servos[channel] is None:
        return
    current = servos[channel].angle
    if current is None:
        current = STAND[channel]
    step_size = (target - current) / steps
    for i in range(steps):
        next_angle = current + (step_size * (i + 1))
        servos[channel].angle = max(0, min(180, next_angle))
        time.sleep(delay)

def oscillate(amplitude, period, phase_offset, t):
    return amplitude * math.sin(2 * math.pi * t / period + phase_offset)

def wake_up():
    if not any(s is not None for s in servos):
        print("wake_up skipped - no servos")
        return
    # Pass 1
    for i, angle in enumerate(STAND):
        _set(i, angle)
    time.sleep(0.5)
    # Pass 2
    for i, angle in enumerate(STAND):
        _set(i, angle)
    time.sleep(0.3)
    # Head shake
    _set(HEAD, 60)
    time.sleep(0.4)
    _set(HEAD, 120)
    time.sleep(0.4)
    _set(HEAD, 60)
    time.sleep(0.4)
    _set(HEAD, 90)
    time.sleep(0.3)
    # Final stand
    stand()

def walk_forward(duration=0.5, amplitude=30, period=1.0):
    if not any(s is not None for s in servos):
        return
    start = time.monotonic()
    while time.monotonic() - start < duration:
        t = time.monotonic() - start
        _set(FL_HIP, STAND[FL_HIP] + oscillate(amplitude, period, 0, t))
        _set(RR_HIP, STAND[RR_HIP] + oscillate(amplitude, period, 0, t))
        _set(FR_HIP, STAND[FR_HIP] + oscillate(amplitude, period, math.pi, t))
        _set(RL_HIP, STAND[RL_HIP] + oscillate(amplitude, period, math.pi, t))
        _set(FL_KNEE, STAND[FL_KNEE] - oscillate(30, period, -math.pi/2, t))
        _set(RR_KNEE, STAND[RR_KNEE] + oscillate(30, period, math.pi/2, t))
        _set(FR_KNEE, STAND[FR_KNEE] + oscillate(30, period, -math.pi/2, t))
        _set(RL_KNEE, STAND[RL_KNEE] + oscillate(30, period, -math.pi/2, t))
        time.sleep(0.02)

def turn_left(duration=0.6, amplitude=25, period=1.0):
    if not any(s is not None for s in servos):
        return
    start = time.monotonic()
    while time.monotonic() - start < duration:
        t = time.monotonic() - start
        _set(FL_HIP, STAND[FL_HIP] + oscillate(amplitude, period, 0, t))
        _set(RL_HIP, STAND[RL_HIP] + oscillate(amplitude, period, 0, t))
        _set(FR_HIP, STAND[FR_HIP] + oscillate(amplitude, period, 0, t))
        _set(RR_HIP, STAND[RR_HIP] + oscillate(amplitude, period, 0, t))
        _set(FL_KNEE, STAND[FL_KNEE] - oscillate(30, period, -math.pi/2, t))
        _set(RR_KNEE, STAND[RR_KNEE] + oscillate(30, period, math.pi/2, t))
        _set(FR_KNEE, STAND[FR_KNEE] + oscillate(30, period, -math.pi/2, t))
        _set(RL_KNEE, STAND[RL_KNEE] + oscillate(30, period, -math.pi/2, t))
        time.sleep(0.02)
    stand()