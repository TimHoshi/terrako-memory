#!/bin/bash
echo "Rebooting Terrako..."

# Stop terrako_core.py if running
pkill -f terrako_core.py 2>/dev/null
sleep 1

# Send sleep to Pico
python3 -c "
import serial, time
try:
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    ser.write(b'SLEEP\n')
    time.sleep(2)
    ser.close()
    print('Pico sleeping')
except:
    print('Pico not available')
"

# Sync memory to GitHub
cd /root/terrako-memory
git add .
git commit -m "Reboot $(date '+%Y-%m-%d %H:%M')" 2>/dev/null
git push 2>/dev/null
echo "Memory synced"

echo "Rebooting Orange Pi..."
reboot
