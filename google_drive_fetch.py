"""
Google Drive Integration Module
Fetch audio (MP3) and image files from separate Google Drive folders.
Matches files by sorted position (1st audio = 1st image, etc.)
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
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return [item.get('song_name', '') for item in data]
            except json.JSONDecodeError:
                return []
    return []


def get_drive_service():
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
            os.unlink(temp_file.name)
            print("Google Drive initialized with Service Account JSON")
            return service
        else:
            raise ValueError("Google Service Account key is invalid")

    except Exception as e:
        print(f"Error initializing Google Drive: {e}")
        return None


def list_drive_files(service, folder_id, mime_types):
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
    Find next unpublished song by matching audio + image by sorted position.
    Audio and image files are matched 1-to-1 by their sorted order.
    """
    service = get_drive_service()
    if not service:
        return None

    audio_files = list_drive_files(service, GOOGLE_DRIVE_AUDIO_FOLDER_ID, ["audio/mpeg"])
    if not audio_files:
        print("No audio files found in Google Drive.")
        return None

    print(f"\nFound {len(audio_files)} audio file(s) in Google Drive.")
    for af in audio_files:
        print(f"  - {af['name']}")

    image_files = list_drive_files(service, GOOGLE_DRIVE_IMAGE_FOLDER_ID,
                                   ["image/jpeg", "image/png", "image/webp"])
    if not image_files:
        print("No image files found in Google Drive.")
        return None

    print(f"Found {len(image_files)} image file(s) in Google Drive.")
    for im in image_files:
        print(f"  - {im['name']}")

    # Match by position: audio[i] pairs with image[i]
    pair_count = min(len(audio_files), len(image_files))
    print(f"\nMatching {pair_count} audio-image pairs by position...")

    for i in range(pair_count):
        audio_info = audio_files[i]
        image_info = image_files[i]
        song_name = audio_info['name']

        if song_name in published:
            print(f"Skipping {song_name} - already published")
            continue

        # Download audio
        Path(LOCAL_AUDIO_DIR).mkdir(parents=True, exist_ok=True)
        audio_path = os.path.join(LOCAL_AUDIO_DIR, audio_info['name'])
        print(f"\nDownloading audio: {audio_info['name']}")
        if not download_file(service, audio_info, audio_path):
            continue

        # Download image
        Path(LOCAL_IMAGE_DIR).mkdir(parents=True, exist_ok=True)
        image_path = os.path.join(LOCAL_IMAGE_DIR, image_info['name'])
        print(f"Downloading image: {image_info['name']}")
        if not download_file(service, image_info, image_path):
            continue

        # Song index is position + 1 (for titles file lookup)
        song_index = i + 1
        print(f"\nSelected pair {song_index}: {song_name}")
        return audio_path, image_path, song_index

    print("\nAll songs have been published.")
    return None


if __name__ == "__main__":
    get_next_unpublished_pair(get_published_songs())
