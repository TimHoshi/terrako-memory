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
    log_path = f"memory/experience/daily_logs/{date_str}.txt"
    save_file(log_path, f"=== {date_str} ===\n\n{reflection}\n\n")
    print(f"Daily log saved: {date_str}.txt")
    
    # Ask what Terrako is still thinking about
    thoughts_response = ollama.chat(
        model="llama3.1:8b",
        messages=[
            {"role": "user", "content": f"{reflection_prompt}\n\nIn one or two sentences, what are you still thinking about as you go to sleep?"}
        ]
    )
    
    current_thoughts = thoughts_response["message"]["content"]
    save_file("memory/inner_life/current_thoughts.txt", 
              f"[{date_str}]\n{current_thoughts}\n\n", 
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
    
    if "nothing today" not in significant.lower():
        save_file("memory/inner_life/significant_moments.txt",
                  f"[{date_str}]\n{significant}\n\n",
                  append=True)
        print("Significant moment recorded.")
    
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