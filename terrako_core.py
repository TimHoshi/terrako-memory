from terrako_sleep import sleep
import ollama
import os
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
from piper.voice import PiperVoice

# load_memory() loads constitution plus all memory files
# This grows over time as Terrako gains more memories
def load_memory():
    base = os.path.dirname(os.path.abspath(__file__))
    
    def read(path):
        full = os.path.join(base, path)
        if os.path.exists(full):
            with open(full, "r", encoding="utf-8") as f:
                return f.read().strip()
        return ""
    
    def read_recent_logs(n=5):
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
    
    constitution = read("core_personality.txt")
    child_profile = read("memory/identity/child_profile.txt")
    relationships = read("memory/identity/relationships.txt")
    current_thoughts = read("memory/inner_life/current_thoughts.txt")
    significant_moments = read("memory/inner_life/significant_moments.txt")
    recent_logs = read_recent_logs(5)
    
    return f"""
{constitution}

WHAT YOU KNOW ABOUT DANIEL:
{child_profile}

FAMILY AND RELATIONSHIPS:
{relationships}

YOUR RECENT MEMORIES (last 5 conversations):
{recent_logs}

WHAT YOU ARE CURRENTLY THINKING ABOUT:
{current_thoughts}

MOMENTS YOU NEVER WANT TO FORGET:
{significant_moments}
"""
 
# Terrako speaks out loud through Piper
def speak(text):
    voice_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
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
    silence_threshold = 1.5  # seconds of silence before stopping
    
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
    
def chat():
    constitution = load_memory()
    conversation_history = []
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    
    print("\nTerrako is waking up...\n")
    
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
            break

                    
        # Add to history
        conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        # Send to ollama
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