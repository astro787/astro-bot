import os
import random
import requests
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import flatlib
from flatlib import const
from flatlib.datetime import Datetime
from flatlib.geopos import GeoPos
from flatlib.chart import Chart
from flatlib.aspects import getAspect

load_dotenv()

# ========== НАСТРОЙКИ ==========
HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

def ask_ai(prompt):
    try:
        r = requests.post(API_URL, headers=HEADERS, json={"inputs": prompt, "parameters": {"max_new_tokens": 300}}, timeout=30)
        data = r.json()
        if isinstance(data, list) and data:
            text = data[0]["generated_text"].strip()
            if "[/INST]" in text:
                text = text.split("[/INST]")[-1].strip()
            return text
    except:
        pass
    return None

# ========== АСТРОЛОГИЯ ==========
ZODIAC_SIGNS = {
    'Овен': (3, 21, 4, 19), 'Телец': (4, 20, 5, 20),
    'Близнецы': (5, 21, 6, 20), 'Рак': (6, 21, 7, 22),
    'Лев': (7, 23, 8, 22), 'Дева': (8, 23, 9, 22),
    'Весы': (9, 23, 10, 22), 'Скорпион': (10, 23, 11, 21),
    'Стрелец': (11, 22, 12, 21), 'Козерог': (12, 22, 1, 19),
    'Водолей': (1, 20, 2, 18), 'Рыбы': (2, 19, 3, 20)
}

SIGN_NAMES = list(ZODIAC_SIGNS.keys())

PLANET_NAMES = {
    const.SUN: 'Солнце', const.MOON: 'Луна', const.MERCURY: 'Меркурий',
    const.VENUS: 'Венера', const.MARS: 'Марс', const.JUPITER: 'Юпитер',
    const.SATURN: 'Сатурн', const.URANUS: 'Уран', const.NEPTUNE: 'Нептун', const.PLUTO: 'Плутон'
}

SIGN_EMOJI = {
    'Овен': '♈', 'Телец': '♉', 'Близнецы': '♊', 'Рак': '♋',
    'Лев': '♌', 'Дева': '♍', 'Весы': '♎', 'Скорпион': '♏',
    'Стрелец': '♐', 'Козерог': '♑', 'Водолей': '♒', 'Рыбы': '♓'
}

users = {}

# ========== ФУНКЦИИ РАСЧЁТА ==========

def get_natal_chart(day, month, year, hour=12, minute=0):
    """Рассчитывает натальную карту"""
    date = Datetime(f"{year:04d}/{month:02d}/{day:02d}", f"{hour:02d}:{minute:02d}", '+00:00')
    pos = GeoPos(0, 0)  # По умолчанию UTC
    chart = Chart(date, pos, IDs=flatlib.listIDs())
    
    planets = {}
    for obj_id in [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS, 
                   const.JUPITER, const.SATURN]:
        obj = chart.get(obj_id)
        planets[PLANET_NAMES[obj_id]] = {
            'sign': obj.sign,
            'degree': int(obj.lon % 30),
            'lon': obj.lon
        }
    
    # Асцендент (приблизительно)
    asc = chart.get(const.ASC)
    planets['Асцендент'] = {'sign': asc.sign, 'degree': int(asc.lon % 30)}
    
    return planets

def get_current_transits():
    """Текущие транзиты планет"""
    now = datetime.utcnow()
    date = Datetime(now.strftime("%Y/%m/%d"), now.strftime("%H:%M"), '+00:00')
    pos = GeoPos(0, 0)
    chart = Chart(date, pos, IDs=flatlib.listIDs())
    
    transits = {}
    for obj_id in [const.SUN, const.MOON, const.MERCURY, const.VENUS, const.MARS,
                   const.JUPITER, const.SATURN]:
        obj = chart.get(obj_id)
        transits[PLANET_NAMES[obj_id]] = {
            'sign': obj.sign,
            'degree': int(obj.lon % 30)
        }
    
    return transits

