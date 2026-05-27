#!/bin/bash
echo "Starting Terrako..."

# Start Ollama if not running
if ! pgrep ollama > /dev/null; then
    ollama serve &
    sleep 5
    echo "Ollama started"
fi

# Remove stale session flag
rm -f /root/terrako-memory/memory/state/session_active.txt

# Start Terrako
cd /root/terrako-memory
python3 terrako_core.py
