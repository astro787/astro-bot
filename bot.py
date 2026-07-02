# bot.py — ОСНОВНОЙ ФАЙЛ
import time
import sys
import os as _os
import socket
import random
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import atexit

# Импорты наших модулей
from ai_client import ai_client
from astro_calc import *
from data_storage import users, save_users, load_users
from cities import CITIES, CITY_TIMEZONES
from chart_drawer import draw_natal_chart_pro
from support import support_start, forward_to_admin, reply_to_user
from config import CAT_EMOJI, cat_emoji, ADMIN_ID

load_dotenv()

SUPPORT_TOKEN = os.getenv("SUPPORT_TOKEN")

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

# Загружаем пользователей
load_users()
atexit.register(save_users)

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

# ===== ОСНОВНЫЕ ФУНКЦИИ БОТА =====
async def start(update, ctx):
    ctx.user_data['mode'] = ''
    uid = update.effective_user.id
    if uid not in users:
        users[uid] = {}
    users[uid]['consent'] = True
    users[uid]['consent_date'] = datetime.now().strftime('%d.%m.%Y %H:%M')
    save_users()
    
    welcome_text = f"""
{cat_emoji()} *АстроБот — ваш персональный астролог*

✨ Создан практикующим астрологом с 12-летним опытом

🔬 *Возможности:*
• 🌟 Натальная карта с графикой
• 🔮 Прогнозы по реальным транзитам (день/неделя/месяц)
• 💞 Совместимость
• 🌙 Лунный календарь
• 🪐 Точные транзитные аспекты

🌍 150+ городов мира | 🎯 Швейцарские эфемериды | 🤖 DeepSeek AI

─────────────────────
📄 *Нажимая кнопку СТАРТ, вы подтверждаете согласие с:*
• Политикой конфиденциальности
• Договором-офертой
• Согласием на обработку данных

Если вы не согласны — просто покиньте бота.
─────────────────────
"""
    await update.message.reply_text(
        welcome_text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🚀 СТАРТ", callback_data="start_accept")]]),
        parse_mode='Markdown'
    )

