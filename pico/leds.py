# Low-level ring helpers for the 8x NeoPixel on GP28.
#
# `pixels` is the single shared ring object; presence.py imports it and drives
# the motion. Leave auto_write at its default (True) or presence.tick() won't
# reach the LEDs. The functions below are the legacy animations kept as a
# fallback for when presence.py is absent.

import board
import neopixel
import time
import math

pixels = neopixel.NeoPixel(board.GP28, 8, brightness=0.3)

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
    """Very dim purple pulse for sleep state."""
    t = time.monotonic()
    b = int(15 + 10 * math.sin(2 * math.pi * t / 4.0))
    pixels.fill((b, 0, b))  # dim purple
    pixels.show()

def sleep_fade():
    """Fade to dim purple sleep pulse."""
    for brightness in range(30, 0, -2):
        pixels.fill((brightness, 0, brightness))
        pixels.show()
        time.sleep(0.05)
    # Settle into slow purple pulse
    for _ in range(40):
        sleep_pulse()
        time.sleep(0.05)

def think_pulse():
    """Slow white pulse while Terrako is thinking."""
    t = time.monotonic()
    b = int(40 + 30 * math.sin(2 * math.pi * t / 2.0))
    pixels.fill((b, b, b))
    pixels.show()