# Akari's presence ring - states for the 8x NeoPixel on GP28.
#
# One ring, one language. `STATE <name>` sets the truth; the ring shows it.
# Every state has a color AND a motion, so it reads alive instead of as a lamp.
#
# Brightness is capped hard on purpose. This ring lives in a bedroom at night.
#
# Drops next to leds.py on the Pico. code.py calls tick() every loop pass.

import time
import math
from leds import pixels

# Hard ceiling. Never let a state override this.
MAX_BRIGHTNESS = 0.25

# name -> rgb, motion, period_s, lo, hi
# motion: steady | breath | pulse | blink | off
STATES = {
    'idle':      {'rgb': (0, 70, 190),    'motion': 'breath', 'period': 6.0, 'lo': 0.15, 'hi': 1.00},
    'here':      {'rgb': (255, 96, 40),   'motion': 'pulse',  'period': 5.0, 'lo': 0.20, 'hi': 0.80},
    'listening': {'rgb': (40, 120, 255),  'motion': 'steady', 'period': 0.0, 'lo': 1.00, 'hi': 1.00},
    'working':   {'rgb': (255, 150, 20),  'motion': 'pulse',  'period': 1.6, 'lo': 0.30, 'hi': 1.00},
    'talking':   {'rgb': (30, 220, 90),   'motion': 'breath', 'period': 2.0, 'lo': 0.55, 'hi': 1.00},
    'knock':     {'rgb': (255, 255, 255), 'motion': 'blink',  'period': 0.0, 'lo': 1.00, 'hi': 1.00},
    'alert':     {'rgb': (255, 30, 20),   'motion': 'pulse',  'period': 2.4, 'lo': 0.25, 'hi': 0.90},
    'happy':     {'rgb': (60, 255, 120),  'motion': 'pulse',  'period': 0.8, 'lo': 0.50, 'hi': 1.00},
    'sleeping':  {'rgb': (50, 0, 64),     'motion': 'breath', 'period': 8.0, 'lo': 0.10, 'hi': 0.40},
    'asleep':    {'rgb': (0, 0, 0),       'motion': 'off',    'period': 0.0, 'lo': 0.0,  'hi': 0.0},
}

_state = 'idle'
_prev = 'idle'
_t0 = time.monotonic()
_revert_at = 0.0
_override = None            # (r, g, b) from `EYE r g b`, held steady
_blink_left = 0
_blink_next = 0.0


def _apply(rgb, scale):
    s = MAX_BRIGHTNESS * max(0.0, min(1.0, scale))
    pixels.fill((int(rgb[0] * s), int(rgb[1] * s), int(rgb[2] * s)))


def current():
    return _state


def set_state(name, remember=True):
    global _state, _prev, _t0, _override, _blink_left, _blink_next, _revert_at
    name = (name or '').strip().lower()
    if name not in STATES:
        return False
    # Don't remember a blink as the state to come back to.
    if remember and _state in STATES and _state != 'knock':
        _prev = _state
    _state = name
    _t0 = time.monotonic()
    _revert_at = 0.0
    _override = None
    if STATES[name]['motion'] == 'blink':
        _blink_left = 3
        _blink_next = time.monotonic()
    return True


def set_state_timed(name, secs):
    """Show a state for `secs`, then fall back to whatever came before."""
    global _revert_at
    if set_state(name):
        _revert_at = time.monotonic() + secs
        return True
    return False


def set_rgb(r, g, b):
    """Raw color held steady. For tests and one-offs."""
    global _override
    _override = (max(0, min(255, int(r))), max(0, min(255, int(g))), max(0, min(255, int(b))))
    _apply(_override, 1.0)


def clear_rgb():
    global _override
    _override = None


def set_brightness(pct):
    global MAX_BRIGHTNESS
    MAX_BRIGHTNESS = max(0.02, min(1.0, float(pct) / 100.0))


def tick():
    global _state, _t0, _revert_at, _blink_left, _blink_next
    now = time.monotonic()

    if _override is not None:
        _apply(_override, 1.0)
        return

    if _revert_at and now >= _revert_at:
        _revert_at = 0.0
        set_state(_prev, remember=False)

    st = STATES.get(_state, STATES['idle'])
    m = st['motion']

    if m == 'off':
        pixels.fill((0, 0, 0))
        return
    if m == 'steady':
        _apply(st['rgb'], st['hi'])
        return
    if m == 'blink':
        if _blink_left <= 0:
            set_state(_prev, remember=False)
            return
        if now >= _blink_next:
            on = (_blink_left % 2) == 1
            _apply(st['rgb'], 1.0 if on else 0.0)
            _blink_left -= 1
            _blink_next = now + 0.12
        return

    # breath / pulse share the math; pulse squares it to make it sharper.
    ph = (now - _t0) / max(0.01, st['period'])
    w = 0.5 - 0.5 * math.cos(2 * math.pi * ph)
    if m == 'pulse':
        w = w * w
    _apply(st['rgb'], st['lo'] + (st['hi'] - st['lo']) * w)