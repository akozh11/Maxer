import os
from dotenv import load_dotenv

# Загружаем переменные из файла .env
load_dotenv()

# Получаем токен бота из переменной окружения
# Если токена нет, бот выдаст понятную ошибку
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Ошибка: Токен бота не найден в файле .env!")