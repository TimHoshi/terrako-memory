cat > /root/terrako-memory/deploy_pico.sh << 'EOF'
#!/bin/bash
echo "Deploying to Pico via ampy..."

# Stop CircuitPython
python3 -c "
import serial, time
ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
ser.write(b'\x03\x03')
time.sleep(2)
ser.close()
"

sleep 1

# Copy files using ampy
ampy --port /dev/ttyACM0 put /root/terrako-memory/pico/code.py /code.py
ampy --port /dev/ttyACM0 put /root/terrako-memory/pico/leds.py /leds.py
ampy --port /dev/ttyACM0 put /root/terrako-memory/pico/movement.py /movement.py
ampy --port /dev/ttyACM0 put /root/terrako-memory/pico/boot.py /boot.py

echo "Pico updated successfully!"
echo "Pico will auto-reload"
EOF

chmod +x /root/terrako-memory/deploy_pico.sh