async def help_command(update, ctx):
    help_text = """
📖 *Справка по АстроБоту*
👤 *Автор:* Практикующий астролог с 12-летним стажем

📝 *Форматы ввода:* `ДД.ММ.ГГГГ`, `ДД.ММ.ГГГГ ЧЧ:ММ`, `ДД.ММ.ГГГГ ЧЧ:ММ Город`
🌍 150+ городов мира | 🤖 DeepSeek AI | 🎯 Точные аспекты
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def logtest(update, ctx):
    await update.message.reply_text(f"{cat_emoji()} Запускаю диагностику...")
    now = get_current_time()
    await update.message.reply_text(f"🕐 Время сервера: {now.strftime('%d.%m.%Y %H:%M:%S')} UTC")
    
    token = os.getenv("DEEPSEEK_TOKEN")
    if token:
        try:
            import requests as req
            resp = req.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"model": "deepseek-chat", "messages": [{"role": "user", "content": "OK"}], "max_tokens": 10},
                timeout=15
            )
            await update.message.reply_text("✅ DeepSeek работает!" if resp.status_code == 200 else f"❌ DeepSeek error {resp.status_code}")
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {e}")
    else:
        await update.message.reply_text("❌ DEEPSEEK_TOKEN не найден!")

async def btn(update, ctx):
    q = update.callback_query; await q.answer(); d = q.data; uid = q.from_user.id
    
    if d == 'start_accept':
        await q.edit_message_reply_markup(reply_markup=None)
        await q.message.reply_text(
            f"{cat_emoji()} *Добро пожаловать!*\n\n"
            "Введите данные своего рождения:\n`ДД.ММ.ГГГГ` или `ДД.ММ.ГГГГ 14:30 Москва`",
            reply_markup=menu_btn(), parse_mode='Markdown'
        )
        return
    
    if d.startswith('f_'):
        print(f"📅 Прогноз запрошен: {get_current_time().strftime('%d.%m.%Y %H:%M:%S')} UTC")
    
    if d == 'forecast':
        if uid in users:
            ctx.user_data['mode'] = 'fp'
            kb = [[InlineKeyboardButton("📅 День", callback_data="f_day"), InlineKeyboardButton("📆 Неделя", callback_data="f_week")],
                  [InlineKeyboardButton("🗓 Месяц", callback_data="f_month")], [InlineKeyboardButton("🔙 Назад", callback_data="back")]]
            await q.edit_message_text(f"✨ *{users[uid]['sign']}* ✨\n\nВыберите период прогноза:", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        else:
            await q.edit_message_text(
                "🔮 *Прогноз ИИ*\n\nВыберите формат ввода:\n📝 `15.05.1990 14:30 Москва`\n📝 `15.05.1990 Москва`",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 С временем", callback_data="newdata")],
                    [InlineKeyboardButton("📝 Без времени", callback_data="newdata_noon")],
                    [InlineKeyboardButton("🔙 Назад", callback_data="back")]
                ]), parse_mode='Markdown'
            )
    elif d.startswith('f_'):
        if uid not in users: await q.message.reply_text("Сначала введите данные своего рождения!"); return
        u = users[uid]; period = {'day':'день','week':'неделю','month':'месяц'}[d[2:]]
        now = get_current_time()
        
        if d == 'f_month': label, ptitle = 'месяц', 'месяц'
        elif d == 'f_week': label, ptitle = 'неделю', 'неделю'
        else: label, ptitle = 'сегодня', 'сегодня'
        
        await q.message.reply_text(f"{cat_emoji()} Рассчитываю прогноз на {label}...")
        
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        transits = calc_transits(); aspects = get_aspects(natal)
        sun_sign = natal['Солнце']['sign']; moon_sign = natal['Луна']['sign']; asc_sign = natal['Асцендент']['sign']
        moon_house = next((h['house_num'] for h in natal['houses'] if h['sign'] == natal['Луна']['sign']), None)
        elements_count = {'Огонь': 0, 'Земля': 0, 'Воздух': 0, 'Вода': 0}
        element_map = {'Овен': 'Огонь', 'Лев': 'Огонь', 'Стрелец': 'Огонь', 'Телец': 'Земля', 'Дева': 'Земля', 'Козерог': 'Земля', 'Близнецы': 'Воздух', 'Весы': 'Воздух', 'Водолей': 'Воздух', 'Рак': 'Вода', 'Скорпион': 'Вода', 'Рыбы': 'Вода'}
        for planet in ['Солнце','Луна','Меркурий','Венера','Марс']:
            if planet in natal:
                elem = element_map.get(natal[planet]['sign'], '')
                if elem: elements_count[elem] += 1
        dominant = max(elements_count, key=elements_count.get)
        
        transit_aspects_data = calc_transit_aspects(natal, transits)
        
        astro = f"""
*Астрологические данные на {now.strftime('%d.%m.%Y')}:*
☀ Солнце в {sun_sign} {natal['Солнце']['degree']}°
🌙 Луна в {moon_sign} {natal['Луна']['degree']}° (в {moon_house if moon_house else '?'} доме)
⬆ ASC в {asc_sign} | 🔥 Доминирующая стихия: {dominant}
"""
        
        # Промпты и лимиты
        if d == 'f_day':
            aspects_text = get_moon_hourly_text(natal, now)
            prompt = f"""Ты — астролог. Прогноз на день ТОЛЬКО по Луне.
📅 {now.strftime('%d.%m.%Y')}
ПРАВИЛА: Только Луна. Указывай время. Нейтральные обращения.
{aspects_text}
ОБЩИЕ ДАННЫЕ: {astro}
СТРУКТУРА: 🌙 НАСТРОЕНИЕ ДНЯ (2-3) | ❤️ ОТНОШЕНИЯ (2) | 💼 ДЕЛА (2) | 🌟 СОВЕТ (1-2)
Дай прогноз. 8-10 предложений. Указывай время. Только Луну."""
            max_tok = 500
        elif d == 'f_month':
            aspects_text = get_aspects_text(transit_aspects_data)
            prompt = f"""Ты — астролог. Прогноз на МЕСЯЦ.
