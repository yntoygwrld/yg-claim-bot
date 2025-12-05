"""Supabase database operations for YG Claim Bot"""
from supabase import create_client, Client
from datetime import datetime, date
from typing import Optional, Dict, Any, List
import config

# Initialize Supabase client
supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


# ============ USER OPERATIONS ============

async def get_user_by_telegram_id(telegram_id: int) -> Optional[Dict]:
    """Get user by Telegram ID"""
    result = supabase.table("users").select("*").eq("telegram_id", telegram_id).execute()
    return result.data[0] if result.data else None


async def get_user_by_email(email: str) -> Optional[Dict]:
    """Get user by email"""
    result = supabase.table("users").select("*").eq("email", email).execute()
    return result.data[0] if result.data else None


async def create_user(email: str, telegram_id: int) -> Dict:
    """Create new user linking email and Telegram"""
    result = supabase.table("users").insert({
        "email": email,
        "telegram_id": telegram_id,
    }).execute()
    return result.data[0]


async def update_user_wallet(telegram_id: int, wallet_address: str) -> Dict:
    """Update user's wallet address"""
    result = supabase.table("users").update({
        "wallet_address": wallet_address,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("telegram_id", telegram_id).execute()
    return result.data[0]


async def update_user_socials(telegram_id: int, platform: str, username: str) -> Dict:
    """Update user's social account username"""
    field = f"{platform}_username"
    result = supabase.table("users").update({
        field: username,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("telegram_id", telegram_id).execute()
    return result.data[0]


async def increment_points(telegram_id: int, points: int) -> bool:
    """Increment user's gentleman_score (points) by specified amount."""
    import logging
    try:
        # Get current score
        result = supabase.table("users").select("gentleman_score").eq("telegram_id", telegram_id).single().execute()
        current_score = result.data.get("gentleman_score", 0) if result.data else 0

        # Update with new total
        new_score = current_score + points
        supabase.table("users").update({
            "gentleman_score": new_score,
            "updated_at": datetime.utcnow().isoformat(),
        }).eq("telegram_id", telegram_id).execute()

        logging.info(f"Points updated for user {telegram_id}: {current_score} -> {new_score} (+{points})")
        return True
    except Exception as e:
        logging.error(f"Error incrementing points for user {telegram_id}: {e}")
        return False


# ============ TOKEN OPERATIONS ============

async def verify_magic_token(token: str) -> Optional[str]:
    """Verify magic link token and return email if valid"""
    result = supabase.table("email_tokens").select("*").eq("token", token).eq("used", False).execute()

    if not result.data:
        return None

    token_data = result.data[0]

    # Check expiration
    expires_at = datetime.fromisoformat(token_data["expires_at"].replace("Z", "+00:00"))
    if datetime.utcnow() > expires_at.replace(tzinfo=None):
        return None

    # Mark token as used
    supabase.table("email_tokens").update({"used": True}).eq("id", token_data["id"]).execute()

    return token_data["email"]


# ============ VIDEO OPERATIONS ============

async def get_random_active_video() -> Optional[Dict]:
    """Get a random active video from the pool"""
    result = supabase.table("videos").select("*").eq("is_active", True).execute()

    if not result.data:
        return None

    import random
    video = random.choice(result.data)

    # Increment times_claimed
    supabase.table("videos").update({
        "times_claimed": video["times_claimed"] + 1
    }).eq("id", video["id"]).execute()

    return video


# ============ CLAIM OPERATIONS ============

async def has_claimed_today(user_id: str) -> bool:
    """Check if user has already claimed today"""
    today = date.today().isoformat()
    result = supabase.table("daily_claims").select("id").eq("user_id", user_id).eq("claim_date", today).execute()
    return len(result.data) > 0


async def create_claim(user_id: str, video_id: str, telegram_id: int) -> Dict:
    """Create a new daily claim record and award points"""
    result = supabase.table("daily_claims").insert({
        "user_id": user_id,
        "video_id": video_id,
        "claim_date": date.today().isoformat(),
    }).execute()

    # Update user stats
    supabase.rpc("increment_user_claims", {"user_id_param": user_id}).execute()

    # Award points for claiming (+10)
    await increment_points(telegram_id, 10)

    return result.data[0]


# ============ REPOST OPERATIONS ============

async def create_repost(user_id: str, video_id: str, platform: str, post_url: str, telegram_id: int) -> Dict:
    """Create a new repost submission and award points"""
    result = supabase.table("reposts").insert({
        "user_id": user_id,
        "video_id": video_id,
        "platform": platform,
        "post_url": post_url,
    }).execute()

    # Award points for submitting (+25)
    await increment_points(telegram_id, 25)

    return result.data[0]


async def get_pending_reposts() -> List[Dict]:
    """Get reposts that need view scraping"""
    result = supabase.table("reposts").select("*").eq("verified", False).execute()
    return result.data


async def update_repost_views(repost_id: str, view_count: int, like_count: int) -> Dict:
    """Update repost with scraped view counts"""
    points = config.BASE_POINTS + int(view_count * config.VIEW_MULTIPLIER)

    result = supabase.table("reposts").update({
        "view_count": view_count,
        "like_count": like_count,
        "verified": True,
        "points_awarded": points,
        "last_scraped_at": datetime.utcnow().isoformat(),
    }).eq("id", repost_id).execute()

    return result.data[0]


# ============ LEADERBOARD OPERATIONS ============

async def get_user_stats(user_id: str) -> Dict:
    """Get user's stats for /mystats command"""
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    return result.data[0] if result.data else {}


async def get_weekly_leaderboard(limit: int = 10) -> List[Dict]:
    """Get top performers for current week"""
    result = supabase.table("leaderboard").select(
        "*, users(telegram_id)"
    ).order("total_views", desc=True).limit(limit).execute()
    return result.data


# ============ BOT SETTINGS OPERATIONS ============

# In-memory cache for settings (reduces DB calls)
_settings_cache: Dict[str, Any] = {}
_cache_timestamp: float = 0
CACHE_TTL_SECONDS = 60  # Refresh cache every minute


async def get_bot_settings() -> Dict[str, Any]:
    """Get current bot settings from database (with caching)"""
    import time
    global _settings_cache, _cache_timestamp

    # Return cached if still valid
    if _settings_cache and (time.time() - _cache_timestamp) < CACHE_TTL_SECONDS:
        return _settings_cache

    try:
        result = supabase.table("bot_settings").select("*").eq("id", 1).execute()

        if result.data:
            _settings_cache = result.data[0]
            _cache_timestamp = time.time()
            return _settings_cache
        else:
            # Create default settings if none exist
            result = supabase.table("bot_settings").insert({
                "id": 1,
                **config.DEFAULT_BOT_SETTINGS
            }).execute()
            _settings_cache = result.data[0]
            _cache_timestamp = time.time()
            return _settings_cache
    except Exception as e:
        # Return defaults on error
        return config.DEFAULT_BOT_SETTINGS


async def update_bot_setting(key: str, value: Any) -> Dict[str, Any]:
    """Update a single bot setting"""
    global _settings_cache, _cache_timestamp

    result = supabase.table("bot_settings").update({
        key: value,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", 1).execute()

    # Invalidate cache
    _cache_timestamp = 0

    return result.data[0] if result.data else {}


async def update_bot_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """Update multiple bot settings at once"""
    global _settings_cache, _cache_timestamp

    settings["updated_at"] = datetime.utcnow().isoformat()
    result = supabase.table("bot_settings").update(settings).eq("id", 1).execute()

    # Invalidate cache
    _cache_timestamp = 0

    return result.data[0] if result.data else {}


async def is_claims_enabled() -> bool:
    """Quick check if claims are enabled"""
    settings = await get_bot_settings()
    return settings.get("claims_enabled", True)


async def is_maintenance_mode() -> bool:
    """Quick check if maintenance mode is on"""
    settings = await get_bot_settings()
    return settings.get("maintenance_mode", False)


async def get_maintenance_message() -> str:
    """Get current maintenance message"""
    settings = await get_bot_settings()
    return settings.get("maintenance_message", "Bot is under maintenance.")


# ============ VIDEO MANAGEMENT OPERATIONS (Admin) ============

async def add_video_by_file_id(telegram_file_id: str, title: str) -> Dict:
    """Add a video to the pool using Telegram file_id"""
    result = supabase.table("videos").insert({
        "telegram_file_id": telegram_file_id,
        "title": title,
        "is_active": True,
        "times_claimed": 0,
    }).execute()
    return result.data[0]


async def get_all_videos_admin() -> List[Dict]:
    """Get all videos for admin management"""
    result = supabase.table("videos").select("*").order("created_at", desc=True).execute()
    return result.data


async def toggle_video_active(video_id: str, is_active: bool) -> Optional[Dict]:
    """Enable or disable a video"""
    result = supabase.table("videos").update({
        "is_active": is_active,
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("id", video_id).execute()
    return result.data[0] if result.data else None


async def delete_video(video_id: str) -> bool:
    """Delete a video from the pool"""
    result = supabase.table("videos").delete().eq("id", video_id).execute()
    return len(result.data) > 0 if result.data else False


async def get_video_by_id(video_id: str) -> Optional[Dict]:
    """Get a video by its ID"""
    result = supabase.table("videos").select("*").eq("id", video_id).execute()
    return result.data[0] if result.data else None
