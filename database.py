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


async def create_claim(user_id: str, video_id: str) -> Dict:
    """Create a new daily claim record"""
    result = supabase.table("daily_claims").insert({
        "user_id": user_id,
        "video_id": video_id,
        "claim_date": date.today().isoformat(),
    }).execute()

    # Update user stats
    supabase.rpc("increment_user_claims", {"user_id_param": user_id}).execute()

    return result.data[0]


# ============ REPOST OPERATIONS ============

async def create_repost(user_id: str, video_id: str, platform: str, post_url: str) -> Dict:
    """Create a new repost submission"""
    result = supabase.table("reposts").insert({
        "user_id": user_id,
        "video_id": video_id,
        "platform": platform,
        "post_url": post_url,
    }).execute()
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
