#!/bin/bash
echo "Setting up Terrako..."

# Timezone
timedatectl set-timezone America/New_York
timedatectl set-ntp true
echo "Timezone set"

# Swap file 6GB
fallocate -l 6G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo "Swap configured"

# Ollama environment
echo 'export OLLAMA_MAX_LOADED_MODELS=1' >> /root/.bashrc
echo 'export OLLAMA_NUM_PARALLEL=1' >> /root/.bashrc
echo 'export OLLAMA_NUM_THREADS=4' >> /root/.bashrc
echo 'export OLLAMA_NUM_CTX=1024' >> /root/.bashrc
source /root/.bashrc
echo "Ollama environment set"

# System packages
apt update && apt install -y \
    git \
    python3-pip \
    python3-serial \
    sox \
    alsa-utils \
    v4l-utils \
    libportaudio2 \
    portaudio19-dev \
    ffmpeg \
    curl \
    wget \
    htop \
    nano \
    zstd
echo "System packages installed"

# Python packages
pip3 install \
    ollama \
    faster-whisper \
    sounddevice \
    numpy \
    opencv-python \
    pyserial \
    soundfile \
    adafruit-ampy \
    --break-system-packages
echo "Python packages installed"

# Install Ollama
curl -fsSL https://ollama.ai/install.sh | sh
echo "Ollama installed"

# Start Ollama and pull models
systemctl enable ollama
systemctl start ollama
sleep 5
ollama pull phi3:mini
echo "phi3:mini downloaded"

# SSH key for GitHub
ssh-keygen -t ed25519 -C "terrako-orangepi" -f ~/.ssh/id_ed25519 -N ""
echo "SSH key generated"
echo ""
echo "╔════════════════════════════════════════╗"
echo "║  Add this key to GitHub before next step ║"
echo "╚════════════════════════════════════════╝"
cat ~/.ssh/id_ed25519.pub
echo ""
read -p "Press Enter after adding key to GitHub..."

# Configure git
git config --global user.email "evalink6@hotmail.com"
git config --global user.name "TimHoshi"

# Clone Terrako
cd /root
git clone git@github.com:TimHoshi/terrako-memory.git
echo "Terrako cloned from GitHub"

# Download voice model (too large for GitHub)
mkdir -p /root/terrako-memory/voices
wget -O /root/terrako-memory/voices/en_US-lessac-medium.onnx \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
wget -O /root/terrako-memory/voices/en_US-lessac-medium.onnx.json \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json
echo "Voice model downloaded"

# Set up Pico mount point
mkdir -p /mnt/pico
echo "Pico mount point created"

# Audio volume
amixer -c 4 cset numid=3 70% 2>/dev/null || true
alsactl store 2>/dev/null || true
echo "Audio configured"

# Make scripts executable
chmod +x /root/terrako-memory/*.sh
echo "Scripts made executable"

# Update file hashes
python3 /root/terrako-memory/update_hashes.py
echo "Hashes updated"

chmod +x /root/terrako-memory/*.sh

echo ""
echo "╔════════════════════════════════════════╗"
echo "║         Setup complete!                ║"
echo "║  Run: cd /root/terrako-memory          ║"
echo "║  Then: ./deploy_pico.sh                ║"
echo "║  Then: ./start_terrako.sh              ║"
echo "╚════════════════════════════════════════╝"