import logging
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из файла token.env
load_dotenv(dotenv_path='utils/token.env')

# Получаем токен из окружения
TOKEN = os.getenv('TOKEN')

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
