import time
import sys
import os as _os
import socket
import random

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

# ========== ЭМОДЗИ КОТА-АСТРОЛОГА ==========
CAT_EMOJI = ['🐱', '😺', '😸', '😻', '😼', '😽', '🙀', '😿', '😾', '🐈', '🐈‍⬛', '✨🐱', '🐱✨', '🔮🐱', '🐱🔮', '🌟🐱', '🐱🌟']

def cat_emoji():
    return random.choice(CAT_EMOJI)

# ========== ID АДМИНА ==========
ADMIN_ID = 870114986

# ========== URL ДОКУМЕНТОВ ==========
PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-07-03-19"
OFERTA_URL = "https://telegra.ph/DOGOVOR-OFERTA-NA-OKAZANIE-USLUG-07-03"
CONSENT_URL = "https://telegra.ph/SOGLASIE-NA-OBRABOTKU-PERSONALNYH-DANNYH-07-03-6"

# ========== СИСТЕМНЫЙ ПРОМПТ (компактный) ==========
SYSTEM_PROMPT = "Ты — астролог. Нейтральные обращения. Отвечай всегда. Основывайся только на данных. Структура: Любовь, Карьера, Энергия, Совет. Упоминай планеты и аспекты."

# ========== ВАЛИДАЦИЯ ==========
def validate_date(day, month, year):
    if year < 1900 or year > datetime.now().year:
        raise ValueError(f"Год: 1900-{datetime.now().year}")
    if not (1 <= month <= 12):
        raise ValueError("Месяц: 1-12")
    if not (1 <= day <= 31):
        raise ValueError("День: 1-31")
    datetime(year, month, day)
    return True

def validate_time(hour, minute):
    if not (0 <= hour <= 23):
        raise ValueError("Часы: 0-23")
    if not (0 <= minute <= 59):
        raise ValueError("Минуты: 0-59")
    return True

# ========== AI КЛИЕНТ ==========
class AIClient:
    def __init__(self, deepseek_token=None, hf_token=None):
        self.deepseek_token = deepseek_token
        self.hf_token = hf_token
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        self.hf_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
        self.max_retries = 2
        self.timeout = 30

    def ask(self, prompt, max_tokens=300):
        if self.deepseek_token:
            result = self._ask_deepseek(prompt, max_tokens)
            if result: return result
        if self.hf_token:
            return self._ask_huggingface(prompt, max_tokens)
        return None

    def _ask_deepseek(self, prompt, max_tokens):
        headers = {"Authorization": f"Bearer {self.deepseek_token}", "Content-Type": "application/json"}
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.5
        }
        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.deepseek_url, headers=headers, json=payload, timeout=self.timeout)
                if response.status_code == 200:
                    data = response.json()
                    text = data["choices"][0]["message"]["content"].strip()
                    if text and len(text) > 10: return text
                elif response.status_code == 429:
                    time.sleep(15 * (attempt + 1))
                else:
                    time.sleep(3)
            except: time.sleep(3)
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
                        if text and len(text) > 10: return text
                elif response.status_code in [503, 429]:
                    time.sleep(15)
                else: time.sleep(3)
            except: time.sleep(3)
        return None

    @staticmethod
    def split_message(text, max_length=4000):
        parts = []
        while len(text) > max_length:
            split_pos = text.rfind('\n', 0, max_length)
            if split_pos == -1: split_pos = text.rfind('. ', 0, max_length)
            if split_pos == -1: split_pos = text.rfind(' ', 0, max_length)
            if split_pos == -1: split_pos = max_length
            parts.append(text[:split_pos].strip())
            text = text[split_pos:].strip()
        if text: parts.append(text)
        return parts

# ========== JSON ХРАНИЛИЩЕ ==========
USERS_FILE = 'data/users.json'

def save_users():
    try:
        os.makedirs('data', exist_ok=True)
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump({str(k): v for k, v in users.items()}, f, ensure_ascii=False, indent=2)
    except: pass

def load_users():
    global users
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = {int(k): v for k, v in json.load(f).items()}
        else: users = {}
    except: users = {}

load_dotenv()
DEEPSEEK_TOKEN = os.getenv("DEEPSEEK_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
ai_client = AIClient(deepseek_token=DEEPSEEK_TOKEN, hf_token=HF_TOKEN)

# ===== KEEP-ALIVE =====
class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, format, *args): pass

def run_keepalive():
    port = int(os.getenv("PORT", 10000))
    HTTPServer(('0.0.0.0', port), PingHandler).serve_forever()

swe.set_ephe_path(None)

SIGN_NAMES = ['Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева', 'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы']
SIGN_EMOJI = {'Овен':'♈','Телец':'♉','Близнецы':'♊','Рак':'♋','Лев':'♌','Дева':'♍','Весы':'♎','Скорпион':'♏','Стрелец':'♐','Козерог':'♑','Водолей':'♒','Рыбы':'♓'}

ZODIAC_SIGNS = {
    'Овен': (3,21,4,19), 'Телец': (4,20,5,20), 'Близнецы': (5,21,6,20),
    'Рак': (6,21,7,22), 'Лев': (7,23,8,22), 'Дева': (8,23,9,22),
    'Весы': (9,23,10,22), 'Скорпион': (10,23,11,21), 'Стрелец': (11,22,12,21),
    'Козерог': (12,22,1,19), 'Водолей': (1,20,2,18), 'Рыбы': (2,19,3,20)
}

