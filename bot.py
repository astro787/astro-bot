import os
import swisseph as swe
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import requests

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

def ask_ai(prompt):
    try:
        r = requests.post(API_URL, headers=HEADERS, json={"inputs": prompt, "parameters": {"max_new_tokens": 400}}, timeout=40)
        d = r.json()
        if isinstance(d, list) and d: return d[0]["generated_text"].strip()
    except: pass
    return None

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

# Координаты городов (широта, долгота)
CITIES = {
    'москва': (55.75, 37.62), 'мск': (55.75, 37.62),
    'питер': (59.93, 30.33), 'спб': (59.93, 30.33), 'санкт-петербург': (59.93, 30.33),
    'новосибирск': (55.03, 82.92), 'нск': (55.03, 82.92),
    'екатеринбург': (56.84, 60.65), 'екб': (56.84, 60.65),
    'казань': (55.79, 49.12), 'нижний': (56.33, 44.0), 'нн': (56.33, 44.0),
    'челябинск': (55.16, 61.43), 'омск': (54.99, 73.37),
    'самара': (53.2, 50.15), 'ростов': (47.23, 39.72),
    'уфа': (54.74, 55.97), 'красноярск': (56.02, 92.87),
    'воронеж': (51.67, 39.18), 'пермь': (58.01, 56.25),
    'волгоград': (48.71, 44.5), 'краснодар': (45.04, 38.98),
    'сочи': (43.59, 39.73), 'владивосток': (43.12, 131.89),
    'якутск': (62.03, 129.73), 'иркутск': (52.29, 104.3),
    'хабаровск': (48.48, 135.08), 'калининград': (54.71, 20.51),
    'минск': (53.9, 27.57), 'киев': (50.45, 30.52),
    'алматы': (43.26, 76.93), 'астана': (51.17, 71.43),
    'нью-йорк': (40.71, -74.0), 'лондон': (51.51, -0.13),
    'париж': (48.86, 2.35), 'берлин': (52.52, 13.4),
    'токио': (35.68, 139.76), 'пекин': (39.9, 116.4),
    'дубай': (25.2, 55.27), 'стамбул': (41.01, 28.98),
}

PLANETS = {'Солнце': swe.SUN, 'Луна': swe.MOON, 'Меркурий': swe.MERCURY,
           'Венера': swe.VENUS, 'Марс': swe.MARS, 'Юпитер': swe.JUPITER,
           'Сатурн': swe.SATURN, 'Уран': swe.URANUS, 'Нептун': swe.NEPTUNE, 'Плутон': swe.PLUTO}

HOUSE_NAMES = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII']

users = {}

def get_zodiac_sign(day, month):
    for sign, (sm, sd, em, ed) in ZODIAC_SIGNS.items():
        if (month == sm and day >= sd) or (month == em and day <= ed): return sign
    return 'Козерог'

def sign_from_lon(lon):
    return SIGN_NAMES[int(lon // 30)]

def degree_in_sign(lon):
    return int(lon % 30)

def calc_natal(day, month, year, hour=12, minute=0, lat=55.75, lon=37.62):
    jd = swe.julday(year, month, day, hour + minute/60.0)
    natal = {}
    for name, pid in PLANETS.items():
        lon_deg = swe.calc_ut(jd, pid)[0][0]
        natal[name] = {'sign': sign_from_lon(lon_deg), 'degree': degree_in_sign(lon_deg), 'lon': lon_deg}
    houses, ascmc = swe.houses(jd, lat, lon, b'P')
    natal['Асцендент'] = {'sign': sign_from_lon(ascmc[0]), 'degree': degree_in_sign(ascmc[0]), 'lon': ascmc[0]}
    natal['MC'] = {'sign': sign_from_lon(ascmc[1]), 'degree': degree_in_sign(ascmc[1]), 'lon': ascmc[1]}
    natal['houses'] = []
    for i in range(12):
        natal['houses'].append({'sign': sign_from_lon(houses[i]), 'degree': degree_in_sign(houses[i])})
    return natal

def calc_transits():
    now = datetime.utcnow()
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
    transits = {}
    for name, pid in PLANETS.items():
        lon_deg = swe.calc_ut(jd, pid)[0][0]
        transits[name] = {'sign': sign_from_lon(lon_deg), 'degree': degree_in_sign(lon_deg), 'lon': lon_deg}
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

def parse_city(city_str):
    return CITIES.get(city_str.lower().strip(), (55.75, 37.62))

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="back")]])