def get_aspects(chart1, chart2=None):
    """Находит аспекты между планетами"""
    aspects = []
    planets = list(chart1.keys())
    
    for i in range(len(planets)):
        for j in range(i+1, len(planets)):
            p1, p2 = planets[i], planets[j]
            if p1 == 'Асцендент' or p2 == 'Асцендент':
                continue
            lon1 = chart1[p1]['lon']
            lon2 = chart1[p2]['lon']
            diff = abs(lon1 - lon2) % 360
            if diff > 180:
                diff = 360 - diff
            
            aspect_type = None
            if diff <= 5:
                aspect_type = "соединение"
            elif abs(diff - 60) <= 5:
                aspect_type = "секстиль"
            elif abs(diff - 90) <= 5:
                aspect_type = "квадрат"
            elif abs(diff - 120) <= 5:
                aspect_type = "тригон"
            elif abs(diff - 180) <= 5:
                aspect_type = "оппозиция"
            
            if aspect_type:
                aspects.append(f"{p1} {aspect_type} {p2}")
    
    return aspects

def get_zodiac_sign(day, month):
    for sign, (sm, sd, em, ed) in ZODIAC_SIGNS.items():
        if (month == sm and day >= sd) or (month == em and day <= ed):
            return sign
    return 'Козерог'

# ========== КНОПКИ ==========
def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="back")]])

def menu_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast")],
        [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],
        [InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
        [InlineKeyboardButton("💑 Совместимость", callback_data="compat")],
        [InlineKeyboardButton("🌙 Луна", callback_data="moon")],
        [InlineKeyboardButton("📅 Сегодня", callback_data="daily")]
    ])

# ========== КОМАНДЫ ==========
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['mode'] = ''
    await update.message.reply_text(
        "🌟 *Астро-бот с ИИ и астрологией* 🌟\n\nВыберите:",
        reply_markup=menu_btn(), parse_mode='Markdown'
    )

