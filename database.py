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

    # Points are awarded ONLY on submit, not on claim
    # This ensures users actually post and share links

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


# ============ PENDING ONBOARDING OPERATIONS ============

async def store_pending_onboarding(telegram_id: int, email: str, token: str) -> Dict:
    """Store pending onboarding when user has valid token but isn't in group yet.
    Uses upsert to handle users who click the link multiple times."""
    result = supabase.table("pending_onboarding").upsert({
        "telegram_id": telegram_id,
        "email": email,
        "original_token": token,
    }, on_conflict="telegram_id").execute()
    return result.data[0] if result.data else {}


async def get_pending_onboarding(telegram_id: int) -> Optional[Dict]:
    """Get pending onboarding record for a telegram user"""
    result = supabase.table("pending_onboarding").select("*").eq(
        "telegram_id", telegram_id
    ).execute()

    if not result.data:
        return None

    record = result.data[0]

    # Check if expired
    expires_at = datetime.fromisoformat(record["expires_at"].replace("Z", "+00:00"))
    if datetime.utcnow() > expires_at.replace(tzinfo=None):
        # Expired - delete and return None
        await delete_pending_onboarding(telegram_id)
        return None

    return record


async def delete_pending_onboarding(telegram_id: int) -> bool:
    """Delete pending onboarding record after successful completion"""
    result = supabase.table("pending_onboarding").delete().eq(
        "telegram_id", telegram_id
    ).execute()
    return True


async def verify_magic_token_without_consuming(token: str) -> Optional[str]:
    """Verify magic link token and return email if valid, WITHOUT marking as used.
    Used when we need to validate token but can't complete onboarding yet."""
    result = supabase.table("email_tokens").select("*").eq("token", token).eq("used", False).execute()

    if not result.data:
        return None

    token_data = result.data[0]

    # Check expiration
    expires_at = datetime.fromisoformat(token_data["expires_at"].replace("Z", "+00:00"))
    if datetime.utcnow() > expires_at.replace(tzinfo=None):
        return None

    # Return email WITHOUT marking token as used
    return token_data["email"]


async def consume_magic_token(token: str) -> bool:
    """Mark a magic token as used after successful onboarding"""
    result = supabase.table("email_tokens").update({"used": True}).eq("token", token).execute()
    return len(result.data) > 0 if result.data else False


# ============ DASHBOARD AUTH TOKEN OPERATIONS ============

async def generate_dashboard_token(email: str) -> str:
    """Generate a dashboard login token for immediate website access.
    This creates a 'dashboard_login' type token that the website can verify."""
    import secrets

    token = secrets.token_hex(32)
    expires_at = datetime.utcnow().replace(tzinfo=None)
    # Token expires in 7 days (same as session)
    from datetime import timedelta
    expires_at = (expires_at + timedelta(days=7)).isoformat() + "Z"

    supabase.table("email_tokens").insert({
        "email": email,
        "token": token,
        "type": "dashboard_login",
        "used": False,
        "expires_at": expires_at,
    }).execute()

    return token


# ============ WALLET REGISTRY OPERATIONS ============
# NOTE: These functions prepare for post-launch token verification.
# Currently in pre-launch mode - wallet verification not enforced yet.
# See /mnt/x/YNTOYG/POST_LAUNCH/02_TOKEN_VERIFICATION.md for activation.

async def get_wallet_by_address(wallet_address: str) -> Optional[Dict]:
    """Check if wallet is already registered to any user.
    Used to prevent duplicate wallet registrations."""
    result = supabase.table("wallet_registry").select("*").eq(
        "wallet_address", wallet_address
    ).execute()
    return result.data[0] if result.data else None


async def register_wallet(
    user_id: str,
    telegram_id: int,
    wallet_address: str,
    token_balance: int = 0,
    verified: bool = False
) -> Dict:
    """Register a new wallet and link to user.

    Args:
        user_id: UUID from users table
        telegram_id: Telegram user ID
        wallet_address: Solana wallet address
        token_balance: Raw token balance (default 0 for pre-launch)
        verified: Whether token holdings were verified (default False for pre-launch)

    Returns:
        Created wallet_registry record
    """
    # Insert into wallet_registry
    registry_result = supabase.table("wallet_registry").insert({
        "wallet_address": wallet_address,
        "user_id": user_id,
        "token_balance": token_balance,
        "token_verified": verified,
        "last_verified_at": datetime.utcnow().isoformat() if verified else None,
    }).execute()

    # Update user record with wallet info
    supabase.table("users").update({
        "wallet_address": wallet_address,
        "wallet_verified": verified,
        "wallet_connected_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }).eq("telegram_id", telegram_id).execute()

    return registry_result.data[0] if registry_result.data else {}


async def is_wallet_verified(telegram_id: int) -> bool:
    """Check if user has a verified wallet connected.
    Used for gating dashboard/leaderboard access."""
    result = supabase.table("users").select(
        "wallet_verified"
    ).eq("telegram_id", telegram_id).single().execute()

    if not result.data:
        return False

    return result.data.get("wallet_verified", False)