📅 {now.strftime('%d.%m.%Y')}
ПРАВИЛА: Только аспекты. Сходящийся = впереди. Нейтральные обращения.
СТРУКТУРА: ❤️ ЛЮБОВЬ (4) | 💼 КАРЬЕРА (4) | 🏃 ЭНЕРГИЯ (3) | 🌟 СОВЕТ (3)
ДАННЫЕ: {astro} {aspects_text}
Дай прогноз. Завершай предложения точкой. Не обрывай."""
            max_tok = 2500
        else:
            aspects_text = get_aspects_text(transit_aspects_data)
            prompt = f"""Ты — астролог. Прогноз на {period}.
📅 {now.strftime('%d.%m.%Y')}
ПРАВИЛА: Только аспекты. Сходящийся = впереди. Нейтральные обращения.
СТРУКТУРА: ❤️ ЛЮБОВЬ (3-4) | 💼 КАРЬЕРА (3-4) | 🏃 ЭНЕРГИЯ (2-3) | 🌟 СОВЕТ (2-3)
ДАННЫЕ: {astro} {aspects_text}
Дай прогноз. Завершай предложения точкой."""
            max_tok = 1200 if d == 'f_week' else 700
        
        forecast = ai_client.ask(prompt, max_tokens=max_tok)
        
        if forecast:
            parts = ai_client.split_message(forecast)
            for i, part in enumerate(parts):
                await update.effective_message.reply_text(
                    f"🌟 *Прогноз на {ptitle}* 🌟\n\n{part}" if i == 0 else part,
                    reply_markup=overview_btn() if i == 0 else None,
                    parse_mode='Markdown'
                )
        else:
            await update.effective_message.reply_text(f"🌟 *Прогноз на {ptitle}*\n\n❤️ Любовь: благоприятный период\n💼 Карьера: сосредоточьтесь на задачах\n🌟 Совет: слушайте интуицию.", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'natal':
        if uid not in users:
            await q.edit_message_text("🌟 *Натальная карта*\n\nВыберите формат ввода:\n📝 `15.05.1990 14:30 Москва`\n📝 `15.05.1990 Москва`",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 С временем", callback_data="newdata")], [InlineKeyboardButton("📝 Без времени", callback_data="newdata_noon")], [InlineKeyboardButton("🔙 Назад", callback_data="back")]]), parse_mode='Markdown')
            return
        u = users[uid]
        await q.message.reply_text(f"{cat_emoji()} Рассчитываю и рисую карту...")
        natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
        
        forecast = ai_client.ask(f"Разбор натальной карты. Данные: {get_natal_summary(natal, u)}", max_tokens=1500)
        img = draw_natal_chart_pro(natal, u['city'], f"{u['hour']:02d}:{u['minute']:02d}")
        await update.effective_message.reply_photo(photo=img)
        
        if forecast:
            parts = ai_client.split_message(forecast)
            for i, part in enumerate(parts):
                await update.effective_message.reply_text(part, reply_markup=overview_btn() if i == len(parts)-1 else None, parse_mode='Markdown')
        else:
            await update.effective_message.reply_text(f"🌟 *Натальная карта*\n📍 {u['city'].title()}\n☀ Солнце: *{natal['Солнце']['sign']}*\n🌙 Луна: *{natal['Луна']['sign']}*\n⬆ ASC: *{natal['Асцендент']['sign']}*\n\n⚠️ Интерпретация временно недоступна.", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'houses':
        if uid not in users: await q.edit_message_text("🏠 *Дома гороскопа*\n\nНужно точное время рождения.\n📝 `15.05.1990 14:30 Москва`", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 Ввести данные", callback_data="newdata")], [InlineKeyboardButton("🔙 Назад", callback_data="back")]]), parse_mode='Markdown')
        else:
            u = users[uid]; natal = calc_natal(u['day'], u['month'], u['year'], u['hour'], u['minute'], u['lat'], u['lon'], u['city'])
            text = f"🏠 *Дома гороскопа*\n📍 {u['city'].title()}\n🕐 {u['hour']:02d}:{u['minute']:02d}\n\n"
            for house in natal['houses']: text += f"*{house['house_num']} дом*: {SIGN_EMOJI.get(house['sign'],'')} {house['sign']} {house['degree']}°\n"
            text += f"\n⬆ Асцендент: *{natal['Асцендент']['sign']}* {natal['Асцендент']['degree']}°"
            await q.edit_message_text(text, reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'transits':
        transits = calc_transits(); now = get_current_time()
        text = f"🪐 *Транзиты*\n📅 {now.strftime('%d.%m.%Y %H:%M')} UTC\n\n"
        for p in ['Солнце','Луна','Меркурий','Венера','Марс','Юпитер','Сатурн','Раху','Кету']:
            if p in transits: text += f"{SIGN_EMOJI.get(transits[p]['sign'],'')} {p}: *{transits[p]['sign']}* {transits[p]['degree']}°\n"
        await q.edit_message_text(text, reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'compat': ctx.user_data['mode'] = 'compat'; await q.edit_message_text("💑 Два знака: *Овен Телец*", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'moon':
        transits = calc_transits(); now = get_current_time()
        phase = now.day % 8; phases = {0:"🌑",1:"🌒",2:"🌓",3:"🌔",4:"🌕",5:"🌖",6:"🌗",7:"🌘"}
        text = f"🌙 *Луна*\n📅 {now.strftime('%d.%m.%Y')}\n\nФаза: {phases.get(phase, '🌑')}\nЗнак: *{transits['Луна']['sign']}* {transits['Луна']['degree']}°"
        await q.edit_message_text(text, reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'daily':
        now = get_current_time(); transits = calc_transits()
        text = f"📅 *Сегодня* ({now.strftime('%d.%m.%Y')})\n\n"
        for sign in SIGN_NAMES:
            text += f"{SIGN_EMOJI.get(sign,'')} *{sign}*: "
            if 'Солнце' in transits and sign == transits['Солнце']['sign']: text += "☀️ Солнце в знаке!\n"
            elif 'Луна' in transits and sign == transits['Луна']['sign']: text += "🌙 Луна в знаке\n"
            else: text += "✨ Хороший день\n"
        await q.edit_message_text(text[:4000], reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'new_client':
        if uid in users: del users[uid]; save_users()
        ctx.user_data.clear(); ctx.user_data['mode'] = ''
        await q.edit_message_text("🔄 *Данные очищены!*\n\nВведите данные: `ДД.ММ.ГГГГ ЧЧ:ММ Город`", reply_markup=menu_btn(), parse_mode='Markdown')
    
    elif d == 'delete_confirm':
        kb = [[InlineKeyboardButton("✅ Да, удалить всё", callback_data="delete_yes")], [InlineKeyboardButton("❌ Нет, отмена", callback_data="back")]]
        await q.edit_message_text("⚠️ *Удалить ВСЕ данные?*\n\nЭто действие нельзя отменить.", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    
    elif d == 'delete_yes':
        if uid in users: del users[uid]; save_users()
        ctx.user_data.clear(); ctx.user_data['mode'] = ''
        await q.edit_message_text("✅ *Все данные удалены!*\n\nВведите данные: `ДД.ММ.ГГГГ ЧЧ:ММ Город`", reply_markup=menu_btn(), parse_mode='Markdown')
    
    elif d == 'subscribe_info':
        await q.edit_message_text("💎 *Подписка*\n\nСкоро здесь будет информация о платных возможностях.\n\nА пока — все функции бота бесплатны!", reply_markup=overview_btn(), parse_mode='Markdown')
    
    elif d == 'support':
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Написать в поддержку", url="https://t.me/astro_chat_helpbot")],
            [InlineKeyboardButton("🔙 Назад", callback_data="back")]
        ])
        await q.edit_message_text("💬 *Поддержка*\n\nЕсли у вас есть вопросы или предложения — нажмите кнопку ниже.\nМы ответим в ближайшее время!", reply_markup=kb, parse_mode='Markdown')
    
    elif d == 'newdata': ctx.user_data['mode'] = 'newdata'; await q.edit_message_text("📝 *Введите данные:*\n`ДД.ММ.ГГГГ ЧЧ:ММ Город`", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'newdata_noon': ctx.user_data['mode'] = 'newdata_noon'; await q.edit_message_text("📝 *Введите дату и город:*\n`ДД.ММ.ГГГГ Город`", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'newdata_natal': ctx.user_data['mode'] = 'newdata'; await q.edit_message_text("📝 *Введите новые данные:*\n`15.05.1990 14:30 Москва`", reply_markup=back_btn(), parse_mode='Markdown')
    elif d == 'back': ctx.user_data['mode'] = ''; await q.edit_message_text("🌟 *Меню*", reply_markup=menu_btn(), parse_mode='Markdown')

async def msg(update, ctx):
    t = update.message.text.strip(); m = ctx.user_data.get('mode',''); uid = update.effective_user.id
    if m in ['newdata', 'newdata_noon']: ctx.user_data['mode'] = ''
    if m == 'compat':
        parts = t.title().split()
        if len(parts)==2 and parts[0] in SIGN_NAMES and parts[1] in SIGN_NAMES:
            fc = ai_client.ask(f"Совместимость {parts[0]} и {parts[1]}. Процент и 2-3 предложения.") or "70% — Хорошая совместимость"
            ctx.user_data['mode'] = ''
            await update.message.reply_text(f"💑 *{parts[0]} + {parts[1]}*\n\n{fc}", reply_markup=overview_btn(), parse_mode='Markdown')
            return
        await update.message.reply_text("❌ *Овен Телец*", reply_markup=back_btn(), parse_mode='Markdown')
        return
    
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
        users[uid] = {'sign':sign,'day':day,'month':month,'year':year,'hour':hour,'minute':minute,'lat':lat,'lon':lon,'city':city_name}
        save_users()
        
        kb = [[InlineKeyboardButton("🔮 Прогноз ИИ", callback_data="forecast")],
              [InlineKeyboardButton("🌟 Натальная карта", callback_data="natal")],
              [InlineKeyboardButton("🏠 Дома", callback_data="houses")],
              [InlineKeyboardButton("🪐 Транзиты", callback_data="transits")],
              [InlineKeyboardButton("🔄 Новые данные", callback_data="newdata_natal")],
              [InlineKeyboardButton("🔙 Назад", callback_data="back")]]
        await update.message.reply_text(f"✨ *{sign}* ✨\n📅 {day:02d}.{month:02d}.{year}\n🕐 {hour:02d}:{minute:02d}\n📍 {city_name.title()}", reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
    except ValueError as e:
        await update.message.reply_text(f"❌ Ошибка: {e}\n\nФорматы:\n• *15.05.1990*\n• *15.05.1990 14:30*\n• *15.05.1990 14:30 Москва*", reply_markup=back_btn(), parse_mode='Markdown')
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
    
    if SUPPORT_TOKEN:
        support_app = Application.builder().token(SUPPORT_TOKEN).build()
        support_app.add_handler(CommandHandler('start', support_start))
        support_app.add_handler(CommandHandler('reply', reply_to_user))
        support_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, forward_to_admin))
        threading.Thread(target=support_app.run_polling, kwargs={'drop_pending_updates': True}, daemon=True).start()
        print("🚀 Бот поддержки запущен!")
    
    print("🚀 Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
