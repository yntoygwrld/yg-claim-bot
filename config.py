"""Configuration settings for YG Claim Bot"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Bot Settings
CLAIM_COOLDOWN_HOURS = 24
TOKEN_EXPIRY_HOURS = 24
MAX_REPOSTS_PER_DAY = 10

# Points Algorithm
BASE_POINTS = 10
VIEW_MULTIPLIER = 0.01  # 1 point per 100 views

# Platforms
SUPPORTED_PLATFORMS = ["tiktok", "instagram", "twitter"]

# URL Patterns
URL_PATTERNS = {
    "tiktok": r"tiktok\.com/@[\w\.]+/video/\d+",
    "instagram": r"instagram\.com/(p|reel)/[\w-]+",
    "twitter": r"(twitter|x)\.com/\w+/status/\d+",
}