# ========== ПРАВИТЕЛИ ЗНАКОВ ==========
SIGN_RULERS = {
    'Овен': 'Марс', 'Телец': 'Венера', 'Близнецы': 'Меркурий',
    'Рак': 'Луна', 'Лев': 'Солнце', 'Дева': 'Меркурий',
    'Весы': 'Венера', 'Скорпион': 'Марс', 'Стрелец': 'Юпитер',
    'Козерог': 'Сатурн', 'Водолей': 'Уран', 'Рыбы': 'Нептун'
}

CITIES = {
    'москва': (55.75, 37.62), 'мск': (55.75, 37.62),
    'питер': (59.93, 30.33), 'спб': (59.93, 30.33),
    'екатеринбург': (56.84, 60.65), 'екб': (56.84, 60.65),
    'новосибирск': (55.03, 82.92), 'нск': (55.03, 82.92),
    'казань': (55.79, 49.12), 'сочи': (43.59, 39.73),
    'владивосток': (43.12, 131.89), 'краснодар': (45.04, 38.98),
    'лондон': (51.51, -0.13), 'париж': (48.86, 2.35), 'берлин': (52.52, 13.40),
    'нью-йорк': (40.71, -74.00), 'токио': (35.68, 139.76), 'дубай': (25.20, 55.27),
}

CITY_TIMEZONES = {
    'москва': 3, 'мск': 3, 'питер': 3, 'спб': 3,
    'екатеринбург': 5, 'екб': 5, 'новосибирск': 7, 'нск': 7,
    'казань': 3, 'сочи': 3, 'владивосток': 10, 'краснодар': 3,
    'лондон': 0, 'париж': 1, 'берлин': 1, 'нью-йорк': -5, 'токио': 9, 'дубай': 4,
}

PLANETS = {'Солнце': swe.SUN, 'Луна': swe.MOON, 'Меркурий': swe.MERCURY,
           'Венера': swe.VENUS, 'Марс': swe.MARS, 'Юпитер': swe.JUPITER,
           'Сатурн': swe.SATURN, 'Уран': swe.URANUS, 'Нептун': swe.NEPTUNE, 'Плутон': swe.PLUTO}

if os.path.exists(USERS_FILE):
    try:
        with open(USERS_FILE) as f:
            if any('day' not in d for d in json.load(f).values()):
                os.remove(USERS_FILE)
    except: os.path.exists(USERS_FILE) and os.remove(USERS_FILE)

load_users()
atexit.register(save_users)

def get_zodiac_sign(day, month):
    for sign, (sm, sd, em, ed) in ZODIAC_SIGNS.items():
        if (month == sm and day >= sd) or (month == em and day <= ed): return sign
    return 'Козерог'

