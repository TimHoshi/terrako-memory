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
# used to fail or fight it. Two ways it can be running now:
#   (a) as the systemd unit akari-listener.service (survives crashes + boots);
#   (b) hand-started from a terminal.
# Either way: stop it, flash, and (for (a)) start it again at the end, so the
# ring gets its HELLO back without anyone remembering to do it.
SERVICE=0
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files akari-listener.service >/dev/null 2>&1 \
   && systemctl cat akari-listener.service >/dev/null 2>&1; then
  SERVICE=1
  echo "stopping akari-listener.service (it holds the Pico port)..."
  systemctl stop akari-listener.service || true
  # make sure it is really gone before we take the port
  for i in $(seq 1 10); do
    pgrep -f akari_listener_v0.py >/dev/null 2>&1 || break
    sleep 1
  done
fi

if [ "$SERVICE" = "0" ] && pgrep -f akari_listener_v0.py >/dev/null 2>&1; then
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

# --- get the board to the REPL, and KEEP it there while we flash ------------
# Ctrl-C twice interrupts whatever code.py is doing (it loops waiting for a
# HELLO, so it never yields the REPL on its own).
# We deliberately do NOT send Ctrl-D here. Ctrl-D restarts code.py, and then
# the REPL never comes back to the flasher -- which is exactly why the first
# put (boot.py) used to just hang forever. Reload at the END instead.
python3 -c "
import serial, time
ser = serial.Serial('$PICO_PORT', 115200, timeout=1)
ser.write(b'\x03\x03')
time.sleep(1.0)
ser.close()
print('Pico interrupted, sitting at REPL')
"

sleep 1

echo "Deploying to Pico ($PICODIR)..."
if command -v mpremote >/dev/null 2>&1; then
  # mpremote is built for CircuitPython and handles the raw REPL far more
  # reliably than ampy. Preferred when present.
  for f in $FILES; do
    mpremote connect "$PICO_PORT" cp "$PICODIR/$f" ":$f" || { echo "failed: $f"; exit 1; }
  done
elif command -v ampy >/dev/null 2>&1; then
  for f in $FILES; do
    # timeout so a wedged REPL fails loudly instead of hanging forever
    timeout 60 ampy --port "$PICO_PORT" put "$PICODIR/$f" "/$f" \
      || { echo "failed: $f (ampy hung or errored)"; exit 1; }
  done
else
  echo "no flasher found: pip3 install --user mpremote  (preferred), or ampy"
  exit 1
fi

echo "Pico updated successfully!"

# One soft reload so boot.py + code.py run and the board reaches 'waiting for HELLO'.
python3 -c "
import serial, time
ser = serial.Serial('$PICO_PORT', 115200, timeout=1)
ser.write(b'\x04')
time.sleep(0.5)
ser.close()
print('Pico soft-reloaded into the new firmware')
"
if [ "$SERVICE" = "1" ]; then
  echo "starting akari-listener.service again (it will HELLO the fresh Pico)..."
  systemctl start akari-listener.service || true
else
  echo "Reminder: start the listener again when you want the door live"
fi