import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
import os

load_dotenv()

ZODIAC_SIGNS = {
    'Овен': (3, 21, 4, 19), 'Телец': (4, 20, 5, 20),
    'Близнецы': (5, 21, 6, 20), 'Рак': (6, 21, 7, 22),
    'Лев': (7, 23, 8, 22), 'Дева': (8, 23, 9, 22),
    'Весы': (9, 23, 10, 22), 'Скорпион': (10, 23, 11, 21),
    'Стрелец': (11, 22, 12, 21), 'Козерог': (12, 22, 1, 19),
    'Водолей': (1, 20, 2, 18), 'Рыбы': (2, 19, 3, 20)
}

COMPATIBILITY = {
    ('Овен', 'Лев'): 95, ('Овен', 'Стрелец'): 92, ('Овен', 'Близнецы'): 85,
    ('Овен', 'Водолей'): 80, ('Овен', 'Весы'): 70, ('Овен', 'Рак'): 45,
    ('Овен', 'Козерог'): 40, ('Овен', 'Дева'): 35, ('Овен', 'Скорпион'): 30,
    ('Овен', 'Телец'): 25, ('Овен', 'Рыбы'): 20,
    ('Телец', 'Дева'): 95, ('Телец', 'Козерог'): 92, ('Телец', 'Рак'): 88,
    ('Телец', 'Рыбы'): 85, ('Телец', 'Скорпион'): 80,
    ('Близнецы', 'Весы'): 95, ('Близнецы', 'Водолей'): 92, ('Близнецы', 'Овен'): 85,
    ('Близнецы', 'Лев'): 82,
    ('Рак', 'Скорпион'): 95, ('Рак', 'Рыбы'): 92, ('Рак', 'Телец'): 88,
    ('Лев', 'Овен'): 95, ('Лев', 'Стрелец'): 90,
    ('Дева', 'Телец'): 95, ('Дева', 'Козерог'): 90,
    ('Весы', 'Близнецы'): 95, ('Весы', 'Водолей'): 90, ('Весы', 'Лев'): 80,
    ('Скорпион', 'Рак'): 95, ('Скорпион', 'Рыбы'): 92,
    ('Стрелец', 'Овен'): 92, ('Стрелец', 'Лев'): 90,
    ('Козерог', 'Телец'): 92, ('Козерог', 'Дева'): 90,
    ('Водолей', 'Близнецы'): 92, ('Водолей', 'Весы'): 90,
    ('Рыбы', 'Рак'): 92, ('Рыбы', 'Скорпион'): 92, ('Рыбы', 'Телец'): 85,
}

def get_compatibility(sign1, sign2):
    return COMPATIBILITY.get((sign1, sign2)) or COMPATIBILITY.get((sign2, sign1), 50)

MOON_PHASES = {
    0: "🌑 Новолуние", 1: "🌒 Молодая луна", 2: "🌓 Первая четверть",
    3: "🌔 Прибывающая луна", 4: "🌕 Полнолуние", 5: "🌖 Убывающая луна",
    6: "🌗 Последняя четверть", 7: "🌘 Старая луна"
}

DAILY_ALL = {
    'Овен': "🔥 Овнам — инициатива и действие!", 'Телец': "🌿 Тельцам — уют и стабильность.",
    'Близнецы': "💬 Близнецам — общение и контакты.", 'Рак': "🌊 Ракам — интуиция и забота.",
    'Лев': "☀️ Львы в центре внимания!", 'Дева': "📋 Девам — порядок и план.",
    'Весы': "⚖️ Весам — гармония и баланс.", 'Скорпион': "🦂 Скорпионам — тайны и сила.",
    'Стрелец': "🏹 Стрельцам — приключения!", 'Козерог': "🏔 Козерогам — достижения.",
    'Водолей': "⚡ Водолеям — идеи и свобода.", 'Рыбы': "🎭 Рыбам — вдохновение и мечты."
}

