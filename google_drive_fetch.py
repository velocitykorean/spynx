"""
Google Drive Integration Module
Fetch audio (MP3) and image files from separate Google Drive folders.
Uses Google Drive API v3 with service account credentials.
"""
import os
import json
import sys
import tempfile
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.http import MediaIoBaseDownload

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

GOOGLE_DRIVE_AUDIO_FOLDER_ID = os.getenv("GOOGLE_DRIVE_AUDIO_FOLDER_ID")
GOOGLE_DRIVE_IMAGE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_IMAGE_FOLDER_ID")
GOOGLE_SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
LOCAL_AUDIO_DIR = os.getenv("LOCAL_AUDIO_DIR", "Audio")
LOCAL_IMAGE_DIR = os.getenv("LOCAL_IMAGE_DIR", "Images")

PUBLISHED_LOG = "published_songs.json"


def get_published_songs():
    """Get list of already published song names."""
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return [item.get('song_name', '') for item in data]
            except json.JSONDecodeError:
                return []
    return []


def get_published_history():
    """Get full publishing history with repost counts."""
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def get_drive_service():
    """Initialize and return Google Drive API client."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

        if not GOOGLE_SERVICE_ACCOUNT_KEY:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_KEY not set")

        if os.path.exists(GOOGLE_SERVICE_ACCOUNT_KEY):
            creds = service_account.Credentials.from_service_account_file(
                GOOGLE_SERVICE_ACCOUNT_KEY, scopes=SCOPES)
            service = build('drive', 'v3', credentials=creds)
            print("Google Drive initialized with Service Account file")
            return service
        elif GOOGLE_SERVICE_ACCOUNT_KEY.strip().startswith('{'):
            temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
            temp_file.write(GOOGLE_SERVICE_ACCOUNT_KEY)
            temp_file.close()

            creds = service_account.Credentials.from_service_account_file(
                temp_file.name, scopes=SCOPES)
            service = build('drive', 'v3', credentials=creds)
            print("Google Drive initialized with Service Account JSON")

            os.unlink(temp_file.name)
            return service
        else:
            raise ValueError("Google Service Account key is invalid")

    except ImportError as e:
        print(f"Installing required Google Drive libraries... Error: {e}")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "google-auth", "google-auth-oauthlib",
                               "google-auth-httplib2", "google-api-python-client"])
        return get_drive_service()
    except Exception as e:
        print(f"Error initializing Google Drive: {e}")
        return None


def list_drive_files(service, folder_id, mime_types):
    """List all files in a Google Drive folder matching given MIME types."""
    if not service:
        return []

    try:
        files = []
        for mime_type in mime_types:
            query = f"'{folder_id}' in parents and trashed=false and mimeType='{mime_type}'"
            results = service.files().list(
                q=query,
                fields="files(id, name, size, mimeType)",
                spaces='drive'
            ).execute()
            files.extend(results.get('files', []))

        files.sort(key=lambda x: x.get('name', ''))
        return files
    except Exception as e:
        print(f"Google Drive API error: {e}")
        return []


def download_file(service, file_info, local_path):
    """Download a file from Google Drive to local storage."""
    try:
        request = service.files().get_media(fileId=file_info['id'])

        with open(local_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(f"  Download progress: {int(status.progress() * 100)}%")

        print(f"Downloaded: {file_info['name']}")
        return True
    except Exception as e:
        print(f"Failed to download {file_info['name']}: {e}")
        return False


def get_next_unpublished_pair(published):
    """
    Find the next unpublished song by index.
    Songs are numbered 01-10 in both audio and image folders.
    Returns (audio_path, image_path, song_index) or None.
    """
    service = get_drive_service()
    if not service:
        return None

    # List audio files (MP3)
    audio_files = list_drive_files(service, GOOGLE_DRIVE_AUDIO_FOLDER_ID, ["audio/mpeg"])
    if not audio_files:
        print("No audio files found in Google Drive.")
        return None

    print(f"\nFound {len(audio_files)} audio file(s) in Google Drive.")
    for af in audio_files[:5]:
        print(f"  - {af['name']}")
    if len(audio_files) > 5:
        print(f"  ... and {len(audio_files) - 5} more")

    # List image files (common image MIME types)
    image_mime_types = ["image/jpeg", "image/png", "image/webp"]
    image_files = list_drive_files(service, GOOGLE_DRIVE_IMAGE_FOLDER_ID, image_mime_types)
    if not image_files:
        print("No image files found in Google Drive.")
        return None

    print(f"Found {len(image_files)} image file(s) in Google Drive.")
    for im in image_files[:5]:
        print(f"  - {im['name']}")
    if len(image_files) > 5:
        print(f"  ... and {len(image_files) - 5} more")

    # Create a mapping: index -> audio/image
    # Assumes files are named like: 01_song.mp3, 02_song.mp3, etc.
    # or matching by position in sorted list
    audio_by_index = {}
    for af in audio_files:
        name = af['name']
        # Try to extract leading number
        idx = _extract_index(name)
        if idx is not None:
            audio_by_index[idx] = af

    image_by_index = {}
    for im in image_files:
        name = im['name']
        idx = _extract_index(name)
        if idx is not None:
            image_by_index[idx] = im

    # Find first unpublished song
    for idx in sorted(set(audio_by_index.keys()) | set(image_by_index.keys())):
        audio_info = audio_by_index.get(idx)
        image_info = image_by_index.get(idx)

        if not audio_info:
            print(f"  Skipping index {idx}: no audio file")
            continue
        if not image_info:
            print(f"  Skipping index {idx}: no image file")
            continue

        song_name = audio_info['name']
        if song_name in published:
            print(f"Skipping {song_name} - already published")
            continue

        # Download audio
        Path(LOCAL_AUDIO_DIR).mkdir(parents=True, exist_ok=True)
        audio_path = os.path.join(LOCAL_AUDIO_DIR, audio_info['name'])
        print(f"\nDownloading audio: {audio_info['name']}")
        if not download_file(service, audio_info, audio_path):
            print(f"Failed to download audio for song {idx}")
            continue

        # Download image
        Path(LOCAL_IMAGE_DIR).mkdir(parents=True, exist_ok=True)
        image_path = os.path.join(LOCAL_IMAGE_DIR, image_info['name'])
        print(f"Downloading image: {image_info['name']}")
        if not download_file(service, image_info, image_path):
            print(f"Failed to download image for song {idx}")
            continue

        print(f"\nSelected song {idx}: {song_name}")
        return audio_path, image_path, idx

    print("\nAll songs have been published.")
    return None


def _extract_index(filename):
    """Extract leading numeric index from filename (e.g., '01_song.mp3' -> 1)."""
    import re
    match = re.match(r'^(\d+)', filename)
    if match:
        return int(match.group(1))
    return None


if __name__ == "__main__":
    get_next_unpublished_pair(get_published_songs())
