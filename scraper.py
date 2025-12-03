"""Social media view scraper for YG Claim Bot"""
import re
import asyncio
import logging
from typing import Optional, Dict, Tuple
from bs4 import BeautifulSoup
import httpx

logger = logging.getLogger(__name__)


async def scrape_tiktok_views(url: str) -> Tuple[int, int]:
    """
    Scrape view and like counts from TikTok video

    Returns:
        Tuple of (view_count, like_count)
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True, timeout=30.0)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # TikTok embeds stats in JSON-LD or meta tags
            # This is a simplified version - real implementation needs more robust parsing

            # Look for view count in various places
            view_count = 0
            like_count = 0

            # Try to find stats in script tags
            scripts = soup.find_all("script", type="application/ld+json")
            for script in scripts:
                if "interactionCount" in script.text:
                    # Parse JSON and extract counts
                    import json
                    try:
                        data = json.loads(script.text)
                        if "interactionStatistic" in data:
                            for stat in data["interactionStatistic"]:
                                if stat.get("interactionType") == "http://schema.org/WatchAction":
                                    view_count = stat.get("userInteractionCount", 0)
                                elif stat.get("interactionType") == "http://schema.org/LikeAction":
                                    like_count = stat.get("userInteractionCount", 0)
                    except json.JSONDecodeError:
                        pass

            return view_count, like_count

    except Exception as e:
        logger.error(f"Error scraping TikTok {url}: {e}")
        return 0, 0


async def scrape_instagram_views(url: str) -> Tuple[int, int]:
    """
    Scrape view and like counts from Instagram post

    Note: Instagram is heavily protected. This may require:
    - Logged-in session cookies
    - Proxy rotation
    - Playwright for JS rendering

    Returns:
        Tuple of (view_count, like_count)
    """
    try:
        # Instagram requires authentication for most scraping
        # This is a placeholder - real implementation needs Playwright or API access
        logger.warning("Instagram scraping requires authenticated session")
        return 0, 0

    except Exception as e:
        logger.error(f"Error scraping Instagram {url}: {e}")
        return 0, 0


async def scrape_twitter_views(url: str) -> Tuple[int, int]:
    """
    Scrape view and like counts from Twitter/X post

    Note: Twitter API or authenticated access typically required

    Returns:
        Tuple of (view_count, like_count)
    """
    try:
        # Twitter/X heavily rate-limits and requires auth
        # This is a placeholder - real implementation needs API or Playwright
        logger.warning("Twitter scraping requires API access or authenticated session")
        return 0, 0

    except Exception as e:
        logger.error(f"Error scraping Twitter {url}: {e}")
        return 0, 0


def detect_platform(url: str) -> Optional[str]:
    """Detect social media platform from URL"""
    patterns = {
        "tiktok": r"tiktok\.com",
        "instagram": r"instagram\.com",
        "twitter": r"(twitter|x)\.com",
    }

    for platform, pattern in patterns.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform

    return None


async def scrape_post_stats(url: str) -> Dict[str, int]:
    """
    Scrape stats from any supported social media post

    Returns:
        Dict with view_count and like_count
    """
    platform = detect_platform(url)

    if not platform:
        logger.warning(f"Unknown platform for URL: {url}")
        return {"view_count": 0, "like_count": 0}

    scrapers = {
        "tiktok": scrape_tiktok_views,
        "instagram": scrape_instagram_views,
        "twitter": scrape_twitter_views,
    }

    scraper = scrapers.get(platform)
    if scraper:
        view_count, like_count = await scraper(url)
        return {"view_count": view_count, "like_count": like_count}

    return {"view_count": 0, "like_count": 0}


async def batch_scrape_reposts(reposts: list) -> list:
    """
    Scrape multiple reposts concurrently

    Args:
        reposts: List of repost dicts with 'post_url' key

    Returns:
        List of dicts with scraped stats
    """
    tasks = [scrape_post_stats(repost["post_url"]) for repost in reposts]
    results = await asyncio.gather(*tasks)

    # Combine reposts with their stats
    for repost, stats in zip(reposts, results):
        repost.update(stats)

    return reposts
