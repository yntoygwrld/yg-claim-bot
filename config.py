"""Configuration settings for YG Claim Bot"""
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Admin Configuration
ADMIN_USER_IDS = [
    8227072324,  # @OriginalYG - YNTOYG SEED
]

# Bot Settings (defaults - can be overridden via database)
CLAIM_COOLDOWN_HOURS = 24
TOKEN_EXPIRY_HOURS = 24
MAX_REPOSTS_PER_DAY = 10

# Points Algorithm
BASE_POINTS = 10
VIEW_MULTIPLIER = 0.01  # 1 point per 100 views

# Platforms
SUPPORTED_PLATFORMS = ["tiktok", "instagram", "twitter"]

# URL Patterns - More permissive to accept all common URL formats
# We collect URLs now, manual audit happens during airdrops
URL_PATTERNS = {
    # TikTok: standard, www, short URLs (vm.tiktok, vt.tiktok)
    "tiktok": r"(www\.)?(tiktok\.com/@[\w\.]+/video/\d+|(vm|vt)\.tiktok\.com/[\w]+)",
    # Instagram: posts, reels, with www and query params
    "instagram": r"(www\.)?instagram\.com/(p|reel|reels)/[\w-]+",
    # Twitter/X: standard, www, mobile
    "twitter": r"(www\.|mobile\.)?(twitter|x)\.com/\w+/status/\d+",
}

# YNTOYG Community
YNTOYG_COVENANT_GROUP_ID = -1003372132039  # Private group: $YNTOYG Covenant
YNTOYG_PORTAL_LINK = "https://t.me/yntoyg"  # PUBLIC portal with Safeguard verification
YNTOYG_COVENANT_DIRECT_INVITE = "https://t.me/+6qtZGyO3cvliNmI0"  # Direct invite (admin use only, bypasses Safeguard)

# Default bot settings (stored in database for runtime changes)
DEFAULT_BOT_SETTINGS = {
    "claims_enabled": True,
    "max_claims_per_day": 1,
    "maintenance_mode": False,
    "maintenance_message": "🔧 Bot is under maintenance. Please check back soon!",
    "announcement": "",  # Optional announcement shown to all users
}