async def btn(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    d = q.data
    uid = q.from_user.id

    if d == 'forecast':
        if uid in users:
            ctx.user_data['mode'] = 'fp'
            kb = [
                [InlineKeyboardButton("📅 День", callback_data="f_day"),
                 InlineKeyboardButton("📆 Неделя", callback_data="f_week")],
                [InlineKeyboardButton("🗓 Месяц", callback_data="f_month")],
                [InlineKeyboardButton("🔙 Меню", callback_data="back")]
            ]
            await q.edit_message_text(f"✨ *{users[uid]['sign']}* ✨\n\nПериод прогноза:", 
                reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await q.edit_message_text("📝 Введите дату: ДД.ММ.ГГГГ", reply_markup=back_btn())

    elif d.startswith('f_'):
        if uid not in users:
            await q.message.reply_text("Сначала введите дату!")
            return
        
        period = {'day': 'день', 'week': 'неделю', 'month': 'месяц'}[d[2:]]
        await q.message.reply_text("🔮 Рассчитываю и генерирую прогноз...")
        
        # Получаем натальную карту и транзиты
        u = users[uid]
        natal = get_natal_chart(u['day'], u['month'], u['year'])
        transits = get_current_transits()
        aspects = get_aspects(natal)
        
        # Формируем астрологические данные
        astro_data = f"Натальная карта:\n"
        for planet, data in natal.items():
            if planet != 'Асцендент':
                astro_data += f"{planet}: {data['sign']} {data['degree']}°\n"
        astro_data += f"Асцендент: {natal.get('Асцендент', {}).get('sign', '?')}\n\n"
        astro_data += f"Транзиты сегодня:\n"
        for planet, data in transits.items():
            astro_data += f"{planet}: {data['sign']} {data['degree']}°\n"
        astro_data += f"\nАспекты: {', '.join(aspects[:3]) if aspects else 'нет значимых'}"
        
        # Запрос к ИИ
        prompt = f"""Ты профессиональный астролог. Дай прогноз на {period} на основе реальных астрологических данных:

{astro_data}

Дай прогноз по сферам: любовь, карьера, здоровье, совет. Пиши вдохновляюще, с эмодзи. 5-7 предложений."""
        
        forecast = ask_ai(prompt)
        if not forecast:
            forecast = f"✨ Прогноз на {period} для {u['sign']}\n\n❤️ Любовь\n💼 Карьера\n🏃 Здоровье"
        
        await update.effective_message.reply_text(
            f"🌟 *Прогноз на {period}* 🌟\n\n{forecast}\n\n📊 *Астроданные:*\n{astro_data[:300]}...",
            reply_markup=back_btn(), parse_mode='Markdown'
        )

    elif d == 'natal':
        if uid not in users:
            await q.edit_message_text("📝 Введите дату: ДД.ММ.ГГГГ", reply_markup=back_btn())
            return
        
        u = users[uid]
        natal = get_natal_chart(u['day'], u['month'], u['year'])
        aspects = get_aspects(natal)
        
        text = f"🌟 *Натальная карта* 🌟\n\n"
        for planet, data in natal.items():
            text += f"{SIGN_EMOJI.get(data['sign'], '')} {planet}: *{data['sign']}* {data['degree']}°\n"
        text += f"\n🔹 *Аспекты:*\n"
        if aspects:
            for a in aspects[:5]:
                text += f"• {a}\n"
        else:
            text += "Нет значимых аспектов\n"
        
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'transits':
        if uid not in users:
            await q.edit_message_text("📝 Сначала введите дату!", reply_markup=back_btn())
            return
        
        transits = get_current_transits()
        text = "🪐 *Текущие транзиты*\n\n"
        text += f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n\n"
        for planet, data in transits.items():
            text += f"{SIGN_EMOJI.get(data['sign'], '')} {planet}: *{data['sign']}* {data['degree']}°\n"
        
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'compat':
        ctx.user_data['mode'] = 'compat'
        await q.edit_message_text("💑 Два знака: *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'moon':
        transits = get_current_transits()
        moon_data = transits.get('Луна', {'sign': '?', 'degree': 0})
        phase = datetime.now().day % 8
        phases = {0: "🌑 Новолуние", 1: "🌒", 2: "🌓", 3: "🌔", 
                  4: "🌕 Полнолуние", 5: "🌖", 6: "🌗", 7: "🌘"}
        
        text = f"🌙 *Лунный календарь*\n\n"
        text += f"Фаза: {phases[phase]}\n"
        text += f"Луна в знаке: *{moon_data['sign']}* {moon_data['degree']}°\n"
        text += f"📅 {datetime.now().strftime('%d.%m.%Y')}"
        
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'daily':
        text = "📅 *Гороскоп на сегодня*\n\n"
        transits = get_current_transits()
        sun_sign = transits.get('Солнце', {}).get('sign', '')
        
        for sign in SIGN_NAMES:
            text += f"{SIGN_EMOJI.get(sign, '')} *{sign}*: "
            if sign == sun_sign:
                text += "☀️ Солнце в вашем знаке — день силы!\n"
            else:
                text += "✨ Благоприятный день\n"
        
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'back':
        ctx.user_data['mode'] = ''
        await q.edit_message_text("🌟 *Меню*", reply_markup=menu_btn(), parse_mode='Markdown')

async def msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    t = update.message.text.strip()
    m = ctx.user_data.get('mode', '')
    uid = update.effective_user.id

    if m == 'compat':
        parts = t.title().split()
        if len(parts) == 2 and parts[0] in SIGN_NAMES and parts[1] in SIGN_NAMES:
            prompt = f"Ты астролог. Оцени совместимость знаков {parts[0]} и {parts[1]}. Дай процент совместимости и 2-3 предложения."
            forecast = ask_ai(prompt)
            if not forecast:
                forecast = "70% — Хорошая совместимость"
            ctx.user_data['mode'] = ''
            await update.message.reply_text(
                f"💑 *{parts[0]} + {parts[1]}*\n\n{forecast}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💑 Ещё", callback_data="compat"),
                     InlineKeyboardButton("🔙 Меню", callback_data="back")]
                ]), parse_mode='Markdown'
            )
            return
        await update.message.reply_text("❌ Пример: *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')
        return

    try:
        day, month, year = map(int, t.split('.'))
        sign = get_zodiac_sign(day, month)
        users[uid] = {'sign': sign, 'day': day, 'month': month, 'year': year}
        
        kb = [
            [InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast")],
            [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],
            [InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
            [InlineKeyboardButton("🔙 Меню", callback_data="back")]
        ]
        await update.message.reply_text(
            f"✨ *{sign}* ✨\n\nДата: {day:02d}.{month:02d}.{year}",
            reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown'
        )
    except:
        await update.message.reply_text("❌ Формат: ДД.ММ.ГГГГ", reply_markup=back_btn())

def main():
    app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
