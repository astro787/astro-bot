import time
import sys
import os as _os
import socket

# Ждём, пока старый инстанс точно умрёт
print("⏳ Ожидание 8с перед стартом для избежания conflict...")
time.sleep(8)

# Проверяем, не запущен ли уже бот
def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) == 0

if is_port_in_use(9999):
    print("❌ Бот уже запущен! Выходим...")
    sys.exit(0)

lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    lock_socket.bind(('localhost', 9999))
    lock_socket.listen(1)
    print(f"🔒 Блокировка на порту 9999 (PID: {_os.getpid()})")
except:
    print("❌ Не удалось занять порт. Выходим...")
    sys.exit(0)

import os
import swisseph as swe
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import atexit
import json

# ========== ВАЛИДАЦИЯ ==========
def validate_date(day: int, month: int, year: int):
    current_year = datetime.now().year
    if year < 1900 or year > current_year:
        raise ValueError(f"Год должен быть между 1900 и {current_year}, получено: {year}")
    if not (1 <= month <= 12):
        raise ValueError(f"Месяц должен быть 1-12, получено: {month}")
    if not (1 <= day <= 31):
        raise ValueError(f"День должен быть 1-31, получено: {day}")
    try:
        datetime(year, month, day)
        return True
    except ValueError:
        raise ValueError(f"Дата не существует: {day:02d}.{month:02d}.{year}")

def validate_time(hour: int, minute: int):
    if not (0 <= hour <= 23):
        raise ValueError(f"Часы должны быть 0-23, получено: {hour}")
    if not (0 <= minute <= 59):
        raise ValueError(f"Минуты должны быть 0-59, получено: {minute}")
    return True
# ========== КОНЕЦ ВАЛИДАЦИИ ==========

