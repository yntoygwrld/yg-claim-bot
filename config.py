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

# Points Configuration
POINTS_CLAIM = 5       # Points for claiming daily video
POINTS_SUBMIT = 10     # Points per platform submission
VIEW_MULTIPLIER = 0.01  # 1 point per 100 views (for future use)

# Platforms
SUPPORTED_PLATFORMS = ["tiktok", "instagram", "twitter"]

# Platform Display Names (for UI)
PLATFORM_NAMES = {
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "twitter": "Twitter/X",
}

# URL Patterns - Research-based regex for accurate detection
# Sources: Stack Overflow, regex101.com, codex.so
URL_PATTERNS = {
    # TikTok: Full URLs, short URLs (vm.tiktok, vt.tiktok), mobile
    "tiktok": r"(?:https?://)?(?:www\.|m\.|vm\.|vt\.)?tiktok\.com/(?:@[\w.-]+/video/\d+|[\w]+/?)",
    # Instagram: Posts (/p/), Reels (/reel/, /reels/)
    "instagram": r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|reels)/[\w-]+/?",
    # Twitter/X: Both domains, video suffix supported
    "twitter": r"(?:https?://)?(?:www\.|mobile\.)?(?:twitter|x)\.com/\w+/status(?:es)?/\d+(?:/video/\d+)?/?",
}

# YNTOYG Community
YNTOYG_COVENANT_GROUP_ID = -1003372132039  # Private group: $YNTOYG Covenant
YNTOYG_PORTAL_LINK = "https://t.me/yntoyg"  # PUBLIC portal with Safeguard verification
YNTOYG_COVENANT_DIRECT_INVITE = "https://t.me/+6qtZGyO3cvliNmI0"  # Direct invite (admin use only, bypasses Safeguard)
BOT_LINK = "https://t.me/yntoyg_claim_bot"  # Link to this bot for easy return

# Default bot settings (stored in database for runtime changes)
DEFAULT_BOT_SETTINGS = {
    "claims_enabled": True,
    "max_claims_per_day": 1,
    "maintenance_mode": False,
    "maintenance_message": "🔧 Bot is under maintenance. Please check back soon!",
    "announcement": "",  # Optional announcement shown to all users
}