def sign_from_lon(lon): return SIGN_NAMES[int(lon // 30)]
def degree_in_sign(lon): return int(lon % 30)

def get_timezone(city_name, lat=None, lon=None):
    city_key = city_name.lower().strip()
    if city_key in CITY_TIMEZONES: return CITY_TIMEZONES[city_key]
    if lon is not None: return round(lon / 15.0)
    return 3

def calc_natal(day, month, year, hour=12, minute=0, lat=55.75, lon=37.62, city_name='москва', house_system=b'P'):
    utc_offset = get_timezone(city_name, lat, lon)
    utc_hour = hour - utc_offset
    if utc_hour < 0: utc_hour += 24
    elif utc_hour >= 24: utc_hour -= 24
    jd = swe.julday(year, month, day, utc_hour + minute / 60.0)
    natal = {}
    for name, pid in PLANETS.items():
        try:
            result, _ = swe.calc_ut(jd, pid)
            lon_deg = result[0] if isinstance(result, tuple) else result[0]
            speed = result[3] if len(result) > 3 else 0
            natal[name] = {'sign': sign_from_lon(lon_deg), 'degree': degree_in_sign(lon_deg), 'lon': lon_deg, 'retro': speed < 0}
        except: continue
    
    try:
        rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
        natal['Раху'] = {'sign': sign_from_lon(rahu_lon), 'degree': degree_in_sign(rahu_lon), 'lon': rahu_lon}
        natal['Кету'] = {'sign': sign_from_lon((rahu_lon + 180) % 360), 'degree': degree_in_sign((rahu_lon + 180) % 360), 'lon': (rahu_lon + 180) % 360}
    except: pass
    
    if abs(lat) > 66.5: house_system = b'W'
    try: houses, ascmc = swe.houses(jd, lat, lon, house_system)
    except: houses, ascmc = swe.houses(jd, lat, lon, b'W')
    
    natal['Асцендент'] = {'sign': sign_from_lon(ascmc[0]), 'degree': degree_in_sign(ascmc[0]), 'lon': ascmc[0]}
    natal['MC'] = {'sign': sign_from_lon(ascmc[1]), 'degree': degree_in_sign(ascmc[1]), 'lon': ascmc[1]}
    natal['houses'] = [{'house_num': i+1, 'sign': sign_from_lon(houses[i]), 'degree': degree_in_sign(houses[i]), 'lon': houses[i]} for i in range(12)]
    return natal

def get_current_time():
    try:
        resp = requests.get("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=3)
        if resp.status_code == 200:
            return datetime.fromisoformat(resp.json()['datetime'].replace('Z', '+00:00')).replace(tzinfo=None)
    except: pass
    return datetime.utcnow()

def calc_transits():
    now = get_current_time()
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
    transits = {}
    for name, pid in PLANETS.items():
        try:
            result = swe.calc_ut(jd, pid)
            lon_deg = result[0] if isinstance(result, tuple) else result[0]
            speed = result[3] if len(result) > 3 else 0
            transits[name] = {'sign': sign_from_lon(lon_deg), 'degree': degree_in_sign(lon_deg), 'lon': lon_deg, 'retro': speed < 0}
        except: continue
    try:
        rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
        transits['Раху'] = {'sign': sign_from_lon(rahu_lon), 'degree': degree_in_sign(rahu_lon), 'lon': rahu_lon}
        transits['Кету'] = {'sign': sign_from_lon((rahu_lon + 180) % 360), 'degree': degree_in_sign((rahu_lon + 180) % 360), 'lon': (rahu_lon + 180) % 360}
    except: pass
    return transits

def get_aspects(planets):
    aspects_list = []
    names = [n for n in planets if n not in ['Асцендент','MC','houses']]
    for i in range(len(names)):
        for j in range(i+1, len(names)):
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
    names = [p for p in natal if p not in ['houses', 'Асцендент', 'MC']]
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
            if asp: aspects.append((names[i], names[j], asp, round(diff, 1)))
    return aspects

def calc_transit_aspects(natal, transits, orb=2.0):
    aspects = []
    for t_name, t_data in transits.items():
        if t_name in ['Раху', 'Кету']: continue
        for n_name, n_data in natal.items():
            if n_name in ['houses', 'Асцендент', 'MC', 'Раху', 'Кету']: continue
            diff = abs(t_data['lon'] - n_data['lon']) % 360
            if diff > 180: diff = 360 - diff
            
            for asp_name, ideal in [('соединение', 0), ('оппозиция', 180), ('тригон', 120), ('квадрат', 90), ('секстиль', 60)]:
                orb_dict = {'соединение': 8, 'оппозиция': 8, 'тригон': 8, 'квадрат': 7, 'секстиль': 5}
                if abs(diff - ideal) <= orb_dict[asp_name]:
                    direction = "сход" if abs(diff - ideal) < orb else "расход"
                    aspects.append({
                        'transit_planet': t_name, 'transit_sign': t_data['sign'],
                        'natal_planet': n_name, 'natal_sign': n_data['sign'],
                        'aspect': asp_name, 'angle': round(diff, 1), 'direction': direction,
                        'transit_house': None
                    })
    
    for asp in aspects:
        t_lon = transits[asp['transit_planet']]['lon']
        for i, h in enumerate(natal['houses']):
            next_h = natal['houses'][(i+1)%12]
            if h['lon'] <= next_h['lon']:
                if h['lon'] <= t_lon < next_h['lon']: asp['transit_house'] = h['house_num']; break
            else:
                if t_lon >= h['lon'] or t_lon < next_h['lon']: asp['transit_house'] = h['house_num']; break
    
    return sorted(aspects, key=lambda x: x['angle'])

def get_house(planet_lon, houses):
    for i, h in enumerate(houses):
        next_h = houses[(i+1)%12]
        if h['lon'] <= next_h['lon']:
            if h['lon'] <= planet_lon < next_h['lon']: return h['house_num']
        else:
            if planet_lon >= h['lon'] or planet_lon < next_h['lon']: return h['house_num']
    return 1

def parse_city(city_str):
    city_key = city_str.lower().strip()
    if city_key in CITIES: return CITIES[city_key][0], CITIES[city_key][1], city_key
    return 55.75, 37.62, 'москва'

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])

def menu_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal"), InlineKeyboardButton("🏠 Дома", callback_data="houses")],
        [InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast"), InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
        [InlineKeyboardButton("💑 Совместимость", callback_data="compat"), InlineKeyboardButton("🌙 Луна", callback_data="moon")],
        [InlineKeyboardButton("📅 Ежедневный гороскоп", callback_data="daily")],
        [InlineKeyboardButton("🔄 Новый клиент", callback_data="new_client")],
        [InlineKeyboardButton("🗑 Удалить данные", callback_data="delete_confirm")],
        [InlineKeyboardButton("💎 Подписка", callback_data="subscribe_info")],
        [InlineKeyboardButton("💬 Поддержка", callback_data="support")],
    ])

def overview_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏠 В начало", callback_data="back")],
        [InlineKeyboardButton("🔄 Новый клиент", callback_data="new_client")],
        [InlineKeyboardButton("💬 Поддержка", callback_data="support")],
        [InlineKeyboardButton("💎 Подписка", callback_data="subscribe_info")],
    ])

