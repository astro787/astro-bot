import os
import swisseph as swe
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import requests

load_dotenv()

# HuggingFace ИИ
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

# Настройка эфемерид
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

PLANETS = {'Солнце': swe.SUN, 'Луна': swe.MOON, 'Меркурий': swe.MERCURY,
           'Венера': swe.VENUS, 'Марс': swe.MARS, 'Юпитер': swe.JUPITER,
           'Сатурн': swe.SATURN, 'Уран': swe.URANUS, 'Нептун': swe.NEPTUNE, 'Плутон': swe.PLUTO}

users = {}

def get_zodiac_sign(day, month):
    for sign, (sm, sd, em, ed) in ZODIAC_SIGNS.items():
        if (month == sm and day >= sd) or (month == em and day <= ed): return sign
    return 'Козерог'

def sign_from_lon(lon):
    return SIGN_NAMES[int(lon // 30)]

def degree_in_sign(lon):
    return int(lon % 30)

def calc_natal(day, month, year, hour=12, minute=0):
    jd = swe.julday(year, month, day, hour + minute/60.0)
    natal = {}
    for name, pid in PLANETS.items():
        lon = swe.calc_ut(jd, pid)[0][0]
        natal[name] = {'sign': sign_from_lon(lon), 'degree': degree_in_sign(lon), 'lon': lon}
    # Асцендент (UTC 0)
    houses, ascmc = swe.houses(jd, 0, 0, b'P')
    natal['Асцендент'] = {'sign': sign_from_lon(ascmc[0]), 'degree': degree_in_sign(ascmc[0])}
    return natal

def calc_transits():
    now = datetime.utcnow()
    jd = swe.julday(now.year, now.month, now.day, now.hour + now.minute/60.0)
    transits = {}
    for name, pid in PLANETS.items():
        lon = swe.calc_ut(jd, pid)[0][0]
        transits[name] = {'sign': sign_from_lon(lon), 'degree': degree_in_sign(lon), 'lon': lon}
    return transits

def get_aspects(planets):
    aspects_list = []
    names = list(planets.keys())
    for i in range(len(names)):
        for j in range(i+1, len(names)):
            if names[i] == 'Асцендент' or names[j] == 'Асцендент': continue
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

def back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Меню", callback_data="back")]])

def menu_btn():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast")],
        [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],
        [InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
        [InlineKeyboardButton("💑 Совместимость", callback_data="compat")],
        [InlineKeyboardButton("🌙 Луна", callback_data="moon")],
        [InlineKeyboardButton("📅 Гороскоп", callback_data="daily")]
    ])

async def start(update, ctx):
    ctx.user_data['mode'] = ''
    await update.message.reply_text("🌟 *Астро-бот с точной астрологией* 🌟\n\nВыберите:", reply_markup=menu_btn(), parse_mode='Markdown')

async def btn(update, ctx):
    q = update.callback_query; await q.answer(); d = q.data; uid = q.from_user.id

    if d == 'forecast':
        if uid in users:
            ctx.user_data['mode'] = 'fp'
            kb = [[InlineKeyboardButton("📅 День", callback_data="f_day"), InlineKeyboardButton("📆 Неделя", callback_data="f_week")],
                  [InlineKeyboardButton("🗓 Месяц", callback_data="f_month")], [InlineKeyboardButton("🔙 Меню", callback_data="back")]]
            await q.edit_message_text(f"✨ *{users[uid]['sign']}* ✨\n\nПериод:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await q.edit_message_text("📝 Дата рождения: ДД.ММ.ГГГГ", reply_markup=back_btn())

    elif d.startswith('f_'):
        if uid not in users: await q.message.reply_text("Сначала дату!"); return
        u = users[uid]; period = {'day':'день','week':'неделю','month':'месяц'}[d[2:]]
        await q.message.reply_text("🔮 Рассчитываю планеты и генерирую прогноз...")
        
        natal = calc_natal(u['day'], u['month'], u['year'])
        transits = calc_transits()
        aspects = get_aspects(natal)
        
        astro = f"Натальная карта:\nСолнце {natal['Солнце']['sign']} {natal['Солнце']['degree']}°\n"
        astro += f"Луна {natal['Луна']['sign']} {natal['Луна']['degree']}°\n"
        astro += f"Асцендент {natal['Асцендент']['sign']}\n\nТранзиты:\n"
        astro += f"Солнце {transits['Солнце']['sign']} {transits['Солнце']['degree']}°\n"
        astro += f"Луна {transits['Луна']['sign']} {transits['Луна']['degree']}°\n"
        astro += f"Марс {transits['Марс']['sign']}\n"
        if aspects: astro += f"\nАспекты: {', '.join(aspects[:3])}"
        
        prompt = f"Ты астролог. Прогноз на {period} для человека с такими данными:\n{astro}\n\nДай прогноз по сферам: любовь, карьера, здоровье, совет. 6-8 предложений с эмодзи."
        forecast = ask_ai(prompt) or f"✨ Прогноз на {period}\n\n❤️ Любовь\n💼 Карьера\n🏃 Здоровье"
        await update.effective_message.reply_text(f"🌟 *Прогноз на {period}* 🌟\n\n{forecast}", reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'natal':
        if uid not in users: await q.edit_message_text("📝 Дата: ДД.ММ.ГГГГ", reply_markup=back_btn()); return
        u = users[uid]; natal = calc_natal(u['day'], u['month'], u['year'])
        aspects = get_aspects(natal)
        text = f"🌟 *Натальная карта*\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Уран','Нептун','Плутон','Асцендент']:
            if p in natal: text += f"{SIGN_EMOJI.get(natal[p]['sign'],'')} {p}: *{natal[p]['sign']}* {natal[p]['degree']}°\n"
        if aspects:
            text += f"\n🔹 *Аспекты:*\n"
            for a in aspects[:5]: text += f"• {a}\n"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'transits':
        transits = calc_transits()
        text = f"🪐 *Транзиты планет*\n\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')} UTC\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн']:
            if p in transits: text += f"{SIGN_EMOJI.get(transits[p]['sign'],'')} {p}: *{transits[p]['sign']}* {transits[p]['degree']}°\n"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'compat':
        ctx.user_data['mode'] = 'compat'
        await q.edit_message_text("💑 Два знака: *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'moon':
        transits = calc_transits()
        phase = datetime.now().day % 8
        phases = {0:"🌑 Новолуние",1:"🌒",2:"🌓",3:"🌔",4:"🌕 Полнолуние",5:"🌖",6:"🌗",7:"🌘"}
        text = f"🌙 *Луна*\n\nФаза: {phases[phase]}\nЗнак: *{transits['Луна']['sign']}* {transits['Луна']['degree']}°\n\n📅 {datetime.now().strftime('%d.%m.%Y')}"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'daily':
        text = "📅 *Гороскоп на сегодня*\n\n"
        transits = calc_transits()
        for sign in SIGN_NAMES:
            text += f"{SIGN_EMOJI.get(sign,'')} *{sign}*: "
            if sign == transits['Солнце']['sign']: text += "☀️ Солнце в знаке — день силы!\n"
            elif sign == transits['Луна']['sign']: text += "🌙 Луна в знаке — эмоции активны\n"
            else: text += "✨ Благоприятный день\n"
        await q.edit_message_text(text, reply_markup=back_btn(), parse_mode='Markdown')

    elif d == 'back':
        ctx.user_data['mode'] = ''
        await q.edit_message_text("🌟 *Меню*", reply_markup=menu_btn(), parse_mode='Markdown')

async def msg(update, ctx):
    t = update.message.text.strip(); m = ctx.user_data.get('mode',''); uid = update.effective_user.id
    if m == 'compat':
        parts = t.title().split()
        if len(parts)==2 and parts[0] in SIGN_NAMES and parts[1] in SIGN_NAMES:
            prompt = f"Ты астролог. Оцени совместимость {parts[0]} и {parts[1]}. Дай процент и 2-3 предложения."
            fc = ask_ai(prompt) or "70% — Хорошая совместимость"
            ctx.user_data['mode'] = ''
            await update.message.reply_text(f"💑 *{parts[0]} + {parts[1]}*\n\n{fc}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💑 Ещё", callback_data="compat"),InlineKeyboardButton("🔙 Меню", callback_data="back")]]), parse_mode='Markdown')
            return
        await update.message.reply_text("❌ *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')
        return
    try:
        day, month, year = map(int, t.split('.'))
        sign = get_zodiac_sign(day, month)
        users[uid] = {'sign': sign, 'day': day, 'month': month, 'year': year}
        kb = [[InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast")],[InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],[InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],[InlineKeyboardButton("🔙 Меню", callback_data="back")]]
        await update.message.reply_text(f"✨ *{sign}* ✨\n\n{day:02d}.{month:02d}.{year}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except:
        await update.message.reply_text("❌ ДД.ММ.ГГГГ", reply_markup=back_btn())

def main():
    app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
