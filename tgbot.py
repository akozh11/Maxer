import os
import json
import logging
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from parser import send_message_to_contact, get_last_messages

# ==================== НАСТРОЙКИ ====================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден в .env файле!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


def load_contacts():
    try:
        with open("max_contacts_with_ids.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


def format_message(msg: dict) -> str:
    arrow = "➡️" if msg["is_outgoing"] else "⬅️"
    return f"{arrow} <b>{msg['sender']}</b> [{msg['time']}]\n{msg['text']}"


@router.message(CommandStart())
async def cmd_start(message: Message):
    text = (
        "👋 <b>Привет! Я — Максер</b>\n\n"
        "Твой личный мост между <b>MAX</b> и <b>Telegram</b>.\n\n"
        "<b>Команды:</b>\n"
        "• <code>/send Имя Текст</code> — отправить сообщение в MAX\n"
        "• <code>/last Имя</code> — последние 5 сообщений\n"
        "• <code>/contacts</code> — список контактов\n"
        "• <code>/help</code> — справка"
    )
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await cmd_start(message)


@router.message(Command("contacts"))
async def cmd_contacts(message: Message):
    contacts = load_contacts()
    if not contacts:
        await message.answer("❌ База контактов пуста. Запусти сначала <code>parser.py</code>")
        return

    text = "<b>📋 Твои контакты:</b>\n\n"
    for c in contacts:
        text += f"• <b>{c['name']}</b>\n"
    await message.answer(text)


@router.message(Command("send"))
async def cmd_send(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("❌ Формат: <code>/send Имя Текст сообщения</code>")
        return

    contact_name, text = args[1], args[2]
    await message.answer(f"⏳ Отправляю <b>{contact_name}</b>...")

    result = send_message_to_contact(contact_name, text)

    if result.get("status") == "успешно":
        await message.answer(f"✅ Отправлено <b>{contact_name}</b>")
    else:
        await message.answer(f"❌ Ошибка: {result.get('причина')}")


@router.message(Command("last"))
async def cmd_last(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Формат: <code>/last Имя</code>")
        return

    contact_name = args[1]
    await message.answer(f"⏳ Загружаю сообщения с <b>{contact_name}</b>...")

    messages = get_last_messages(contact_name, count=5)
    if not messages:
        await message.answer(f"Сообщений от <b>{contact_name}</b> нет.")
        return

    text = f"<b>📨 Последние сообщения — {contact_name}</b>\n\n"
    for msg in messages:
        text += format_message(msg) + "\n\n"

    await message.answer(text)


@router.message(F.text)
async def unknown(message: Message):
    await message.answer("Неизвестная команда. Напиши <code>/help</code>")


async def main():
    logger.info("🤖 Максер-бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")