# ===== ГРАФИЧЕСКАЯ КАРТА (компактная) =====
def draw_natal_chart_pro(natal, city_name='', birth_time=''):
    fig, ax = plt.subplots(figsize=(14, 14), subplot_kw={'projection': 'polar'})
    ax.set_theta_zero_location('N'); ax.set_theta_direction(1); ax.set_ylim(0, 1.5)
    ax.set_xticks([]); ax.set_yticks([]); ax.spines['polar'].set_visible(False)
    ax.set_facecolor('white'); fig.patch.set_facecolor('white')
    
    elements = {
        'Огонь': {'color': '#e74c3c', 'signs': ['Овен', 'Лев', 'Стрелец']},
        'Земля': {'color': '#27ae60', 'signs': ['Телец', 'Дева', 'Козерог']},
        'Воздух': {'color': '#8e44ad', 'signs': ['Близнецы', 'Весы', 'Водолей']},
        'Вода': {'color': '#2980b9', 'signs': ['Рак', 'Скорпион', 'Рыбы']},
    }
    sign_colors = {s: d['color'] for d in elements.values() for s in d['signs']}
    
    asc_lon = natal.get('Асцендент', {}).get('lon', 0)
    offset = np.radians(90) - np.radians(asc_lon)
    
    for i, sign in enumerate(SIGN_NAMES):
        start_angle = np.radians(i * 30) + offset
        end_angle = np.radians(i * 30 + 30) + offset
        color = sign_colors.get(sign, '#2c3e50')
        theta = np.linspace(start_angle, end_angle, 30)
        ax.fill_between(theta, 1.05, 1.20, color=color, alpha=0.25)
        ax.plot([start_angle, start_angle], [1.05, 1.20], color=color, linewidth=1.5, alpha=0.5)
        mid = start_angle + np.radians(15)
        ax.annotate(f"{SIGN_EMOJI.get(sign,'')}", xy=(mid, 1.16), ha='center', va='center', fontsize=10, color=color, weight='bold')
        ax.annotate(sign, xy=(mid, 1.10), ha='center', va='center', fontsize=6.5, color=color, weight='bold')
    
    ax.plot(np.linspace(0, 2*np.pi, 300), [1.05]*300, color='#cccccc', linewidth=1, alpha=0.5)
    ax.fill_between(np.linspace(0, 2*np.pi, 300), 0.90, 1.05, color='#fafafa', alpha=0.5)
    
    planet_symbols = {'Солнце': '☉', 'Луна': '☽', 'Меркурий': '☿', 'Венера': '♀', 'Марс': '♂', 'Юпитер': '♃', 'Сатурн': '♄', 'Уран': '♅', 'Нептун': '♆', 'Плутон': '♇', 'Раху': '☊', 'Кету': '☋'}
    planet_radii = {'Плутон': 0.92, 'Нептун': 0.93, 'Уран': 0.94, 'Сатурн': 0.95, 'Юпитер': 0.96, 'Марс': 0.97, 'Венера': 0.98, 'Меркурий': 1.00, 'Луна': 1.02, 'Солнце': 1.04, 'Раху': 0.99, 'Кету': 0.91}
    planet_positions = {}
    
    for name, data in natal.items():
        if name in ['houses', 'Асцендент', 'MC', 'Десцендент', 'IC']: continue
        angle = np.radians(SIGN_NAMES.index(data['sign']) * 30 + data['degree']) + offset
        r = planet_radii.get(name, 0.97)
        planet_positions[name] = (angle, r)
        color = '#8e44ad' if name == 'Раху' else '#e67e22' if name == 'Кету' else '#1a1a1a'
        ax.annotate(planet_symbols.get(name, ''), xy=(angle, r), ha='center', va='center', fontsize=13, color=color, weight='bold', zorder=9)
        ax.annotate(f"{data['degree']}°", xy=(angle, r + 0.02), ha='center', va='bottom', fontsize=5.5, color=color, weight='bold')
    
    ax.add_artist(plt.Circle((0, 0), 0.04, color='#1a1a1a', zorder=10))
    
    aspect_colors = {'соединение': '#e74c3c', 'оппозиция': '#e74c3c', 'тригон': '#27ae60', 'квадрат': '#e74c3c', 'секстиль': '#2980b9'}
    for p1, p2, asp_name, _ in get_aspects_with_angles(natal):
        if p1 in planet_positions and p2 in planet_positions:
            ang1, r1 = planet_positions[p1]; ang2, r2 = planet_positions[p2]
            color = aspect_colors.get(asp_name, '#bdc3c7')
            lw = 1.5 if asp_name in ['соединение','оппозиция','тригон'] else 1.0
            ax.plot([ang1, ang2], [r1, r2], color=color, linewidth=lw, alpha=0.5, linestyle='--' if asp_name == 'квадрат' else '-', zorder=1)
    
    for i, house in enumerate(natal.get('houses', [])):
        house_angle = np.radians(house['lon']) + offset
        lw, alpha, color = (2.5, 0.9, '#e74c3c') if house['house_num'] in [1,4,7,10] else (1.2, 0.7, '#1a1a1a')
        ax.plot([house_angle, house_angle], [0.90, 1.20], color=color, linewidth=lw, alpha=alpha)
        next_angle = np.radians(natal['houses'][(i+1)%12]['lon']) + offset
        mid_angle = (house_angle + (next_angle - house_angle) % (2*np.pi) / 2) % (2*np.pi)
        ax.annotate(str(house['house_num']), xy=(mid_angle, 1.30), ha='center', va='center', fontsize=10, color='#1a1a1a', weight='bold', bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='#cccccc', alpha=0.9))
        if house['house_num'] == 1: ax.annotate('ASC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 10: ax.annotate('MC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
    
    title = 'НАТАЛЬНАЯ КАРТА'
    if city_name: title += f' • {city_name.title()}'
    if birth_time: title += f' • {birth_time}'
    fig.text(0.5, 0.97, title, ha='center', va='top', fontsize=16, color='#1a1a1a', weight='bold')
    plt.tight_layout(pad=1)
    buf = BytesIO(); plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
    buf.seek(0); plt.close()
    return buf

# ===== ПОДДЕРЖКА =====
async def support_msg(update, ctx):
    user = update.effective_user
    await ctx.bot.send_message(ADMIN_ID, f"📩 *Сообщение*\n👤 {user.full_name}\n🆔 `{user.id}`\n💬 {update.message.text}\n\n_Ответ:_ `/reply {user.id} текст`", parse_mode='Markdown')
    await update.message.reply_text("✅ *Отправлено!*", parse_mode='Markdown')

async def reply_cmd(update, ctx):
    if update.effective_user.id != ADMIN_ID: return
    args = update.message.text.split(maxsplit=2)
    if len(args) < 3: await update.message.reply_text("❌ `/reply ID текст`"); return
    try:
        await ctx.bot.send_message(int(args[1]), f"💬 *Ответ:*\n\n{args[2]}\n\n─ @Astromasbot", parse_mode='Markdown')
        await update.message.reply_text("✅ Отправлено")
    except: await update.message.reply_text("❌ Ошибка")

# ===== КОМАНДЫ МЕНЮ =====
async def natal_cmd(update, ctx):
    await update.message.reply_text("🌟 *Натальная карта*\nВведите: `ДД.ММ.ГГГГ ЧЧ:ММ Город`", parse_mode='Markdown')
async def forecast_cmd(update, ctx):
    await update.message.reply_text("🔮 *Прогноз ИИ*\nВведите: `ДД.ММ.ГГГГ ЧЧ:ММ Город`", parse_mode='Markdown')
async def transits_cmd(update, ctx):
    t = calc_transits(); now = get_current_time()
    text = f"🪐 *Транзиты* {now.strftime('%d.%m.%Y %H:%M')}\n\n"
    for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Раху','Кету']:
        if p in t: text += f"{SIGN_EMOJI.get(t[p]['sign'],'')} {p}: *{t[p]['sign']}* {t[p]['degree']}°{' ℞' if t[p].get('retro') else ''}\n"
    await update.message.reply_text(text, parse_mode='Markdown')
async def compat_cmd(update, ctx):
    await update.message.reply_text("💑 *Совместимость*\nВведите: *Овен Телец*", parse_mode='Markdown')
async def moon_cmd(update, ctx):
    t = calc_transits(); now = get_current_time()
    phase = {0:"🌑",1:"🌒",2:"🌓",3:"🌔",4:"🌕",5:"🌖",6:"🌗",7:"🌘"}.get(now.day % 8, "🌑")
    await update.message.reply_text(f"🌙 *Луна* {now.strftime('%d.%m.%Y')}\n{phase} *{t['Луна']['sign']}* {t['Луна']['degree']}°", parse_mode='Markdown')
async def daily_cmd(update, ctx):
    now = get_current_time(); t = calc_transits()
    text = f"📅 *{now.strftime('%d.%m.%Y')}*\n\n"
    for sign in SIGN_NAMES:
        text += f"{SIGN_EMOJI.get(sign,'')} *{sign}*: "
        if t.get('Солнце',{}).get('sign') == sign: text += "☀️\n"
        elif t.get('Луна',{}).get('sign') == sign: text += "🌙\n"
        else: text += "✨\n"
    await update.message.reply_text(text[:4000], parse_mode='Markdown')
async def delete_cmd(update, ctx):
    uid = update.effective_user.id
    if uid in users: del users[uid]; save_users()
    await update.message.reply_text("✅ *Данные удалены!*", parse_mode='Markdown')
async def support_cmd(update, ctx):
    await update.message.reply_text("💬 *Поддержка*\nПишите вопрос здесь.", parse_mode='Markdown')

# ===== СТАРТ =====
async def start(update, ctx):
    if ctx.args and ctx.args[0] == 'support':
        await update.message.reply_text("💬 *Поддержка*\nПишите вопрос здесь.", parse_mode='Markdown')
        return
    ctx.user_data['mode'] = ''
    await update.message.reply_text(
        f"{cat_emoji()} *АстроБот — ваш персональный астролог*\n\n"
        f"✨ 12 лет опыта | 🌍 150+ городов | 🎯 Швейцарские эфемериды | 🤖 DeepSeek AI\n\n"
        f"📄 *Ознакомьтесь:*\n"
        f"• [Политика конфиденциальности]({PRIVACY_URL})\n"
        f"• [Договор-оферта]({OFERTA_URL})\n"
        f"• ✅ [Согласие на обработку данных]({CONSENT_URL})\n\n"
        f"Нажимая «Принимаю», вы подтверждаете согласие.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Принимаю", callback_data="start_accept")],
            [InlineKeyboardButton("❌ Отказываюсь", callback_data="start_decline")]
        ]), parse_mode='Markdown'
    )

