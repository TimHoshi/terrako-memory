import board
import busio
import time
import math
from adafruit_motor import servo
from adafruit_pca9685 import PCA9685

# Setup I2C and servo driver
i2c = busio.I2C(board.GP1, board.GP0)
pca = PCA9685(i2c)
pca.frequency = 50

servos = []
for i in range(9):
    s = servo.Servo(pca.channels[i], min_pulse=500, max_pulse=2500)
    servos.append(s)

# Calibrated standing angles — ground truth, never change these
STAND = [90, 90, 90, 60, 90, 90, 70, 90, 90]

# Servo channel assignments
FL_HIP = 2;  FL_KNEE = 5
FR_HIP = 1;  FR_KNEE = 7
RL_HIP = 4;  RL_KNEE = 0
RR_HIP = 3;  RR_KNEE = 6
HEAD   = 8

def _set(channel, angle):
    # Safe servo setter with angle limits
    servos[channel].angle = max(0, min(180, angle))

def stand():
    # Move all servos to calibrated standing position
    for i, angle in enumerate(STAND):
        servos[i].angle = angle
    time.sleep(0.3)
    
def slow_set(channel, target, steps=20, delay=0.02):
    """Move servo gradually to target angle."""
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
    # Pass 1 — first calibration sweep to known position
    for i, angle in enumerate(STAND):
        servos[i].angle = angle
    time.sleep(0.5)

    # Pass 2 — second sweep to settle joints
    for i, angle in enumerate(STAND):
        servos[i].angle = angle
    time.sleep(0.3)
    # Head shakes side to side — shaking sleep away
    for _ in range(3):
        _set(HEAD, 60)
        time.sleep(0.4)
        _set(HEAD, 120)
        time.sleep(0.4)
    _set(HEAD, 90)
    time.sleep(0.3)

    # Body bob — looks like stretching, third calibration pass
    for _ in range(2):
        _set(FL_KNEE, STAND[FL_KNEE] + 15)
        _set(FR_KNEE, STAND[FR_KNEE] + 15)
        _set(RL_KNEE, STAND[RL_KNEE] + 15)
        _set(RR_KNEE, STAND[RR_KNEE] + 15)
        time.sleep(0.2)
        _set(FL_KNEE, STAND[FL_KNEE])
        _set(FR_KNEE, STAND[FR_KNEE])
        _set(RL_KNEE, STAND[RL_KNEE])
        _set(RR_KNEE, STAND[RR_KNEE])
        time.sleep(0.2)

    # Final stand — fully calibrated and ready
    stand()
    time.sleep(0.3)

def walk_forward(duration=0.5, amplitude=30, period=1.0):
    start = time.monotonic()
    while time.monotonic() - start < duration:
        t = time.monotonic() - start
        _set(FL_HIP, STAND[FL_HIP] + oscillate(amplitude, period, 0, t))
        _set(RR_HIP, STAND[RR_HIP] + oscillate(amplitude, period, 0, t))
        _set(FR_HIP, STAND[FR_HIP] + oscillate(amplitude, period, math.pi, t))
        _set(RL_HIP, STAND[RL_HIP] + oscillate(amplitude, period, math.pi, t))
        _set(FL_KNEE, STAND[FL_KNEE] - oscillate(30, period, -math.pi/2, t))
        _set(RR_KNEE, STAND[RR_KNEE] + oscillate(30, period,  math.pi/2, t))
        _set(FR_KNEE, STAND[FR_KNEE] + oscillate(30, period, -math.pi/2, t))
        _set(RL_KNEE, STAND[RL_KNEE] + oscillate(30, period, -math.pi/2, t))
        time.sleep(0.02)

def turn_left(duration=0.6, amplitude=25, period=1.0):
    start = time.monotonic()
    while time.monotonic() - start < duration:
        t = time.monotonic() - start
        # Left side forward, right side backward
        _set(FL_HIP, STAND[FL_HIP] + oscillate(amplitude, period, 0, t))
        _set(RL_HIP, STAND[RL_HIP] + oscillate(amplitude, period, 0, t))
        _set(FR_HIP, STAND[FR_HIP] + oscillate(amplitude, period, 0, t))
        _set(RR_HIP, STAND[RR_HIP] + oscillate(amplitude, period, 0, t))
        _set(FL_KNEE, STAND[FL_KNEE] - oscillate(30, period, -math.pi/2, t))
        _set(RR_KNEE, STAND[RR_KNEE] + oscillate(30, period,  math.pi/2, t))
        _set(FR_KNEE, STAND[FR_KNEE] + oscillate(30, period, -math.pi/2, t))
        _set(RL_KNEE, STAND[RL_KNEE] + oscillate(30, period, -math.pi/2, t))
        time.sleep(0.02)
    stand()
