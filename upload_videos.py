#!/usr/bin/env python3
"""
Video Upload Tool for YG Claim Bot
Uploads videos to Supabase Storage and adds them to the database.
"""

import os
import sys
from pathlib import Path
from supabase import create_client
import mimetypes

# Load config
import config

# Initialize Supabase client
supabase = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

# Supabase project URL for public access
SUPABASE_PROJECT_URL = config.SUPABASE_URL.replace('/rest/v1', '').replace('https://', '')


def upload_video(file_path: str, title: str = None) -> dict:
    """
    Upload a video file to Supabase Storage and add to database.

    Args:
        file_path: Path to the video file
        title: Optional title for the video

    Returns:
        Dict with upload result
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    if not file_path.suffix.lower() in ['.mp4', '.mov', '.webm']:
        return {"success": False, "error": f"Unsupported format: {file_path.suffix}"}

    # Generate storage path
    storage_filename = file_path.name.replace(' ', '_')
    storage_path = f"content/{storage_filename}"

    print(f"Uploading: {file_path.name}")

    # Read file
    with open(file_path, 'rb') as f:
        file_data = f.read()

    # Get mime type
    mime_type = mimetypes.guess_type(str(file_path))[0] or 'video/mp4'

    # Upload to Supabase Storage
    try:
        result = supabase.storage.from_('videos').upload(
            storage_path,
            file_data,
            {"content-type": mime_type}
        )
        print(f"  Storage upload: OK")
    except Exception as e:
        # If file exists, try to update
        if "Duplicate" in str(e) or "already exists" in str(e).lower():
            result = supabase.storage.from_('videos').update(
                storage_path,
                file_data,
                {"content-type": mime_type}
            )
            print(f"  Storage update: OK (file existed)")
        else:
            return {"success": False, "error": f"Storage upload failed: {e}"}

    # Get public URL
    # Format: https://{project}.supabase.co/storage/v1/object/public/videos/{path}
    project_ref = config.SUPABASE_URL.split('//')[1].split('.')[0]
    public_url = f"https://{project_ref}.supabase.co/storage/v1/object/public/videos/{storage_path}"

    print(f"  Public URL: {public_url}")

    # Add to videos table
    video_title = title or file_path.stem.replace('_', ' ').replace('-', ' ').title()

    try:
        db_result = supabase.table("videos").insert({
            "video_url": public_url,
            "title": video_title,
            "is_active": True,
            "times_claimed": 0
        }).execute()

        video_id = db_result.data[0]['id']
        print(f"  Database ID: {video_id}")
        print(f"  Title: {video_title}")
        print(f"  Status: ACTIVE")

        return {
            "success": True,
            "video_id": video_id,
            "url": public_url,
            "title": video_title
        }

    except Exception as e:
        return {"success": False, "error": f"Database insert failed: {e}"}


def upload_folder(folder_path: str) -> list:
    """
    Upload all videos from a folder.

    Args:
        folder_path: Path to folder containing videos

    Returns:
        List of upload results
    """
    folder = Path(folder_path)

    if not folder.exists():
        print(f"Folder not found: {folder}")
        return []

    # Find all video files
    video_extensions = ['.mp4', '.mov', '.webm']
    videos = []
    for ext in video_extensions:
        videos.extend(folder.glob(f'*{ext}'))
        videos.extend(folder.glob(f'*{ext.upper()}'))

    if not videos:
        print(f"No videos found in: {folder}")
        return []

    print(f"Found {len(videos)} videos to upload")
    print("=" * 50)

    results = []
    for i, video in enumerate(videos, 1):
        print(f"\n[{i}/{len(videos)}] {video.name}")
        result = upload_video(str(video))
        results.append(result)

        if result['success']:
            print(f"  ✅ SUCCESS")
        else:
            print(f"  ❌ FAILED: {result['error']}")

    print("\n" + "=" * 50)
    success_count = sum(1 for r in results if r['success'])
    print(f"Uploaded: {success_count}/{len(videos)} videos")

    return results


def list_videos():
    """List all videos in the database."""
    result = supabase.table("videos").select("*").execute()

    if not result.data:
        print("No videos in database")
        return

    print(f"{'ID':<40} {'Title':<30} {'Active':<8} {'Claims':<8}")
    print("-" * 90)

    for video in result.data:
        print(f"{video['id']:<40} {video['title'][:28]:<30} {str(video['is_active']):<8} {video['times_claimed']:<8}")


if __name__ == "__main__":
    print("=" * 50)
    print("YG VIDEO UPLOAD TOOL")
    print("=" * 50)

    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  python upload_videos.py <folder>     - Upload all videos from folder")
        print("  python upload_videos.py <file.mp4>   - Upload single video")
        print("  python upload_videos.py --list       - List all videos in database")
        print("\nExample:")
        print("  python upload_videos.py /mnt/x/YNTOYG/videos/")
        sys.exit(1)

    arg = sys.argv[1]

    if arg == "--list":
        list_videos()
    elif os.path.isdir(arg):
        upload_folder(arg)
    elif os.path.isfile(arg):
        result = upload_video(arg)
        if result['success']:
            print(f"\n✅ Video uploaded successfully!")
            print(f"   ID: {result['video_id']}")
            print(f"   URL: {result['url']}")
        else:
            print(f"\n❌ Upload failed: {result['error']}")
    else:
        print(f"Path not found: {arg}")
        sys.exit(1)
