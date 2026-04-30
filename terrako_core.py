from terrako_sleep import sleep, read_weekly_summaries
import ollama
import os
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
from piper.voice import PiperVoice
from datetime import datetime
import cv2
import base64

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Session flag functions
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

# load_memory() loads constitution plus all memory files
def load_memory(incomplete_session=None):
    base = BASE_DIR

    def read(path):
        full = os.path.join(base, path)
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""

    def read_recent_logs(n=1):
        logs_dir = os.path.join(base, "memory/experience/daily_logs")
        if not os.path.exists(logs_dir):
            return ""
        files = sorted([
            f for f in os.listdir(logs_dir)
            if f.endswith(".txt")
        ])[-n:]
        combined = ""
        for f in files:
            combined += f"\n\n--- {f} ---\n"
            combined += read(f"memory/experience/daily_logs/{f}")
        return combined.strip()

    def read_last_thoughts():
        path = os.path.join(base, "memory/inner_life/current_thoughts.txt")
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content[-500:] if len(content) > 500 else content

    def read_last_emotional_development():
        path = os.path.join(base, "memory/inner_life/emotional_development.txt")
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return content[-500:] if len(content) > 500 else content

    constitution = read("core_personality.txt")
    child_profile = read("memory/identity/child_profile.txt")
    relationships = read("memory/identity/relationships.txt")
    current_thoughts = read_last_thoughts()
    significant_moments = read("memory/inner_life/significant_moments.txt")
    emotional_development = read_last_emotional_development()
    recent_logs = read_recent_logs(1)

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

FAMILY AND RELATIONSHIPS:
{relationships}

YOUR RECENT MEMORIES (last conversation):
{recent_logs}

WHAT YOU ARE CURRENTLY THINKING ABOUT:
{current_thoughts}

MOMENTS YOU NEVER WANT TO FORGET:
{significant_moments}

YOUR EMOTIONAL DEVELOPMENT:
{emotional_development}
{incomplete_note}
"""

# Terrako speaks out loud through Piper
def speak(text):
    voice_path = os.path.join(BASE_DIR,
        "voices", "en_US-lessac-medium.onnx")
    voice = PiperVoice.load(voice_path)
    stream = sd.OutputStream(
        samplerate=voice.config.sample_rate,
        channels=1,
        dtype='int16'
    )
    stream.start()
    for chunk in voice.synthesize(text):
        audio = chunk.audio_int16_array
        stream.write(audio)
    stream.stop()
    stream.close()

# Terrako listens through mic via Whisper
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
        audio,
        language="en",
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
            threshold=0.3
        )
    )

    text = " ".join([s.text for s in segments]).strip()

    if text:
        corrections = {
            "teracle": "Terrako",
            "tarako": "Terrako",
            "terrico": "Terrako",
            "teraco": "Terrako",
            "torako": "Terrako",
            "tirico": "Terrako",
            "terraco": "Terrako",
            "terrko": "Terrako",
            "terako": "Terrako",
            "terroco": "Terrako",
        }
        text_lower = text.lower()
        for wrong, right in corrections.items():
            text_lower = text_lower.replace(wrong, right)
        text = text_lower
        print(f"You said: {text}")
        return text
    return ""

# Terrako sees with moondream
def see(prompt="Describe what you see simply and in your own voice. You are Terrako, a small robot. What is in front of you right now?"):
    try:
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            return "I can't open my eyes right now."

        ret, frame = cap.read()
        cap.release()

        if not ret:
            return "I couldn't see anything."

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

    except Exception as e:
        return f"I tried to look but something went wrong: {e}"

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
        model="llama3.1:8b",
        messages=[
            {"role": "system", "content": constitution},
            {"role": "user", "content": wake_prompt}
        ]
    )
    intro_text = intro["message"]["content"]
    print(f"Terrako: {intro_text}\n")
    speak(intro_text)

    who_is_there = listen(whisper_model)
    if who_is_there:
        conversation_history.append({
            "role": "user",
            "content": who_is_there
        })

        greeting = ollama.chat(
            model="llama3.1:8b",
            messages=[
                {"role": "system", "content": constitution},
                {"role": "user", "content": who_is_there},
                {"role": "assistant", "content": ""},
            ]
        )
        greeting_text = greeting["message"]["content"]
        print(f"Terrako: {greeting_text}\n")
        speak(greeting_text)
        conversation_history.append({
            "role": "assistant",
            "content": greeting_text
        })

    while True:
        user_input = listen(whisper_model)

        if not user_input:
            continue

        cleaned = user_input.lower().strip().rstrip('.,!?')
        if cleaned in ["quit", "exit", "goodbye", "goodnight", "good night", "bye"]:
            print("\nTerrako: Goodnight. I'll think about today.\n")
            speak("Goodnight. I'll think about today.")
            sleep(conversation_history)
            global camera_running
            break

        vision_triggers = [
            "what do you see", "can you see", "look at",
            "what's in front", "describe what", "what do i look like",
            "who is here", "who's there", "what does it look like"
        ]

        if any(trigger in user_input.lower() for trigger in vision_triggers):
            print("Terrako is looking...")
            vision_description = see()
            if vision_description:
                user_input = f"{user_input} [Terrako looks and sees: {vision_description}]"

        conversation_history.append({
            "role": "user",
            "content": user_input
        })

        print("Terrako is thinking...")
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[
                {"role": "system", "content": constitution}
            ] + conversation_history
        )

        terrako_response = response["message"]["content"]

        conversation_history.append({
            "role": "assistant",
            "content": terrako_response
        })

        print(f"\nTerrako: {terrako_response}\n")
        speak(terrako_response)

if __name__ == "__main__":
    chat()