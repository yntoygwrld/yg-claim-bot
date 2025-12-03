"""Video management for YG Claim Bot"""
import logging
import random
from typing import Optional, Dict, List
from datetime import date
from supabase import Client

logger = logging.getLogger(__name__)


async def get_random_video(supabase: Client) -> Optional[Dict]:
    """
    Get a random active video from the pool

    Videos are weighted by inverse of times_claimed to favor
    less-used videos for better distribution
    """
    try:
        # Get all active videos
        result = supabase.table("videos").select("*").eq("is_active", True).execute()

        if not result.data:
            logger.warning("No active videos in pool")
            return None

        videos = result.data

        # Weight by inverse of times_claimed (newer videos get more chances)
        # Add 1 to avoid division by zero
        weights = [1 / (v.get("times_claimed", 0) + 1) for v in videos]
        total_weight = sum(weights)
        normalized_weights = [w / total_weight for w in weights]

        # Select video using weighted random
        selected = random.choices(videos, weights=normalized_weights, k=1)[0]

        return selected

    except Exception as e:
        logger.error(f"Error getting random video: {e}")
        return None


async def increment_video_claims(supabase: Client, video_id: str) -> None:
    """Increment the times_claimed counter for a video"""
    try:
        video = supabase.table("videos").select("times_claimed").eq("id", video_id).execute()

        if video.data:
            current_count = video.data[0].get("times_claimed", 0)
            supabase.table("videos").update({
                "times_claimed": current_count + 1
            }).eq("id", video_id).execute()

    except Exception as e:
        logger.error(f"Error incrementing video claims: {e}")


async def add_video_to_pool(
    supabase: Client,
    video_url: str,
    title: str = None,
    thumbnail_url: str = None
) -> Dict:
    """
    Add a new video to the pool

    Args:
        supabase: Supabase client
        video_url: URL to video file in Supabase storage
        title: Optional title for the video
        thumbnail_url: Optional thumbnail URL
    """
    try:
        result = supabase.table("videos").insert({
            "video_url": video_url,
            "title": title,
            "thumbnail_url": thumbnail_url,
            "is_active": True,
            "times_claimed": 0,
        }).execute()

        logger.info(f"Added new video to pool: {video_url}")
        return result.data[0]

    except Exception as e:
        logger.error(f"Error adding video to pool: {e}")
        return None


async def deactivate_video(supabase: Client, video_id: str) -> None:
    """Deactivate a video (remove from rotation without deleting)"""
    try:
        supabase.table("videos").update({
            "is_active": False
        }).eq("id", video_id).execute()

        logger.info(f"Deactivated video: {video_id}")

    except Exception as e:
        logger.error(f"Error deactivating video: {e}")


async def get_video_stats(supabase: Client) -> Dict:
    """Get statistics about the video pool"""
    try:
        all_videos = supabase.table("videos").select("*").execute()

        if not all_videos.data:
            return {
                "total_videos": 0,
                "active_videos": 0,
                "total_claims": 0,
                "avg_claims_per_video": 0,
            }

        active = [v for v in all_videos.data if v.get("is_active", False)]
        total_claims = sum(v.get("times_claimed", 0) for v in all_videos.data)

        return {
            "total_videos": len(all_videos.data),
            "active_videos": len(active),
            "total_claims": total_claims,
            "avg_claims_per_video": total_claims / len(all_videos.data) if all_videos.data else 0,
        }

    except Exception as e:
        logger.error(f"Error getting video stats: {e}")
        return {}


async def get_user_claimed_videos(supabase: Client, user_id: str, days: int = 7) -> List[str]:
    """
    Get list of video IDs claimed by user in the last N days

    Useful for ensuring variety in video assignments
    """
    try:
        from datetime import datetime, timedelta

        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()

        result = supabase.table("daily_claims").select(
            "video_id"
        ).eq("user_id", user_id).gte("claimed_at", cutoff).execute()

        return [claim["video_id"] for claim in result.data]

    except Exception as e:
        logger.error(f"Error getting user claimed videos: {e}")
        return []


async def get_fresh_video_for_user(supabase: Client, user_id: str) -> Optional[Dict]:
    """
    Get a video the user hasn't seen recently

    Falls back to random if all videos have been claimed
    """
    try:
        # Get videos user has claimed recently
        claimed_ids = await get_user_claimed_videos(supabase, user_id, days=7)

        # Get all active videos
        result = supabase.table("videos").select("*").eq("is_active", True).execute()

        if not result.data:
            return None

        # Filter out recently claimed
        fresh_videos = [v for v in result.data if v["id"] not in claimed_ids]

        if fresh_videos:
            # Weight and select from fresh videos
            weights = [1 / (v.get("times_claimed", 0) + 1) for v in fresh_videos]
            total = sum(weights)
            normalized = [w / total for w in weights]
            return random.choices(fresh_videos, weights=normalized, k=1)[0]
        else:
            # User has seen all videos, return random
            logger.info(f"User {user_id} has seen all videos, returning random")
            return random.choice(result.data)

    except Exception as e:
        logger.error(f"Error getting fresh video for user: {e}")
        return await get_random_video(supabase)
