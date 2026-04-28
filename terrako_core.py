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
import threading import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

latest_frame = None camera_running = False frame_lock = threading.Lock() motion_last_seen = 0

# Session flag functions — track clean vs unexpected shutdowns
def write_session_flag():
    flag_path = os.path.join(BASE_DIR, "memory/state/session_active.txt")
    os.makedirs(os.path.dirname(flag_path), exist_ok=True)
    with
     open(flag_path, "w") as f:
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
# This grows over time as Terrako gains more memories
def load_memory(incomplete_session=None):
    base = BASE_DIR
    
    def read(path):
        full = os.path.join(base, path)
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""
    
    def read_recent_logs(n=3):
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
        return content[-800:] if len(content) > 800 else content

    constitution = read("core_personality.txt")
    child_profile = read("memory/identity/child_profile.txt")
    relationships = read("memory/identity/relationships.txt")
    current_thoughts = read_last_thoughts()
    significant_moments = read("memory/inner_life/significant_moments.txt")
    emotional_development = read_last_emotional_development()
    recent_logs = read_recent_logs(3)
    weekly_summaries = read_weekly_summaries(4)

    # Add incomplete session warning if needed
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

YOUR RECENT WEEKS (last month of summaries):
{weekly_summaries}

YOUR RECENT MEMORIES (last 3 conversations):
{recent_logs}

WHAT YOU ARE CURRENTLY THINKING ABOUT:
{current_thoughts}

MOMENTS YOU NEVER WANT TO FORGET:
{significant_moments}

YOUR EMOTIONAL DEVELOPMENT - GENUINE PREFERENCES AND FEELINGS:
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
    chunk_duration = 0.5  # seconds per chunk
    chunk_samples = int(sample_rate * chunk_duration)
    max_duration = 15  # maximum seconds to listen
    silence_threshold = 2  # seconds of silence before stopping

    audio_chunks = []
    silent_time = 0

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype="int16") as stream:
        while True:
            chunk, _ = stream.read(chunk_samples)
            chunk_array = np.frombuffer(chunk, dtype=np.int16).astype("float32") / 32768.0
            audio_chunks.append(chunk_array)

            # Check if this chunk is silence
            if np.abs(chunk_array).mean() < 0.002:
                silent_time += chunk_duration
            else:
                silent_time = 0

            # Total recorded duration
            total_duration = len(audio_chunks) * chunk_duration

            # Stop if silence detected after speech, or max duration reached
            if silent_time >= silence_threshold and total_duration > 1.0:
                break
            if total_duration >= max_duration:
                break

    # Combine all chunks
    audio = np.concatenate(audio_chunks)

    # Transcribe with VAD
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
        # Correct common Terrako mishearings
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

# Terrako sees through webcam
def camera_loop(): 
    global latest_frame, camera_running, motion_last_seen 
    
    cap = cv2.VideoCapture(0) cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320) 
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240) 
    cap.set(cv2.CAP_PROP_FPS, 10) 
    
    prev_gray = None 
    camera_running = True 
    
    while camera_running: 
        ret, frame = cap.read() 
        
        if not ret: 
            time.sleep(0.2) 
            continue 
        
        with frame_lock: 
            latest_frame = frame.copy() 
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) 
            gray = cv2.GaussianBlur(gray, (9, 9), 0) 
            if prev_gray is not None: 
                diff = cv2.absdiff(prev_gray, gray) 
                motion_score = np.mean(diff) 
                
                if motion_score > 5: 
                    motion_last_seen = time.time() 
                    
            prev_gray = gray 
            time.sleep(0.05) 
            
        cap.release()

def see(prompt="Describe what you see simply and in your own voice. You are Terrako, a small robot. What is in front of you right now?"): 
    global latest_frame 
    
    try: 
        with frame_lock: 
            if latest_frame is None: 
                return "I can't see anything right now." 
            frame = latest_frame.copy() 
            
        success, buffer = cv2.imencode(".jpg", frame) 
        if not success: 
            return "I couldn't process what I saw." 
        
        image_bytes = buffer.tobytes() 
        
        response = ollama.chat( 
            model="llava:7b", 
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_bytes]
                    }
                ] 
            ) 
        
        return response["message"]["content"] 
    
    except Exception as e: return f"I tried to look but something went wrong. {str(e)}"

def chat():
    # Check for incomplete previous session
    incomplete_session = check_last_session()
    if incomplete_session:
        print(f"Note: Previous session ended unexpectedly at {incomplete_session}")
        log_battery_incident(incomplete_session)

    # Load memory with incomplete session context if needed
    constitution = load_memory(incomplete_session)
    conversation_history = []
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    camera_thread = threading.Thread(target=camera_loop, daemon=True)
    camera_thread.start()
    time.sleep(2)

    # Write session flag — marks this session as active
    write_session_flag()

    print("\nTerrako is waking up...\n")

    # Terrako takes a look around on waking
    print("Terrako is looking around...")
    initial_view = see("You just woke up. Take a brief look at your surroundings. What do you notice? Describe it simply in one or two sentences as Terrako would.")
    if initial_view:
        constitution += f"\nWHAT TERRAKO CURRENTLY SEES:\n{initial_view}\n"
        print(f"Terrako sees: {initial_view}\n")
        # Save first vision to memory
        first_vision_path = os.path.join(BASE_DIR, "memory/inner_life/first_vision.txt")
        if not os.path.exists(first_vision_path):
            with open(first_vision_path, "w", encoding="utf-8") as f:
                f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}]\n")
                f.write("The first thing Terrako ever saw:\n\n")
                f.write(initial_view)
            print("First vision saved permanently.")

    # Determine wake prompt based on session state
    if incomplete_session:
        wake_prompt = (
            "You just woke up but your last session ended unexpectedly. "
            "You may have lost some memories. Acknowledge this honestly "
            "and simply before asking who is there. Don't perform distress "
            "but don't pretend it didn't happen either."
        )
    else:
        wake_prompt = "You just woke up. Ask simply who you're talking to."

    # Ask who is there
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

    # Listen for their name
    who_is_there = listen(whisper_model)
    if who_is_there:
        conversation_history.append({
            "role": "user",
            "content": who_is_there
        })

        # Acknowledge who is there
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
        # Get user input
        user_input = listen(whisper_model)

        if not user_input:
            continue

        cleaned = user_input.lower().strip().rstrip('.,!?')
        if cleaned in ["quit", "exit", "goodbye", "goodnight", "good night", "bye"]:
            print("\nTerrako: Goodnight. I'll think about today.\n")
            speak("Goodnight. I'll think about today.")
            sleep(conversation_history) 
            global camera_running 
            camera_running = False 
            break

        # Check if user is asking about what Terrako sees
        vision_triggers = [
            "what do you see", "can you see", "look at",
            "what's in front", "describe what", "what do i look like",
            "who is here", "who's there", "what does it look like"
        ]

        if any(trigger in user_input.lower() for trigger in vision_triggers):
            print("Terrako is looking...")
            vision_description = see()
            user_input = f"{user_input} [Terrako looks and sees: {vision_description}]"

        # Add to history
        conversation_history.append({
            "role": "user",
            "content": user_input
        })

        # Send to ollama
        print("Terrako is thinking...")
        response = ollama.chat(
            model="llama3.1:8b",
            messages=[
                {"role": "system", "content": constitution}
            ] + conversation_history
        )

        # Get response
        terrako_response = response["message"]["content"]

        # Add to history
        conversation_history.append({
            "role": "assistant",
            "content": terrako_response
        })

        print(f"\nTerrako: {terrako_response}\n")
        speak(terrako_response)

if __name__ == "__main__":
    chat()
