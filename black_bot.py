"""
BLACK PRO — Telegram Bot
Бот для оплаты через Kaspi и генерации кода активации
Автор: Нұржайық Мұсапарқан
"""

import logging
import random
import string
import json
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ───────────────────────────────────────────────
# НАСТРОЙКИ — замени на свои значения
# ───────────────────────────────────────────────
BOT_TOKEN = "8843885728:AAFwu0_OpKLccR_xTDcGNBtCvb8kIXDJLlQ"

# Kaspi номер для оплаты
KASPI_PHONE = "+7 (778) 090-34-88"   # ← твой номер Kaspi
KASPI_NAME  = "Нұржайық М."           # ← имя получателя в Kaspi
PRICE       = 990                      # тенге

# ID твоего Telegram аккаунта (для уведомлений об оплатах)
# Узнать свой ID: написать боту @userinfobot
ADMIN_ID = 7653338497  # ← замени на свой Telegram ID

# Файл для хранения кодов (потом можно заменить на Firebase)
CODES_FILE = "activation_codes.json"
# ───────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Работа с файлом кодов ──────────────────────

def load_codes() -> dict:
    if os.path.exists(CODES_FILE):
        with open(CODES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_codes(data: dict):
    with open(CODES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_code() -> str:
    """Генерирует уникальный код вида BLACK-XXXX-XXXX"""
    part1 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    part2 = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"BLACK-{part1}-{part2}"


def create_unique_code() -> str:
    """Создаёт код, которого ещё нет в базе"""
    codes = load_codes()
    while True:
        code = generate_code()
        if code not in codes.values():
            return code


def save_new_activation(user_id: int, username: str, code: str):
    codes = load_codes()
    codes[str(user_id)] = {
        "code": code,
        "username": username or "—",
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "used": False,
    }
    save_codes(codes)


# ── Хэндлеры ──────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    keyboard = [
        [InlineKeyboardButton("💳 Оплатить 990 ₸ через Kaspi", callback_data="pay")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "🛡 *BLACK PRO* — защита от мошенников.\n\n"
        "После оплаты ты получишь уникальный код активации прямо здесь в боте.\n\n"
        "Нажми кнопку ниже, чтобы начать:",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "pay":
        keyboard = [[InlineKeyboardButton("✅ Я оплатил(а), отправить чек", callback_data="sent_payment")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            "💳 *Оплата BLACK PRO*\n\n"
            f"Сумма: *{PRICE} ₸*\n"
            f"Получатель: *{KASPI_NAME}*\n"
            f"Номер Kaspi: `{KASPI_PHONE}`\n\n"
            "📋 *Инструкция:*\n"
            "1. Открой Kaspi.kz → Переводы\n"
            "2. По номеру телефона\n"
            f"3. Введи номер: `{KASPI_PHONE}`\n"
            f"4. Сумма: *990 ₸*\n"
            "5. В комментарии напиши: *BLACK PRO*\n"
            "6. Сделай скриншот чека\n"
            "7. Нажми кнопку ниже и отправь скриншот\n\n"
            "⏱ Код придёт в течение нескольких минут после проверки.",
            parse_mode="Markdown",
            reply_markup=reply_markup,
        )

    elif query.data == "sent_payment":
        context.user_data["waiting_for_receipt"] = True
        await query.edit_message_text(
            "📸 Отлично! Теперь отправь скриншот чека из Kaspi этим сообщением.\n\n"
            "_Мы проверим оплату и отправим код активации._",
            parse_mode="Markdown",
        )

    elif query.data == "help":
        await query.edit_message_text(
            "❓ *Помощь*\n\n"
            "По всем вопросам: @nurikmen606\n\n"  # ← замени на свой username
            "Или напиши на email: nurikmen606@gmail.com\n\n"
            "/start — вернуться в главное меню",
            parse_mode="Markdown",
        )

    elif query.data.startswith("approve_"):
        # Одобрить оплату (только для админа)
        target_user_id = int(query.data.split("_")[1])
        await approve_payment(update, context, target_user_id)

    elif query.data.startswith("reject_"):
        target_user_id = int(query.data.split("_")[1])
        await context.bot.send_message(
            chat_id=target_user_id,
            text="❌ К сожалению, мы не смогли подтвердить твою оплату.\n\n"
                 "Попробуй снова или напиши нам: @nurikmen606",
        )
        await query.edit_message_text("❌ Оплата отклонена.")


async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Генерирует и отправляет код активации пользователю"""
    codes = load_codes()
    entry = codes.get(str(user_id))

    if entry and entry.get("code"):
        code = entry["code"]
    else:
        code = create_unique_code()

    # Получаем username
    try:
        chat = await context.bot.get_chat(user_id)
        username = chat.username or chat.first_name or str(user_id)
    except Exception:
        username = str(user_id)

    save_new_activation(user_id, username, code)

    # Отправляем код пользователю
    await context.bot.send_message(
        chat_id=user_id,
        text="🎉 *Оплата подтверждена! Добро пожаловать в BLACK PRO.*\n\n"
             f"🔑 Твой код активации:\n\n"
             f"`{code}`\n\n"
             "📱 *Как активировать:*\n"
             "1. Открой приложение BLACK\n"
             "2. Перейди в раздел *PRO подписка*\n"
             "3. Введи этот код\n"
             "4. Наслаждайся полной защитой!\n\n"
             "⚠️ Код одноразовый. Не передавай никому.",
        parse_mode="Markdown",
    )

    # Уведомляем админа об успешной активации
    await update.callback_query.edit_message_text(
        f"✅ Код отправлен пользователю {username} ({user_id})\nКод: `{code}`",
        parse_mode="Markdown",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пользователь прислал фото — скорее всего чек"""
    user = update.effective_user

    # Уведомляем пользователя
    await update.message.reply_text(
        "✅ Чек получен! Проверяем оплату...\n\n"
        "⏱ Обычно это занимает до 10 минут. Мы пришлём код сюда.",
    )

    # Отправляем админу с кнопками одобрить/отклонить
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить и выдать код", callback_data=f"approve_{user.id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user.id}"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    caption = (
        f"💳 *Новая оплата BLACK PRO*\n\n"
        f"👤 Пользователь: {user.first_name} {user.last_name or ''}\n"
        f"🔗 Username: @{user.username or '—'}\n"
        f"🆔 ID: `{user.id}`\n"
        f"🕐 Время: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Проверь чек и нажми кнопку:"
    )

    await context.bot.send_photo(
        chat_id=ADMIN_ID,
        photo=update.message.photo[-1].file_id,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Любой текст — направляем к оплате"""
    await update.message.reply_text(
        "Нажми /start чтобы начать или выбери опцию из меню.",
    )


# ── Команды для админа ────────────────────────

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список всех кодов (только для админа)"""
    if update.effective_user.id != ADMIN_ID:
        return

    codes = load_codes()
    if not codes:
        await update.message.reply_text("Кодов пока нет.")
        return

    text = "📋 *Все активации:*\n\n"
    for uid, info in codes.items():
        text += (
            f"👤 {info['username']} (ID: {uid})\n"
            f"🔑 `{info['code']}`\n"
            f"📅 {info['date']}\n\n"
        )

    await update.message.reply_text(text, parse_mode="Markdown")


async def admin_send_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ручная отправка кода: /sendcode 123456789
    (на случай если нужно отправить вручную)
    """
    if update.effective_user.id != ADMIN_ID:
        return

    args = context.args
    if not args:
        await update.message.reply_text("Использование: /sendcode <user_id>")
        return

    target_id = int(args[0])
    code = create_unique_code()
    save_new_activation(target_id, str(target_id), code)

    await context.bot.send_message(
        chat_id=target_id,
        text="🎉 *Поздравляем! Твой код активации BLACK PRO:*\n\n"
             f"`{code}`\n\n"
             "Введи его в приложении BLACK в разделе PRO подписка.",
        parse_mode="Markdown",
    )
    await update.message.reply_text(f"✅ Код `{code}` отправлен пользователю {target_id}", parse_mode="Markdown")


# ── Запуск ────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", admin_list))
    app.add_handler(CommandHandler("sendcode", admin_send_code))

    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler))

    # Фото (чек оплаты)
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

    # Текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("BLACK Bot запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
