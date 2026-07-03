import time
import sys
import os as _os
import socket
import random

print("⏳ Ожидание 8с перед стартом для избежания conflict...")
time.sleep(8)

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

CAT_EMOJI = ['🐱', '😺', '😸', '😻', '😼', '😽', '🙀', '😿', '😾', '🐈', '🐈‍⬛', '✨🐱', '🐱✨', '🔮🐱', '🐱🔮', '🌟🐱', '🐱🌟']
def cat_emoji(): return random.choice(CAT_EMOJI)

ADMIN_ID = 870114986

PRIVACY_URL = "https://telegra.ph/Politika-konfidencialnosti-07-03-19"
OFERTA_URL = "https://telegra.ph/DOGOVOR-OFERTA-NA-OKAZANIE-USLUG-07-03"
CONSENT_URL = "https://telegra.ph/SOGLASIE-NA-OBRABOTKU-PERSONALNYH-DANNYH-07-03-6"

SYSTEM_PROMPT = "Ты — астролог. Нейтральные обращения. Отвечай всегда. Основывайся только на данных. Начинай сразу с прогноза, без приветствий и дат. Завершай каждое предложение. Не обрывай мысли. Упоминай планеты и аспекты."

def validate_date(day, month, year):
    if year < 1900 or year > datetime.now().year: raise ValueError(f"Год: 1900-{datetime.now().year}")
    if not (1 <= month <= 12): raise ValueError("Месяц: 1-12")
    if not (1 <= day <= 31): raise ValueError("День: 1-31")
    datetime(year, month, day)
    return True

def validate_time(hour, minute):
    if not (0 <= hour <= 23): raise ValueError("Часы: 0-23")
    if not (0 <= minute <= 59): raise ValueError("Минуты: 0-59")
    return True

