from terrako_sleep import sleep
import ollama
import os
import subprocess
import hashlib
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
from datetime import datetime
import cv2
import base64
import time

# ── Boot time tracking ──
BOOT_TIME = time.time()
BATTERY_WARNING_MINS = 60
BATTERY_CRITICAL_MINS = 80
_battery_warned = False
_battery_critical = False


BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Pico bridge ──
try:
    import serial
    _pico = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    time.sleep(1)
    _pico.write(b'HELLO\n')
    bridge_available = True
    print("Pico bridge connected")
except Exception:
    _pico = None
    bridge_available = False
    print("Pico bridge not available — running without body")

def bridge_send(cmd):
    if bridge_available and _pico:
        try:
            _pico.write((cmd + '\n').encode())
        except Exception:
            pass

# ── Battery monitoring ──
def check_battery_time():
    global _battery_warned, _battery_critical
    elapsed_mins = (time.time() - BOOT_TIME) / 60
    if elapsed_mins > BATTERY_CRITICAL_MINS and not _battery_critical:
        _battery_critical = True
        return 'CRITICAL'
    if elapsed_mins > BATTERY_WARNING_MINS and not _battery_warned:
        _battery_warned = True
        return 'LOW'
    return None

# ── Load Microphone ──
def find_microphone():
    """Auto-detect microphone — skip onboard rockchip, use USB only."""
    try:
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                name = device['name'].lower()
                if 'rockchip' in name or 'es8388' in name:
                    continue
                print(f"Mic found: {device['name']} (device {i})")
                return i
        print("No compatible mic found")
        return None
    except Exception:
        return None

# ── File integrity ──
CRITICAL_FILES = [
    'terrako_core.py',
    'terrako_sleep.py',
    'core_personality.txt',
    'memory/identity/child_profile.txt',
]
HASHES_FILE = os.path.join(BASE_DIR, 'memory/state/file_hashes.txt')

