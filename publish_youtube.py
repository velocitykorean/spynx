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


def upload_to_youtube(video_path, title, description, tags=None, category_id='10'):
    """
    Upload video to YouTube.
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

    print(f"[youtube] Uploaded! Video ID: {response['id']}")
    print(f"[youtube] URL: https://youtube.com/watch?v={response['id']}")

    return response


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python publish_youtube.py <video_path>")
        sys.exit(1)

    video_file = sys.argv[1]
    if not os.path.exists(video_file):
        print(f"[youtube] Video not found: {video_file}")
        sys.exit(1)

    title = "New Music Release"
    description = "#music #newmusic #song"

    try:
        upload_to_youtube(video_file, title, description)
    except Exception as e:
        print(f"[youtube] Upload failed: {e}")
        sys.exit(1)
