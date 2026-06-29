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
import time
import sys
import os as _os

# ========== ЗАЩИТА ОТ ДВОЙНОГО ЗАПУСКА ==========
LOCK_FILE = '/tmp/astro_bot.pid'

def check_lock():
    if _os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                old_pid = int(f.read().strip())
            try:
                _os.kill(old_pid, 0)
                print(f"❌ Бот уже запущен (PID: {old_pid})! Выходим...")
                sys.exit(0)
            except OSError:
                _os.remove(LOCK_FILE)
        except:
            _os.remove(LOCK_FILE)
    
    with open(LOCK_FILE, 'w') as f:
        f.write(str(_os.getpid()))
    print(f"🔒 Блокировка (PID: {_os.getpid()})")

def remove_lock():
    try:
        if _os.path.exists(LOCK_FILE):
            _os.remove(LOCK_FILE)
    except:
        pass

check_lock()
atexit.register(remove_lock)
# ========== КОНЕЦ ЗАЩИТЫ ==========

# ========== ВАЛИДАЦИЯ ==========
def validate_date(day: int, month: int, year: int):
    """Проверяет корректность даты"""
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
    """Проверяет корректность времени"""
    if not (0 <= hour <= 23):
        raise ValueError(f"Часы должны быть 0-23, получено: {hour}")
    if not (0 <= minute <= 59):
        raise ValueError(f"Минуты должны быть 0-59, получено: {minute}")
    return True
# ========== КОНЕЦ ВАЛИДАЦИИ ==========

