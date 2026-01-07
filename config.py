"""Конфигурация бота и переменные окружения"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Путь к корню проекта
BASE_DIR = Path(__file__).parent

# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

# OpenAI/ProxyAPI настройки
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY не найден в переменных окружения!")

# Логирование
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = BASE_DIR / "bot.log"

# Настройки LLM
LLM_MAX_TOKENS = 4000
LLM_TEMPERATURE = 0.7
LLM_TIMEOUT = 30  # секунд

# Retry настройки
MAX_RETRIES = 3
RETRY_DELAY = 1  # секунд (экспоненциальная задержка)

# Настройки сессий
SESSION_TIMEOUT = 3600  # секунд (1 час)

