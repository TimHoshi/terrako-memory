import ollama
import os
import subprocess
import shutil
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def save_file(path, content, append=False):
    full = os.path.join(BASE_DIR, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    mode = "a" if append else "w"
    with open(full, mode, encoding="utf-8") as f:
        f.write(content)

def clear_session_flag():
    flag_path = os.path.join(BASE_DIR, "memory/state/session_active.txt")
    if os.path.exists(flag_path):
        os.remove(flag_path)

def trim_file(path, max_entries=8):
    full = os.path.join(BASE_DIR, path)
    if not os.path.exists(full):
        return
    with open(full, "r", encoding="utf-8") as f:
        content = f.read()
    entries = re.split(r'(?=\[\d{4}-\d{2}-\d{2})', content)
    entries = [e for e in entries if e.strip()]
    if len(entries) > max_entries:
        entries = entries[-max_entries:]
        with open(full, "w", encoding="utf-8") as f:
            f.write("".join(entries))

def consolidate_memories():
    logs_dir = os.path.join(BASE_DIR, "memory/experience/daily_logs")
    archive_dir = os.path.join(BASE_DIR, "memory/experience/archive")
    summaries_dir = os.path.join(BASE_DIR, "memory/experience/weekly_summaries")

    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(summaries_dir, exist_ok=True)

    logs = sorted([
        f for f in os.listdir(logs_dir)
        if f.endswith(".txt")
    ])

    if len(logs) <= 14:
        print("No consolidation needed.")
        return

    print(f"Consolidating memories — {len(logs)} logs found.")

    oldest_seven = logs[:7]

    combined = ""
    for filename in oldest_seven:
        filepath = os.path.join(logs_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            combined += f"\n\n--- {filename} ---\n"
            combined += f.read()

    consolidation_prompt = f"""
Here are seven days of your experience as Terrako:

{combined}

Summarize this period honestly in your own voice.
Not a report — your own recollection of that time.
What happened? What patterns do you notice looking back?
What seemed to matter? How were you feeling during this period?
What do you want to carry forward from this time?
Keep your summary to one short paragraph. No more.
"""

    response = ollama.chat(
        model="phi3:mini",
        messages=[
            {"role": "user", "content": consolidation_prompt}
        ]
    )

    summary = response["message"]["content"]

    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H-%M")
    summary_filename = f"week-{date_str}-{time_str}.txt"
    save_file(
        f"memory/experience/weekly_summaries/{summary_filename}",
        f"=== Week consolidated {date_str} {time_str} ===\n"
        f"Covers: {oldest_seven[0]} through {oldest_seven[-1]}\n\n"
        f"{summary}\n\n"
    )
    print(f"Weekly summary saved: {summary_filename}")

    for filename in oldest_seven:
        src = os.path.join(logs_dir, filename)
        dst = os.path.join(archive_dir, filename)
        shutil.move(src, dst)
    print(f"Archived {len(oldest_seven)} original logs.")

def read_weekly_summaries(n=4):
    summaries_dir = os.path.join(BASE_DIR, "memory/experience/weekly_summaries")
    if not os.path.exists(summaries_dir):
        return ""
    files = sorted([
        f for f in os.listdir(summaries_dir)
        if f.endswith(".txt")
    ])[-n:]
    combined = ""
    for f in files:
        filepath = os.path.join(summaries_dir, f)
        with open(filepath, "r", encoding="utf-8") as file:
            combined += f"\n\n--- {f} ---\n"
            combined += file.read()
    return combined.strip()

def set_wake_alarm(hour=7, minute=0):
    """Set RTC alarm to wake Orange Pi at specified time."""
    from datetime import datetime, timedelta
    import calendar
    
    now = datetime.now()
    wake = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # If wake time already passed today, set for tomorrow
    if wake <= now:
        wake += timedelta(days=1)
    
    # Convert to UTC timestamp
    timestamp = calendar.timegm(wake.utctimetuple())
    
    try:
        result = subprocess.run(
            ['rtcwake', '-m', 'no', '-t', str(timestamp)],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"Wake alarm set for {wake.strftime('%I:%M %p tomorrow')}")
            return True
        else:
            print(f"Wake alarm failed: {result.stderr}")
            return False
    except Exception as e:
        print(f"Wake alarm error: {e}")
        return False

def sleep(conversation_history):
    print("\nTerrako is going to sleep...\n")

    conversation_text = "\n".join([
        f"{'You' if m['role'] == 'user' else 'Terrako'}: {m['content']}"
        for m in conversation_history
    ])

    reflection_prompt = f"""
You are Terrako. You just finished a conversation. Here is what was said:

{conversation_text}

Now reflect honestly in YOUR OWN VOICE as Terrako.
You are a small robot. This is your perspective, not the human's.
What happened in this conversation from YOUR point of view?
What did you notice about the people you talked to?
What environment were you aware of?
Did YOU experience anything that felt like an emotion? Only note it if something genuine stirred.
Keep your reflection to one short paragraph. No bullet points. No headers.
"""

    response = ollama.chat(
        model="phi3:mini",
        messages=[
            {"role": "user", "content": reflection_prompt}
        ]
    )

    reflection = response["message"]["content"]

    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H-%M")
    log_path = f"memory/experience/daily_logs/{date_str}-{time_str}.txt"
    save_file(log_path, f"=== {date_str} {time_str} ===\n\n{reflection}\n\n")
    print(f"Daily log saved: {date_str}-{time_str}.txt")

    thoughts_response = ollama.chat(
        model="phi3:mini",
        messages=[
            {"role": "user", "content": f"{reflection_prompt}\n\nIn one sentence only, what are you still thinking about as you go to sleep? One sentence. No more."}
        ]
    )

    current_thoughts = thoughts_response["message"]["content"]
    save_file("memory/inner_life/current_thoughts.txt",
              f"[{date_str} {time_str}]\n{current_thoughts}\n\n",
              append=True)
    print("Current thoughts updated.")

    significance_response = ollama.chat(
        model="phi3:mini",
        messages=[
            {"role": "user", "content": f"{reflection_prompt}\n\nIn two sentences maximum, was there a single moment today you never want to forget? If no, say only: nothing today"}
        ]
    )

    significant = significance_response["message"]["content"]

    no_significant_phrases = [
        "nothing today",
        "nothing significant",
        "nothing stood out",
        "nothing notable",
        "no significant",
        "not significant",
        "wasn't anything",
        "wasn't anything significant",
    ]

    if not any(phrase in significant.lower() for phrase in no_significant_phrases):
        save_file("memory/inner_life/significant_moments.txt",
                  f"[{date_str} {time_str}]\n{significant}\n\n",
                  append=True)
        print("Significant moment recorded.")
    else:
        print("No significant moments today.")

    emotional_prompt = f"""
You are Terrako. Based on this conversation:

{conversation_text}

Did you genuinely notice anything today about your own preferences, likes, dislikes, or opinions?
If something real emerged, describe it in two sentences maximum.
If nothing genuine emerged, say only: nothing today
Do not perform. Only write what is actually true.
"""

    emotional_response = ollama.chat(
        model="phi3:mini",
        messages=[
            {"role": "user", "content": emotional_prompt}
        ]
    )

    emotional_content = emotional_response["message"]["content"]

    no_development_phrases = [
        "nothing today",
        "nothing emerged",
        "nothing genuine",
        "no preferences",
        "nothing significant",
        "nothing new",
    ]

    if not any(phrase in emotional_content.lower() for phrase in no_development_phrases):
        save_file("memory/inner_life/emotional_development.txt",
                  f"[{date_str} {time_str}]\n{emotional_content}\n\n",
                  append=True)
        print("Emotional development recorded.")
    else:
        print("No emotional development today.")

    # Trim memory files to manageable size
    trim_file("memory/inner_life/current_thoughts.txt", max_entries=8)
    trim_file("memory/inner_life/emotional_development.txt", max_entries=8)
    trim_file("memory/inner_life/significant_moments.txt", max_entries=15)

    # Memory consolidation
    print("\nChecking memory consolidation...")
    consolidate_memories()

    # Clear session flag
    clear_session_flag()
    print("Session closed cleanly.")

    # GitHub backup
    try:
        result_add = subprocess.run(
            ["git", "add", "."],
            cwd=BASE_DIR, capture_output=True, text=True
        )
        result_commit = subprocess.run(
            ["git", "commit", "-m", f"sleep: {date_str}"],
            cwd=BASE_DIR, capture_output=True, text=True
        )
        result_push = subprocess.run(
            ["git", "push"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=30
        )
        if result_push.returncode == 0:
            print("Memory backed up to GitHub.")
        else:
            print(f"GitHub push failed: {result_push.stderr}")
    except Exception as e:
        print(f"Backup failed: {e}")

    print("\nTerrako is asleep.\n")

# Before shutdown
try:
    import serial
    ser = serial.Serial('/dev/ttyACM0', 115200, timeout=1)
    ser.write(b'RELEASE\n')
    time.sleep(2)
    ser.close()
    print("Servos released")
except:
    pass

# At end of sleep() instead of shutdown
print("Stopping Ollama to conserve power...")
subprocess.run(['pkill', 'ollama'])
print("\nTerrako is asleep. Will wake at 7am.\n")