# ========== AI КЛИЕНТ ==========
class AIClient:
    """Надёжный клиент для AI с повторными попытками"""
    
    def __init__(self, api_url, token, max_retries=3, timeout=40):
        self.api_url = api_url
        self.headers = {"Authorization": f"Bearer {token}"}
        self.max_retries = max_retries
        self.timeout = timeout
    
    def ask(self, prompt, max_tokens=400):
        """Отправляет запрос с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=self.headers,
                    json={"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}},
                    timeout=self.timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list) and data:
                        text = data[0].get("generated_text", "").strip()
                        if text and len(text) > 10:
                            print(f"✅ AI ответ: {len(text)} символов")
                            return text
                
                elif response.status_code == 503:
                    wait = 10 * (attempt + 1)
                    print(f"⏳ Модель загружается, ждём {wait}с...")
                    time.sleep(wait)
                elif response.status_code == 429:
                    wait = 20 * (attempt + 1)
                    print(f"⏳ Rate limit, ждём {wait}с...")
                    time.sleep(wait)
                else:
                    print(f"❌ Ошибка API: {response.status_code}")
                    if attempt < self.max_retries - 1:
                        time.sleep(5)
            
            except requests.Timeout:
                print(f"⏱ Таймаут (попытка {attempt+1}/{self.max_retries})")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
            except Exception as e:
                print(f"❌ Ошибка: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(5)
        
        print("❌ Все попытки исчерпаны")
        return None
    
    @staticmethod
    def split_message(text, max_length=4000):
        """Разбивает длинное сообщение на части"""
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
    """Сохраняет пользователей в JSON"""
    try:
        os.makedirs('data', exist_ok=True)
        data_to_save = {str(k): v for k, v in users.items()}
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        print(f"✅ Сохранено: {len(users)} пользователей")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def load_users():
    """Загружает пользователей из JSON"""
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

HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
ai_client = AIClient(API_URL, HF_TOKEN)

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

# ========== ЗАГРУЗКА ПОЛЬЗОВАТЕЛЕЙ ==========
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
        natal['Раху'] = {
            'sign': sign_from_lon(rahu_lon), 
            'degree': degree_in_sign(rahu_lon), 
            'lon': rahu_lon,
            'retro': True
        }
        ketu_lon = (rahu_lon + 180) % 360
        natal['Кету'] = {
            'sign': sign_from_lon(ketu_lon), 
            'degree': degree_in_sign(ketu_lon), 
            'lon': ketu_lon,
            'retro': True
        }
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

def calc_transits():
    now = datetime.utcnow()
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
    """Профессиональная астрологическая карта с ASC слева (9 часов)"""
    
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
        ax.annotate(f"{SIGN_EMOJI.get(sign, '')}",
                    xy=(mid_angle, 1.16), ha='center', va='center',
                    fontsize=10, color=color, weight='bold')
        ax.annotate(sign,
                    xy=(mid_angle, 1.10), ha='center', va='center',
                    fontsize=6.5, color=color, weight='bold')
    
    ax.plot(np.linspace(0, 2*np.pi, 300), [1.05]*300, color='#cccccc', linewidth=1, alpha=0.5)
    
    theta_bg = np.linspace(0, 2*np.pi, 300)
    ax.fill_between(theta_bg, 0.90, 1.05, color='#fafafa', alpha=0.5)
    ax.plot(np.linspace(0, 2*np.pi, 300), [0.90]*300, color='#cccccc', linewidth=1, alpha=0.5)
    
    planet_symbols = {
        'Солнце': '☉', 'Луна': '☽', 'Меркурий': '☿', 'Венера': '♀',
        'Марс': '♂', 'Юпитер': '♃', 'Сатурн': '♄', 'Уран': '♅',
        'Нептун': '♆', 'Плутон': '♇',
        'Раху': '☊', 'Кету': '☋',
    }
    
    planet_radii = {
        'Плутон': 0.92, 'Нептун': 0.93, 'Уран': 0.94,
        'Сатурн': 0.95, 'Юпитер': 0.96, 'Марс': 0.97,
        'Венера': 0.98, 'Меркурий': 1.00, 'Луна': 1.02, 'Солнце': 1.04,
        'Раху': 0.99, 'Кету': 0.91,
    }
    
    planet_positions = {}
    
    for name, data in natal.items():
        if name in ['houses', 'Асцендент', 'MC', 'Десцендент', 'IC']:
            continue
        
        lon = data['lon']
        degree_in_this_sign = data['degree']
        sign_index = SIGN_NAMES.index(data['sign'])
        sign_start_lon = sign_index * 30
        angle = np.radians(sign_start_lon + degree_in_this_sign) + offset
        
        symbol = planet_symbols.get(name, '')
        r = planet_radii.get(name, 0.97)
        planet_positions[name] = (angle, r)
        
        if name == 'Раху':
            color = '#8e44ad'
        elif name == 'Кету':
            color = '#e67e22'
        else:
            color = '#1a1a1a'
        
        ax.annotate(symbol, xy=(angle, r), ha='center', va='center',
                    fontsize=13, color=color, weight='bold', zorder=9)
        ax.annotate(f"{degree_in_this_sign}°",
                    xy=(angle, r + 0.02), ha='center', va='bottom',
                    fontsize=5.5, color=color, weight='bold')
    
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
            
            ax.plot([ang1, ang2], [r1, r2], color=color, linewidth=lw, 
                    alpha=alpha, linestyle=linestyle, zorder=1)
    
    for i, house in enumerate(natal.get('houses', [])):
        house_lon = house['lon']
        house_angle = np.radians(house_lon) + offset
        
        if house['house_num'] in [1, 4, 7, 10]:
            linewidth, alpha, color = 2.5, 0.9, '#e74c3c'
        else:
            linewidth, alpha, color = 1.2, 0.7, '#1a1a1a'
        
        ax.plot([house_angle, house_angle], [0.90, 1.20], color=color, 
                linewidth=linewidth, alpha=alpha, linestyle='-')
        
        next_house = natal['houses'][(i+1) % 12]
        next_house_angle = np.radians(next_house['lon']) + offset
        
        angle_diff = (next_house_angle - house_angle) % (2 * np.pi)
        mid_angle = (house_angle + angle_diff / 2) % (2 * np.pi)
        
        sign_name = house['sign']
        sign_deg = house['degree']
        
        ax.annotate(f"{sign_deg}° {SIGN_EMOJI.get(sign_name, '')}",
                    xy=(house_angle, 1.24), ha='center', va='center',
                    fontsize=5.5, color='#555')
        
        ax.annotate(str(house['house_num']),
                    xy=(mid_angle, 1.30), ha='center', va='center',
                    fontsize=10, color='#1a1a1a', weight='bold',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', 
                             edgecolor='#cccccc', alpha=0.9))
        
        if house['house_num'] == 1:
            ax.annotate('ASC', xy=(house_angle, 1.36), ha='center', va='center',
                        fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 4:
            ax.annotate('IC', xy=(house_angle, 1.36), ha='center', va='center',
                        fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 7:
            ax.annotate('DSC', xy=(house_angle, 1.36), ha='center', va='center',
                        fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 10:
            ax.annotate('MC', xy=(house_angle, 1.36), ha='center', va='center',
                        fontsize=10, color='#e74c3c', weight='bold')
    
    title = 'НАТАЛЬНАЯ КАРТА'
    if city_name:
        title += f' • {city_name.title()}'
    if birth_time:
        title += f' • {birth_time}'
    
    fig.text(0.5, 0.97, title, ha='center', va='top',
             fontsize=16, color='#1a1a1a', weight='bold', fontfamily='serif')
    
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

✨ *Возможности:*
• 🌟 Натальная карта
• 🔮 Прогнозы по реальным транзитам
• 💞 Совместимость
• 🌙 Лунный календарь
• 📅 Ежедневный гороскоп

🌍 100+ городов | 🎯 Математическая точность
"""
    await update.message.reply_text(
        welcome_text,
        reply_markup=menu_btn(),
        parse_mode='Markdown'
    )

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
• 🤖 AI-прогнозы (Mistral-7B)
• 💾 Данные сохраняются
"""
    await update.message.reply_text(
        help_text,
        parse_mode='Markdown'
    )

async def btn(update, ctx):
    q = update.callback_query; await q.answer(); d = q.data; uid = q.from_user.id
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
                "📝 *Без времени:* `15.05.1990`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Ввести с временем", callback_data="newdata")],
                    [InlineKeyboardButton("📝 Ввести без времени", callback_data="newdata_noon")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]),
                parse_mode='Markdown'
            )
    elif d.startswith('f_'):
        if uid not in users: await q.message.reply_text("Сначала введите данные!"); return
        u = users[uid]; period = {'day':'день','week':'неделю','month':'месяц'}[d[2:]]
        await q.message.reply_text("🔮 Рассчитываю и генерирую прогноз...")
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        transits = calc_transits(); aspects = get_aspects(natal)
        astro = f"Карта: ☀ {natal['Солнце']['sign']} {natal['Солнце']['degree']}°, 🌙 {natal['Луна']['sign']} {natal['Луна']['degree']}°, ASC {natal['Асцендент']['sign']}, MC {natal['MC']['sign']}\n"
        astro += f"Транзиты: ☀ {transits['Солнце']['sign']}, 🌙 {transits['Луна']['sign']}, ♂ {transits['Марс']['sign']}\n"
        if 'Раху' in natal and 'Раху' in transits:
            astro += f"Узлы: ☊ Раху в {natal['Раху']['sign']}, транзит в {transits['Раху']['sign']}\n"
        if aspects: astro += f"Аспекты: {', '.join(aspects[:3])}"
        prompt = f"Ты астролог. Прогноз на {period}:\n{astro}\n\n6-8 предложений по сферам: любовь, карьера, здоровье, совет. Учти влияние Лунных узлов Раху и Кету. С эмодзи."
        forecast = ai_client.ask(prompt)
        if forecast:
            parts = ai_client.split_message(forecast)
            for i, part in enumerate(parts):
                if i == 0:
                    await update.effective_message.reply_text(f"🌟 *Прогноз на {period}* 🌟\n\n{part}", reply_markup=back_btn(), parse_mode='Markdown')
                else:
                    await update.effective_message.reply_text(part)
        else:
            await update.effective_message.reply_text(f"✨ Прогноз на {period}\n\n❤️ Любовь: благоприятный период\n💼 Карьера: новые возможности\n🏃 Здоровье: всё стабильно\n\n🌟 Совет: доверяйте интуиции", reply_markup=back_btn())
    elif d == 'natal':
        if uid not in users: 
            await q.edit_message_text(
                "🌟 *Натальная карта*\n\n"
                "Выберите формат ввода:\n\n"
                "📝 *С временем:* `15.05.1990 14 30 Москва`\n"
                "📝 *Без времени:* `15.05.1990`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Ввести с временем", callback_data="newdata")],
                    [InlineKeyboardButton("📝 Ввести без времени", callback_data="newdata_noon")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]),
                parse_mode='Markdown'
            )
            return
        u = users[uid]
        await q.message.reply_text("🎨 Рассчитываю и рисую карту...")
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'],
                           u['lat'], u['lon'], u['city'])
        aspects = get_aspects(natal)
        
        text = f"🌟 *Натальная карта*\n📍 {u['city'].title()}\n🕐 {u['hour']:02d}:{u['minute']:02d} (местное)\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Уран','Нептун','Плутон','Раху','Кету']:
            if p in natal: 
                retro = " ℞" if natal[p].get('retro') else ""
                text += f"{SIGN_EMOJI.get(natal[p]['sign'],'')} {p}: *{natal[p]['sign']}* {natal[p]['degree']}°{retro}\n"
        if aspects:
            text += f"\n🔹 *Аспекты:*\n"
            for a in aspects[:8]: text += f"• {a}\n"
        
        birth_time_str = f"{u['hour']:02d}:{u['minute']:02d}"
        img = draw_natal_chart_pro(natal, u['city'], birth_time_str)
        
        await update.effective_message.reply_photo(photo=img)
        await update.effective_message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]),
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
        text = f"🪐 *Транзиты*\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Раху','Кету']:
            if p in transits: text += f"{SIGN_EMOJI.get(transits[p]['sign'],'')} {p}: *{transits[p]['sign']}* {transits[p]['degree']}°\n"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'compat':
        ctx.user_data['mode'] = 'compat'
        await q.edit_message_text("💑 Два знака: *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'moon':
        transits = calc_transits(); phase = datetime.now().day % 8
        phases = {0:"🌑 Новолуние",1:"🌒",2:"🌓",3:"🌔",4:"🌕 Полнолуние",5:"🌖",6:"🌗",7:"🌘"}
        text = f"🌙 *Луна*\n\nФаза: {phases.get(phase, '🌑')}\n"
        if 'Луна' in transits: text += f"Знак: *{transits['Луна']['sign']}* {transits['Луна']['degree']}°"
        if 'Раху' in transits:
            text += f"\n☊ Раху: *{transits['Раху']['sign']}* {transits['Раху']['degree']}°"
            text += f"\n☋ Кету: *{transits['Кету']['sign']}* {transits['Кету']['degree']}°"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'daily':
        text = "📅 *Сегодня*\n\n"; transits = calc_transits()
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
        await q.edit_message_text(
            "📝 *Введите данные:*\n\n"
            "*С временем:* `ДД.ММ.ГГГГ ЧЧ ММ Город`\n"
            "Пример: `15.05.1990 14 30 Москва`",
            reply_markup=back_btn(),
            parse_mode='Markdown'
        )
    elif d == 'newdata_noon':
        ctx.user_data['mode'] = 'newdata_noon'
        await q.edit_message_text(
            "📝 *Введите дату рождения:*\n\n"
            "Формат: `ДД.ММ.ГГГГ`\n"
            "Пример: `15.05.1990`\n\n"
            "Время будет установлено на 12:00, город — Москва",
            reply_markup=back_btn(),
            parse_mode='Markdown'
        )
    elif d == 'newdata_natal':
        ctx.user_data['mode'] = 'newdata'
        await q.edit_message_text(
            "📝 *Введите новые данные:*\n\n"
            "📝 *С временем:* `15.05.1990 14 30 Москва`\n"
            "📝 *Без времени:* `15.05.1990`",
            reply_markup=back_btn(),
            parse_mode='Markdown'
        )
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
        await update.message.reply_text(f"❌ Ошибка: {e}\n\nФорматы:\n• *15.05.1990*\n• *15.05.1990 14 30*\n• *15.05.1990 14 30 Москва*\n• *15.05.1990 14 30 Нью-Йорк*", reply_markup=back_btn(), parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка: {e}")
        await update.message.reply_text("❌ Произошла ошибка. Попробуйте другой формат:\n• *15.05.1990*\n• *15.05.1990 14 30*\n• *15.05.1990 14 30 Москва*", reply_markup=back_btn(), parse_mode='Markdown')

def main():
    TOKEN = os.getenv('TELEGRAM_TOKEN')
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    
    threading.Thread(target=run_keepalive, daemon=True).start()
    
    print("🚀 Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
