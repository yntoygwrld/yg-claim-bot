"""Leaderboard calculation for YG Claim Bot"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from supabase import Client
import config

logger = logging.getLogger(__name__)


def get_week_start() -> datetime:
    """Get the start of the current week (Monday)"""
    today = datetime.utcnow()
    days_since_monday = today.weekday()
    week_start = today - timedelta(days=days_since_monday)
    return week_start.replace(hour=0, minute=0, second=0, microsecond=0)


async def calculate_weekly_leaderboard(supabase: Client) -> List[Dict]:
    """
    Calculate and update the weekly leaderboard

    This should be run periodically (e.g., hourly or daily)
    """
    week_start = get_week_start().date().isoformat()

    try:
        # Get all verified reposts for this week
        reposts = supabase.table("reposts").select(
            "user_id, view_count"
        ).eq("verified", True).gte(
            "submitted_at", week_start
        ).execute()

        if not reposts.data:
            logger.info("No reposts to process for leaderboard")
            return []

        # Aggregate by user
        user_stats = {}
        for repost in reposts.data:
            user_id = repost["user_id"]
            if user_id not in user_stats:
                user_stats[user_id] = {"posts_count": 0, "total_views": 0}

            user_stats[user_id]["posts_count"] += 1
            user_stats[user_id]["total_views"] += repost.get("view_count", 0)

        # Sort by total views
        sorted_users = sorted(
            user_stats.items(),
            key=lambda x: x[1]["total_views"],
            reverse=True
        )

        # Update leaderboard table
        for rank, (user_id, stats) in enumerate(sorted_users, 1):
            # Upsert leaderboard entry
            supabase.table("leaderboard").upsert({
                "user_id": user_id,
                "week_start": week_start,
                "posts_count": stats["posts_count"],
                "total_views": stats["total_views"],
                "rank": rank,
            }).execute()

        logger.info(f"Updated leaderboard with {len(sorted_users)} users")

        return [
            {
                "user_id": user_id,
                "rank": rank,
                **stats
            }
            for rank, (user_id, stats) in enumerate(sorted_users, 1)
        ]

    except Exception as e:
        logger.error(f"Error calculating leaderboard: {e}")
        return []


async def update_user_score(supabase: Client, user_id: str, points: int) -> None:
    """
    Update a user's gentleman score

    Called when a repost is verified with view counts
    """
    try:
        # Get current score
        user = supabase.table("users").select("gentleman_score").eq("id", user_id).execute()

        if user.data:
            current_score = user.data[0].get("gentleman_score", 0)
            new_score = current_score + points

            supabase.table("users").update({
                "gentleman_score": new_score,
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", user_id).execute()

            logger.info(f"Updated user {user_id} score: {current_score} -> {new_score}")

    except Exception as e:
        logger.error(f"Error updating user score: {e}")


async def update_user_streak(supabase: Client, user_id: str) -> int:
    """
    Update a user's claim streak

    Called when user claims daily video
    Returns the new streak count
    """
    try:
        user = supabase.table("users").select(
            "streak_count", "updated_at"
        ).eq("id", user_id).execute()

        if not user.data:
            return 0

        current_streak = user.data[0].get("streak_count", 0)
        last_update = user.data[0].get("updated_at")

        # Check if last claim was yesterday (streak continues)
        if last_update:
            last_date = datetime.fromisoformat(last_update.replace("Z", "+00:00"))
            yesterday = datetime.utcnow() - timedelta(days=1)

            if last_date.date() == yesterday.date():
                # Streak continues
                new_streak = current_streak + 1
            elif last_date.date() == datetime.utcnow().date():
                # Already claimed today
                new_streak = current_streak
            else:
                # Streak broken
                new_streak = 1
        else:
            new_streak = 1

        supabase.table("users").update({
            "streak_count": new_streak,
        }).eq("id", user_id).execute()

        return new_streak

    except Exception as e:
        logger.error(f"Error updating user streak: {e}")
        return 0


def calculate_points(view_count: int, like_count: int = 0) -> int:
    """
    Calculate points from view and like counts

    Formula:
    - Base points: 10
    - View bonus: 1 point per 100 views
    - Like bonus: 1 point per 10 likes (smaller multiplier)
    """
    base = config.BASE_POINTS
    view_bonus = int(view_count * config.VIEW_MULTIPLIER)
    like_bonus = int(like_count * 0.1)  # 1 point per 10 likes

    return base + view_bonus + like_bonus


def get_streak_multiplier(streak_count: int) -> float:
    """
    Get bonus multiplier based on streak

    - 7-day streak: 1.5x
    - 14-day streak: 2x
    - 30-day streak: 3x
    """
    if streak_count >= 30:
        return 3.0
    elif streak_count >= 14:
        return 2.0
    elif streak_count >= 7:
        return 1.5
    else:
        return 1.0
