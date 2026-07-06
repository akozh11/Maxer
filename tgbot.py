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
OWNER_ID = int(os.getenv("OWNER_ID", 0))   # ← ЖЁСТКО ПРОПИСАННЫЙ ВЛАДЕЛЕЦ

if not BOT_TOKEN or not OWNER_ID:
    raise ValueError("BOT_TOKEN и OWNER_ID должны быть в .env файле!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


def is_owner(user_id: int) -> bool:
    """Проверяет, является ли пользователь владельцем этого Максера"""
    return user_id == OWNER_ID


def load_contacts():
    try:
        with open("max_contacts_with_ids.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


# ==================== ОБРАБОТЧИКИ ====================
@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ Этот Максер настроен только на владельца.")
        return

    await message.answer(
        "👋 <b>Максер</b> — твой личный помощник.\n\n"
        "Доступные команды:\n"
        "• <code>/send Имя Текст</code>\n"
        "• <code>/last Имя</code>\n"
        "• <code>/contacts</code>\n"
        "• <code>/help</code>"
    )


@router.message(Command("send"))
async def cmd_send(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("Формат: <code>/send Имя Текст сообщения</code>")
        return

    contact_name, text = args[1], args[2]
    result = send_message_to_contact(contact_name, text)

    if result.get("status") == "успешно":
        await message.answer(f"✅ Отправлено: <b>{contact_name}</b>")
    else:
        await message.answer(f"❌ Ошибка: {result.get('причина')}")


@router.message(Command("last"))
async def cmd_last(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Формат: <code>/last Имя</code>")
        return

    messages = get_last_messages(args[1], count=5)
    if not messages:
        await message.answer("Сообщений не найдено.")
        return

    text = f"<b>Последние сообщения — {args[1]}</b>\n\n"
    for m in messages:
        arrow = "➡️" if m["is_outgoing"] else "⬅️"
        text += f"{arrow} <b>{m['sender']}</b> [{m['time']}]\n{m['text']}\n\n"

    await message.answer(text)


@router.message(Command("contacts"))
async def cmd_contacts(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return

    contacts = load_contacts()
    if not contacts:
        await message.answer("База контактов пуста.")
        return

    text = "<b>Твои контакты:</b>\n\n"
    for c in contacts:
        text += f"• {c['name']}\n"
    await message.answer(text)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await cmd_start(message)


@router.message(F.text)
async def unknown(message: Message):
    if not is_owner(message.from_user.id):
        await message.answer("⛔ Этот бот только для владельца.")
        return
    await message.answer("Неизвестная команда. Напиши /help")


async def main():
    logger.info("Максер запущен (только для владельца)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())