# ========== AI КЛИЕНТ (DeepSeek + HuggingFace резерв) ==========
class AIClient:
    def __init__(self, deepseek_token=None, hf_token=None):
        self.deepseek_token = deepseek_token
        self.hf_token = hf_token
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        self.hf_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
        self.max_retries = 3
        self.timeout = 40

    def ask(self, prompt, max_tokens=400):
        # 1. Пробуем DeepSeek
        if self.deepseek_token:
            print("🔍 DEEPSEEK_TOKEN: ✅ найден, пробую DeepSeek...")
            result = self._ask_deepseek(prompt, max_tokens)
            if result:
                return result
            print("⚠️ DeepSeek не ответил, переключаюсь на HuggingFace...")
        else:
            print("🔍 DEEPSEEK_TOKEN: ❌ НЕ НАЙДЕН")

        # 2. Резерв: HuggingFace
        if self.hf_token:
            print("🔄 Пробую HuggingFace...")
            return self._ask_huggingface(prompt, max_tokens)

        print("❌ Нет доступных AI-моделей")
        return None

    def _ask_deepseek(self, prompt, max_tokens):
        headers = {
            "Authorization": f"Bearer {self.deepseek_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Ты — профессиональный астролог с 25-летним опытом."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.7
        }
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.deepseek_url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    if text and len(text) > 10:
                        print(f"✅ DeepSeek ответил: {len(text)} символов")
                        return text
                elif response.status_code == 429:
                    wait = 20 * (attempt + 1)
                    print(f"⏳ DeepSeek rate limit, ждём {wait}с...")
                    time.sleep(wait)
                else:
                    print(f"❌ DeepSeek ошибка API: {response.status_code} - {response.text[:200]}")
                    if attempt < self.max_retries - 1:
                        time.sleep(5)
            except requests.Timeout:
                print(f"⏱ DeepSeek таймаут (попытка {attempt+1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
            except Exception as e:
                print(f"❌ DeepSeek ошибка: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
        return None

    def _ask_huggingface(self, prompt, max_tokens):
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.hf_url, headers=headers,
                    json={"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}},
                    timeout=self.timeout
                )
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and data:
                        text = data[0].get("generated_text", "").strip()
                        if text and len(text) > 10:
                            print(f"✅ HF ответ: {len(text)} символов")
                            return text
                elif response.status_code == 503:
                    wait = 10 * (attempt + 1)
                    print(f"⏳ HF модель загружается, ждём {wait}с...")
                    time.sleep(wait)
                elif response.status_code == 429:
                    wait = 20 * (attempt + 1)
                    print(f"⏳ HF rate limit, ждём {wait}с...")
                    time.sleep(wait)
                else:
                    print(f"❌ HF ошибка API: {response.status_code}")
                    if attempt < self.max_retries - 1:
                        time.sleep(5)
            except requests.Timeout:
                print(f"⏱ HF таймаут (попытка {attempt+1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
            except Exception as e:
                print(f"❌ HF ошибка: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
        print("❌ HF все попытки исчерпаны")
        return None

    @staticmethod
    def split_message(text, max_length=4000):
        parts = []
        while len(text) > max_length:
            split_pos = text.rfind('\n', 0, max_length)
            if split_pos == -1 or split_pos < max_length * 0.7:
                split_pos = text.rfind('. ', 0, max_length)
            if split_pos == -1 or split_pos < max_length * 0.7:
                split_pos = text.rfind(' ', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            parts.append(text[:split_pos].strip())
            text = text[split_pos:].strip()
        if text:
            parts.append(text)
        return parts
# ========== КОНЕЦ AI КЛИЕНТА ==========

# ========== JSON ХРАНИЛИЩЕ ==========
USERS_FILE = 'data/users.json'

def save_users():
    try:
        os.makedirs('data', exist_ok=True)
        data_to_save = {str(k): v for k, v in users.items()}
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        print(f"✅ Сохранено: {len(users)} пользователей")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def load_users():
    global users
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            users = {int(k): v for k, v in data.items()}
            print(f"📂 Загружено: {len(users)} пользователей")
        else:
            print("📄 Файл не найден, начинаем с пустого")
            users = {}
    except Exception as e:
        print(f"❌ Ошибка загрузки: {e}")
        users = {}
# ========== КОНЕЦ JSON ХРАНИЛИЩА ==========

load_dotenv()

# Инициализация AI клиента с DeepSeek основным и HF резервным
DEEPSEEK_TOKEN = os.getenv("DEEPSEEK_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
ai_client = AIClient(deepseek_token=DEEPSEEK_TOKEN, hf_token=HF_TOKEN)

# ===== KEEP-ALIVE СЕРВЕР =====
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def run_keepalive():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), PingHandler)
    print(f"Keep-alive сервер на порту {port}")
    server.serve_forever()

swe.set_ephe_path(None)

SIGN_NAMES = ['Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева',
              'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы']

SIGN_EMOJI = {'Овен':'♈','Телец':'♉','Близнецы':'♊','Рак':'♋','Лев':'♌','Дева':'♍',
              'Весы':'♎','Скорпион':'♏','Стрелец':'♐','Козерог':'♑','Водолей':'♒','Рыбы':'♓'}

ZODIAC_SIGNS = {
    'Овен': (3,21,4,19), 'Телец': (4,20,5,20), 'Близнецы': (5,21,6,20),
    'Рак': (6,21,7,22), 'Лев': (7,23,8,22), 'Дева': (8,23,9,22),
    'Весы': (9,23,10,22), 'Скорпион': (10,23,11,21), 'Стрелец': (11,22,12,21),
    'Козерог': (12,22,1,19), 'Водолей': (1,20,2,18), 'Рыбы': (2,19,3,20)
}

CITIES = {
    'москва': (55.75, 37.62), 'мск': (55.75, 37.62),
    'питер': (59.93, 30.33), 'спб': (59.93, 30.33), 'санкт-петербург': (59.93, 30.33),
    'воронеж': (51.67, 39.18), 'белгород': (50.60, 36.60), 'брянск': (53.25, 34.37),
    'владимир': (56.14, 40.40), 'иваново': (56.99, 40.97), 'калуга': (54.53, 36.28),
    'кострома': (57.77, 40.93), 'курск': (51.74, 36.19), 'липецк': (52.60, 39.60),
    'орёл': (52.97, 36.08), 'орел': (52.97, 36.08), 'рязань': (54.63, 39.69),
    'смоленск': (54.78, 32.05), 'тамбов': (52.73, 41.44), 'тверь': (56.86, 35.92),
    'тула': (54.20, 37.62), 'ярославль': (57.63, 39.87),
    'калининград': (54.71, 20.51), 'архангельск': (64.54, 40.54), 'вологда': (59.22, 39.88),
    'мурманск': (68.97, 33.08), 'петрозаводск': (61.79, 34.36), 'сыктывкар': (61.67, 50.82),
    'великий новгород': (58.52, 31.27), 'псков': (57.81, 28.35), 'череповец': (59.13, 37.91),
    'ростов': (47.23, 39.72), 'ростов-на-дону': (47.23, 39.72), 'краснодар': (45.04, 38.98),
    'сочи': (43.59, 39.73), 'волгоград': (48.71, 44.50), 'астрахань': (46.35, 48.04),
    'волжский': (48.79, 44.78), 'новороссийск': (44.72, 37.77), 'таганрог': (47.22, 38.90),
    'шахты': (47.71, 40.21), 'армавир': (45.00, 41.12), 'симферополь': (44.95, 34.10),
    'севастополь': (44.61, 33.52), 'майкоп': (44.61, 40.11), 'элиста': (46.31, 44.26),
    'пятигорск': (44.05, 43.06), 'ставрополь': (45.04, 41.97), 'махачкала': (42.98, 47.50),
    'грозный': (43.31, 45.69), 'нальчик': (43.48, 43.61), 'владикавказ': (43.02, 44.68),
    'черкесск': (44.23, 42.06), 'назрань': (43.23, 44.77), 'хасавюрт': (43.25, 46.59),
    'дербент': (42.07, 48.30),
    'нижний': (56.33, 44.00), 'нн': (56.33, 44.00), 'нижний новгород': (56.33, 44.00),
    'казань': (55.79, 49.12), 'самара': (53.20, 50.15), 'уфа': (54.74, 55.97),
    'пермь': (58.01, 56.25), 'саратов': (51.53, 46.03), 'тольятти': (53.53, 49.35),
    'ижевск': (56.85, 53.23), 'ульяновск': (54.33, 48.39), 'чебоксары': (56.13, 47.25),
    'киров': (58.60, 49.66), 'оренбург': (51.77, 55.10), 'пенза': (53.20, 45.00),
    'саранск': (54.19, 45.18), 'набережные челны': (55.74, 52.41), 'йошкар-ола': (56.63, 47.90),
    'стерлитамак': (53.63, 55.95), 'энгельс': (51.50, 46.12), 'дзержинск': (56.24, 43.46),
    'альметьевск': (54.90, 52.32),
    'екатеринбург': (56.84, 60.65), 'екб': (56.84, 60.65), 'челябинск': (55.16, 61.43),
    'тюмень': (57.15, 65.53), 'магнитогорск': (53.42, 58.98), 'сургут': (61.25, 73.42),
    'нижний тагил': (57.92, 59.98), 'курган': (55.47, 65.35), 'нижневартовск': (60.94, 76.58),
    'ханты-мансийск': (61.00, 69.00), 'салехард': (66.53, 66.61), 'златоуст': (55.17, 59.67),
    'миасс': (55.05, 60.11), 'копейск': (55.10, 61.62),
    'новосибирск': (55.03, 82.92), 'нск': (55.03, 82.92), 'омск': (54.99, 73.37),
    'красноярск': (56.02, 92.87), 'иркутск': (52.29, 104.30), 'барнаул': (53.35, 83.78),
    'новокузнецк': (53.76, 87.14), 'кемерово': (55.36, 86.08), 'томск': (56.50, 84.97),
    'улан-удэ': (51.83, 107.61), 'чита': (52.03, 113.50), 'братск': (56.15, 101.63),
    'ангарск': (52.54, 103.89), 'абакан': (53.72, 91.44), 'норильск': (69.35, 88.20),
    'бийск': (52.54, 85.22), 'прокопьевск': (53.90, 86.72), 'кызыл': (51.72, 94.45),
    'горно-алтайск': (51.96, 85.96),
    'владивосток': (43.12, 131.89), 'якутск': (62.03, 129.73), 'хабаровск': (48.48, 135.08),
    'благовещенск': (50.28, 127.54), 'южно-сахалинск': (46.96, 142.74),
    'петропавловск-камчатский': (53.02, 158.65), 'магадан': (59.56, 150.80),
    'анадырь': (64.73, 177.51), 'комсомольск-на-амуре': (50.55, 137.01),
    'уссурийск': (43.80, 131.95), 'находка': (42.82, 132.87), 'артём': (43.36, 132.19),
    'артем': (43.36, 132.19),
    'минск': (53.90, 27.57), 'гомель': (52.43, 30.98), 'могилёв': (53.90, 30.34),
    'могилев': (53.90, 30.34), 'витебск': (55.19, 30.20), 'гродно': (53.68, 23.83),
    'брест': (52.10, 23.70), 'киев': (50.45, 30.52), 'харьков': (49.99, 36.23),
    'одесса': (46.48, 30.73), 'днепр': (48.47, 35.04), 'львов': (49.84, 24.03),
    'астана': (51.17, 71.43), 'алматы': (43.26, 76.93), 'шымкент': (42.32, 69.60),
    'караганда': (49.80, 73.10), 'ташкент': (41.30, 69.24), 'самарканд': (39.65, 66.96),
    'бухара': (39.77, 64.42), 'баку': (40.41, 49.87), 'ганжа': (40.68, 46.36),
    'ереван': (40.18, 44.51), 'тбилиси': (41.72, 44.79), 'батуми': (41.65, 41.64),
    'бишкек': (42.87, 74.59), 'ош': (40.53, 72.80), 'душанбе': (38.54, 68.78),
    'худжанд': (40.28, 69.62), 'ашхабад': (37.95, 58.38), 'кишинёв': (47.01, 28.86),
    'кишинев': (47.01, 28.86),
    'нью-йорк': (40.71, -74.00), 'лондон': (51.51, -0.13), 'париж': (48.86, 2.35),
    'берлин': (52.52, 13.40), 'токио': (35.68, 139.76), 'пекин': (39.90, 116.40),
    'дубай': (25.20, 55.27), 'стамбул': (41.01, 28.98),
}

CITY_TIMEZONES = {
    'москва': 3, 'мск': 3, 'питер': 3, 'спб': 3, 'санкт-петербург': 3,
    'воронеж': 3, 'белгород': 3, 'брянск': 3, 'владимир': 3, 'иваново': 3,
    'калуга': 3, 'кострома': 3, 'курск': 3, 'липецк': 3, 'орёл': 3, 'орел': 3,
    'рязань': 3, 'смоленск': 3, 'тамбов': 3, 'тверь': 3, 'тула': 3, 'ярославль': 3,
    'калининград': 2, 'архангельск': 3, 'вологда': 3, 'мурманск': 3,
    'петрозаводск': 3, 'сыктывкар': 3, 'великий новгород': 3, 'псков': 3, 'череповец': 3,
    'ростов': 3, 'ростов-на-дону': 3, 'краснодар': 3, 'сочи': 3, 'волгоград': 3,
    'астрахань': 4, 'волжский': 3, 'новороссийск': 3, 'таганрог': 3, 'шахты': 3,
    'армавир': 3, 'симферополь': 3, 'севастополь': 3, 'майкоп': 3, 'элиста': 3,
    'пятигорск': 3, 'ставрополь': 3, 'махачкала': 3, 'грозный': 3,
    'нальчик': 3, 'владикавказ': 3, 'черкесск': 3, 'назрань': 3,
    'хасавюрт': 3, 'дербент': 3,
    'нижний': 3, 'нн': 3, 'нижний новгород': 3, 'казань': 3, 'саратов': 4,
    'тольятти': 4, 'ижевск': 4, 'ульяновск': 4, 'чебоксары': 3, 'киров': 3,
    'пенза': 3, 'саранск': 3, 'набережные челны': 3, 'йошкар-ола': 3,
    'энгельс': 4, 'дзержинск': 3, 'альметьевск': 3,
    'самара': 4, 'уфа': 5, 'пермь': 5, 'оренбург': 5, 'стерлитамак': 5,
    'екатеринбург': 5, 'екб': 5, 'челябинск': 5, 'тюмень': 5,
    'магнитогорск': 5, 'сургут': 5, 'нижний тагил': 5, 'курган': 5,
    'нижневартовск': 5, 'ханты-мансийск': 5, 'салехард': 5,
    'златоуст': 5, 'миасс': 5, 'копейск': 5,
    'омск': 6, 'новосибирск': 7, 'нск': 7, 'красноярск': 7, 'барнаул': 7,
    'новокузнецк': 7, 'кемерово': 7, 'томск': 7, 'абакан': 7, 'норильск': 7,
    'бийск': 7, 'прокопьевск': 7, 'кызыл': 7, 'горно-алтайск': 7,
    'иркутск': 8, 'улан-удэ': 8, 'чита': 9, 'братск': 8, 'ангарск': 8,
    'владивосток': 10, 'хабаровск': 10, 'благовещенск': 9, 'уссурийск': 10,
    'находка': 10, 'артём': 10, 'артем': 10, 'комсомольск-на-амуре': 10,
    'якутск': 9, 'южно-сахалинск': 11, 'петропавловск-камчатский': 12,
    'магадан': 11, 'анадырь': 12,
    'минск': 3, 'гомель': 3, 'могилёв': 3, 'могилев': 3, 'витебск': 3,
    'гродно': 3, 'брест': 3,
    'киев': 2, 'харьков': 2, 'одесса': 2, 'днепр': 2, 'львов': 2,
    'астана': 5, 'алматы': 5, 'шымкент': 5, 'караганда': 5,
    'ташкент': 5, 'самарканд': 5, 'бухара': 5,
    'баку': 4, 'ганжа': 4,
    'ереван': 4, 'тбилиси': 4, 'батуми': 4,
    'бишкек': 6, 'ош': 6,
    'душанбе': 5, 'худжанд': 5,
    'ашхабад': 5,
    'кишинёв': 2, 'кишинев': 2,
    'нью-йорк': -5, 'лондон': 0, 'париж': 1, 'берлин': 1,
    'токио': 9, 'пекин': 8, 'дубай': 4, 'стамбул': 3,
}

HOUSE_SYSTEMS = {
    b'P': 'Плацидус', b'K': 'Кох', b'W': 'Whole Sign',
    b'O': 'Порфирий', b'C': 'Кампанус',
}

DEFAULT_HOUSE_SYSTEM = b'P'

PLANETS = {'Солнце': swe.SUN, 'Луна': swe.MOON, 'Меркурий': swe.MERCURY,
           'Венера': swe.VENUS, 'Марс': swe.MARS, 'Юпитер': swe.JUPITER,
           'Сатурн': swe.SATURN, 'Уран': swe.URANUS, 'Нептун': swe.NEPTUNE, 'Плутон': swe.PLUTO}

HOUSE_NAMES = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']

load_users()
atexit.register(save_users)

def get_zodiac_sign(day, month):
    for sign, (sm, sd, em, ed) in ZODIAC_SIGNS.items():
        if (month == sm and day >= sd) or (month == em and day <= ed): return sign
    return 'Козерог'

def sign_from_lon(lon):
    return SIGN_NAMES[int(lon // 30)]

def degree_in_sign(lon):
    return int(lon % 30)

def get_timezone(city_name, lat=None, lon=None):
    city_key = city_name.lower().strip()
    if city_key in CITY_TIMEZONES:
        return CITY_TIMEZONES[city_key]
    if lon is not None:
        return round(lon / 15.0)
    return 3

def calc_natal(day, month, year, hour=12, minute=0, lat=55.75, lon=37.62, 
               city_name='москва', house_system=b'P'):
    utc_offset = get_timezone(city_name, lat, lon)
    utc_hour = hour - utc_offset
    if utc_hour < 0: utc_hour += 24
    elif utc_hour >= 24: utc_hour -= 24
    utc_total = utc_hour + minute / 60.0
    jd = swe.julday(year, month, day, utc_total)
    natal = {}
    for name, pid in PLANETS.items():
        try:
            result, _ = swe.calc_ut(jd, pid)
            lon_deg = result[0] if isinstance(result, tuple) else result[0]
            natal[name] = {'sign': sign_from_lon(lon_deg), 'degree': degree_in_sign(lon_deg), 'lon': lon_deg}
        except: continue
    
    try:
        rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
        natal['Раху'] = {'sign': sign_from_lon(rahu_lon), 'degree': degree_in_sign(rahu_lon), 'lon': rahu_lon, 'retro': True}
        ketu_lon = (rahu_lon + 180) % 360
        natal['Кету'] = {'sign': sign_from_lon(ketu_lon), 'degree': degree_in_sign(ketu_lon), 'lon': ketu_lon, 'retro': True}
    except Exception as e:
        print(f"Ошибка расчёта Лунных узлов: {e}")
    
    if abs(lat) > 66.5: house_system = b'W'
    try:
        houses, ascmc = swe.houses(jd, lat, lon, house_system)
    except:
        houses, ascmc = swe.houses(jd, lat, lon, b'W')
    natal['Асцендент'] = {'sign': sign_from_lon(ascmc[0]), 'degree': degree_in_sign(ascmc[0]), 'lon': ascmc[0]}
    natal['MC'] = {'sign': sign_from_lon(ascmc[1]), 'degree': degree_in_sign(ascmc[1]), 'lon': ascmc[1]}
    natal['houses'] = []
    for i in range(12):
        natal['houses'].append({'house_num': i+1, 'sign': sign_from_lon(houses[i]), 'degree': degree_in_sign(houses[i]), 'lon': houses[i]})
    return natal

def get_current_time():
    """Получает точное текущее время через API, с запасным вариантом"""
    try:
        resp = requests.get("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            now = datetime.fromisoformat(data['datetime'].replace('Z', '+00:00'))
            now = now.replace(tzinfo=None)
            print(f"🕐 Точное время получено: {now.strftime('%d.%m.%Y %H:%M:%S')}")
            return now
    except Exception as e:
        print(f"⚠️ Не удалось получить точное время: {e}")
    
    now = datetime.utcnow()
    print(f"🕐 Использую системное время: {now.strftime('%d.%m.%Y %H:%M:%S')}")
    return now

def calc_transits():
    now = get_current_time()
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
    transits = {}
    for name, pid in PLANETS.items():
        try:
            lon_deg = swe.calc_ut(jd, pid)[0][0]
            transits[name] = {'sign': sign_from_lon(lon_deg), 'degree': degree_in_sign(lon_deg), 'lon': lon_deg}
        except: continue
    
    try:
        rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
        transits['Раху'] = {'sign': sign_from_lon(rahu_lon), 'degree': degree_in_sign(rahu_lon), 'lon': rahu_lon}
        ketu_lon = (rahu_lon + 180) % 360
        transits['Кету'] = {'sign': sign_from_lon(ketu_lon), 'degree': degree_in_sign(ketu_lon), 'lon': ketu_lon}
    except Exception as e:
        print(f"Ошибка расчёта транзитов узлов: {e}")
    return transits

def get_aspects(planets):
    aspects_list = []
    names = list(planets.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            if names[i] in ['Асцендент','MC','houses'] or names[j] in ['Асцендент','MC','houses']: continue
            diff = abs(planets[names[i]]['lon'] - planets[names[j]]['lon']) % 360
            if diff > 180: diff = 360 - diff
            asp = None
            if diff <= 5: asp = "соединение"
            elif abs(diff-60) <= 5: asp = "секстиль"
            elif abs(diff-90) <= 6: asp = "квадрат"
            elif abs(diff-120) <= 6: asp = "тригон"
            elif abs(diff-180) <= 6: asp = "оппозиция"
            if asp: aspects_list.append(f"{names[i]} {asp} {names[j]}")
    return aspects_list

def get_aspects_with_angles(natal):
    aspects = []
    names = [p for p in natal.keys() if p not in ['houses', 'Асцендент', 'MC', 'Десцендент', 'IC']]
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            diff = abs(natal[names[i]]['lon'] - natal[names[j]]['lon']) % 360
            if diff > 180: diff = 360 - diff
            asp = None
            if diff <= 5: asp = 'соединение'
            elif abs(diff-60) <= 5: asp = 'секстиль'
            elif abs(diff-90) <= 6: asp = 'квадрат'
            elif abs(diff-120) <= 6: asp = 'тригон'
            elif abs(diff-180) <= 6: asp = 'оппозиция'
            if asp: aspects.append((names[i], names[j], asp, diff))
    return aspects

def calc_transit_aspects(natal, transits, orb=2.0):
    """
    Рассчитывает точные аспекты между транзитными и натальными планетами.
    Возвращает список с детальной информацией.
    """
    aspects = []
    aspect_meanings = {
        'соединение': {'символ': '☌', 'влияние': 'усиление, новые начинания', 'орбис': 8},
        'оппозиция': {'символ': '☍', 'влияние': 'напряжение, осознание', 'орбис': 8},
        'тригон': {'символ': '△', 'влияние': 'гармония, возможности', 'орбис': 8},
        'квадрат': {'символ': '□', 'влияние': 'вызов, действие', 'орбис': 7},
        'секстиль': {'символ': '⚹', 'влияние': 'благоприятные шансы', 'орбис': 5},
    }
    
    for t_name, t_data in transits.items():
        if t_name in ['Раху', 'Кету']:
            continue
        for n_name, n_data in natal.items():
            if n_name in ['houses', 'Асцендент', 'MC', 'Раху', 'Кету']:
                continue
            
            diff = abs(t_data['lon'] - n_data['lon']) % 360
            if diff > 180:
                diff = 360 - diff
            
            for asp_name, asp_info in aspect_meanings.items():
                ideal_angle = {'соединение': 0, 'оппозиция': 180, 'тригон': 120, 'квадрат': 90, 'секстиль': 60}[asp_name]
                deviation = abs(diff - ideal_angle)
                
                if deviation <= asp_info['орбис']:
                    if deviation < orb:
                        direction = "сходящийся (усиливается)"
                    elif deviation < 0.5:
                        direction = "точный"
                    else:
                        direction = "расходящийся (ослабевает)"
                    
                    aspects.append({
                        'transit_planet': t_name,
                        'transit_sign': t_data['sign'],
                        'natal_planet': n_name,
                        'natal_sign': n_data['sign'],
                        'aspect': asp_name,
                        'symbol': asp_info['символ'],
                        'angle': round(diff, 1),
                        'deviation': round(deviation, 1),
                        'direction': direction,
                        'influence': asp_info['влияние'],
                        'transit_house': None
                    })
    
    # Определяем дома для транзитных планет
    for asp in aspects:
        t_name = asp['transit_planet']
        t_lon = transits[t_name]['lon']
        for i, h in enumerate(natal['houses']):
            next_h = natal['houses'][(i + 1) % 12]
            if h['lon'] <= next_h['lon']:
                if h['lon'] <= t_lon < next_h['lon']:
                    asp['transit_house'] = h['house_num']
                    break
            else:
                if t_lon >= h['lon'] or t_lon < next_h['lon']:
                    asp['transit_house'] = h['house_num']
                    break
    
    # Сортируем по важности: точные аспекты первые
    aspects.sort(key=lambda x: x['deviation'])
    return aspects

def parse_city(city_str):
    city_key = city_str.lower().strip()
    if city_key in CITIES:
        return CITIES[city_key][0], CITIES[city_key][1], city_key
    return 55.75, 37.62, 'москва'

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])

def menu_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal"),
         InlineKeyboardButton("🏠 Дома", callback_data="houses")],
        [InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast"),
         InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
        [InlineKeyboardButton("💑 Совместимость", callback_data="compat"),
         InlineKeyboardButton("🌙 Луна", callback_data="moon")],
        [InlineKeyboardButton("📅 Ежедневный гороскоп", callback_data="daily")],
        [InlineKeyboardButton("ℹ️ Помощь", callback_data="help")]
    ])

# ===== ГРАФИЧЕСКАЯ КАРТА =====
def draw_natal_chart_pro(natal, city_name='', birth_time=''):
    fig, ax = plt.subplots(figsize=(14, 14), subplot_kw={'projection': 'polar'})
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(1)
    ax.set_ylim(0, 1.5)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines['polar'].set_visible(False)
    ax.set_facecolor('white')
    fig.patch.set_facecolor('white')
    
    elements = {
        'Огонь': {'color': '#e74c3c', 'signs': ['Овен', 'Лев', 'Стрелец']},
        'Земля': {'color': '#27ae60', 'signs': ['Телец', 'Дева', 'Козерог']},
        'Воздух': {'color': '#8e44ad', 'signs': ['Близнецы', 'Весы', 'Водолей']},
        'Вода': {'color': '#2980b9', 'signs': ['Рак', 'Скорпион', 'Рыбы']},
    }
    
    sign_colors = {}
    for element, data in elements.items():
        for sign in data['signs']:
            sign_colors[sign] = data['color']
    
    asc_lon = natal.get('Асцендент', {}).get('lon', 0)
    offset = np.radians(90) - np.radians(asc_lon)
    
    for i, sign in enumerate(SIGN_NAMES):
        sign_start = i * 30
        sign_end = sign_start + 30
        start_angle = np.radians(sign_start) + offset
        end_angle = np.radians(sign_end) + offset
        color = sign_colors.get(sign, '#2c3e50')
        theta = np.linspace(start_angle, end_angle, 30)
        ax.fill_between(theta, 1.05, 1.20, color=color, alpha=0.25)
        ax.plot([start_angle, start_angle], [1.05, 1.20], color=color, linewidth=1.5, alpha=0.5)
        mid_angle = start_angle + np.radians(15)
        ax.annotate(f"{SIGN_EMOJI.get(sign, '')}", xy=(mid_angle, 1.16), ha='center', va='center', fontsize=10, color=color, weight='bold')
        ax.annotate(sign, xy=(mid_angle, 1.10), ha='center', va='center', fontsize=6.5, color=color, weight='bold')
    
    ax.plot(np.linspace(0, 2*np.pi, 300), [1.05]*300, color='#cccccc', linewidth=1, alpha=0.5)
    
    theta_bg = np.linspace(0, 2*np.pi, 300)
    ax.fill_between(theta_bg, 0.90, 1.05, color='#fafafa', alpha=0.5)
    ax.plot(np.linspace(0, 2*np.pi, 300), [0.90]*300, color='#cccccc', linewidth=1, alpha=0.5)
    
    planet_symbols = {
        'Солнце': '☉', 'Луна': '☽', 'Меркурий': '☿', 'Венера': '♀',
        'Марс': '♂', 'Юпитер': '♃', 'Сатурн': '♄', 'Уран': '♅',
        'Нептун': '♆', 'Плутон': '♇', 'Раху': '☊', 'Кету': '☋',
    }
    
    planet_radii = {
        'Плутон': 0.92, 'Нептун': 0.93, 'Уран': 0.94,
        'Сатурн': 0.95, 'Юпитер': 0.96, 'Марс': 0.97,
        'Венера': 0.98, 'Меркурий': 1.00, 'Луна': 1.02, 'Солнце': 1.04,
        'Раху': 0.99, 'Кету': 0.91,
    }
    
    planet_positions = {}
    
    for name, data in natal.items():
        if name in ['houses', 'Асцендент', 'MC', 'Десцендент', 'IC']: continue
        lon = data['lon']
        degree_in_this_sign = data['degree']
        sign_index = SIGN_NAMES.index(data['sign'])
        sign_start_lon = sign_index * 30
        angle = np.radians(sign_start_lon + degree_in_this_sign) + offset
        symbol = planet_symbols.get(name, '')
        r = planet_radii.get(name, 0.97)
        planet_positions[name] = (angle, r)
        if name == 'Раху': color = '#8e44ad'
        elif name == 'Кету': color = '#e67e22'
        else: color = '#1a1a1a'
        ax.annotate(symbol, xy=(angle, r), ha='center', va='center', fontsize=13, color=color, weight='bold', zorder=9)
        ax.annotate(f"{degree_in_this_sign}°", xy=(angle, r + 0.02), ha='center', va='bottom', fontsize=5.5, color=color, weight='bold')
    
    earth = plt.Circle((0, 0), 0.04, color='#1a1a1a', zorder=10)
    ax.add_artist(earth)
    
    aspect_lines = get_aspects_with_angles(natal)
    aspect_colors = {
        'соединение': '#e74c3c', 'оппозиция': '#e74c3c',
        'тригон': '#27ae60', 'квадрат': '#e74c3c', 'секстиль': '#2980b9',
    }
    
    for (p1, p2, asp_name, angle_diff) in aspect_lines:
        if p1 in planet_positions and p2 in planet_positions:
            ang1, r1 = planet_positions[p1]
            ang2, r2 = planet_positions[p2]
            color = aspect_colors.get(asp_name, '#bdc3c7')
            if asp_name == 'оппозиция': linestyle, alpha, lw = '-', 0.7, 1.5
            elif asp_name == 'тригон': linestyle, alpha, lw = '-', 0.6, 1.5
            elif asp_name == 'квадрат': linestyle, alpha, lw = '--', 0.6, 1.2
            elif asp_name == 'секстиль': linestyle, alpha, lw = ':', 0.5, 1.0
            else: linestyle, alpha, lw = '-', 0.7, 1.0
            ax.plot([ang1, ang2], [r1, r2], color=color, linewidth=lw, alpha=alpha, linestyle=linestyle, zorder=1)
    
    for i, house in enumerate(natal.get('houses', [])):
        house_lon = house['lon']
        house_angle = np.radians(house_lon) + offset
        if house['house_num'] in [1, 4, 7, 10]: linewidth, alpha, color = 2.5, 0.9, '#e74c3c'
        else: linewidth, alpha, color = 1.2, 0.7, '#1a1a1a'
        ax.plot([house_angle, house_angle], [0.90, 1.20], color=color, linewidth=linewidth, alpha=alpha, linestyle='-')
        next_house = natal['houses'][(i+1) % 12]
        next_house_angle = np.radians(next_house['lon']) + offset
        angle_diff = (next_house_angle - house_angle) % (2 * np.pi)
        mid_angle = (house_angle + angle_diff / 2) % (2 * np.pi)
        sign_name = house['sign']
        sign_deg = house['degree']
        ax.annotate(f"{sign_deg}° {SIGN_EMOJI.get(sign_name, '')}", xy=(house_angle, 1.24), ha='center', va='center', fontsize=5.5, color='#555')
        ax.annotate(str(house['house_num']), xy=(mid_angle, 1.30), ha='center', va='center', fontsize=10, color='#1a1a1a', weight='bold', bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#cccccc', alpha=0.9))
        if house['house_num'] == 1: ax.annotate('ASC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 4: ax.annotate('IC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 7: ax.annotate('DSC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 10: ax.annotate('MC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
    
    title = 'НАТАЛЬНАЯ КАРТА'
    if city_name: title += f' • {city_name.title()}'
    if birth_time: title += f' • {birth_time}'
    fig.text(0.5, 0.97, title, ha='center', va='top', fontsize=16, color='#1a1a1a', weight='bold', fontfamily='serif')
    plt.tight_layout(pad=1)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
    buf.seek(0)
    plt.close()
    return buf

async def start(update, ctx):
    ctx.user_data['mode'] = ''
    welcome_text = """
🌟 *АстроБот — ваш персональный астролог*

Создан практикующим астрологом с 12-летним опытом консультирования.

🔬 *Техническая база:*
• Швейцарские эфемериды (Swiss Ephemeris)
• Система домов Плацидуса
• Лунные узлы (☊ Раху / ☋ Кету)
• Профессиональная графическая карта
• Точные транзитные аспекты

✨ *Возможности:*
• 🌟 Натальная карта
• 🔮 Прогнозы по реальным транзитам
• 💞 Совместимость
• 🌙 Лунный календарь
• 📅 Ежедневный гороскоп

🌍 100+ городов | 🎯 Математическая точность
"""
    await update.message.reply_text(welcome_text, reply_markup=menu_btn(), parse_mode='Markdown')

async def help_command(update, ctx):
    help_text = """
📖 *Справка по АстроБоту*

👤 *Автор:* Практикующий астролог с 12-летним стажем

📝 *Форматы ввода данных:*
• `ДД.ММ.ГГГГ` — полдень, Москва
• `ДД.ММ.ГГГГ ЧЧ ММ` — Москва
• `ДД.ММ.ГГГГ ЧЧ ММ Город`

🌍 *Примеры городов:*
🇷🇺 Москва, Питер, Казань, Сочи, Екатеринбург, Владивосток
🇧🇾 Минск, Гомель
🇰🇿 Астана, Алматы
🇺🇸 Нью-Йорк, 🇬🇧 Лондон, 🇫🇷 Париж, 🇯🇵 Токио

🔧 *Функции:*
🌟 *Натальная карта* — расчёт + графика
🏠 *Дома гороскопа* — 12 домов
🔮 *Прогноз ИИ* — день/неделя/месяц
🪐 *Транзиты* — планеты сейчас
💑 *Совместимость* — по знакам
🌙 *Луна* — фаза и положение
📅 *Гороскоп* — на сегодня

*Особенности:*
• ☊ Раху и ☋ Кету — Лунные узлы
• 🎨 Графическая карта
• 🤖 AI-прогнозы (DeepSeek)
• 🎯 Точные транзитные аспекты
• 💾 Данные сохраняются
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def logtest(update, ctx):
    """Тестовая команда для проверки токенов и связи с DeepSeek API"""
    await update.message.reply_text("🔍 Запускаю диагностику...")
    
    now = get_current_time()
    await update.message.reply_text(f"🕐 Текущее время сервера: {now.strftime('%d.%m.%Y %H:%M:%S')} UTC")
    
    token = os.getenv("DEEPSEEK_TOKEN")
    if token:
        print("🔍 DEEPSEEK_TOKEN: ✅ найден (длина: {})".format(len(token)))
        await update.message.reply_text("✅ DEEPSEEK_TOKEN найден! Пробую подключиться к DeepSeek API...")
        
        try:
            import requests as req
            resp = req.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "Скажи: OK"}],
                    "max_tokens": 10
                },
                timeout=15
            )
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                print(f"✅ DeepSeek API ответил: {text}")
                await update.message.reply_text(f"✅ DeepSeek работает! Ответ: {text}")
            else:
                print(f"❌ DeepSeek API ошибка: {resp.status_code} - {resp.text[:200]}")
                await update.message.reply_text(f"❌ DeepSeek API error {resp.status_code}: {resp.text[:300]}")
        except Exception as e:
            print(f"❌ Ошибка соединения с DeepSeek: {e}")
            await update.message.reply_text(f"❌ Нет связи с DeepSeek: {str(e)[:300]}")
    else:
        print("🔍 DEEPSEEK_TOKEN: ❌ НЕ НАЙДЕН")
        await update.message.reply_text("❌ DEEPSEEK_TOKEN не найден в переменных окружения!")
    
    hf = os.getenv("HF_TOKEN")
    if hf:
        print("🔍 HF_TOKEN: ✅ найден")
        await update.message.reply_text("✅ HF_TOKEN найден (резерв)")
    else:
        print("🔍 HF_TOKEN: ❌ НЕ НАЙДЕН")
        await update.message.reply_text("⚠️ HF_TOKEN не найден (резерв недоступен)")
    
    tg = os.getenv("TELEGRAM_TOKEN")
    if tg:
        print("🔍 TELEGRAM_TOKEN: ✅ найден")
    else:
        print("🔍 TELEGRAM_TOKEN: ❌ НЕ НАЙДЕН")

async def btn(update, ctx):
    q = update.callback_query; await q.answer(); d = q.data; uid = q.from_user.id
    
    if d.startswith('f_'):
        now = get_current_time()
        print(f"📅 Прогноз запрошен: {now.strftime('%d.%m.%Y %H:%M:%S')} UTC")
    
    if d == 'forecast':
        if uid in users:
            ctx.user_data['mode'] = 'fp'
            kb = [[InlineKeyboardButton("📅 День", callback_data="f_day"), InlineKeyboardButton("📆 Неделя", callback_data="f_week")],
                  [InlineKeyboardButton("🗓 Месяц", callback_data="f_month")], [InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await q.edit_message_text(f"✨ *{users[uid]['sign']}* ✨\n\nПериод:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await q.edit_message_text(
                "🔮 *Прогноз ИИ*\n\n"
                "Выберите формат ввода:\n\n"
                "📝 *С временем:* `15.05.1990 14 30 Москва`\n"
                "📝 *Без времени:* `15.05.1990 Москва`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 С временем", callback_data="newdata")],
                    [InlineKeyboardButton("📝 Без времени", callback_data="newdata_noon")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]),
                parse_mode='Markdown'
            )
    elif d.startswith('f_'):
        if uid not in users: await q.message.reply_text("Сначала введите данные!"); return
        u = users[uid]; period = {'day':'день','week':'неделю','month':'месяц'}[d[2:]]
        now = get_current_time()
        await q.message.reply_text(f"🔮 Рассчитываю прогноз на {now.strftime('%d.%m.%Y')}...")
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        transits = calc_transits(); aspects = get_aspects(natal)
        sun_sign = natal['Солнце']['sign']; moon_sign = natal['Луна']['sign']; asc_sign = natal['Асцендент']['sign']
        moon_house = None
        for h in natal['houses']:
            if h['sign'] == natal['Луна']['sign']: moon_house = h['house_num']; break
        elements_count = {'Огонь': 0, 'Земля': 0, 'Воздух': 0, 'Вода': 0}
        element_map = {'Овен': 'Огонь', 'Лев': 'Огонь', 'Стрелец': 'Огонь', 'Телец': 'Земля', 'Дева': 'Земля', 'Козерог': 'Земля', 'Близнецы': 'Воздух', 'Весы': 'Воздух', 'Водолей': 'Воздух', 'Рак': 'Вода', 'Скорпион': 'Вода', 'Рыбы': 'Вода'}
        for planet in ['Солнце','Луна','Меркурий','Венера','Марс']:
            if planet in natal:
                elem = element_map.get(natal[planet]['sign'], '')
                if elem: elements_count[elem] += 1
        dominant = max(elements_count, key=elements_count.get)
        
        # Рассчитываем точные транзитные аспекты
        transit_aspects_data = calc_transit_aspects(natal, transits)
        
        astro = f"""
*Астрологические данные на {now.strftime('%d.%m.%Y')}:*

☀ Солнце в {sun_sign} {natal['Солнце']['degree']}°
🌙 Луна в {moon_sign} {natal['Луна']['degree']}° (в {moon_house if moon_house else '?'} доме)
⬆ ASC в {asc_sign}
🔥 Доминирующая стихия: {dominant}

*Транзиты сейчас:*
☀ {transits['Солнце']['sign']} | 🌙 {transits['Луна']['sign']} | ☿ {transits['Меркурий']['sign']}
♀ {transits['Венера']['sign']} | ♂ {transits['Марс']['sign']} | ♃ {transits['Юпитер']['sign']}
♄ {transits['Сатурн']['sign']} | ☊ {transits['Раху']['sign']} | ☋ {transits['Кету']['sign']}

*Натальные аспекты:* {', '.join(aspects[:4]) if aspects else 'нет значимых'}
"""
        
        # Формируем детальное описание точных аспектов
        aspects_text = ""
        if transit_aspects_data:
            aspects_text = "\n*ТОЧНЫЕ ТРАНЗИТНЫЕ АСПЕКТЫ:*\n"
            for i, asp in enumerate(transit_aspects_data[:8]):
                house_info = f" в {asp['transit_house']} доме" if asp['transit_house'] else ""
                aspects_text += f"{asp['symbol']} {asp['transit_planet']} ({asp['transit_sign']}) {asp['aspect']} с {asp['natal_planet']} натальным ({asp['natal_sign']}) — {asp['influence']}{house_info}\n"
                aspects_text += f"   Угол: {asp['angle']}° | Отклонение: {asp['deviation']}° | {asp['direction']}\n"
        else:
            aspects_text = "\n*Точных транзитных аспектов сейчас нет.*\n"
        
        prompt = f"""Ты — профессиональный астролог с 25-летним опытом. Сделай ПРЕДСКАЗАТЕЛЬНЫЙ прогноз на {period} на основе ТОЧНЫХ математических аспектов.

📅 ДАТА ПРОГНОЗА: {now.strftime('%d.%m.%Y')}

⚠️ ВАЖНЕЙШИЕ ПРАВИЛА:
1. Основывай прогноз СТРОГО на предоставленных аспектах
2. Для КАЖДОГО утверждения указывай КОНКРЕТНЫЙ аспект: "потому что транзитный Марс в точном квадрате (90°) к вашему натальному Солнцу..."
3. Учитывай, сходящийся аспект или расходящийся:
   - Сходящийся (усиливается) = событие/тенденция впереди, нарастает
   - Расходящийся (ослабевает) = событие/тенденция уже прошло пик
4. Для каждого аспекта учитывай ДОМА — они показывают СФЕРУ ЖИЗНИ
5. Не пиши общих фраз вроде "будьте осторожны" без привязки к аспекту

СТРУКТУРА ОТВЕТА:
❤️ ЛЮБОВЬ И ОТНОШЕНИЯ (3-4 предложения)
- Какие аспекты влияют: укажи конкретные транзиты к Венере, Луне, управителю 7 дома
- Прогноз: что произойдёт в ближайший {period}

💼 КАРЬЕРА И ФИНАНСЫ (3-4 предложения)
- Какие аспекты влияют: укажи конкретные транзиты к Меркурию, Сатурну, Юпитеру
- Прогноз: какие действия принесут результат

🏃 ЭНЕРГИЯ И ЗДОРОВЬЕ (2-3 предложения)
- Какие аспекты влияют: укажи транзиты к Марсу, Солнцу
- Прогноз: уровень энергии и рекомендации

🌟 ГЛАВНЫЙ СОВЕТ НА {period.upper()} (2-3 предложения)
- Самый важный аспект {period[:4]} и как его использовать

АСТРО-ДАННЫЕ:
{astro}

{aspects_text}

Дай прогноз. 15-20 предложений. Указывай градусы и направление аспектов."""
        
        forecast = ai_client.ask(prompt, max_tokens=700)
        if forecast:
            parts = ai_client.split_message(forecast)
            for i, part in enumerate(parts):
                if i == 0:
                    await update.effective_message.reply_text(f"🌟 *Прогноз на {period}* 🌟\n\n{part}", reply_markup=back_btn(), parse_mode='Markdown')
                else:
                    await update.effective_message.reply_text(part)
        else:
            # Резервная интерпретация с использованием точных аспектов
            fallback = f"""🌟 *Прогноз на {period}* ({now.strftime('%d.%m.%Y')})

"""
            if transit_aspects_data:
                for asp in transit_aspects_data[:4]:
                    house_info = f" в {asp['transit_house']} доме" if asp['transit_house'] else ""
                    fallback += f"{asp['symbol']} {asp['transit_planet']} {asp['aspect']} с {asp['natal_planet']} натальным{house_info} — {asp['influence']}\n"
            
            love_text = {'Овен': 'время страсти и новых знакомств', 'Телец': 'время чувственности и стабильности', 'Близнецы': 'время общения и флирта', 'Рак': 'время глубоких эмоций и заботы', 'Лев': 'время романтики и внимания', 'Дева': 'время практичности в отношениях', 'Весы': 'время гармонии и партнёрства', 'Скорпион': 'время страсти и трансформации', 'Стрелец': 'время приключений и свободы', 'Козерог': 'время серьёзных решений', 'Водолей': 'время необычных знакомств', 'Рыбы': 'время романтики и вдохновения'}
            career_text = {'Овен': 'проявите инициативу, вас заметят', 'Телец': 'сосредоточьтесь на финансах', 'Близнецы': 'делитесь идеями, налаживайте связи', 'Рак': 'работайте в комфортном темпе', 'Лев': 'берите лидерство, вас поддержат', 'Дева': 'время анализа и планирования', 'Весы': 'ищите баланс и партнёрство', 'Скорпион': 'копайте глубже, найдёте скрытое', 'Стрелец': 'расширяйте горизонты, учитесь', 'Козерог': 'стройте долгосрочные планы', 'Водолей': 'внедряйте инновации', 'Рыбы': 'доверьтесь интуиции в делах'}
            
            fallback += f"""
❤️ *Любовь:* {love_text.get(transits['Венера']['sign'], 'благоприятный период')}

💼 *Карьера:* {career_text.get(transits['Марс']['sign'], 'сосредоточьтесь на задачах')}

🌟 *Совет:* Обратите внимание на указанные выше точные аспекты — они показывают главные тенденции {period[:4]}.
"""
            await update.effective_message.reply_text(fallback, reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'natal':
        if uid not in users: 
            await q.edit_message_text(
                "🌟 *Натальная карта*\n\n"
                "Выберите формат ввода:\n\n"
                "📝 *С временем:* `15.05.1990 14 30 Москва`\n"
                "📝 *Без времени:* `15.05.1990 Москва`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 С временем", callback_data="newdata")],
                    [InlineKeyboardButton("📝 Без времени", callback_data="newdata_noon")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]),
                parse_mode='Markdown'
            )
            return
        u = users[uid]
        await q.message.reply_text("🎨 Рассчитываю и рисую карту...")
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        aspects = get_aspects(natal)
        
        asc_sign = natal['Асцендент']['sign']
        asc_deg = natal['Асцендент']['degree']
        sun_sign = natal['Солнце']['sign']
        sun_deg = natal['Солнце']['degree']
        moon_sign = natal['Луна']['sign']
        moon_deg = natal['Луна']['degree']
        mer_sign = natal['Меркурий']['sign']
        mer_deg = natal['Меркурий']['degree']
        ven_sign = natal['Венера']['sign']
        ven_deg = natal['Венера']['degree']
        mar_sign = natal['Марс']['sign']
        mar_deg = natal['Марс']['degree']
        jup_sign = natal['Юпитер']['sign']
        sat_sign = natal['Сатурн']['sign']
        ura_sign = natal['Уран']['sign']
        nep_sign = natal['Нептун']['sign']
        plu_sign = natal['Плутон']['sign']
        rahu_sign = natal['Раху']['sign']
        rahu_deg = natal['Раху']['degree']
        ketu_sign = natal['Кету']['sign']
        ketu_deg = natal['Кету']['degree']
        
        def get_house(planet_lon, houses):
            for i, h in enumerate(houses):
                next_h = houses[(i+1) % 12]
                if h['lon'] <= next_h['lon']:
                    if h['lon'] <= planet_lon < next_h['lon']:
                        return h['house_num']
                else:
                    if planet_lon >= h['lon'] or planet_lon < next_h['lon']:
                        return h['house_num']
            return 1
        
        sun_house = get_house(natal['Солнце']['lon'], natal['houses'])
        moon_house = get_house(natal['Луна']['lon'], natal['houses'])
        mer_house = get_house(natal['Меркурий']['lon'], natal['houses'])
        ven_house = get_house(natal['Венера']['lon'], natal['houses'])
        mar_house = get_house(natal['Марс']['lon'], natal['houses'])
        jup_house = get_house(natal['Юпитер']['lon'], natal['houses'])
        sat_house = get_house(natal['Сатурн']['lon'], natal['houses'])
        rahu_house = get_house(natal['Раху']['lon'], natal['houses'])
        ketu_house = get_house(natal['Кету']['lon'], natal['houses'])
        
        def get_planet_aspects(planet_name):
            planet_aspects = []
            for a in aspects:
                if planet_name in a:
                    planet_aspects.append(a)
            return planet_aspects
        
        sun_aspects = get_planet_aspects('Солнце')
        moon_aspects = get_planet_aspects('Луна')
        mer_aspects = get_planet_aspects('Меркурий')
        ven_aspects = get_planet_aspects('Венера')
        mar_aspects = get_planet_aspects('Марс')
        
        asc_ruler = {
            'Овен': 'Марс', 'Телец': 'Венера', 'Близнецы': 'Меркурий',
            'Рак': 'Луна', 'Лев': 'Солнце', 'Дева': 'Меркурий',
            'Весы': 'Венера', 'Скорпион': 'Плутон', 'Стрелец': 'Юпитер',
            'Козерог': 'Сатурн', 'Водолей': 'Уран', 'Рыбы': 'Нептун',
        }
        ruler_name = asc_ruler.get(asc_sign, '')
        ruler_sign = natal[ruler_name]['sign'] if ruler_name in natal else ''
        ruler_house = get_house(natal[ruler_name]['lon'], natal['houses']) if ruler_name in natal else ''
        
        astro_data = f"""
*НАТАЛЬНАЯ КАРТА*
📍 {u['city'].title()} | 🕐 {u['hour']:02d}:{u['minute']:02d}

*1. АСЦЕНДЕНТ:*
ASC в {asc_sign} {asc_deg}° (1 дом)
Управитель ASC: {ruler_name} в {ruler_sign} ({ruler_house} дом)

*2. ЛУНА:*
🌙 в {moon_sign} {moon_deg}° ({moon_house} дом)
Аспекты Луны: {', '.join(moon_aspects) if moon_aspects else 'нет значимых'}

*3. СОЛНЦЕ:*
☀ в {sun_sign} {sun_deg}° ({sun_house} дом)
Аспекты Солнца: {', '.join(sun_aspects) if sun_aspects else 'нет значимых'}

*4. МЕРКУРИЙ:*
☿ в {mer_sign} {mer_deg}° ({mer_house} дом)
Аспекты Меркурия: {', '.join(mer_aspects) if mer_aspects else 'нет значимых'}

*5. ВЕНЕРА:*
♀ в {ven_sign} {ven_deg}° ({ven_house} дом)
Аспекты Венеры: {', '.join(ven_aspects) if ven_aspects else 'нет значимых'}

*6. МАРС:*
♂ в {mar_sign} {mar_deg}° ({mar_house} дом)
Аспекты Марса: {', '.join(mar_aspects) if mar_aspects else 'нет значимых'}

*7. КАРМИЧЕСКИЕ УЗЛЫ:*
☊ Раху в {rahu_sign} {rahu_deg}° ({rahu_house} дом)
☋ Кету в {ketu_sign} {ketu_deg}° ({ketu_house} дом)

*Другие планеты:*
♃ Юпитер в {jup_sign} ({jup_house} дом)
♄ Сатурн в {sat_sign} ({sat_house} дом)
♅ Уран в {ura_sign}
♆ Нептун в {nep_sign}
♇ Плутон в {plu_sign}
"""
        
        prompt = f"""Ты — профессиональный астролог с 12-летним опытом. Сделай глубокий разбор натальной карты по западной астрологии.

СТРУКТУРА ОТВЕТА (разбей по темам):

🌟 *1. АСЦЕНДЕНТ — как вас воспринимают:*
Раскрой: как человека воспринимают при первой встрече, какие качества показывать чтобы получать интересные события от Вселенной. Формула успеха через знак ASC и дом управителя ASC.

🌙 *2. ЛУНА — эмоции и потребности:*
Раскрой: базовые эмоции и потребности, реакции, через что чувствует комфорт и безопасность. Негативные аспекты — источники напряжения. Позитивные аспекты — возможности.

☀ *3. СОЛНЦЕ — самооценка и таланты:*
Раскрой: в чём особенность и индивидуальность, таланты, как самооценка завязана, что делать для реализации потенциала. Сложности через негативные аспекты.

☿ *4. МЕРКУРИЙ — общение и интеллект:*
Раскрой: стиль общения, навыки коммуникации, как воспринимает информацию, о чём интересно говорить, область интересов.

♀ *5. ВЕНЕРА — любовь и стиль:*
Раскрой: как выражает чувства, язык любви, какой в любви, что нравится, как раскрыть женственность, стиль одежды.

♂ *6. МАРС — мотивация и действия:*
Раскрой: что мотивирует, поведение в кризисе и стрессе, как начать действовать, как ведёт себя в конкуренции.

☊ *7. КАРМИЧЕСКИЕ УЗЛЫ — предназначение:*
Раскрой: куда двигаться по Северному узлу, какие качества нарабатывать. Что оставить в прошлом по Южному узлу.

ПРАВИЛА:
- Основывайся ТОЛЬКО на данных карты
- Пиши развёрнуто, каждый раздел 4-6 предложений
- Указывай причину: "потому что Марс в Овне..."
- Используй профессиональные термины с пояснениями
- Для негативных аспектов давай рекомендации как проработать
- Для позитивных — как использовать

ДАННЫЕ КАРТЫ:
{astro_data}

Сделай полный разбор. 30-40 предложений. Используй эмодзи."""
        
        forecast = ai_client.ask(prompt, max_tokens=1500)
        
        birth_time_str = f"{u['hour']:02d}:{u['minute']:02d}"
        img = draw_natal_chart_pro(natal, u['city'], birth_time_str)
        await update.effective_message.reply_photo(photo=img)
        
        if forecast:
            parts = ai_client.split_message(forecast)
            for i, part in enumerate(parts):
                await update.effective_message.reply_text(
                    part,
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]]) if i == len(parts)-1 else None,
                    parse_mode='Markdown'
                )
        else:
            basic_text = f"""🌟 *Натальная карта*
📍 {u['city'].title()} | 🕐 {u['hour']:02d}:{u['minute']:02d}

*Планеты в знаках:*
☀ Солнце: *{sun_sign}* {sun_deg}° ({sun_house} дом)
🌙 Луна: *{moon_sign}* {moon_deg}° ({moon_house} дом)
☿ Меркурий: *{mer_sign}* {mer_deg}° ({mer_house} дом)
♀ Венера: *{ven_sign}* {ven_deg}° ({ven_house} дом)
♂ Марс: *{mar_sign}* {mar_deg}° ({mar_house} дом)
♃ Юпитер: *{jup_sign}* ({jup_house} дом)
♄ Сатурн: *{sat_sign}* ({sat_house} дом)
♅ Уран: *{ura_sign}*
♆ Нептун: *{nep_sign}*
♇ Плутон: *{plu_sign}*
☊ Раху: *{rahu_sign}* ({rahu_house} дом)
☋ Кету: *{ketu_sign}* ({ketu_house} дом)

⬆ ASC: *{asc_sign}* | Управитель: {ruler_name} в {ruler_sign}

*Аспекты:* {', '.join(aspects[:6]) if aspects else 'нет значимых'}

⚠️ Подробная интерпретация временно недоступна. Попробуйте позже."""
            await update.effective_message.reply_text(
                basic_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]]),
                parse_mode='Markdown'
            )
    elif d == 'houses':
        if uid not in users: 
            await q.edit_message_text(
                "🏠 *Дома гороскопа*\n\n"
                "Для расчёта домов нужно точное время рождения.\n\n"
                "📝 *Формат:* `15.05.1990 14 30 Москва`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Ввести данные", callback_data="newdata")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]),
                parse_mode='Markdown'
            )
            return
        u = users[uid]; natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        text = f"🏠 *Дома гороскопа*\n📍 {u['city'].title()}\n🕐 {u['hour']:02d}:{u['minute']:02d} (местное)\n\n"
        for house in natal['houses']: text += f"*{house['house_num']} дом*: {SIGN_EMOJI.get(house['sign'],'')} {house['sign']} {house['degree']}°\n"
        text += f"\n⬆ Асцендент: *{natal['Асцендент']['sign']}* {natal['Асцендент']['degree']}°"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'transits':
        transits = calc_transits()
        now = get_current_time()
        text = f"🪐 *Транзиты*\n📅 {now.strftime('%d.%m.%Y %H:%M')} UTC\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Раху','Кету']:
            if p in transits: text += f"{SIGN_EMOJI.get(transits[p]['sign'],'')} {p}: *{transits[p]['sign']}* {transits[p]['degree']}°\n"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'compat':
        ctx.user_data['mode'] = 'compat'
        await q.edit_message_text("💑 Два знака: *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'moon':
        transits = calc_transits()
        now = get_current_time()
        phase = now.day % 8
        phases = {0:"🌑 Новолуние",1:"🌒",2:"🌓",3:"🌔",4:"🌕 Полнолуние",5:"🌖",6:"🌗",7:"🌘"}
        text = f"🌙 *Луна*\n📅 {now.strftime('%d.%m.%Y')}\n\nФаза: {phases.get(phase, '🌑')}\n"
        if 'Луна' in transits: text += f"Знак: *{transits['Луна']['sign']}* {transits['Луна']['degree']}°"
        if 'Раху' in transits:
            text += f"\n☊ Раху: *{transits['Раху']['sign']}* {transits['Раху']['degree']}°"
            text += f"\n☋ Кету: *{transits['Кету']['sign']}* {transits['Кету']['degree']}°"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'daily':
        now = get_current_time()
        text = f"📅 *Сегодня* ({now.strftime('%d.%m.%Y')})\n\n"
        transits = calc_transits()
        for sign in SIGN_NAMES:
            text += f"{SIGN_EMOJI.get(sign,'')} *{sign}*: "
            if 'Солнце' in transits and sign == transits['Солнце']['sign']: text += "☀️ Солнце в знаке!\n"
            elif 'Луна' in transits and sign == transits['Луна']['sign']: text += "🌙 Луна в знаке\n"
            elif 'Раху' in transits and sign == transits['Раху']['sign']: text += "☊ Раху в знаке\n"
            elif 'Кету' in transits and sign == transits['Кету']['sign']: text += "☋ Кету в знаке\n"
            else: text += "✨ Хороший день\n"
        await q.edit_message_text(text[:4000], reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'help':
        await help_command(update, ctx)
    elif d == 'newdata':
        ctx.user_data['mode'] = 'newdata'
        await q.edit_message_text("📝 *Введите данные:*\n\n*С временем:* `ДД.ММ.ГГГГ ЧЧ ММ Город`\nПример: `15.05.1990 14 30 Москва`", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'newdata_noon':
        ctx.user_data['mode'] = 'newdata_noon'
        await q.edit_message_text("📝 *Введите дату и город:*\n\nФормат: `ДД.ММ.ГГГГ Город`\nПример: `15.05.1990 Москва`\n\nВремя будет установлено на 12:00", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'newdata_natal':
        ctx.user_data['mode'] = 'newdata'
        await q.edit_message_text("📝 *Введите новые данные:*\n\n📝 *С временем:* `15.05.1990 14 30 Москва`\n📝 *Без времени:* `15.05.1990 Москва`", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'back':
        ctx.user_data['mode'] = ''
        await q.edit_message_text("🌟 *Меню*", reply_markup=menu_btn(), parse_mode='Markdown')

async def msg(update, ctx):
    t = update.message.text.strip(); m = ctx.user_data.get('mode',''); uid = update.effective_user.id
    if m in ['newdata', 'newdata_noon']: ctx.user_data['mode'] = ''
    if m == 'compat':
        parts = t.title().split()
        if len(parts)==2 and parts[0] in SIGN_NAMES and parts[1] in SIGN_NAMES:
            prompt = f"Совместимость {parts[0]} и {parts[1]}. Процент и 2-3 предложения."
            fc = ai_client.ask(prompt) or "70% — Хорошая совместимость"
            ctx.user_data['mode'] = ''
            await update.message.reply_text(f"💑 *{parts[0]} + {parts[1]}*\n\n{fc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💑 Ещё", callback_data="compat"),InlineKeyboardButton("🔙 Назад", callback_data="back")]]), parse_mode='Markdown')
            return
        await update.message.reply_text("❌ *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')
        return
    try:
        parts = t.split()
        if len(parts) >= 3:
            date_part = parts[0]; day, month, year = map(int, date_part.split('.'))
            hour = int(parts[1]) if len(parts) > 1 else 12; minute = int(parts[2]) if len(parts) > 2 else 0
            city_str = ' '.join(parts[3:]) if len(parts) > 3 else 'москва'
        elif '.' in t and len(t.split('.')) == 3 and ' ' in t:
            parts_dot = t.split()
            date_part = parts_dot[0]
            day, month, year = map(int, date_part.split('.'))
            hour, minute = 12, 0
            city_str = ' '.join(parts_dot[1:]) if len(parts_dot) > 1 else 'москва'
        elif '.' in t and len(t.split('.')) == 3:
            day, month, year = map(int, t.split('.')); hour, minute = 12, 0; city_str = 'москва'
        else: raise ValueError
        
        validate_date(day, month, year)
        validate_time(hour, minute)
        
        lat, lon, city_name = parse_city(city_str); sign = get_zodiac_sign(day, month)
        users[uid] = {'sign':sign,'day':day,'month':month,'year':year,'hour':hour,'minute':minute,'lat':lat,'lon':lon,'city':city_name}
        save_users()
        
        kb = [[InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast")],
              [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],
              [InlineKeyboardButton("🏠 Дома гороскопа", callback_data="houses")],
              [InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
              [InlineKeyboardButton("🔄 Новые данные", callback_data="newdata_natal")],
              [InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await update.message.reply_text(f"✨ *{sign}* ✨\n📅 {day:02d}.{month:02d}.{year}\n🕐 {hour:02d}:{minute:02d}\n📍 {city_name.title()}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except ValueError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}\n\nФорматы:\n• *15.05.1990*\n• *15.05.1990 14 30*\n• *15.05.1990 14 30 Москва*\n• *15.05.1990 Москва*", reply_markup=back_btn(), parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text("❌ Произошла ошибка.", reply_markup=back_btn(), parse_mode='Markdown')

def main():
    TOKEN = os.getenv('TELEGRAM_TOKEN')
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CommandHandler('logtest', logtest))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    threading.Thread(target=run_keepalive, daemon=True).start()
    print("🚀 Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
