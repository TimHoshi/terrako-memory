#!/bin/bash
echo "Deploying to Pico..."

# Auto-detect Pico port
PICO_PORT=""
for port in /dev/ttyACM0 /dev/ttyACM1 /dev/ttyACM2; do
    if [ -e "$port" ]; then
        PICO_PORT=$port
        echo "Pico found on $PICO_PORT"
        break
    fi
done

if [ -z "$PICO_PORT" ]; then
    echo "Pico not found! Is it connected?"
    exit 1
fi

# Stop CircuitPython
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

# Copy files using ampy
echo "Copying files..."
ampy --port $PICO_PORT put /root/terrako-memory/pico/boot.py /boot.py
ampy --port $PICO_PORT put /root/terrako-memory/pico/code.py /code.py
ampy --port $PICO_PORT put /root/terrako-memory/pico/leds.py /leds.py
ampy --port $PICO_PORT put /root/terrako-memory/pico/movement.py /movement.py

echo "Pico updated successfully!"
echo "Pico will auto-reload"