forecasts = {
    'day': [
        "💫 День возможностей!\n\n❤️ Сюрприз в любви.\n💼 Новые идеи.\n🏃 Энергия на высоте.",
        "🌟 Гармоничный день.\n\n❤️ Вечер с близкими.\n💼 Финансы решатся.\n🏃 Отдых и релакс.",
        "⚡ День перемен.\n\n❤️ Возможно знакомство.\n💼 Беритесь за проекты.\n🏃 Спорт поможет.",
        "🌙 День размышлений.\n\n❤️ Разговор по душам.\n💼 Рутина подождёт.\n🏃 Йога или медитация."
    ],
    'week': [
        "🌟 Неделя роста!\n\n❤️ Романтический сюрприз.\n💼 Поступления.\n🏃 Энергия на пике.",
        "💫 Неделя гармонии.\n\n❤️ Укрепите отношения.\n💼 Без конфликтов.\n🏃 Гуляйте.",
        "⚡ Динамичная неделя.\n\n❤️ Встреча из прошлого.\n💼 Карьерный рост.\n🏃 Режим сна."
    ],
    'month': [
        "🌙 Месяц перемен.\n\n❤️ Новый уровень.\n💼 Бонусы.\n🏃 Здоровье в приоритете.",
        "🌟 Успешный месяц!\n\n❤️ Гармония.\n💼 Сделки.\n🏃 Энергии хватит.",
        "💫 Месяц идей.\n\n❤️ Романтика.\n💼 Возможности.\n🏃 В зал!"
    ],
    'year': [
        "🌟 Год возможностей!\n\n❤️ Судьба.\n💼 Карьера.\n🏃 Привычки.",
        "💫 Год гармонии.\n\n❤️ Семья.\n💼 Доход.\n🏃 Иммунитет.",
        "⚡ Год перемен!\n\n❤️ Знакомства.\n💼 Повышение.\n🏃 Активность."
    ]
}

users_data = {}

def get_zodiac_sign(day, month):
    for sign, (sm, sd, em, ed) in ZODIAC_SIGNS.items():
        if (month == sm and day >= sd) or (month == em and day <= ed):
            return sign
    return 'Козерог'

def get_back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 В главное меню", callback_data="back")]])

