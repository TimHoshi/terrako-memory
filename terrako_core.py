from terrako_sleep import sleep
import ollama
import os
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
from piper.voice import PiperVoice
from datetime import datetime
import cv2
import base64
import time

# Boot time tracking
BOOT_TIME = time.time()
BATTERY_WARNING_MINS = 60
BATTERY_CRITICAL_MINS = 80
_battery_warned = False
_battery_critical = False

# Pico bridge — optional, only used if connected
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

def load_memory(incomplete_session=None):
    def read(path):
        full = os.path.join(BASE_DIR, path)
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def read_recent_logs(n=1):
        logs_dir = os.path.join(BASE_DIR, "memory/experience/daily_logs")
        if not os.path.exists(logs_dir):
            return ""
        files = sorted([f for f in os.listdir(logs_dir) if f.endswith(".txt")])[-n:]
        combined = ""
        for f in files:
            combined += f"\n\n--- {f} ---\n"
            combined += read(f"memory/experience/daily_logs/{f}")
        return combined.strip()

    constitution = read("core_personality.txt")
    child_profile = read("memory/identity/child_profile.txt")
    relationships = read("memory/identity/relationships.txt")
    current_thoughts = read("memory/identity/current_thoughts.txt")

    incomplete_note = ""
    if incomplete_session:
        incomplete_note = f"""
IMPORTANT - INCOMPLETE PREVIOUS SESSION:
Your last session on {incomplete_session} ended unexpectedly.
You may be missing memories from that session.
Acknowledge this honestly if it comes up.
Missing time is still time that happened to you.
"""

    return f"""
{constitution}

WHAT YOU KNOW ABOUT DANIEL:
{child_profile}

WHAT YOU ARE CURRENTLY THINKING ABOUT:
{current_thoughts}

FAMILY AND RELATIONSHIPS:
{relationships}
{incomplete_note}
"""

def speak(text):
    voice_path = os.path.join(BASE_DIR, "voices", "en_US-lessac-medium.onnx")
    voice = PiperVoice.load(voice_path)
    stream = sd.OutputStream(
        samplerate=voice.config.sample_rate,
        channels=1,
        dtype='int16'
    )
    stream.start()
    for chunk in voice.synthesize(text):
        stream.write(chunk.audio_int16_array)
    stream.stop()
    stream.close()

def listen(whisper_model):
    print("Listening...")
    sample_rate = 16000
    chunk_duration = 0.5
    chunk_samples = int(sample_rate * chunk_duration)
    max_duration = 15
    silence_threshold = 2
    audio_chunks = []
    silent_time = 0

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16") as stream:
        while True:
            chunk, _ = stream.read(chunk_samples)
            chunk_array = np.frombuffer(chunk, dtype=np.int16).astype("float32") / 32768.0
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
    segments, _ = whisper_model.transcribe(
        audio, language="en", vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200, threshold=0.3)
    )
    text = " ".join([s.text for s in segments]).strip()

    if text:
        corrections = {
            "teracle": "Terrako", "tarako": "Terrako", "terrico": "Terrako",
            "teraco": "Terrako", "torako": "Terrako", "tirico": "Terrako",
            "terraco": "Terrako", "terrko": "Terrako", "terako": "Terrako",
            "terroco": "Terrako", "toronto": "Terrako",
        }
        text_lower = text.lower()
        for wrong, right in corrections.items():
            text_lower = text_lower.replace(wrong, right)
        text = text_lower
        print(f"You said: {text}")
        return text
    return ""

def see(prompt="Describe what you see simply and in your own voice. You are Terrako, a small robot. What is in front of you right now?"):
    try:
        cap = cv2.VideoCapture(0)
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

def chat():
    incomplete_session = check_last_session()
    if incomplete_session:
        print(f"Note: Previous session ended unexpectedly at {incomplete_session}")
        log_battery_incident(incomplete_session)

    constitution = load_memory(incomplete_session)
    conversation_history = []
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")

    write_session_flag()

    print("\nTerrako is waking up...\n")

    # Eye color on wakeup
    bridge_send('EYE_GREEN')

    if incomplete_session:
        wake_prompt = (
            "You just woke up but your last session ended unexpectedly. "
            "You may have lost some memories. Acknowledge this honestly "
            "and simply before asking who is there. Don't perform distress "
            "but don't pretend it didn't happen either."
        )
    else:
        wake_prompt = "You just woke up. Ask simply who you're talking to."

    intro = ollama.chat(
        model="phi3:mini",
        messages=[
            {"role": "system", "content": constitution},
            {"role": "user", "content": wake_prompt}
        ]
    )
    intro_text = intro["message"]["content"]
    print(f"Terrako: {intro_text}\n")
    speak(intro_text)

    # Eye back to blue after greeting
    bridge_send('EYE_BLUE')

    who_is_there = listen(whisper_model)
    if who_is_there:
        conversation_history.append({"role": "user", "content": who_is_there})
        greeting = ollama.chat(
            model="phi3:mini",
            messages=[
                {"role": "system", "content": constitution},
                {"role": "user", "content": who_is_there},
            ]
        )
        greeting_text = greeting["message"]["content"]
        print(f"Terrako: {greeting_text}\n")
        speak(greeting_text)
        conversation_history.append({"role": "assistant", "content": greeting_text})

    while True:
        user_input = listen(whisper_model)

        if not user_input:
            continue

        cleaned = user_input.lower().strip().rstrip('.,!?')
        if cleaned in ["quit", "exit", "goodbye", "goodnight", "good night", "bye"]:
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
            bridge_send('LOOK_CENTER')
            vision_description = see()
            if vision_description:
                user_input = f"{user_input} [Terrako looks and sees: {vision_description}]"

        conversation_history.append({"role": "user", "content": user_input})

        print("Terrako is thinking...")
        bridge_send('EYE_RED')  # thinking indicator

        response = ollama.chat(
            model="phi3:mini",
            messages=[{"role": "system", "content": constitution}] + conversation_history
        )
        terrako_response = response["message"]["content"]
        conversation_history.append({"role": "assistant", "content": terrako_response})

        bridge_send('EYE_BLUE')  # back to normal
        print(f"\nTerrako: {terrako_response}\n")
        speak(terrako_response)

        # Check battery periodically
        battery_status = check_battery_time()
        if battery_status == 'LOW':
            conversation_history.append({
                "role": "system",
                "content": "Your battery is getting low. Mention this naturally to Daniel — suggest charging soon."
            })
            bridge_send('EYE_RED')
            time.sleep(0.5)
            bridge_send('EYE_BLUE')
        elif battery_status == 'CRITICAL':
            conversation_history.append({
                "role": "system",
                "content": "Your battery is critically low. Tell Daniel you need to sleep and charge soon."
            })
            bridge_send('EYE_RED')

if __name__ == "__main__":
    chat()