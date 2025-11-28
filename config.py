import os
from pathlib import Path

# =========================
# CONFIGURATION
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OWNER_ID = int(os.getenv("OWNER_ID", "7941244038"))
UPDATES_CHANNEL = os.getenv("UPDATES_CHANNEL", "@tonystark_jr")
FORCE_JOIN_CHANNEL = os.getenv("FORCE_JOIN_CHANNEL", "@tonystark_jr")
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", "-5066591546"))
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Cookies configuration
COOKIES_FILE = os.getenv("COOKIES_FILE", "cookies.txt")

# MongoDB
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "youtube_bot")
MONGO_USERS = os.getenv("MONGO_USERS", "users")
MONGO_ADMINS = os.getenv("MONGO_ADMINS", "admins")
MONGO_REDEEM = os.getenv("MONGO_REDEEM", "redeem_codes")
MONGO_WHITELIST = os.getenv("MONGO_WHITELIST", "whitelist")

# Credit System
BASE_CREDITS = 20
REFERRER_BONUS = 20
CLAIMER_BONUS = 15
PREMIUM_BOT_USERNAME = "@ayushxchat_robot"

# File limits
DOWNLOAD_DIR = Path("downloads")
MAX_FREE_SIZE = 50 * 1024 * 1024
PREMIUM_SIZE = 450 * 1024 * 1024
YOUTUBE_REGEX = re.compile(r"(https?://)?(www\.)?(youtube\.com|youtu\.be)/[\w\-?&=/%]+", re.I)

# Media Generation
BASE_MEDIA_GEN_LIMIT = 10
MAX_CONCURRENT_GENERATIONS = 2

# GeminiGen AI
BEARER_TOKEN = os.getenv("BEARER_TOKEN", "")
COOKIE_FILE_CONTENT = os.getenv("COOKIE_FILE_CONTENT", "")

# Ensure directories
DOWNLOAD_DIR.mkdir(exist_ok=True)
Path(COOKIES_FILE).touch(exist_ok=True)
