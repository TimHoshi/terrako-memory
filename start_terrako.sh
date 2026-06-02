cat > /root/terrako-memory/start_terrako.sh << 'EOF'
#!/bin/bash
echo "Starting Terrako..."

# Reset Pico first
echo "Resetting Pico..."
python3 -c "
import serial, time
try:
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    ser.write(b'\x03\x03')
    time.sleep(0.5)
    ser.write(b'\x04')
    time.sleep(3)
    ser.close()
    print('Pico reset')
except Exception as e:
    print(f'Pico reset failed: {e}')
"

sleep 2

# Start Ollama via systemd
systemctl start ollama
sleep 8

# Verify Ollama is running
if ! systemctl is-active --quiet ollama; then
    echo "Ollama failed to start!"
    exit 1
fi
echo "Ollama running"

# Remove stale session flag
rm -f /root/terrako-memory/memory/state/session_active.txt

# Start Terrako
cd /root/terrako-memory
python3 terrako_core.py
EOF

chmod +x /root/terrako-memory/start_terrako.sh