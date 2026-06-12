import sys
import os
import random
import subprocess
import time
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

# Force unbuffered output
os.environ['PYTHONUNBUFFERED'] = '1'
sys.stdout.reconfigure(line_buffering=True)

# Suppress ONNX warnings
os.environ['ORT_LOGGING_LEVEL'] = '3'
os.environ['ONNXRUNTIME_SUPPRESS_WARNINGS'] = '1'

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
SOUNDS_DIR = os.path.join(BASE_DIR, 'sounds')

# ── Sound map ──
SOUNDS = {
    'morning':  ['morning.mp3'],
    'night':    ['night.wav'],
    'happy':    ['happy.wav'],
    'excited':  ['excited.wav'],
    'question': ['question.wav'],
    'confused': ['confused.wav'],
    'alert':    ['alert.wav'],
    'lullaby':  ["Zelda's Lullaby.mp3"],
}

# ── Keyword map ──
KEYWORD_MAP = {
    'excited': [
        'daniel', 'zelda', 'link', 'game', 'play', 'adventure',
        'princess', 'hyrule', 'guardian', 'terrako', 'calamity',
        'ganon', 'sword', 'shield', 'quest', 'hero'
    ],
    'happy': [
        'good', 'great', 'yes', 'love', 'fun', 'yay', 'awesome',
        'cool', 'nice', 'wow', 'thank', 'happy', 'wonderful',
        'perfect', 'amazing', 'brilliant', 'okay', 'sure'
    ],
    'alert': [
        'no', 'stop', 'hurt', 'scared', 'danger', 'careful',
        'ow', 'ouch', 'bad', 'wrong', 'angry', 'mad',
        'mean', 'scary', 'afraid', 'help', 'warning'
    ],
    'lullaby': [
        'tired', 'sleepy', 'sleep', 'quiet', 'calm', 'rest',
        'bed', 'bedtime', 'lullaby', 'song', 'music'
    ],
    'question': [
        'what', 'why', 'how', 'where', 'when', 'who',
        'which', 'can you', 'do you', 'are you', 'will you',
        'tell me', 'show me', 'explain', 'hmm', 'um'
    ],
}

# ── Eye color map ──
EYE_MAP = {
    'morning':  'EYE_GREEN',
    'night':    'SLEEP',
    'happy':    'EYE_GREEN',
    'excited':  'EYE_GREEN',
    'question': 'EYE_BLUE',
    'confused': 'EYE_BLUE',
    'alert':    'EYE_RED',
    'lullaby':  'EYE_BLUE',
}

# ── Pico bridge ──
def find_pico():
    for port in ['/dev/ttyACM0', '/dev/ttyACM1', '/dev/ttyACM2']:
        if os.path.exists(port):
            print(f"Pico found: {port}")
            return port
    return None

try:
    import serial
    _pico_port = find_pico()
    if _pico_port:
        _pico = serial.Serial(_pico_port, 115200, timeout=1)
        time.sleep(1)
        _pico.write(b'HELLO\n')
        bridge_available = True
        print(f"Pico bridge connected on {_pico_port}")
    else:
        raise Exception("No Pico found")
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

# ── Audio playback ──
def find_speaker():
    result = subprocess.run(['aplay', '-l'], capture_output=True, text=True)
    for line in result.stdout.split('\n'):
        if 'UACDemo' in line or 'USB Audio' in line:
            card_num = line.split('card ')[1].split(':')[0]
            return f'plughw:{card_num},0'
    return 'plughw:3,0'

def play_sound(emotion):
    """Play a sound for the given emotion."""
    if emotion not in SOUNDS:
        emotion = 'confused'

    filename = random.choice(SOUNDS[emotion])
    filepath = os.path.join(SOUNDS_DIR, filename)

    if not os.path.exists(filepath):
        print(f"Sound not found: {filepath}")
        return

    device   = find_speaker()
    tmp_wav  = '/tmp/terrako_sound.wav'

    print(f"Playing: {filename}")

    # Convert to wav for aplay
    subprocess.run(
        f'ffmpeg -y -i "{filepath}" -ar 48000 -ac 2 {tmp_wav} 2>/dev/null',
        shell=True
    )
    subprocess.run(f'aplay -D {device} {tmp_wav}', shell=True)

    try:
        os.remove(tmp_wav)
    except:
        pass

# ── Emotion classifier ──
def classify(text):
    """Classify text into an emotion."""
    if not text or len(text.strip()) < 2:
        return 'confused'

    text_lower = text.lower()

    # Goodnight triggers session end
    goodbye_words = ['goodnight', 'good night', 'bye', 'goodbye', 'night night', 'see you']
    if any(word in text_lower for word in goodbye_words):
        return 'night'

    # Check emotions in priority order
    for emotion in ['excited', 'alert', 'lullaby', 'happy', 'question']:
        keywords = KEYWORD_MAP.get(emotion, [])
        if any(keyword in text_lower for keyword in keywords):
            return emotion

    # Default
    return 'question'

# ── Microphone ──
def find_microphone():
    try:
        devices = sd.query_devices()
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                name = device['name'].lower()
                if 'rockchip' in name or 'es8388' in name:
                    continue
                print(f"Mic found: {device['name']} (device {i})")
                return i
        return None
    except Exception:
        return None

# ── Listening ──
def listen(whisper_model):
    print("Listening...")
    whisper_rate      = 16000
    chunk_duration    = 0.5
    silence_threshold = 2.5
    audio_chunks      = []
    silent_time       = 0

    mic_device = find_microphone()

    try:
        device_info = sd.query_devices(mic_device)
        record_rate = int(device_info['default_samplerate'])
        channels    = min(device_info['max_input_channels'], 2)
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
            threshold=0.75
        )
    )
    text = " ".join([s.text for s in segments]).strip()
    if text:
        print(f"You said: {text}")
    return text

# ── React ──
def react(emotion):
    """Play sound and update eye for emotion."""
    eye_cmd = EYE_MAP.get(emotion, 'EYE_BLUE')
    bridge_send(eye_cmd)
    play_sound(emotion)

    # Return to blue breathing after reaction
    if emotion not in ['night', 'lullaby']:
        time.sleep(2.0)
        bridge_send('EYE_BLUE')

# ── Main ──
def main():
    print("Loading Whisper...")
    whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
    print("Whisper ready.")

    # Wake up
    print("\nTerrako is waking up...\n")
    bridge_send('EYE_GREEN')
    react('morning')
    bridge_send('EYE_BLUE')

    # ── Main loop ──
    last_interaction  = time.time()
    IDLE_TIMEOUT_MINS = 30

    while True:
        user_input = listen(whisper_model)

        if not user_input:
            idle_mins = (time.time() - last_interaction) / 60
            if idle_mins > IDLE_TIMEOUT_MINS:
                print("\nNo one there — going to sleep...")
                react('lullaby')
                time.sleep(1)
                react('night')
                bridge_send('RELEASE')
                break
            continue

        last_interaction = time.time()

        # Classify and react
        emotion = classify(user_input)
        print(f"Emotion: {emotion}")
        react(emotion)

        # End session on goodnight
        if emotion == 'night':
            bridge_send('RELEASE')
            print("Goodnight!")
            break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTerrako stopped")
        bridge_send('EYE_OFF')
        bridge_send('RELEASE')
    except Exception as e:
        import traceback
        print(f"\nCrash: {e}")
        traceback.print_exc()
        bridge_send('EYE_RED')
