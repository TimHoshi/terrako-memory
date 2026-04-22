import ollama
import os
import subprocess
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def save_file(path, content, append=False):
    full = os.path.join(BASE_DIR, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    mode = "a" if append else "w"
    with open(full, mode, encoding="utf-8") as f:
        f.write(content)

# Clear session flag on clean shutdown
def clear_session_flag():
    flag_path = os.path.join(BASE_DIR, "memory/state/session_active.txt")
    if os.path.exists(flag_path):
        os.remove(flag_path)

def sleep(conversation_history):
    print("\nTerrako is going to sleep...\n")
    
    # Build conversation text for reflection
    conversation_text = "\n".join([
        f"{'You' if m['role'] == 'user' else 'Terrako'}: {m['content']}"
        for m in conversation_history
    ])
    
    # Ask Terrako to reflect
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
    
    # Save dated daily log
    date_str = datetime.now().strftime("%Y-%m-%d")
    time_str = datetime.now().strftime("%H-%M")
    log_path = f"memory/experience/daily_logs/{date_str}-{time_str}.txt"
    save_file(log_path, f"=== {date_str} {time_str} ===\n\n{reflection}\n\n")
    print(f"Daily log saved: {date_str}-{time_str}.txt")
    
    # Ask what Terrako is still thinking about
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
    
    # Ask if anything was significant
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

    # Check for emerging emotional patterns
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

    # Log battery incident if session flag still exists
    # (means previous session ended unexpectedly)
    flag_path = os.path.join(BASE_DIR, "memory/state/session_active.txt")
    if os.path.exists(flag_path):
        with open(flag_path, "r") as f:
            last_session = f.read().strip()
        save_file("memory/state/battery_incidents.txt",
                  f"[{date_str} {time_str}]\n"
                  f"Clean sleep after incomplete session.\n"
                  f"Previous session started: {last_session}\n\n",
                  append=True)

    # Clear session flag — clean shutdown
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