class AIClient:
    def __init__(self, deepseek_token=None, hf_token=None):
        self.deepseek_token = deepseek_token; self.hf_token = hf_token
        self.deepseek_url = "https://api.deepseek.com/v1/chat/completions"
        self.hf_url = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
        self.max_retries = 2; self.timeout = 40

    def ask(self, prompt, max_tokens=300):
        if self.deepseek_token:
            result = self._ask_deepseek(prompt, max_tokens)
            if result: return result
        if self.hf_token: return self._ask_huggingface(prompt, max_tokens)
        return None

    def _ask_deepseek(self, prompt, max_tokens):
        headers = {"Authorization": f"Bearer {self.deepseek_token}", "Content-Type": "application/json"}
        payload = {"model": "deepseek-chat", "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}], "max_tokens": max_tokens, "temperature": 0.5}
        for _ in range(self.max_retries):
            try:
                resp = requests.post(self.deepseek_url, headers=headers, json=payload, timeout=self.timeout)
                if resp.status_code == 200:
                    text = resp.json()["choices"][0]["message"]["content"].strip()
                    if text and len(text) > 10: return text
                elif resp.status_code == 429: time.sleep(15)
                else: time.sleep(3)
            except: time.sleep(3)
        return None

    def _ask_huggingface(self, prompt, max_tokens):
        headers = {"Authorization": f"Bearer {self.hf_token}"}
        for _ in range(self.max_retries):
            try:
                resp = requests.post(self.hf_url, headers=headers, json={"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}}, timeout=self.timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list) and data:
                        text = data[0].get("generated_text", "").strip()
                        if text and len(text) > 10: return text
                elif resp.status_code in [503, 429]: time.sleep(15)
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
            parts.append(text[:split_pos].strip()); text = text[split_pos:].strip()
        if text: parts.append(text)
        return parts

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

class PingHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK")
    def log_message(self, format, *args): pass

def run_keepalive():
    HTTPServer(('0.0.0.0', int(os.getenv("PORT", 10000))), PingHandler).serve_forever()

swe.set_ephe_path(None)

SIGN_NAMES = ['Овен', 'Телец', 'Близнецы', 'Рак', 'Лев', 'Дева', 'Весы', 'Скорпион', 'Стрелец', 'Козерог', 'Водолей', 'Рыбы']
SIGN_EMOJI = {'Овен':'♈','Телец':'♉','Близнецы':'♊','Рак':'♋','Лев':'♌','Дева':'♍','Весы':'♎','Скорпион':'♏','Стрелец':'♐','Козерог':'♑','Водолей':'♒','Рыбы':'♓'}

ZODIAC_SIGNS = {
    'Овен': (3,21,4,19), 'Телец': (4,20,5,20), 'Близнецы': (5,21,6,20),
    'Рак': (6,21,7,22), 'Лев': (7,23,8,22), 'Дева': (8,23,9,22),
    'Весы': (9,23,10,22), 'Скорпион': (10,23,11,21), 'Стрелец': (11,22,12,21),
    'Козерог': (12,22,1,19), 'Водолей': (1,20,2,18), 'Рыбы': (2,19,3,20)
}

SIGN_RULERS = {
    'Овен': 'Марс', 'Телец': 'Венера', 'Близнецы': 'Меркурий',
    'Рак': 'Луна', 'Лев': 'Солнце', 'Дева': 'Меркурий',
    'Весы': 'Венера', 'Скорпион': 'Марс', 'Стрелец': 'Юпитер',
    'Козерог': 'Сатурн', 'Водолей': 'Уран', 'Рыбы': 'Нептун'
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
    'симферополь': (44.95, 34.10), 'севастополь': (44.61, 33.52),
    'пятигорск': (44.05, 43.06), 'ставрополь': (45.04, 41.97), 'махачкала': (42.98, 47.50),
    'грозный': (43.31, 45.69), 'нальчик': (43.48, 43.61), 'владикавказ': (43.02, 44.68),
    'нижний': (56.33, 44.00), 'нн': (56.33, 44.00), 'нижний новгород': (56.33, 44.00),
    'казань': (55.79, 49.12), 'самара': (53.20, 50.15), 'уфа': (54.74, 55.97),
    'пермь': (58.01, 56.25), 'саратов': (51.53, 46.03), 'тольятти': (53.53, 49.35),
    'ижевск': (56.85, 53.23), 'ульяновск': (54.33, 48.39), 'чебоксары': (56.13, 47.25),
    'киров': (58.60, 49.66), 'оренбург': (51.77, 55.10), 'пенза': (53.20, 45.00),
    'саранск': (54.19, 45.18), 'набережные челны': (55.74, 52.41), 'йошкар-ола': (56.63, 47.90),
    'екатеринбург': (56.84, 60.65), 'екб': (56.84, 60.65), 'челябинск': (55.16, 61.43),
    'тюмень': (57.15, 65.53), 'магнитогорск': (53.42, 58.98), 'сургут': (61.25, 73.42),
    'нижний тагил': (57.92, 59.98), 'курган': (55.47, 65.35), 'нижневартовск': (60.94, 76.58),
    'новосибирск': (55.03, 82.92), 'нск': (55.03, 82.92), 'омск': (54.99, 73.37),
    'красноярск': (56.02, 92.87), 'иркутск': (52.29, 104.30), 'барнаул': (53.35, 83.78),
    'новокузнецк': (53.76, 87.14), 'кемерово': (55.36, 86.08), 'томск': (56.50, 84.97),
    'улан-удэ': (51.83, 107.61), 'чита': (52.03, 113.50), 'братск': (56.15, 101.63),
    'абакан': (53.72, 91.44), 'норильск': (69.35, 88.20),
    'владивосток': (43.12, 131.89), 'якутск': (62.03, 129.73), 'хабаровск': (48.48, 135.08),
    'южно-сахалинск': (46.96, 142.74), 'петропавловск-камчатский': (53.02, 158.65), 'магадан': (59.56, 150.80),
    'лондон': (51.51, -0.13), 'париж': (48.86, 2.35), 'берлин': (52.52, 13.40),
    'рим': (41.90, 12.50), 'мадрид': (40.42, -3.70), 'барселона': (41.39, 2.17),
    'амстердам': (52.37, 4.90), 'вена': (48.21, 16.37), 'прага': (50.09, 14.42),
    'варшава': (52.23, 21.01), 'будапешт': (47.50, 19.04), 'стокгольм': (59.33, 18.07),
    'осло': (59.91, 10.75), 'хельсинки': (60.17, 24.94), 'афины': (37.98, 23.73),
    'стамбул': (41.01, 28.98), 'дублин': (53.35, -6.26), 'лиссабон': (38.72, -9.14),
    'цюрих': (47.38, 8.54), 'женева': (46.20, 6.14), 'милан': (45.47, 9.19),
    'мюнхен': (48.14, 11.58), 'гамбург': (53.55, 9.99), 'франкфурт': (50.11, 8.68),
    'киев': (50.45, 30.52), 'минск': (53.90, 27.57), 'рига': (56.95, 24.11),
    'вильнюс': (54.69, 25.28), 'таллин': (59.44, 24.75),
    'токио': (35.68, 139.76), 'пекин': (39.90, 116.40), 'шанхай': (31.23, 121.47),
    'гонконг': (22.32, 114.17), 'сингапур': (1.35, 103.82), 'сеул': (37.57, 126.98),
    'дубай': (25.20, 55.27), 'абу-даби': (24.45, 54.38), 'доха': (25.29, 51.53),
    'дели': (28.61, 77.23), 'мумбаи': (19.08, 72.88), 'банкок': (13.75, 100.50),
    'джакарта': (-6.21, 106.85), 'манила': (14.60, 120.98),
    'ташкент': (41.30, 69.24), 'алматы': (43.26, 76.93), 'астана': (51.17, 71.43),
    'бишкек': (42.87, 74.59), 'душанбе': (38.54, 68.78), 'ашхабад': (37.95, 58.38),
    'баку': (40.41, 49.87), 'тбилиси': (41.72, 44.79), 'ереван': (40.18, 44.51),
    'тегеран': (35.69, 51.39), 'багдад': (33.32, 44.42), 'эр-рияд': (24.71, 46.68),
    'нью-йорк': (40.71, -74.00), 'лос-анджелес': (34.05, -118.24),
    'чикаго': (41.88, -87.63), 'хьюстон': (29.76, -95.37), 'майами': (25.76, -80.19),
    'торонто': (43.65, -79.38), 'ванкувер': (49.28, -123.12), 'мехико': (19.43, -99.13),
    'буэнос-айрес': (-34.60, -58.38), 'сан-паулу': (-23.55, -46.63),
    'сантьяго': (-33.45, -70.67), 'лима': (-12.05, -77.04),
    'каир': (30.04, 31.24), 'кейптаун': (-33.92, 18.42), 'найроби': (-1.29, 36.82),
    'лагос': (6.45, 3.40), 'йоханнесбург': (-26.20, 28.05),
    'сидней': (-33.87, 151.21), 'мельбурн': (-37.81, 144.96), 'окленд': (-36.85, 174.76),
}

CITY_TIMEZONES = {
    'москва': 3, 'мск': 3, 'питер': 3, 'спб': 3, 'санкт-петербург': 3,
    'воронеж': 3, 'белгород': 3, 'брянск': 3, 'владимир': 3, 'иваново': 3,
    'калуга': 3, 'кострома': 3, 'курск': 3, 'липецк': 3, 'орёл': 3, 'орел': 3,
    'рязань': 3, 'смоленск': 3, 'тамбов': 3, 'тверь': 3, 'тула': 3, 'ярославль': 3,
    'калининград': 2, 'архангельск': 3, 'вологда': 3, 'мурманск': 3,
    'петрозаводск': 3, 'сыктывкар': 3, 'великий новгород': 3, 'псков': 3, 'череповец': 3,
    'ростов': 3, 'ростов-на-дону': 3, 'краснодар': 3, 'сочи': 3, 'волгоград': 3,
    'астрахань': 4, 'симферополь': 3, 'севастополь': 3,
    'пятигорск': 3, 'ставрополь': 3, 'махачкала': 3, 'грозный': 3,
    'нальчик': 3, 'владикавказ': 3,
    'нижний': 3, 'нн': 3, 'нижний новгород': 3, 'казань': 3,
    'самара': 4, 'уфа': 5, 'пермь': 5, 'оренбург': 5,
    'екатеринбург': 5, 'екб': 5, 'челябинск': 5, 'тюмень': 5,
    'магнитогорск': 5, 'сургут': 5, 'нижний тагил': 5, 'курган': 5,
    'нижневартовск': 5,
    'омск': 6, 'новосибирск': 7, 'нск': 7, 'красноярск': 7, 'барнаул': 7,
    'новокузнецк': 7, 'кемерово': 7, 'томск': 7, 'абакан': 7, 'норильск': 7,
    'иркутск': 8, 'улан-удэ': 8, 'чита': 9, 'братск': 8,
    'владивосток': 10, 'хабаровск': 10, 'южно-сахалинск': 11,
    'петропавловск-камчатский': 12, 'магадан': 11, 'якутск': 9,
    'лондон': 0, 'париж': 1, 'берлин': 1, 'рим': 1, 'мадрид': 1, 'барселона': 1,
    'амстердам': 1, 'вена': 1, 'прага': 1, 'варшава': 1, 'будапешт': 1,
    'стокгольм': 1, 'осло': 1, 'хельсинки': 2, 'афины': 2, 'стамбул': 3, 'дублин': 0,
    'лиссабон': 0, 'цюрих': 1, 'женева': 1, 'милан': 1, 'мюнхен': 1, 'гамбург': 1, 'франкфурт': 1,
    'киев': 2, 'минск': 3, 'рига': 2, 'вильнюс': 2, 'таллин': 2,
    'токио': 9, 'пекин': 8, 'шанхай': 8, 'гонконг': 8, 'сингапур': 8, 'сеул': 9,
    'дубай': 4, 'абу-даби': 4, 'доха': 3, 'дели': 5.5, 'мумбаи': 5.5, 'банкок': 7,
    'джакарта': 7, 'манила': 8,
    'ташкент': 5, 'алматы': 5, 'астана': 5, 'бишкек': 6, 'душанбе': 5, 'ашхабад': 5,
    'баку': 4, 'тбилиси': 4, 'ереван': 4,
    'тегеран': 3.5, 'багдад': 3, 'эр-рияд': 3,
    'нью-йорк': -5, 'лос-анджелес': -8, 'чикаго': -6, 'хьюстон': -6, 'майами': -5,
    'торонто': -5, 'ванкувер': -8, 'мехико': -6,
    'буэнос-айрес': -3, 'сан-паулу': -3, 'сантьяго': -4, 'лима': -5,
    'каир': 2, 'кейптаун': 2, 'найроби': 3, 'лагос': 1, 'йоханнесбург': 2,
    'сидней': 10, 'мельбурн': 10, 'окленд': 12,
}

PLANETS = {'Солнце': swe.SUN, 'Луна': swe.MOON, 'Меркурий': swe.MERCURY, 'Венера': swe.VENUS,
           'Марс': swe.MARS, 'Юпитер': swe.JUPITER, 'Сатурн': swe.SATURN,
           'Уран': swe.URANUS, 'Нептун': swe.NEPTUNE, 'Плутон': swe.PLUTO}

if os.path.exists(USERS_FILE):
    try:
        with open(USERS_FILE) as f:
            if any('day' not in d for d in json.load(f).values()): os.remove(USERS_FILE)
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

def calc_natal(day, month, year, hour=12, minute=0, lat=55.75, lon=37.62, city_name='москва'):
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
    else: house_system = b'P'
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
            transits[name] = {
                'sign': sign_from_lon(lon_deg),
                'degree': degree_in_sign(lon_deg),
                'lon': lon_deg,
                'retro': speed < 0
            }
        except:
            continue
    
    try:
        rahu_lon = swe.calc_ut(jd, swe.MEAN_NODE)[0][0]
        transits['Раху'] = {'sign': sign_from_lon(rahu_lon), 'degree': degree_in_sign(rahu_lon), 'lon': rahu_lon}
        transits['Кету'] = {'sign': sign_from_lon((rahu_lon + 180) % 360), 'degree': degree_in_sign((rahu_lon + 180) % 360), 'lon': (rahu_lon + 180) % 360}
    except:
        pass
    
    return transits

def get_aspects(planets):
    aspects_list = []
    names = [n for n in planets if n not in ['Асцендент','MC','houses']]
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            diff = abs(planets[names[i]]['lon'] - planets[names[j]]['lon']) % 360
            if diff > 180: diff = 360 - diff
            if diff <= 5: asp = "соединение"
            elif abs(diff-60) <= 5: asp = "секстиль"
            elif abs(diff-90) <= 6: asp = "квадрат"
            elif abs(diff-120) <= 6: asp = "тригон"
            elif abs(diff-180) <= 6: asp = "оппозиция"
            else: continue
            aspects_list.append(f"{names[i]} {asp} {names[j]}")
    return aspects_list

def get_aspects_with_angles(natal):
    aspects = []
    names = [p for p in natal if p not in ['houses', 'Асцендент', 'MC']]
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            diff = abs(natal[names[i]]['lon'] - natal[names[j]]['lon']) % 360
            if diff > 180: diff = 360 - diff
            if diff <= 5: asp = 'соединение'
            elif abs(diff-60) <= 5: asp = 'секстиль'
            elif abs(diff-90) <= 6: asp = 'квадрат'
            elif abs(diff-120) <= 6: asp = 'тригон'
            elif abs(diff-180) <= 6: asp = 'оппозиция'
            else: continue
            aspects.append((names[i], names[j], asp, round(diff, 1)))
    return aspects

def calc_transit_aspects(natal, transits):
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
                    direction = "сход" if abs(diff - ideal) < 2 else "расход"
                    aspects.append({'transit_planet': t_name, 'transit_sign': t_data['sign'], 'natal_planet': n_name, 'natal_sign': n_data['sign'], 'aspect': asp_name, 'angle': round(diff, 1), 'direction': direction, 'transit_house': None})
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

def back_btn(): return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Назад", callback_data="back")]])

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

WAITING_EMOJI = ['🐱⏳', '😺⏳', '😸⏳', '😻⏳', '🐱⌛', '😺⌛', '🔮🐱⏳', '🌟🐱⌛']

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
        elif house['house_num'] == 4: ax.annotate('IC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 7: ax.annotate('DSC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
        elif house['house_num'] == 10: ax.annotate('MC', xy=(house_angle, 1.36), ha='center', va='center', fontsize=10, color='#e74c3c', weight='bold')
    
    title = 'НАТАЛЬНАЯ КАРТА'
    if city_name: title += f' • {city_name.title()}'
    if birth_time: title += f' • {birth_time}'
    fig.text(0.5, 0.97, title, ha='center', va='top', fontsize=16, color='#1a1a1a', weight='bold')
    plt.tight_layout(pad=1)
    buf = BytesIO(); plt.savefig(buf, format='png', dpi=200, bbox_inches='tight', facecolor='white', edgecolor='none')
    buf.seek(0); plt.close()
    return buf

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

async def natal_cmd(update, ctx):
    uid = update.effective_user.id
    if uid in users and 'sign' in users[uid]:
        u = users[uid]
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        img = draw_natal_chart_pro(natal, u['city'], f"{u['hour']:02d}:{u['minute']:02d}")
        await update.message.reply_photo(photo=img)
        await update.message.reply_text(f"🌟 *Натальная карта*\n📍 {u['city'].title()}\n☀ {natal['Солнце']['sign']} | 🌙 {natal['Луна']['sign']} | ASC {natal['Асцендент']['sign']}", reply_markup=overview_btn(), parse_mode='Markdown')
    else:
        await update.message.reply_text("🌟 *Натальная карта*\nВведите: `ДД.ММ.ГГГГ ЧЧ:ММ Город`", parse_mode='Markdown')

async def forecast_cmd(update, ctx):
    uid = update.effective_user.id
    if uid in users and 'sign' in users[uid]:
        await update.message.reply_text(f"✨ *{users[uid]['sign']}* — выберите период:", reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 День", callback_data="f_day"), InlineKeyboardButton("📆 Неделя", callback_data="f_week")],
            [InlineKeyboardButton("🗓 Месяц", callback_data="f_month")]
        ]), parse_mode='Markdown')
    else:
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
    t = calc_transits()
    now = get_current_time()
    phase_num = now.day % 8
    phases = {0: "🌑 Новолуние", 1: "🌒 Молодая", 2: "🌓 Первая четверть", 3: "🌔 Прибывающая", 4: "🌕 Полнолуние", 5: "🌖 Убывающая", 6: "🌗 Последняя четверть", 7: "🌘 Старая"}
    phase = phases.get(phase_num, "🌑")
    moon_sign = t['Луна']['sign']
    moon_deg = t['Луна']['degree']
    await update.message.reply_text(
        f"🌙 *Луна*\n📅 {now.strftime('%d.%m.%Y')}\n\nФаза: {phase}\nЗнак: *{moon_sign}* {moon_deg}°",
        parse_mode='Markdown'
    )

async def daily_cmd(update, ctx):
    now = get_current_time(); t = calc_transits()
    text = f"📅 *Гороскоп на {now.strftime('%d.%m.%Y')}*\n\n"
    planet_signs = {}
    for p in ['Солнце', 'Луна', 'Меркурий', 'Венера', 'Марс']:
        if p in t:
            planet_signs[p] = t[p]['sign']
    
    for sign in SIGN_NAMES:
        text += f"{SIGN_EMOJI.get(sign,'')} *{sign}*: "
        planets_here = [p for p, s in planet_signs.items() if s == sign]
        if planets_here:
            text += ', '.join(planets_here) + f" в знаке — {'энергия и активность' if 'Марс' in planets_here or 'Солнце' in planets_here else 'эмоции и чувства' if 'Луна' in planets_here else 'общение и контакты' if 'Меркурий' in planets_here else 'гармония и любовь' if 'Венера' in planets_here else 'влияние планет'}\n"
        else:
            text += "✨ Нейтральный день\n"
    await update.message.reply_text(text[:4000], parse_mode='Markdown')

async def delete_cmd(update, ctx):
    uid = update.effective_user.id
    if uid in users: del users[uid]; save_users()
    await update.message.reply_text("✅ *Данные удалены!*", parse_mode='Markdown')

async def support_cmd(update, ctx):
    await update.message.reply_text("💬 *Поддержка*\nПишите вопрос здесь.", parse_mode='Markdown')

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
            await q.edit_message_text("🔮 *Прогноз ИИ*\n\n📝 `15.05.1990 14:30 Москва`\n📝 `15.05.1990 Москва`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 С временем", callback_data="newdata"), InlineKeyboardButton("📝 Без времени", callback_data="newdata_noon")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]), parse_mode='Markdown')
    
    elif d.startswith('f_'):
        if uid not in users or 'sign' not in users[uid]: await q.message.reply_text("Введите данные рождения!"); return
        u = users[uid]; period = {'day':'день','week':'неделю','month':'месяц'}[d[2:]]
        now = get_current_time()
        ptitle = {'f_day':'сегодня','f_week':'неделю','f_month':'месяц'}.get(d, '')
        
        wait_msg = await q.message.reply_text(f"{random.choice(WAITING_EMOJI)} Рассчитываю прогноз на {ptitle}...")
        
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        transits = calc_transits()
        transit_aspects = calc_transit_aspects(natal, transits)
        aspects = get_aspects(natal)
        
        planet_data = []
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн']:
            if p in natal:
                house = get_house(natal[p]['lon'], natal['houses'])
                retro = '℞' if natal[p].get('retro') else ''
                planet_data.append(f"{p}:{natal[p]['sign']}{natal[p]['degree']}°({house}д){retro}")
        
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
            moon_data = []
            for h in [0, 6, 12, 18]:
                jd_h = swe.julday(now.year, now.month, now.day, h)
                m_lon = swe.calc_ut(jd_h, swe.MOON)[0][0]
                m_sign = sign_from_lon(m_lon)
                m_house = get_house(m_lon, natal['houses'])
                moon_data.append(f"{h:02d}:{m_sign}({m_house}д)")
            
            prompt = f"""Прогноз на день. Начинай сразу с прогноза.
{astro}
Луна: {' → '.join(moon_data)}

Дай 6-8 предл.: настроение, отношения, дела, совет. Упоминай планеты."""
            max_tok = 350
        
        elif d == 'f_month':
            prompt = f"""Прогноз на месяц. Начинай сразу с прогноза.
{astro}

Дай 10-12 предл.: любовь, карьера, энергия, совет. Упоминай транзитные аспекты."""
            max_tok = 1200
        else:
            prompt = f"""Прогноз на {period}. Начинай сразу с прогноза.
{astro}

Дай 6-8 предл.: любовь, карьера, энергия, совет. Упоминай аспекты."""
            max_tok = 500 if d == 'f_week' else 400
        
        forecast = ai_client.ask(prompt, max_tokens=max_tok)
        
        try: await wait_msg.delete()
        except: pass
        
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
        wait_msg = await q.message.reply_text(f"{random.choice(WAITING_EMOJI)} Рассчитываю натальную карту...")
        
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
        prompt = f"""Разбор натальной карты. Начинай сразу с разбора.
{astro_data}

Структура: ASC, Луна, Солнце, Меркурий, Венера, Марс, Узлы. 20-25 предл. Упоминай аспекты."""
        
        forecast = ai_client.ask(prompt, max_tokens=900)
        img = draw_natal_chart_pro(natal, u['city'], f"{u['hour']:02d}:{u['minute']:02d}")
        
        try: await wait_msg.delete()
        except: pass
        
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
        t = calc_transits()
        now = get_current_time()
        phase_num = now.day % 8
        phases = {0: "🌑 Новолуние", 1: "🌒 Молодая", 2: "🌓 Первая четверть", 3: "🌔 Прибывающая", 4: "🌕 Полнолуние", 5: "🌖 Убывающая", 6: "🌗 Последняя четверть", 7: "🌘 Старая"}
        phase = phases.get(phase_num, "🌑")
        moon_sign = t['Луна']['sign']
        moon_deg = t['Луна']['degree']
        await q.edit_message_text(
            f"🌙 *Луна*\n📅 {now.strftime('%d.%m.%Y')}\n\nФаза: {phase}\nЗнак: *{moon_sign}* {moon_deg}°",
            reply_markup=overview_btn(),
            parse_mode='Markdown'
        )
    
    elif d == 'daily':
        now = get_current_time(); t = calc_transits()
        text = f"📅 *Гороскоп на {now.strftime('%d.%m.%Y')}*\n\n"
        planet_signs = {}
        for p in ['Солнце', 'Луна', 'Меркурий', 'Венера', 'Марс']:
            if p in t:
                planet_signs[p] = t[p]['sign']
        
        for sign in SIGN_NAMES:
            text += f"{SIGN_EMOJI.get(sign,'')} *{sign}*: "
            planets_here = [p for p, s in planet_signs.items() if s == sign]
            if planets_here:
                text += ', '.join(planets_here) + f" в знаке — {'энергия и активность' if 'Марс' in planets_here or 'Солнце' in planets_here else 'эмоции и чувства' if 'Луна' in planets_here else 'общение и контакты' if 'Меркурий' in planets_here else 'гармония и любовь' if 'Венера' in planets_here else 'влияние планет'}\n"
            else:
                text += "✨ Нейтральный день\n"
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
            wait_msg = await update.message.reply_text(f"{random.choice(WAITING_EMOJI)} Рассчитываю совместимость...")
            fc = ai_client.ask(f"Совместимость {parts[0]} {parts[1]}. Процент и 3-4 предложения с рекомендациями.", 200)
            try: await wait_msg.delete()
            except: pass
            ctx.user_data['mode'] = ''
            await update.message.reply_text(f"💑 *{parts[0]} + {parts[1]}*\n\n{fc or '70% — Хорошая совместимость'}", reply_markup=overview_btn(), parse_mode='Markdown')
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
