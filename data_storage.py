import os
import json

USERS_FILE = 'data/users.json'
users = {}

def save_users():
    try:
        os.makedirs('data', exist_ok=True)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in users.items()}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def load_users():
    global users
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = {int(k): v for k, v in json.load(f).items()}
    except:
        users = {}
