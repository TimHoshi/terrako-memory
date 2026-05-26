#!/bin/bash
echo "Deploying to Pico..."
mount /dev/sda1 /mnt/pico
cp /root/terrako-memory/pico/code.py /mnt/pico/code.py
cp /root/terrako-memory/pico/leds.py /mnt/pico/leds.py
cp /root/terrako-memory/pico/movement.py /mnt/pico/movement.py
umount /mnt/pico
echo "Pico updated successfully!"