async def help_command(update, ctx):
    await update.message.reply_text("📖 Формат: `ДД.ММ.ГГГГ ЧЧ:ММ Город`\nИспользуйте кнопку Меню слева.", parse_mode='Markdown')

async def logtest(update, ctx):
    token = os.getenv("DEEPSEEK_TOKEN")
    if token:
        try:
            resp = requests.post("https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "OK"}], "max_tokens": 10}, timeout=10)
            await update.message.reply_text(f"✅ DeepSeek: {resp.status_code}")
        except: await update.message.reply_text("❌ Нет связи")
    else: await update.message.reply_text("❌ Токен не найден")

# ===== ОСНОВНАЯ ЛОГИКА =====
async def btn(update, ctx):
    q = update.callback_query; await q.answer(); d = q.data; uid = q.from_user.id
    
    if d == 'start_accept':
        if uid not in users: users[uid] = {}
        users[uid]['consent'] = True
        users[uid]['consent_date'] = datetime.now().strftime('%d.%m.%Y %H:%M')
        save_users()
        await q.message.delete()
        await q.message.reply_text(f"{cat_emoji()} *Согласие принято!*\nВведите данные рождения:\n`ДД.ММ.ГГГГ ЧЧ:ММ Город`\nИли используйте кнопку Меню слева.", reply_markup=menu_btn(), parse_mode='Markdown')
        return
    
    if d == 'start_decline':
        await q.message.delete()
        await q.message.reply_text("❌ *Отказ.* Бот не сохраняет данные. /start для возврата.", parse_mode='Markdown')
        return
    
    if d in ['forecast', 'natal', 'houses', 'newdata', 'newdata_noon', 'newdata_natal']:
        if uid not in users or not users[uid].get('consent'):
            await q.answer("⚠️ Примите согласие в /start", show_alert=True); return
    
    if d == 'forecast':
        if uid in users and 'sign' in users[uid]:
            ctx.user_data['mode'] = 'fp'
            kb = [[InlineKeyboardButton("📅 День", callback_data="f_day"), InlineKeyboardButton("📆 Неделя", callback_data="f_week")],
                  [InlineKeyboardButton("🗓 Месяц", callback_data="f_month")], [InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await q.edit_message_text(f"✨ *{users[uid]['sign']}* — период:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await q.edit_message_text("🔮 *Прогноз ИИ*\n\n📝 С временем: `15.05.1990 14:30 Москва`\n📝 Без времени: `15.05.1990 Москва`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 С временем", callback_data="newdata"), InlineKeyboardButton("📝 Без времени", callback_data="newdata_noon")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]), parse_mode='Markdown')
    
    elif d.startswith('f_'):
        if uid not in users or 'sign' not in users[uid]: await q.message.reply_text("Введите данные рождения!"); return
        u = users[uid]; period = {'day':'день','week':'неделю','month':'месяц'}[d[2:]]
        now = get_current_time()
        ptitle = {'f_day':'сегодня','f_week':'неделю','f_month':'месяц'}.get(d, '')
        
        await q.message.reply_text(f"{cat_emoji()} Рассчитываю...")
        
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        transits = calc_transits()
        transit_aspects = calc_transit_aspects(natal, transits)
        aspects = get_aspects(natal)
        
        # ===== КОМПАКТНЫЕ АСТРОДАННЫЕ =====
        planet_data = []
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн']:
            if p in natal:
                house = get_house(natal[p]['lon'], natal['houses'])
                retro = '℞' if natal[p].get('retro') else ''
                ruler = SIGN_RULERS.get(natal[p]['sign'], '')
                planet_data.append(f"{p}:{natal[p]['sign']}{natal[p]['degree']}°({house}д){retro}")
        
        # Управитель ASC
        asc_sign = natal['Асцендент']['sign']
        asc_ruler = SIGN_RULERS.get(asc_sign, '')
        asc_ruler_house = get_house(natal[asc_ruler]['lon'], natal['houses']) if asc_ruler in natal else '?'
        
        transit_strs = []
        for a in transit_aspects[:8]:
            t_retro = '℞' if transits.get(a['transit_planet'], {}).get('retro') else ''
            transit_strs.append(f"{a['transit_planet']}{t_retro} {a['aspect'][:3]} {a['natal_planet']} ({a['direction']})")
        
        astro = f"""
ASC:{asc_sign} | ☀:{natal['Солнце']['sign']} | 🌙:{natal['Луна']['sign']}
Планеты: {' | '.join(planet_data[:7])}
Упр.ASC: {asc_ruler}({asc_ruler_house}д)
Транзиты: {', '.join(transit_strs[:6]) if transit_strs else 'нет'}
Аспекты: {', '.join(aspects[:4]) if aspects else 'нет'}
"""
        
        if d == 'f_day':
            # Луна по часам (компактно)
            moon_data = []
            for h in [0, 6, 12, 18]:
                jd_h = swe.julday(now.year, now.month, now.day, h)
                m_lon = swe.calc_ut(jd_h, swe.MOON)[0][0]
                m_sign = sign_from_lon(m_lon)
                m_house = get_house(m_lon, natal['houses'])
                moon_data.append(f"{h:02d}:{m_sign}({m_house}д)")
            
            prompt = f"""Прогноз на день. {now.strftime('%d.%m.%Y')}
{astro}
Луна: {' → '.join(moon_data)}

Дай 6-8 предл.: настроение, отношения, дела, совет. Упоминай планеты."""
            max_tok = 350
        
        elif d == 'f_month':
            prompt = f"""Прогноз на месяц. {now.strftime('%d.%m.%Y')}
{astro}

Дай 10-12 предл.: любовь, карьера, энергия, совет. Упоминай транзитные аспекты."""
            max_tok = 1200
        else:
            prompt = f"""Прогноз на {period}. {now.strftime('%d.%m.%Y')}
{astro}

Дай 6-8 предл.: любовь, карьера, энергия, совет. Упоминай аспекты."""
            max_tok = 500 if d == 'f_week' else 400
        
        forecast = ai_client.ask(prompt, max_tokens=max_tok)
        if forecast:
            parts = ai_client.split_message(forecast)
            for i, part in enumerate(parts):
                await update.effective_message.reply_text(
                    f"🌟 *Прогноз на {ptitle}*\n\n{part}" if i == 0 else part,
                    reply_markup=overview_btn() if i == 0 else None, parse_mode='Markdown')
        else:
            await update.effective_message.reply_text(f"🌟 *Прогноз на {ptitle}*\n\n❤️ Благоприятно\n💼 Сосредоточьтесь\n🌟 Слушайте интуицию", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'natal':
        if uid not in users or 'sign' not in users[uid]:
            await q.edit_message_text("🌟 *Натальная карта*\n📝 `15.05.1990 14:30 Москва`", reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 С временем", callback_data="newdata"), InlineKeyboardButton("📝 Без времени", callback_data="newdata_noon")],
                [InlineKeyboardButton("🔙 Назад", callback_data="back")]
            ]), parse_mode='Markdown'); return
        
        u = users[uid]
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        aspects = get_aspects_with_angles(natal)
        
        planet_info = []
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн']:
            if p in natal:
                h = get_house(natal[p]['lon'], natal['houses'])
                retro = '℞' if natal[p].get('retro') else ''
                planet_info.append(f"{p}:{natal[p]['sign']}{natal[p]['degree']}°({h}д){retro}")
        
        asc_sign = natal['Асцендент']['sign']
        asc_ruler = SIGN_RULERS.get(asc_sign, '')
        asc_ruler_house = get_house(natal[asc_ruler]['lon'], natal['houses']) if asc_ruler in natal else '?'
        
        aspect_strs = [f"{a[0]} {a[2]} {a[1]}" for a in aspects[:8]]
        
        astro_data = f"""
📍 {u['city'].title()} | {u['hour']:02d}:{u['minute']:02d}
ASC:{asc_sign} (упр. {asc_ruler} в {asc_ruler_house}д)
{' | '.join(planet_info)}
☊:{natal['Раху']['sign']} | ☋:{natal['Кету']['sign']}
Аспекты: {', '.join(aspect_strs) if aspect_strs else 'нет'}
"""
        prompt = f"""Разбор натальной карты.
{astro_data}

Структура: ASC, Луна, Солнце, Меркурий, Венера, Марс, Узлы. 20-25 предл. Упоминай аспекты."""
        
        forecast = ai_client.ask(prompt, max_tokens=900)
        img = draw_natal_chart_pro(natal, u['city'], f"{u['hour']:02d}:{u['minute']:02d}")
        await update.effective_message.reply_photo(photo=img)
        
        if forecast:
            parts = ai_client.split_message(forecast)
            for i, part in enumerate(parts):
                await update.effective_message.reply_text(part, reply_markup=overview_btn() if i == len(parts)-1 else None, parse_mode='Markdown')
        else:
            await update.effective_message.reply_text(f"🌟 *Натальная карта*\n📍 {u['city'].title()}\n☀ {natal['Солнце']['sign']} | 🌙 {natal['Луна']['sign']} | ASC {asc_sign}", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'houses':
        if uid not in users or 'sign' not in users[uid]:
            await q.edit_message_text("🏠 Нужно время рождения.\n📝 `15.05.1990 14:30 Москва`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Ввести", callback_data="newdata")], [InlineKeyboardButton("🔙 Назад", callback_data="back")]]), parse_mode='Markdown')
        else:
            u = users[uid]; natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
            text = f"🏠 *Дома* {u['city'].title()} {u['hour']:02d}:{u['minute']:02d}\n\n"
            for h in natal['houses']: text += f"*{h['house_num']}*: {SIGN_EMOJI.get(h['sign'],'')} {h['sign']} {h['degree']}°\n"
            text += f"\nASC: *{natal['Асцендент']['sign']}*"
            await q.edit_message_text(text, reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'transits':
        t = calc_transits(); now = get_current_time()
        text = f"🪐 *Транзиты* {now.strftime('%d.%m.%Y %H:%M')}\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Раху','Кету']:
            if p in t: text += f"{SIGN_EMOJI.get(t[p]['sign'],'')} {p}: *{t[p]['sign']}* {t[p]['degree']}°{' ℞' if t[p].get('retro') else ''}\n"
        await q.edit_message_text(text, reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'compat':
        ctx.user_data['mode'] = 'compat'
        await q.edit_message_text("💑 Два знака: *Овен Телец*", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'moon':
        t = calc_transits(); now = get_current_time()
        phase = {0:"🌑",1:"🌒",2:"🌓",3:"🌔",4:"🌕",5:"🌖",6:"🌗",7:"🌘"}.get(now.day % 8, "🌑")
        await q.edit_message_text(f"🌙 *Луна* {now.strftime('%d.%m.%Y')}\n{phase} *{t['Луна']['sign']}* {t['Луна']['degree']}°", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'daily':
        now = get_current_time(); t = calc_transits()
        text = f"📅 *{now.strftime('%d.%m.%Y')}*\n\n"
        for sign in SIGN_NAMES:
            text += f"{SIGN_EMOJI.get(sign,'')} *{sign}*: "
            if t.get('Солнце',{}).get('sign') == sign: text += "☀️\n"
            elif t.get('Луна',{}).get('sign') == sign: text += "🌙\n"
            else: text += "✨\n"
        await q.edit_message_text(text[:4000], reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'new_client':
        if uid in users: del users[uid]; save_users()
        ctx.user_data.clear(); ctx.user_data['mode'] = ''
        await q.edit_message_text("🔄 *Очищено!* Введите: `ДД.ММ.ГГГГ ЧЧ:ММ Город`", reply_markup=menu_btn(), parse_mode='Markdown')
    
    elif d == 'delete_confirm':
        await q.edit_message_text("⚠️ *Удалить всё?* Согласие будет отозвано.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Да", callback_data="delete_yes"), InlineKeyboardButton("❌ Нет", callback_data="back")]]), parse_mode='Markdown')
    
    elif d == 'delete_yes':
        if uid in users: del users[uid]; save_users()
        ctx.user_data.clear(); ctx.user_data['mode'] = ''
        await q.edit_message_text("✅ *Удалено!* Введите: `ДД.ММ.ГГГГ ЧЧ:ММ Город`", reply_markup=menu_btn(), parse_mode='Markdown')
    
    elif d == 'subscribe_info':
        await q.edit_message_text("💎 *Подписка*\nСкоро. Пока бесплатно!", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'support':
        await q.edit_message_text("💬 *Поддержка*\nПишите вопрос здесь.", parse_mode='Markdown')
    
    elif d == 'newdata': ctx.user_data['mode'] = 'newdata'; await q.edit_message_text("📝 `ДД.ММ.ГГГГ ЧЧ:ММ Город`", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'newdata_noon': ctx.user_data['mode'] = 'newdata_noon'; await q.edit_message_text("📝 `ДД.ММ.ГГГГ Город`", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'newdata_natal': ctx.user_data['mode'] = 'newdata'; await q.edit_message_text("📝 `15.05.1990 14:30 Москва`", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'back': ctx.user_data['mode'] = ''; await q.edit_message_text("🌟 *Меню*", reply_markup=menu_btn(), parse_mode='Markdown')

async def msg(update, ctx):
    t = update.message.text.strip(); m = ctx.user_data.get('mode',''); uid = update.effective_user.id
    
    if not m and not t.startswith('/') and '.' not in t:
        await support_msg(update, ctx); return
    
    if m in ['newdata', 'newdata_noon']: ctx.user_data['mode'] = ''
    if m == 'compat':
        parts = t.title().split()
        if len(parts)==2 and parts[0] in SIGN_NAMES and parts[1] in SIGN_NAMES:
            fc = ai_client.ask(f"Совместимость {parts[0]} {parts[1]}. Процент и 2-3 предл.", 100) or "70% — Хорошая совместимость"
            ctx.user_data['mode'] = ''
            await update.message.reply_text(f"💑 *{parts[0]} + {parts[1]}*\n{fc}", reply_markup=overview_btn(), parse_mode='Markdown')
            return
        await update.message.reply_text("❌ *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown'); return
    
    try:
        t_clean = t
        parts_check = t.split()
        if len(parts_check) >= 2 and ':' in parts_check[1] and parts_check[1].count(':') == 1:
            parts_check[1] = parts_check[1].replace(':', ' '); t_clean = ' '.join(parts_check)
        
        parts = t_clean.split()
        
        if len(parts) >= 3:
            date_part = parts[0]; day, month, year = map(int, date_part.split('.'))
            if parts[1].isdigit() and parts[2].isdigit(): hour, minute = int(parts[1]), int(parts[2]); city_str = ' '.join(parts[3:]) if len(parts) > 3 else 'москва'
            elif parts[1].isdigit(): hour, minute = int(parts[1]), 0; city_str = ' '.join(parts[2:]) if len(parts) > 2 else 'москва'
            else: hour, minute = 12, 0; city_str = ' '.join(parts[1:]) if len(parts) > 1 else 'москва'
        elif '.' in t_clean and len(t_clean.split('.')) == 3 and ' ' in t_clean:
            parts_dot = t_clean.split(); date_part = parts_dot[0]
            day, month, year = map(int, date_part.split('.')); hour, minute = 12, 0
            city_str = ' '.join(parts_dot[1:]) if len(parts_dot) > 1 else 'москва'
        elif '.' in t_clean and len(t_clean.split('.')) == 3:
            day, month, year = map(int, t_clean.split('.')); hour, minute = 12, 0; city_str = 'москва'
        else: raise ValueError("Неверный формат")
        
        validate_date(day, month, year); validate_time(hour, minute)
        lat, lon, city_name = parse_city(city_str); sign = get_zodiac_sign(day, month)
        users[uid] = {'sign':sign,'day':day,'month':month,'year':year,'hour':hour,'minute':minute,'lat':lat,'lon':lon,'city':city_name,'consent': True,'consent_date': datetime.now().strftime('%d.%m.%Y %H:%M')}
        save_users()
        
        kb = [[InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast"), InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],
              [InlineKeyboardButton("🏠 Дома", callback_data="houses"), InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
              [InlineKeyboardButton("🔄 Новые данные", callback_data="newdata_natal"), InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await update.message.reply_text(f"✨ *{sign}* | {day:02d}.{month:02d}.{year} | {hour:02d}:{minute:02d} | {city_name.title()}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    
    except ValueError as e:
        await update.message.reply_text(f"❌ {e}\nФорматы: `15.05.1990` / `15.05.1990 14:30 Москва`", reply_markup=back_btn(), parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text("❌ Ошибка.", reply_markup=back_btn(), parse_mode='Markdown')

def main():
    TOKEN = os.getenv('TELEGRAM_TOKEN')
    app = Application.builder().token(TOKEN).build()
    for cmd, handler in [('start', start), ('help', help_command), ('logtest', logtest),
                          ('natal', natal_cmd), ('forecast', forecast_cmd), ('transits', transits_cmd),
                          ('compat', compat_cmd), ('moon', moon_cmd), ('daily', daily_cmd),
                          ('delete', delete_cmd), ('support', support_cmd),
                          ('support_msg', support_msg), ('reply', reply_cmd)]:
        app.add_handler(CommandHandler(cmd, handler))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    threading.Thread(target=run_keepalive, daemon=True).start()
    print("🚀 Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
