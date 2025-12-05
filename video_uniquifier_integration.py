#!/usr/bin/env python3
"""
Video Uniquifier Integration for YG Claim Bot

This module integrates the video uniquification system with the Telegram bot.
It handles downloading videos, uniquifying metadata, and serving to users.
"""

import os
import sys
import asyncio
import aiohttp
import tempfile
import logging
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

# Add metadata thing directory to path for imports
METADATA_DIR = Path(__file__).parent.parent / "metadata thing"
sys.path.insert(0, str(METADATA_DIR))

from video_uniquifier import generate_complete_fake_metadata, generate_xmp_xml
from mp4_xmp_injector import replace_xmp_in_mp4, find_xmp_box

logger = logging.getLogger(__name__)


class VideoUniquifier:
    """
    Async-compatible video uniquifier for Telegram bot integration.

    Usage:
        uniquifier = VideoUniquifier()

        # For URL-based videos:
        success, unique_path = await uniquifier.uniquify_from_url(video_url)

        # For local files:
        success, unique_path = await uniquifier.uniquify_from_file(local_path)

        # Send to user via Telegram, then cleanup:
        await uniquifier.cleanup(unique_path)
    """

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the uniquifier.

        Args:
            cache_dir: Directory for temporary files. Default: system temp
        """
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path(tempfile.gettempdir()) / "yg_video_cache"

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"VideoUniquifier initialized with cache: {self.cache_dir}")

    async def download_video(self, url: str) -> Tuple[bool, str]:
        """
        Download video from URL to local cache.

        Args:
            url: Video URL

        Returns:
            Tuple of (success, local_path_or_error)
        """
        try:
            # Generate temp filename
            parsed = urlparse(url)
            filename = Path(parsed.path).name or "video.mp4"
            if not filename.endswith('.mp4'):
                filename = filename + '.mp4'

            import uuid
            unique_name = f"dl_{uuid.uuid4().hex[:8]}_{filename}"
            local_path = self.cache_dir / unique_name

            # Download with aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return False, f"Download failed: HTTP {response.status}"

                    with open(local_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)

            logger.debug(f"Downloaded: {url} -> {local_path}")
            return True, str(local_path)

        except Exception as e:
            logger.error(f"Download error: {e}")
            return False, f"Download error: {str(e)}"

    def _uniquify_sync(self, input_path: str) -> Tuple[bool, str, dict]:
        """
        Synchronous uniquification (runs in executor).

        Args:
            input_path: Path to source MP4

        Returns:
            Tuple of (success, output_path_or_error, metadata_dict)
        """
        input_path = Path(input_path)

        if not input_path.exists():
            return False, f"File not found: {input_path}", {}

        # Check for XMP box
        with open(input_path, 'rb') as f:
            data = f.read()

        if find_xmp_box(data) is None:
            # No XMP - still return the original file but log warning
            logger.warning(f"No XMP metadata in {input_path.name} - serving original")
            return True, str(input_path), {"warning": "No XMP metadata found"}

        # Generate output path
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        output_path = self.cache_dir / f"unique_{unique_id}_{input_path.name}"

        # Generate and inject fake metadata
        fake_metadata = generate_complete_fake_metadata()
        fake_xmp = generate_xmp_xml(fake_metadata)

        success = replace_xmp_in_mp4(str(input_path), str(output_path), fake_xmp)

        if not success:
            return False, "XMP injection failed", {}

        metadata_summary = {
            "creator_tool": fake_metadata["creatorTool"],
            "project_path": fake_metadata["windowsAtom"]["uncProjectPath"],
            "source_files": [i["filePath"] for i in fake_metadata["ingredients"]],
            "unique_id": unique_id
        }

        logger.info(f"Uniquified: {input_path.name} -> {output_path.name}")
        logger.debug(f"New metadata: {metadata_summary}")

        return True, str(output_path), metadata_summary

    async def uniquify_from_file(self, file_path: str) -> Tuple[bool, str, dict]:
        """
        Uniquify a local video file.

        Args:
            file_path: Path to local MP4 file

        Returns:
            Tuple of (success, unique_path_or_error, metadata_dict)
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._uniquify_sync, file_path)

    async def uniquify_from_url(self, video_url: str) -> Tuple[bool, str, dict]:
        """
        Download and uniquify a video from URL.

        Args:
            video_url: URL of the video

        Returns:
            Tuple of (success, unique_path_or_error, metadata_dict)
        """
        # Download first
        success, download_result = await self.download_video(video_url)
        if not success:
            return False, download_result, {}

        downloaded_path = download_result

        # Uniquify
        success, unique_result, metadata = await self.uniquify_from_file(downloaded_path)

        # Clean up downloaded file if different from unique file
        if downloaded_path != unique_result:
            try:
                Path(downloaded_path).unlink()
            except:
                pass

        return success, unique_result, metadata

    async def cleanup(self, file_path: str) -> bool:
        """
        Clean up a temporary file.

        Args:
            file_path: Path to file to delete

        Returns:
            True if deleted successfully
        """
        try:
            path = Path(file_path)
            if path.exists() and str(self.cache_dir) in str(path.parent):
                path.unlink()
                logger.debug(f"Cleaned up: {file_path}")
                return True
        except Exception as e:
            logger.warning(f"Cleanup failed for {file_path}: {e}")
        return False

    async def cleanup_all(self) -> int:
        """
        Clean up all cached files.

        Returns:
            Number of files deleted
        """
        count = 0
        try:
            for file in self.cache_dir.glob("*.mp4"):
                file.unlink()
                count += 1
        except Exception as e:
            logger.error(f"Cleanup all error: {e}")

        logger.info(f"Cleaned up {count} cached files")
        return count


# Singleton instance for the bot
_uniquifier: Optional[VideoUniquifier] = None


def get_uniquifier() -> VideoUniquifier:
    """Get or create the singleton uniquifier instance."""
    global _uniquifier
    if _uniquifier is None:
        # Use a directory relative to the bot
        cache_dir = Path(__file__).parent / "video_cache"
        _uniquifier = VideoUniquifier(str(cache_dir))
    return _uniquifier


async def serve_unique_video(video_url: str) -> Tuple[bool, str, dict]:
    """
    Convenience function to serve a unique video.

    Args:
        video_url: URL or local path of the video

    Returns:
        Tuple of (success, unique_path_or_error, metadata_dict)
    """
    uniquifier = get_uniquifier()

    # Check if it's a URL or local path
    if video_url.startswith(('http://', 'https://')):
        return await uniquifier.uniquify_from_url(video_url)
    else:
        return await uniquifier.uniquify_from_file(video_url)


# ============ EXAMPLE USAGE ============

if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.DEBUG)

    async def test():
        print("=" * 60)
        print("VIDEO UNIQUIFIER INTEGRATION TEST")
        print("=" * 60)

        # Test with local file
        test_video = str(METADATA_DIR / "video (1).mp4")

        print(f"\nTesting with: {test_video}")

        success, result, metadata = await serve_unique_video(test_video)

        if success:
            print(f"\n✅ SUCCESS!")
            print(f"   Unique path: {result}")
            print(f"   Creator: {metadata.get('creator_tool', 'N/A')}")
            print(f"   Sources: {metadata.get('source_files', [])}")

            # Cleanup
            uniquifier = get_uniquifier()
            await uniquifier.cleanup(result)
            print(f"\n   Cleaned up: {result}")
        else:
            print(f"\n❌ FAILED: {result}")

    asyncio.run(test())
