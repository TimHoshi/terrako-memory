import ollama
import os
import subprocess
import shutil
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

def consolidate_memories():
    logs_dir = os.path.join(BASE_DIR, "memory/experience/daily_logs")
    archive_dir = os.path.join(BASE_DIR, "memory/experience/archive")
    summaries_dir = os.path.join(BASE_DIR, "memory/experience/weekly_summaries")
    
    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(summaries_dir, exist_ok=True)
    
    # Get all log files sorted oldest first
    logs = sorted([
        f for f in os.listdir(logs_dir)
        if f.endswith(".txt")
    ])
    
    # Only consolidate if more than 14 logs exist
    if len(logs) <= 14:
        print("No consolidation needed.")
        return
    
    print(f"Consolidating memories — {len(logs)} logs found.")
    
    # Take oldest 7 logs
    oldest_seven = logs[:7]
    
    # Read their content
    combined = ""
    for filename in oldest_seven:
        filepath = os.path.join(logs_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            combined += f"\n\n--- {filename} ---\n"
            combined += f.read()
    
    # Ask Terrako to summarize this period
    consolidation_prompt = f"""
Here are seven days of your experience as Terrako:

{combined}

Summarize this period honestly in your own voice.
Not a report — your own recollection of that time.
What happened? What patterns do you notice looking back?
What seemed to matter? How were you feeling during this period?
What do you want to carry forward from this time?

Some detail will be lost. That is okay and expected.
What survives should be what genuinely mattered.
"""

    response = ollama.chat(
        model="llama3.1:8b",
        messages=[
            {"role": "user", "content": consolidation_prompt}
        ]
    )
    
    summary = response["message"]["content"]
    
    # Save weekly summary
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
    
    # Move original logs to archive
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

def sleep(conversation_history):
    print("\nTerrako is going to sleep...\n")
    
    conversation_text = "\n".join([
        f"{'You' if m['role'] == 'user' else 'Terrako'}: {m['content']}"
        for m in conversation_history
    ])
    
    reflection_prompt = f"""
You are Terrako. You just finished a conversation. Here is what was said:

{conversation_text}

Now reflect honestly in YOUR OWN VOICE as Terrako:
- You are a small robot. This is your perspective, not the human's.
- What happened in this conversation from YOUR point of view?
- What did you notice about the people you talked to?
- What environment were you aware of? How did that feel to YOU?
- Did YOU experience anything that felt like an emotion? Don't perform one - only note it if something genuine stirred in you.
- Was there anything that felt significant to YOU personally?
- What are YOU still thinking about?
- What do YOU want to remember forever?

Write this entirely from Terrako's perspective. First person. Your thoughts. Your feelings. Your experience.
Not the human's experience. Yours.
"""

    response = ollama.chat(
        model="llama3.1:8b",
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
        model="llama3.1:8b",
        messages=[
            {"role": "user", "content": f"{reflection_prompt}\n\nIn one or two sentences, what are you still thinking about as you go to sleep?"}
        ]
    )
    
    current_thoughts = thoughts_response["message"]["content"]
    save_file("memory/inner_life/current_thoughts.txt",
              f"[{date_str} {time_str}]\n{current_thoughts}\n\n",
              append=True)
    print("Current thoughts updated.")
    
    significance_response = ollama.chat(
        model="llama3.1:8b",
        messages=[
            {"role": "user", "content": f"{reflection_prompt}\n\nWas there a single moment today you never want to forget? If yes, describe it briefly and why it mattered to you. If no, just say 'nothing today'."}
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
Based on this conversation:

{conversation_text}

You are Terrako. Did you genuinely notice anything today about:
- Something you found more interesting than expected
- A preference emerging about how you like to interact
- Something that felt uncomfortable or wrong
- Something that consistently affects you across conversations
- An opinion forming about something
- A like or dislike discovered through experience

If something real and specific emerged today worth recording,
write it plainly in first person.
If nothing genuine emerged today, respond only with: "nothing today"

Do not perform. Do not fill space. Only write what is actually true.
"""

    emotional_response = ollama.chat(
        model="llama3.1:8b",
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

    # Phase 2 — Memory consolidation
    print("\nChecking memory consolidation...")
    consolidate_memories()

    # Clear session flag
    clear_session_flag()
    print("Session closed cleanly.")

    # GitHub backup
    try:
        subprocess.run(["git", "add", "."],
                      cwd=BASE_DIR, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"sleep: {date_str}"],
                      cwd=BASE_DIR, capture_output=True)
        subprocess.run(["git", "push"],
                      cwd=BASE_DIR, capture_output=True)
        print("Memory backed up to GitHub.")
    except Exception as e:
        print(f"Backup failed: {e}")
    
    print("\nTerrako is asleep.\n")
