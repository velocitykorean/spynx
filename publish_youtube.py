"""
YouTube Upload Script
Uses OAuth refresh token to upload videos to YouTube.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()


def get_authenticated_service():
    """Authenticate using refresh token from environment."""
    client_id = (os.getenv('YOUTUBE_CLIENT_ID') or os.getenv('YT_CLIENT_ID', '')).strip()
    client_secret = (os.getenv('YOUTUBE_CLIENT_SECRET') or os.getenv('YT_CLIENT_SECRET', '')).strip()
    refresh_token = (os.getenv('YOUTUBE_REFRESH_TOKEN') or os.getenv('YT_REFRESH_TOKEN', '')).strip()

    def mask(s):
        return f"{s[:4]}...{s[-4:]}" if s and len(s) > 8 else "MISSING"

    print(f"[youtube] Client ID: {mask(client_id)}")
    print(f"[youtube] Client Secret: {mask(client_secret)}")
    print(f"[youtube] Refresh Token: {mask(refresh_token)}")

    if not all([client_id, client_secret, refresh_token]):
        raise ValueError(
            "Missing YouTube credentials! Set these environment variables:\n"
            "  - YT_CLIENT_ID\n"
            "  - YT_CLIENT_SECRET\n"
            "  - YT_REFRESH_TOKEN"
        )

    creds = Credentials(
        None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube"]
    )

    try:
        creds.refresh(Request())
    except Exception as e:
        if "invalid_grant" in str(e).lower():
            print("\n❌ [youtube] AUTH ERROR: Refresh token has EXPIRED or been REVOKED.")
            print("💡 Generate a new refresh token from Google Cloud Console.")
        raise

    return build('youtube', 'v3', credentials=creds)


def set_video_thumbnail(youtube, video_id, thumbnail_path):
    """
    Upload and set custom thumbnail for a YouTube video.
    Note: Requires YouTube channel to be verified for custom thumbnails.
    """
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        print(f"[youtube] Thumbnail file not found: {thumbnail_path}")
        return None

    print(f"[youtube] Uploading thumbnail: {thumbnail_path}")
    mimetype = 'image/png' if str(thumbnail_path).lower().endswith('.png') else 'image/jpeg'
    try:
        media = MediaFileUpload(
            str(thumbnail_path),
            mimetype=mimetype,
            resumable=False
        )
        request = youtube.thumbnails().set(
            videoId=video_id,
            media_body=media
        )
        response = request.execute()
        print(f"[youtube] Thumbnail successfully set for video: {video_id}")
        return response
    except Exception as e:
        print(f"[youtube] WARNING: Failed to set thumbnail: {e}")
        return None


def upload_to_youtube(video_path, title, description, tags=None, category_id='10', thumbnail_path=None):
    """
    Upload video to YouTube and optionally set custom thumbnail.
    Category 10 = Music
    """
    if tags is None:
        tags = ['music', 'song', 'pop', 'cinematic', 'emotional', 'newmusic']

    youtube = get_authenticated_service()

    body = {
        'snippet': {
            'title': title,
            'description': description,
            'tags': tags,
            'categoryId': category_id
        },
        'status': {
            'privacyStatus': 'public',
            'selfDeclaredMadeForKids': False,
        }
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=-1,
        resumable=True,
        mimetype='video/mp4'
    )

    print(f"[youtube] Uploading: {title}")
    request = youtube.videos().insert(
        part=','.join(body.keys()),
        body=body,
        media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"[youtube] Progress: {int(status.progress() * 100)}%")

    video_id = response['id']
    print(f"[youtube] Uploaded! Video ID: {video_id}")
    print(f"[youtube] URL: https://youtube.com/watch?v={video_id}")

    # Upload custom thumbnail if available
    if thumbnail_path:
        set_video_thumbnail(youtube, video_id, thumbnail_path)

    return response


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  Upload video:            python publish_youtube.py <video_path> [thumbnail_path] [title] [description]")
        print("  Set thumbnail on video:  python publish_youtube.py --set-thumbnail <video_id> <thumbnail_path>")
        sys.exit(1)

    if sys.argv[1] == '--set-thumbnail':
        if len(sys.argv) < 4:
            print("Usage: python publish_youtube.py --set-thumbnail <video_id> <thumbnail_path>")
            sys.exit(1)
        video_id = sys.argv[2]
        thumb_file = sys.argv[3]
        if not os.path.exists(thumb_file):
            print(f"[youtube] Thumbnail not found: {thumb_file}")
            sys.exit(1)
        youtube = get_authenticated_service()
        set_video_thumbnail(youtube, video_id, thumb_file)
        sys.exit(0)

    video_file = sys.argv[1]
    thumb_file = sys.argv[2] if len(sys.argv) > 2 and os.path.exists(sys.argv[2]) else None
    title = sys.argv[3] if len(sys.argv) > 3 else "New Music Release"
    description = sys.argv[4] if len(sys.argv) > 4 else "#music #newmusic #song"

    if not os.path.exists(video_file):
        print(f"[youtube] Video not found: {video_file}")
        sys.exit(1)

    try:
        upload_to_youtube(video_file, title, description, thumbnail_path=thumb_file)
    except Exception as e:
        print(f"[youtube] Upload failed: {e}")
        sys.exit(1)