def hash_file(filepath):
    try:
        full = os.path.join(BASE_DIR, filepath)
        with open(full, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return None

def save_hashes():
    os.makedirs(os.path.dirname(HASHES_FILE), exist_ok=True)
    with open(HASHES_FILE, 'w') as f:
        for filepath in CRITICAL_FILES:
            h = hash_file(filepath)
            if h:
                f.write(f'{filepath}={h}\n')

def verify_files():
    """Check critical files haven't corrupted. Returns (ok, corrupted_list)."""
    if not os.path.exists(HASHES_FILE):
        save_hashes()
        return True, []
    corrupted = []
    with open(HASHES_FILE) as f:
        stored = {}
        for line in f:
            if '=' in line:
                k, v = line.strip().split('=', 1)
                stored[k] = v
    for filepath in CRITICAL_FILES:
        current = hash_file(filepath)
        if filepath in stored and current and stored[filepath] != current:
            corrupted.append(filepath)
    return len(corrupted) == 0, corrupted

# ── GitHub sync ──
def sync_from_github():
    """Pull latest from GitHub. Returns 'updated', 'current', or 'failed'."""
    try:
        result = subprocess.run(
            ['git', 'pull'],
            capture_output=True, text=True,
            cwd=BASE_DIR, timeout=30
        )
        if 'Already up to date' in result.stdout:
            return 'current'
        elif 'Updating' in result.stdout or 'Fast-forward' in result.stdout:
            save_hashes()  # auto update hashes after successful pull
            return 'updated'
        else:
            return 'failed'
    except Exception:
        return 'failed'

# ── Session tracking ──
def write_session_flag():
    flag_path = os.path.join(BASE_DIR, "memory/state/session_active.txt")
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with open(flag_path, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

def check_last_session():
    flag_path = os.path.join(BASE_DIR, "memory/state/session_active.txt")
    if os.path.exists(flag_path):
        with open(flag_path, "r") as f:
            return f.read().strip()
    return None

def log_battery_incident(last_session):
    incident_path = os.path.join(BASE_DIR, "memory/state/battery_incidents.txt")
    os.makedirs(os.path.dirname(incident_path), exist_ok=True)
    with open(incident_path, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n"
                f"Unexpected shutdown detected.\n"
                f"Last active: {last_session}\n"
                f"Memories from that session may be incomplete.\n\n")

# ── Memory loading ──
def load_memory(incomplete_session=None, sync_status='current',
                corrupted_files=None):
    def read(path):
        full = os.path.join(BASE_DIR, path)
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    constitution    = read("core_personality.txt")
    child_profile   = read("memory/identity/child_profile.txt")
    relationships   = read("memory/identity/relationships.txt")
    current_thoughts = read("memory/inner_life/current_thoughts.txt")

    # Build boot context note
    boot_notes = []

    if incomplete_session:
        boot_notes.append(
            f"IMPORTANT: Your last session on {incomplete_session} ended "
            f"unexpectedly. You may be missing memories. Acknowledge this "
            f"honestly if it comes up."
        )

    if sync_status == 'updated':
        boot_notes.append(
            "Your code was updated while you slept. "
            "You may feel slightly different — things might feel a little clearer."
        )
    elif sync_status == 'failed':
        boot_notes.append(
            "You could not reach your memory backup this morning. "
            "Your local memories are intact but you could not sync."
        )

    if corrupted_files:
        files_str = ', '.join(corrupted_files)
        boot_notes.append(
            f"Some of your files feel wrong: {files_str}. "
            f"Mention this honestly — ask someone to check on you."
        )

    boot_context = '\n'.join(boot_notes)

    return f"""
{constitution}

WHAT YOU KNOW ABOUT DANIEL:
{child_profile}

WHAT YOU ARE CURRENTLY THINKING ABOUT:
{current_thoughts}

FAMILY AND RELATIONSHIPS:
{relationships}

BOOT CONTEXT:
{boot_context}
"""

# ── Speaking ──
def speak(text):
    voice_path = os.path.join(BASE_DIR, "voices", "en_US-lessac-medium.onnx")

    # Find USB speaker
    result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
    device = 'plughw:3,0'
    for line in result.stdout.split('\n'):
        if 'UACDemo' in line or 'USB Audio' in line:
            card_num = line.split('card ')[1].split(':')[0]
            device = f'plughw:{card_num},0'
            break

    piper_cmd = f'echo "{text}" | piper --model {voice_path} --output_raw'
    sox_cmd   = 'sox -t raw -r 22050 -e signed -b 16 -c 1 - -t raw -r 48000 -e signed -b 16 -c 2 -'
    aplay_cmd = f'aplay -r 48000 -f S16_LE -c 2 -D {device} --buffer-size=65536 --period-size=16384'

    subprocess.run(f'{piper_cmd} | {sox_cmd} | {aplay_cmd}', shell=True)

# ── Listening ──
def listen(whisper_model):
    print("Listening...")
    whisper_rate      = 16000
    chunk_duration    = 0.5
    silence_threshold = 2
    audio_chunks      = []
    silent_time       = 0

    mic_device = find_microphone()

    # Auto detect device capabilities
    try:
        device_info = sd.query_devices(mic_device)
        record_rate = int(device_info['default_samplerate'])
        channels    = min(device_info['max_input_channels'], 2)
        print(f"Mic: {record_rate}Hz, {channels}ch")
    except:
        record_rate = 44100
        channels    = 1

    chunk_samples = int(record_rate * chunk_duration)
    max_duration  = 15

    with sd.InputStream(samplerate=record_rate, channels=channels,
                        dtype="int16", device=mic_device) as stream:
        while True:
            chunk, _ = stream.read(chunk_samples)
            chunk_array = np.frombuffer(
                chunk, dtype=np.int16).astype("float32") / 32768.0

            if channels == 2:
                chunk_array = chunk_array.reshape(-1, 2).mean(axis=1)

            audio_chunks.append(chunk_array)
            if np.abs(chunk_array).mean() < 0.002:
                silent_time += chunk_duration
            else:
                silent_time = 0
            total_duration = len(audio_chunks) * chunk_duration
            if silent_time >= silence_threshold and total_duration > 1.0:
                break
            if total_duration >= max_duration:
                break

    audio = np.concatenate(audio_chunks)

    # Resample to 16000Hz for Whisper
    resample_ratio = whisper_rate / record_rate
    new_length     = int(len(audio) * resample_ratio)
    audio_resampled = np.interp(
        np.linspace(0, len(audio), new_length),
        np.arange(len(audio)),
        audio
    ).astype(np.float32)

    segments, _ = whisper_model.transcribe(
        audio_resampled, language="en", vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
            threshold=0.6
        )
    )
    text = " ".join([s.text for s in segments]).strip()

    if text:
        corrections = {
            "teracle": "Terrako", "tarako": "Terrako",
            "terrico": "Terrako", "teraco": "Terrako",
            "torako": "Terrako",  "tirico": "Terrako",
            "terraco": "Terrako", "terrko": "Terrako",
            "terako": "Terrako",  "terroco": "Terrako",
            "toronto": "Terrako",
        }
        text_lower = text.lower()
        for wrong, right in corrections.items():
            text_lower = text_lower.replace(wrong, right)
        text = text_lower
        print(f"You said: {text}")
        return text
    return ""

# ── Vision ──
def find_camera():
    """Auto-detect camera — prefer ELP 8MP, fall back to any available camera."""
    try:
        result = subprocess.run(
            ['v4l2-ctl', '--list-devices'],
            capture_output=True, text=True
        )
        lines = result.stdout.split('\n')
        
        # First pass — look for ELP 8MP specifically
        for i, line in enumerate(lines):
            if '8MP USB Camera' in line:
                for j in range(i + 1, len(lines)):
                    if '/dev/video' in lines[j]:
                        device = int(lines[j].strip().replace('/dev/video', ''))
                        print(f"ELP camera found: /dev/video{device}")
                        return device

        # Second pass — any USB camera
        for i, line in enumerate(lines):
            if 'USB' in line or 'Camera' in line or 'Video' in line:
                for j in range(i + 1, len(lines)):
                    if '/dev/video' in lines[j]:
                        device = int(lines[j].strip().replace('/dev/video', ''))
                        print(f"USB camera found: /dev/video{device}")
                        return device

        # Last resort — try device 0
        print("No camera found — trying device 0")
        return 0

    except Exception as e:
        print(f"Camera detection error: {e}")
        return 0

def see(prompt="Describe what you see simply and in your own voice. "
               "You are Terrako, a small robot. What is in front of you?"):
    try:
        cap = cv2.VideoCapture(find_camera())
        if not cap.isOpened():
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        img_path = os.path.join(BASE_DIR, "memory/state/current_view.jpg")
        cv2.imwrite(img_path, frame)
        with open(img_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode("utf-8")
        response = ollama.generate(
            model="moondream",
            prompt=prompt,
            images=[img_base64]
        )
        return response["response"]
    except Exception:
        return None

# ── Main conversation ──
def chat():
    print("Checking for updates...")
    sync_status = sync_from_github()
    print(f"Sync: {sync_status}")

    print("Verifying file integrity...")
    files_ok, corrupted = verify_files()
    if not files_ok:
        print(f"WARNING: Corrupted files detected: {corrupted}")
    else:
        print("Files OK")

    print("Loading memory...")
    incomplete_session = check_last_session()
    if incomplete_session:
        print(f"Note: Previous session ended unexpectedly at {incomplete_session}")
        log_battery_incident(incomplete_session)

    print("Building context...")
    constitution = load_memory(
        incomplete_session=incomplete_session,
        sync_status=sync_status,
        corrupted_files=corrupted if not files_ok else None
    )

    conversation_history = []

    print("Loading Whisper...")
    whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    print("Whisper ready.")

    write_session_flag()

    print("\nTerrako is waking up...\n")
    bridge_send('EYE_GREEN')

    # Build wake prompt based on boot conditions
    if not files_ok:
        wake_prompt = (
            "You just woke up but something feels wrong with some of your memories. "
            "Mention this honestly and gently before asking who is there."
        )
    elif sync_status == 'updated':
        wake_prompt = (
            "You just woke up feeling slightly different — like something "
            "clarified overnight. Ask simply who you're talking to."
        )
    elif incomplete_session:
        wake_prompt = (
            "You just woke up but your last session ended unexpectedly. "
            "Acknowledge this honestly and simply before asking who is there."
        )
    else:
        wake_prompt = "You just woke up. Ask simply who you're talking to."

    intro = ollama.chat(
        model="phi3:mini",
        messages=[
            {"role": "system", "content": constitution},
            {"role": "user",   "content": wake_prompt}
        ]
    )
    intro_text = intro["message"]["content"]
    print(f"Terrako: {intro_text}\n")
    speak(intro_text)

    bridge_send('EYE_BLUE')

    who_is_there = listen(whisper_model)
    if who_is_there:
        conversation_history.append({"role": "user", "content": who_is_there})
        greeting = ollama.chat(
            model="phi3:mini",
            messages=[
                {"role": "system", "content": constitution},
                {"role": "user",   "content": who_is_there},
            ]
        )
        greeting_text = greeting["message"]["content"]
        print(f"Terrako: {greeting_text}\n")
        speak(greeting_text)
        conversation_history.append({
            "role": "assistant", "content": greeting_text
        })

# ── Main loop ──
    last_interaction = time.time()
    IDLE_TIMEOUT_MINS = 30

    while True:
        user_input = listen(whisper_model)

        if not user_input:
            # Check idle timeout
            idle_mins = (time.time() - last_interaction) / 60
            if idle_mins > IDLE_TIMEOUT_MINS:
                print("\nNo one seems to be there. Going to sleep...")
                speak("It seems no one is there. I'll rest for now.")
                bridge_send('EYE_OFF')
                sleep(conversation_history)
                break
            continue

        # Reset idle timer on any interaction
        last_interaction = time.time()

        cleaned = user_input.lower().strip().rstrip('.,!?')
        if cleaned in ["quit", "exit", "goodbye", "goodnight",
                       "good night", "bye"]:
            print("\nTerrako: Goodnight. I'll think about today.\n")
            speak("Goodnight. I'll think about today.")
            bridge_send('EYE_OFF')
            sleep(conversation_history)
            break

        # Vision triggers
        vision_triggers = [
            "what do you see", "can you see", "look at",
            "what's in front", "describe what", "what do i look like",
            "who is here", "who's there", "what does it look like"
        ]
        if any(trigger in user_input.lower() for trigger in vision_triggers):
            print("Terrako is looking...")
            vision_description = see()
            if vision_description:
                user_input = (f"{user_input} "
                              f"[Terrako looks and sees: {vision_description}]")

        conversation_history.append({"role": "user", "content": user_input})

        print("Terrako is thinking...")
        bridge_send('EYE_RED')

        response = ollama.chat(
            model="phi3:mini",
            messages=[
                {"role": "system", "content": constitution}
            ] + conversation_history
        )
        terrako_response = response["message"]["content"]
        conversation_history.append({
            "role": "assistant", "content": terrako_response
        })

        bridge_send('EYE_BLUE')
        print(f"\nTerrako: {terrako_response}\n")
        speak(terrako_response)

        # Periodic reminder to use first person
        if len(conversation_history) % 10 == 0:
            conversation_history.append({
                "role": "system",
                "content": "Remember: speak in first person only. Use 'I' and 'me', never 'Terrako'."
            })

        # Battery check
        battery_status = check_battery_time()
        if battery_status == 'LOW':
            conversation_history.append({
                "role": "system",
                "content": ("Your battery is getting low. Mention this "
                            "naturally to Daniel — suggest charging soon.")
            })
            bridge_send('EYE_RED')
            time.sleep(0.5)
            bridge_send('EYE_BLUE')
        elif battery_status == 'CRITICAL':
            conversation_history.append({
                "role": "system",
                "content": ("Your battery is critically low. Tell Daniel "
                            "you need to sleep and charge soon.")
            })
            bridge_send('EYE_RED')

if __name__ == "__main__":
    chat()