def main_menu_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Личный прогноз", callback_data="personal")],
        [InlineKeyboardButton("💑 Совместимость", callback_data="compat")],
        [InlineKeyboardButton("🌙 Лунный календарь", callback_data="moon")],
        [InlineKeyboardButton("📅 Гороскоп на сегодня", callback_data="daily_all")]
    ])

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['mode'] = ''
    await update.message.reply_text(
        "🌟 *Астро-бот* 🌟\n\nВыберите функцию:",
        reply_markup=main_menu_keyboard(), parse_mode='Markdown'
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == 'personal':
        if user_id in users_data:
            sign = users_data[user_id]['sign']
            keyboard = [
                [InlineKeyboardButton("📅 День", callback_data="day"),
                 InlineKeyboardButton("📆 Неделя", callback_data="week")],
                [InlineKeyboardButton("🗓 Месяц", callback_data="month"),
                 InlineKeyboardButton("📅 Год", callback_data="year")],
                [InlineKeyboardButton("🔄 Изменить дату", callback_data="change_date")],
                [InlineKeyboardButton("🔙 В главное меню", callback_data="back")]
            ]
            try:
                await query.edit_message_text(
                    f"✨ *Ваш знак: {sign}* ✨\n\nВыберите период:",
                    reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
                )
            except:
                pass
        else:
            try:
                await query.edit_message_text(
                    "📝 Введите дату рождения: ДД.ММ.ГГГГ",
                    reply_markup=get_back_button()
                )
            except:
                pass

    elif data == 'compat':
        context.user_data['mode'] = 'compat'
        try:
            await query.edit_message_text(
                "💑 Введите два знака через пробел.\nПример: *Овен Телец*",
                reply_markup=get_back_button(), parse_mode='Markdown'
            )
        except:
            pass

    elif data == 'moon':
        moon_phase = datetime.now().day % 8
        text = f"🌙 *Лунный календарь*\n\n{MOON_PHASES[moon_phase]}\n📅 {datetime.now().strftime('%d.%m.%Y')}"
        try:
            await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode='Markdown')
        except:
            pass

    elif data == 'daily_all':
        text = "📅 *Гороскоп на сегодня*\n\n"
        for sign, fcast in DAILY_ALL.items():
            text += f"*{sign}*: {fcast}\n\n"
        try:
            await query.edit_message_text(text, reply_markup=get_back_button(), parse_mode='Markdown')
        except:
            pass

    elif data in ['day', 'week', 'month', 'year']:
        if user_id not in users_data:
            await query.message.reply_text("⚠️ Сначала введите дату рождения!", reply_markup=get_back_button())
            return
        sign = users_data[user_id]['sign']
        periods = {'day': 'день', 'week': 'неделю', 'month': 'месяц', 'year': 'год'}
        forecast = random.choice(forecasts[data])
        await query.message.reply_text(
            f"🌟 *Прогноз на {periods[data]} для {sign}* 🌟\n\n{forecast}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📅 День", callback_data="day"),
                 InlineKeyboardButton("📆 Неделя", callback_data="week")],
                [InlineKeyboardButton("🗓 Месяц", callback_data="month"),
                 InlineKeyboardButton("📅 Год", callback_data="year")],
                [InlineKeyboardButton("🔙 В главное меню", callback_data="back")]
            ]), parse_mode='Markdown'
        )

    elif data == 'change_date':
        try:
            await query.edit_message_text(
                "📝 Введите новую дату: ДД.ММ.ГГГГ",
                reply_markup=get_back_button()
            )
        except:
            pass

    elif data == 'back':
        context.user_data['mode'] = ''
        try:
            await query.edit_message_text(
                "🌟 *Астро-бот* 🌟\n\nВыберите функцию:",
                reply_markup=main_menu_keyboard(), parse_mode='Markdown'
            )
        except:
            pass

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    mode = context.user_data.get('mode', '')
    user_id = update.effective_user.id

    if mode == 'compat':
        parts = text.split()
        if len(parts) == 2:
            sign_map = {s.lower(): s for s in ZODIAC_SIGNS}
            sign1 = sign_map.get(parts[0].lower())
            sign2 = sign_map.get(parts[1].lower())
            if sign1 and sign2:
                compat = get_compatibility(sign1, sign2)
                emoji = "💖" if compat >= 80 else "💛" if compat >= 50 else "💔"
                desc = "Идеальная пара!" if compat >= 80 else "Хорошая совместимость" if compat >= 60 else "Возможны трудности" if compat >= 40 else "Сложные отношения"
                context.user_data['mode'] = ''
                await update.message.reply_text(
                    f"💑 *{sign1} + {sign2}*\n\n{emoji} {compat}% — {desc}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💑 Ещё пару", callback_data="compat"),
                         InlineKeyboardButton("🔙 В главное меню", callback_data="back")]
                    ]), parse_mode='Markdown'
                )
                return
        await update.message.reply_text(
            "❌ Пример: *Овен Телец*",
            reply_markup=get_back_button(), parse_mode='Markdown'
        )
        return

    try:
        day, month, year = map(int, text.split('.'))
        if not (1 <= day <= 31 and 1 <= month <= 12):
            raise ValueError
        sign = get_zodiac_sign(day, month)
        users_data[user_id] = {'sign': sign}
        keyboard = [
            [InlineKeyboardButton("📅 День", callback_data="day"),
             InlineKeyboardButton("📆 Неделя", callback_data="week")],
            [InlineKeyboardButton("🗓 Месяц", callback_data="month"),
             InlineKeyboardButton("📅 Год", callback_data="year")],
            [InlineKeyboardButton("🔙 В главное меню", callback_data="back")]
        ]
        await update.message.reply_text(
            f"✨ *Ваш знак: {sign}* ✨\n\nВыберите период:",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown'
        )
    except:
        await update.message.reply_text(
            "❌ Формат: ДД.ММ.ГГГГ\nНапример: 15.05.1990",
            reply_markup=get_back_button()
        )

def main():
    print("🚀 Запуск Астро-бота...")
    app = Application.builder().token(os.getenv('TELEGRAM_TOKEN')).build()
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    print("✅ Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()