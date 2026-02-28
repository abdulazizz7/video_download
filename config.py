import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(',')))
SECRET_GROUP_ID = int(os.getenv('SECRET_GROUP_ID', '-1001234567890'))  # Maxfiy guruh ID

# Rate limiting
USER_LIMIT = 5  # Bir user 1 daqiqada 5 ta link yubora oladi
TIME_WINDOW = 60  # 1 daqiqa

# Cache vaqtlari
VIDEO_CACHE_TIME = 86400  # 24 soat

# Majburiy obuna kanallari
FORCED_CHANNELS = []

# Database
DATABASE_PATH = 'bot_database.db'