import hashlib, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HASHES_FILE = os.path.join(BASE_DIR, 'memory/state/file_hashes.txt')
CRITICAL_FILES = [
    'terrako_core.py',
    'terrako_sleep.py',
    'core_personality.txt',
    'memory/identity/child_profile.txt',
]

os.makedirs(os.path.dirname(HASHES_FILE), exist_ok=True)
with open(HASHES_FILE, 'w') as f:
    for filepath in CRITICAL_FILES:
        full = os.path.join(BASE_DIR, filepath)
        if os.path.exists(full):
            with open(full, 'rb') as ff:
                h = hashlib.md5(ff.read()).hexdigest()
            f.write(f'{filepath}={h}\n')
            print(f'Hashed: {filepath}')
print('Hashes updated!')