def menu_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast")],
        [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],
        [InlineKeyboardButton("🏠 Дома гороскопа", callback_data="houses")],
        [InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
        [InlineKeyboardButton("💑 Совместимость", callback_data="compat")],
        [InlineKeyboardButton("🌙 Луна", callback_data="moon")],
        [InlineKeyboardButton("📅 Гороскоп", callback_data="daily")]
    ])

async def start(update, ctx):
    ctx.user_data['mode'] = ''
    await update.message.reply_text(
        "🌟 *Астро-бот с точной астрологией* 🌟\n\n"
        "Введите данные в формате:\n"
        "*ДД.ММ.ГГГГ ЧЧ ММ Город*\n\n"
        "Пример: *15.05.1990 14 30 Москва*\n"
        "Или просто: *15.05.1990* (полдень, Москва)",
        reply_markup=menu_btn(), parse_mode='Markdown'
    )

async def btn(update, ctx):
    q = update.callback_query; await q.answer(); d = q.data; uid = q.from_user.id

    if d == 'forecast':
        if uid in users:
            ctx.user_data['mode'] = 'fp'
            kb = [[InlineKeyboardButton("📅 День", callback_data="f_day"), InlineKeyboardButton("📆 Неделя", callback_data="f_week")],
                  [InlineKeyboardButton("🗓 Месяц", callback_data="f_month")], [InlineKeyboardButton("🔙 Меню", callback_data="back")]]
            await q.edit_message_text(f"✨ *{users[uid]['sign']}* ✨\n\nПериод:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await q.edit_message_text("📝 Введите: *ДД.ММ.ГГГГ ЧЧ ММ Город*\nПример: 15.05.1990 14 30 Москва", reply_markup=back_btn(), parse_mode='Markdown')

    elif d.startswith('f_'):
        if uid not in users: await q.message.reply_text("Сначала введите данные!"); return
        u = users[uid]; period = {'day':'день','week':'неделю','month':'месяц'}[d[2:]]
        await q.message.reply_text("🔮 Рассчитываю и генерирую прогноз...")
        
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'])
        transits = calc_transits()
        aspects = get_aspects(natal)
        
        astro = f"Карта: ☀ {natal['Солнце']['sign']} {natal['Солнце']['degree']}°, "
        astro += f"🌙 {natal['Луна']['sign']} {natal['Луна']['degree']}°, "
        astro += f"ASC {natal['Асцендент']['sign']}, MC {natal['MC']['sign']}\n"
        astro += f"Транзиты: ☀ {transits['Солнце']['sign']}, 🌙 {transits['Луна']['sign']}, ♂ {transits['Марс']['sign']}\n"
        if aspects: astro += f"Аспекты: {', '.join(aspects[:3])}"
        
        prompt = f"Ты астролог. Прогноз на {period}:\n{astro}\n\n6-8 предложений по сферам: любовь, карьера, здоровье, совет. С эмодзи."
        forecast = ask_ai(prompt) or f"✨ Прогноз на {period}\n\n❤️ Любовь\n💼 Карьера\n🏃 Здоровье"
        await update.effective_message.reply_text(f"🌟 *Прогноз на {period}* 🌟\n\n{forecast}", reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'natal':
        if uid not in users: await q.edit_message_text("📝 Введите данные", reply_markup=back_btn()); return
        u = users[uid]; natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'])
        aspects = get_aspects(natal)
        text = f"🌟 *Натальная карта*\n📍 {u['city']} ({u['lat']}, {u['lon']})\n🕐 {u['hour']:02d}:{u['minute']:02d} UTC\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Уран','Нептун','Плутон','Асцендент','MC']:
            if p in natal: text += f"{SIGN_EMOJI.get(natal[p]['sign'],'')} {p}: *{natal[p]['sign']}* {natal[p]['degree']}°\n"
        if aspects:
            text += f"\n🔹 *Аспекты:*\n"
            for a in aspects[:6]: text += f"• {a}\n"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'houses':
        if uid not in users: await q.edit_message_text("📝 Введите данные", reply_markup=back_btn()); return
        u = users[uid]; natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'])
        text = f"🏠 *Дома гороскопа*\n📍 {u['city']}\n🕐 {u['hour']:02d}:{u['minute']:02d}\n\n"
        for i, house in enumerate(natal['houses']):
            text += f"*{i+1} дом*: {SIGN_EMOJI.get(house['sign'],'')} {house['sign']} {house['degree']}°\n"
        text += f"\n⬆ Асцендент: *{natal['Асцендент']['sign']}* {natal['Асцендент']['degree']}°"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'transits':
        transits = calc_transits()
        text = f"🪐 *Транзиты*\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн']:
            text += f"{SIGN_EMOJI.get(transits[p]['sign'],'')} {p}: *{transits[p]['sign']}* {transits[p]['degree']}°\n"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'compat':
        ctx.user_data['mode'] = 'compat'
        await q.edit_message_text("💑 Два знака: *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'moon':
        transits = calc_transits()
        phase = datetime.now().day % 8
        phases = {0:"🌑 Новолуние",1:"🌒",2:"🌓",3:"🌔",4:"🌕 Полнолуние",5:"🌖",6:"🌗",7:"🌘"}
        text = f"🌙 *Луна*\n\nФаза: {phases[phase]}\nЗнак: *{transits['Луна']['sign']}* {transits['Луна']['degree']}°"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'daily':
        text = "📅 *Сегодня*\n\n"
        transits = calc_transits()
        for sign in SIGN_NAMES:
            text += f"{SIGN_EMOJI.get(sign,'')} *{sign}*: "
            if sign == transits['Солнце']['sign']: text += "☀️ Солнце в знаке!\n"
            elif sign == transits['Луна']['sign']: text += "🌙 Луна в знаке\n"
            else: text += "✨ Хороший день\n"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'back':
        ctx.user_data['mode'] = ''
        await q.edit_message_text("🌟 *Меню*", reply_markup=menu_btn(), parse_mode='Markdown')

async def msg(update, ctx):
    t = update.message.text.strip(); m = ctx.user_data.get('mode',''); uid = update.effective_user.id
    
    if m == 'compat':
        parts = t.title().split()
        if len(parts)==2 and parts[0] in SIGN_NAMES and parts[1] in SIGN_NAMES:
            prompt = f"Совместимость {parts[0]} и {parts[1]}. Процент и 2-3 предложения."
            fc = ask_ai(prompt) or "70% — Хорошая совместимость"
            ctx.user_data['mode'] = ''
            await update.message.reply_text(f"💑 *{parts[0]} + {parts[1]}*\n\n{fc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💑 Ещё", callback_data="compat"),InlineKeyboardButton("🔙 Меню", callback_data="back")]]), parse_mode='Markdown')
            return
        await update.message.reply_text("❌ *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')
        return
    
    # Разбор даты, времени и города
    try:
        parts = t.split()
        if len(parts) >= 3:
            # Формат: ДД.ММ.ГГГГ ЧЧ ММ [Город]
            date_part = parts[0]
            day, month, year = map(int, date_part.split('.'))
            hour = int(parts[1]) if len(parts) > 1 else 12
            minute = int(parts[2]) if len(parts) > 2 else 0
            city_str = ' '.join(parts[3:]) if len(parts) > 3 else 'москва'
        elif '.' in t and len(t.split('.')) == 3:
            day, month, year = map(int, t.split('.'))
            hour, minute = 12, 0
            city_str = 'москва'
        else:
            raise ValueError
        
        lat, lon = parse_city(city_str)
        city_name = city_str.title()
        sign = get_zodiac_sign(day, month)
        users[uid] = {'sign': sign, 'day': day, 'month': month, 'year': year,
                      'hour': hour, 'minute': minute, 'lat': lat, 'lon': lon, 'city': city_name}
        
        kb = [[InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast")],
              [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],
              [InlineKeyboardButton("🏠 Дома гороскопа", callback_data="houses")],
              [InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
              [InlineKeyboardButton("🔙 Меню", callback_data="back")]]
        await update.message.reply_text(
            f"✨ *{sign}* ✨\n📅 {day:02d}.{month:02d}.{year}\n🕐 {hour:02d}:{minute:02d}\n📍 {city_name}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown'
        )
    except:
        await update.message.reply_text(
            "❌ Форматы:\n• *15.05.1990*\n• *15.05.1990 14 30*\n• *15.05.1990 14 30 Москва*\n• *15.05.1990 14 30 Нью-Йорк*",
            reply_markup=back_btn(), parse_mode='Markdown'
        )

def main():
    app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
