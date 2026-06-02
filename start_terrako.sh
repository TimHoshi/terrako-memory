cat > /root/terrako-memory/start_terrako.sh << 'EOF'
#!/bin/bash
echo "Starting Terrako..."

# Kill any existing Ollama instances
pkill ollama 2>/dev/null
sleep 2

# Start Ollama fresh
ollama serve &
sleep 8

# Verify Ollama is running
if ! pgrep ollama > /dev/null; then
    echo "Ollama failed to start!"
    exit 1
fi
echo "Ollama running"

# Remove stale session flag
rm -f /root/terrako-memory/memory/state/session_active.txt

# In start_terrako.sh add after ollama serve
if ! ollama list | grep -q "phi3:mini"; then
    echo "Downloading phi3:mini..."
    ollama pull phi3:mini
fi

# Start Terrako
cd /root/terrako-memory
python3 terrako_core.py
EOF

chmod +x /root/terrako-memory/start_terrako.sh