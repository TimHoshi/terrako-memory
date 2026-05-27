import board
import neopixel
import time
import math

pixels = neopixel.NeoPixel(board.GP28, 12, brightness=0.3)

def test_pixels():
    """Boot test — returns True if NeoPixel responds."""
    try:
        pixels.fill((10, 0, 0))
        time.sleep(0.1)
        pixels.fill((0, 0, 0))
        return True
    except Exception:
        return False

def startup_sequence():
    print("Starting color cycle...")
    colors = [
        (255, 0,   0),
        (0,   255, 0),
        (0,   0,   255),
        (255, 255, 0),
        (255, 0,   255),
        (0,   255, 255),
        (255, 255, 255),
    ]
    for color in colors:
        pixels.fill(color)
        time.sleep(1.5)
    for b in range(255, 0, -5):
        pixels.fill((0, 0, b))
        time.sleep(0.02)
    pixels.fill((0, 0, 0))

def set_color(color):
    if color == 'red':     pixels.fill((255, 0,   0))
    elif color == 'green': pixels.fill((0,   255, 0))
    elif color == 'blue':  pixels.fill((0,   0,   255))
    elif color == 'orange':pixels.fill((255, 80,  0))
    elif color == 'white': pixels.fill((255, 255, 255))
    elif color == 'off':   pixels.fill((0,   0,   0))

def breathe():
    """Normal blue breathing — time based sine wave, never gets stuck."""
    t = time.monotonic()
    b = int(35 + 35 * math.sin(2 * math.pi * t / 3.0))
    pixels.fill((0, 0, b))

def sleep_pulse():
    """Very slow dim pulse for sleep state — barely visible in dark room."""
    t = time.monotonic()
    b = int(8 + 7 * math.sin(2 * math.pi * t / 6.0))
    pixels.fill((0, 0, b))

def sleep_fade():
    """Slowly fade eye to off during sleep sequence."""
    for b in range(50, 0, -2):
        pixels.fill((0, 0, b))
        time.sleep(0.05)
    pixels.fill((0, 0, 0))

def think_pulse():
    """Slow amber pulse while Terrako is thinking."""
    t = time.monotonic()
    b = int(60 + 40 * math.sin(2 * math.pi * t / 2.0))
    r = b
    g = int(b * 0.4)
    pixels.fill((r, g, 0))