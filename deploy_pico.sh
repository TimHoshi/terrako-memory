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

# --- clean stop of the listener (added by Akari, Oct 1 2026) ----------------
# The Guardian listener holds the Pico serial port, so flashing while it runs
# used to fail or fight it. Stop it the right way: ask its own /shutdown first
# (that sends RELEASE so the servos go slack, then closes the port), and fall
# back to pkill only if the door is unreachable. This is the handoff, so it is
# no longer a thing to remember.
if pgrep -f akari_listener_v0.py >/dev/null 2>&1; then
  echo "stopping akari-listener (it holds the Pico port)..."
  LISTEN_TOKEN="${AKARI_TOKEN:-}"
  LISTEN_PORT="${AKARI_PORT:-}"
  for f in /etc/akari-listener.env "$HOME/.akari_listener.env" "$SCRIPT_DIR/.akari_listener.env"; do
    [ -f "$f" ] || continue
    if [ -z "$LISTEN_TOKEN" ]; then
      LISTEN_TOKEN=$(sed -n 's/^[[:space:]]*AKARI_TOKEN[[:space:]]*=[[:space:]]*//p' "$f" | tr -d '"' | head -1)
    fi
    if [ -z "$LISTEN_PORT" ]; then
      LISTEN_PORT=$(sed -n 's/^[[:space:]]*AKARI_PORT[[:space:]]*=[[:space:]]*//p' "$f" | tr -d '"' | head -1)
    fi
  done
  STOPPED=0
  if [ -n "$LISTEN_TOKEN" ] && command -v curl >/dev/null 2>&1; then
    CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
      -H "Authorization: Bearer $LISTEN_TOKEN" \
      "http://127.0.0.1:${LISTEN_PORT:-8787}/shutdown" || true)
    [ "$CODE" = "200" ] && STOPPED=1 && echo "listener acknowledged clean stop"
  fi
  if [ "$STOPPED" = "0" ]; then
    echo "clean stop unavailable; falling back to pkill"
    pkill -f akari_listener_v0.py || true
  fi
  sleep 2
  if pgrep -f akari_listener_v0.py >/dev/null 2>&1; then
    echo "warning: akari-listener still running; the Pico port may be busy"
  fi
fi

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
echo "Reminder: start the listener again when you want the door live"