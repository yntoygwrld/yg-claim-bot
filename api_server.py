"""
HTTP API Server for YG Video Claim System

This server provides HTTP endpoints for the website to request video preparation.
Runs alongside the Telegram bot on Koyeb.

Endpoints:
- POST /api/video/prepare - Download, uniquify, and upload video to Supabase Storage
- GET /health - Health check endpoint
"""

import os
import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, jsonify
from functools import wraps
import tempfile

# Import bot components
from video_uniquifier_integration import get_uniquifier
from supabase import create_client
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# API Secret for authentication
API_SECRET = os.getenv("API_SECRET", "")

# Supabase client for storage
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

# Telegram Bot Token for file downloads
BOT_TOKEN = config.TELEGRAM_BOT_TOKEN


def require_api_key(f):
    """Decorator to require API key authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Missing authorization header"}), 401

        token = auth_header[7:]  # Remove 'Bearer ' prefix

        if not API_SECRET:
            logger.error("API_SECRET not configured!")
            return jsonify({"error": "Server misconfigured"}), 500

        if token != API_SECRET:
            return jsonify({"error": "Invalid API key"}), 401

        return f(*args, **kwargs)
    return decorated


async def download_telegram_file(file_id: str, output_path: str) -> bool:
    """Download file from Telegram servers using file_id"""
    import aiohttp

    try:
        # Get file path from Telegram
        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"

        async with aiohttp.ClientSession() as session:
            # Get file info
            async with session.get(get_file_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to get file info: {response.status}")
                    return False

                data = await response.json()
                if not data.get("ok"):
                    logger.error(f"Telegram API error: {data}")
                    return False

                file_path = data["result"]["file_path"]

            # Download the actual file
            download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

            async with session.get(download_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download file: {response.status}")
                    return False

                with open(output_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)

        logger.info(f"Downloaded Telegram file to: {output_path}")
        return True

    except Exception as e:
        logger.error(f"Error downloading Telegram file: {e}")
        return False


def upload_to_supabase_storage(local_path: str, storage_path: str) -> str:
    """Upload file to Supabase Storage and return public URL"""
    try:
        with open(local_path, 'rb') as f:
            file_data = f.read()

        # Upload to Supabase Storage
        result = supabase.storage.from_('unique-videos').upload(
            storage_path,
            file_data,
            file_options={"content-type": "video/mp4"}
        )

        # Get public URL
        public_url = supabase.storage.from_('unique-videos').get_public_url(storage_path)

        logger.info(f"Uploaded to Supabase: {storage_path}")
        return public_url

    except Exception as e:
        logger.error(f"Error uploading to Supabase: {e}")
        raise


def delete_from_supabase_storage(storage_path: str) -> bool:
    """Delete file from Supabase Storage"""
    try:
        supabase.storage.from_('unique-videos').remove([storage_path])
        logger.info(f"Deleted from Supabase: {storage_path}")
        return True
    except Exception as e:
        logger.error(f"Error deleting from Supabase: {e}")
        return False


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "yg-video-api",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route('/api/video/prepare', methods=['POST'])
@require_api_key
def prepare_video():
    """
    Prepare a unique video for download.

    Request:
    {
        "file_id": "telegram_file_id",
        "claim_id": "uuid",
        "user_id": "uuid"
    }

    Response:
    {
        "success": true,
        "storage_path": "temp/claim_id.mp4",
        "download_url": "https://...",
        "expires_at": "2025-12-10T12:30:00Z",
        "file_size": 28456789,
        "metadata": {
            "creator_tool": "...",
            "unique_id": "..."
        }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        file_id = data.get('file_id')
        claim_id = data.get('claim_id')
        user_id = data.get('user_id')

        if not file_id:
            return jsonify({"error": "file_id is required"}), 400
        if not claim_id:
            return jsonify({"error": "claim_id is required"}), 400

        # Create temp directory
        temp_dir = Path(tempfile.gettempdir()) / "yg_api_temp"
        temp_dir.mkdir(exist_ok=True)

        # Download from Telegram
        download_path = temp_dir / f"dl_{claim_id}.mp4"

        # Run async download
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            download_success = loop.run_until_complete(
                download_telegram_file(file_id, str(download_path))
            )
        finally:
            loop.close()

        if not download_success:
            return jsonify({"error": "Failed to download video from Telegram"}), 500

        # Uniquify the video
        uniquifier = get_uniquifier()

        # Run async uniquification
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            success, unique_path, metadata = loop.run_until_complete(
                uniquifier.uniquify_from_file(str(download_path))
            )
        finally:
            loop.close()

        if not success:
            # Cleanup downloaded file
            download_path.unlink(missing_ok=True)
            return jsonify({"error": f"Failed to uniquify video: {unique_path}"}), 500

        # Get file size
        file_size = Path(unique_path).stat().st_size

        # Upload to Supabase Storage
        storage_path = f"temp/{claim_id}.mp4"

        try:
            download_url = upload_to_supabase_storage(unique_path, storage_path)
        except Exception as e:
            # Cleanup temp files
            download_path.unlink(missing_ok=True)
            Path(unique_path).unlink(missing_ok=True)
            return jsonify({"error": f"Failed to upload: {str(e)}"}), 500

        # Cleanup temp files
        download_path.unlink(missing_ok=True)
        if unique_path != str(download_path):
            Path(unique_path).unlink(missing_ok=True)

        # Calculate expiry (30 minutes from now)
        expires_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat() + "Z"

        logger.info(f"Video prepared successfully: {claim_id}")

        return jsonify({
            "success": True,
            "storage_path": storage_path,
            "download_url": download_url,
            "expires_at": expires_at,
            "file_size": file_size,
            "metadata": metadata
        })

    except Exception as e:
        logger.exception(f"Error in prepare_video: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/video/cleanup', methods=['POST'])
@require_api_key
def cleanup_video():
    """
    Delete a video from Supabase Storage.

    Request:
    {
        "storage_path": "temp/claim_id.mp4"
    }

    Response:
    {
        "success": true
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        storage_path = data.get('storage_path')

        if not storage_path:
            return jsonify({"error": "storage_path is required"}), 400

        success = delete_from_supabase_storage(storage_path)

        return jsonify({"success": success})

    except Exception as e:
        logger.exception(f"Error in cleanup_video: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/video/cleanup-expired', methods=['POST'])
@require_api_key
def cleanup_expired():
    """
    Delete all expired videos from Supabase Storage.
    Called by website before each new claim (lazy cleanup).

    Request:
    {
        "expired_paths": ["temp/claim1.mp4", "temp/claim2.mp4"]
    }

    Response:
    {
        "success": true,
        "deleted_count": 2
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        expired_paths = data.get('expired_paths', [])

        if not expired_paths:
            return jsonify({"success": True, "deleted_count": 0})

        # Delete all expired files
        try:
            supabase.storage.from_('unique-videos').remove(expired_paths)
            logger.info(f"Deleted {len(expired_paths)} expired videos")
        except Exception as e:
            logger.error(f"Error during bulk delete: {e}")

        return jsonify({
            "success": True,
            "deleted_count": len(expired_paths)
        })

    except Exception as e:
        logger.exception(f"Error in cleanup_expired: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # For local testing only - Koyeb uses gunicorn
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=True)
