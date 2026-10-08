"""
Google Drive Integration Module (spyionx)
Fetch audio (MP3) and image files from separate Google Drive folders.
Matches files by sorted position (1st audio = 1st image, etc.)
Supports Weighted Random Repost Mode when all songs have been published once.
"""
import os
import json
import sys
import random
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
ALLOW_REPOST = os.getenv("ALLOW_REPOST", "true").lower() == "true"

PUBLISHED_LOG = "published_songs.json"


def get_published_songs():
    """Get list of already published song names."""
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                return [item.get('song_name', '').strip() for item in data if item.get('song_name')]
            except json.JSONDecodeError:
                return []
    return []


def get_repost_counts():
    """Count how many times each song has been published."""
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                counts = {}
                for item in data:
                    sname = item.get('song_name', '').strip().lower()
                    if sname:
                        counts[sname] = counts.get(sname, 0) + 1
                return counts
            except json.JSONDecodeError:
                return {}
    return {}


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
    If all songs have been published once, uses Weighted Random Repost Selection
    to pair a random song with a random background image so daily publishing never stops.
    """
    service = get_drive_service()
    if not service:
        return None

    audio_files = list_drive_files(service, GOOGLE_DRIVE_AUDIO_FOLDER_ID, ["audio/mpeg"])
    if not audio_files:
        print("No audio files found in Google Drive.")
        return None

    print(f"\nFound {len(audio_files)} audio file(s) in Google Drive.")

    image_files = list_drive_files(service, GOOGLE_DRIVE_IMAGE_FOLDER_ID,
                                   ["image/jpeg", "image/png", "image/webp"])
    if not image_files:
        print("No image files found in Google Drive.")
        return None

    print(f"Found {len(image_files)} image file(s) in Google Drive.")

    # Match by position: audio[i] pairs with image[i]
    pair_count = min(len(audio_files), len(image_files))

    published_lower = [p.lower().strip() for p in published]
    print(f"\nAlready published ({len(published_lower)} songs): {published}")

    # Phase 1: Try finding an unpublished song
    for i in range(pair_count):
        audio_info = audio_files[i]
        image_info = image_files[i]
        song_name = audio_info['name'].strip()

        if song_name.lower() in published_lower:
            print(f"Skipping [{i+1}] {song_name} - already published")
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

        song_index = i + 1
        print(f"\n✅ Selected NEW unpublished pair {song_index}: {song_name} with Image: {image_info['name']}")
        return audio_path, image_path, song_index

    # Phase 2: All songs have been published - REPOST / RECYCLE MODE
    if ALLOW_REPOST:
        print("\n🔄 REPOST MODE: All songs published once. Selecting weighted random song + random image...")
        repost_counts = get_repost_counts()

        # Build weighted choices (songs posted fewer times get higher weight)
        weighted_indices = []
        weights = []
        for i in range(pair_count):
            sname = audio_files[i]['name'].strip().lower()
            count = repost_counts.get(sname, 0)
            weight = max(1, 1000 // (3 ** min(count, 6)))
            weighted_indices.append(i)
            weights.append(weight)

        selected_idx = random.choices(weighted_indices, weights=weights, k=1)[0]

        # Pick random background image from available images
        random_image_info = random.choice(image_files)
        selected_audio_info = audio_files[selected_idx]

        song_name = selected_audio_info['name']
        print(f"  🎲 Selected for repost: Song #{selected_idx + 1} '{song_name}' with Image '{random_image_info['name']}'")

        # Download audio
        Path(LOCAL_AUDIO_DIR).mkdir(parents=True, exist_ok=True)
        audio_path = os.path.join(LOCAL_AUDIO_DIR, selected_audio_info['name'])
        if not download_file(service, selected_audio_info, audio_path):
            return None

        # Download image
        Path(LOCAL_IMAGE_DIR).mkdir(parents=True, exist_ok=True)
        image_path = os.path.join(LOCAL_IMAGE_DIR, random_image_info['name'])
        if not download_file(service, random_image_info, image_path):
            return None

        return audio_path, image_path, selected_idx + 1

    print("\nAll songs have been published (repost disabled).")
    return None


if __name__ == "__main__":
    get_next_unpublished_pair(get_published_songs())
