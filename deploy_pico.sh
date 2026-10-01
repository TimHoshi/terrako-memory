#!/bin/bash
# deploy_pico.sh - push the full Pico firmware to the board.
# Rewritten by Akari, Oct 1 2026: self-locating, and it now ships the whole
# set (boot, code, leds, presence, movement) from THIS repo's ./pico.
# The old version hard-coded /root/terrako-memory/pico and silently skipped
# presence.py, so the ring engine never made it onto the card.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PICODIR="$SCRIPT_DIR/pico"

if [ ! -d "$PICODIR" ]; then
  echo "no pico dir next to me ($PICODIR)"; exit 1
fi

# Auto-detect Pico port
PICO_PORT=""
for port in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2; do
  if [ -e "$port" ]; then PICO_PORT=$port; echo "Pico found on $PICO_PORT"; break; fi
done
if [ -z "$PICO_PORT" ]; then echo "Pico not found! Is it connected?"; exit 1; fi

# Every file the shell needs. Keep this list in sync if a new module lands.
FILES="boot.py code.py leds.py presence.py movement.py"
for f in $FILES; do
  if [ ! -f "$PICODIR/$f" ]; then echo "missing $PICODIR/$f"; exit 1; fi
done

# Stop CircuitPython so ampy can write
python3 -c "
import serial, time
ser = serial.Serial('$PICO_PORT', 115200, timeout=1)
ser.write(b'\x03\x03')
time.sleep(0.5)
ser.write(b'\x04')
time.sleep(3)
ser.close()
print('Pico rebooted')
"

sleep 2

echo "Deploying to Pico ($PICODIR)..."
for f in $FILES; do
  ampy --port "$PICO_PORT" put "$PICODIR/$f" "/$f" || { echo "failed: $f"; exit 1; }
done

echo "Pico updated successfully!"
echo "Pico will auto-reload"