"""
Google Drive Integration Module (spyionx)
Fetch audio (MP3) and image files from separate Google Drive folders.
Matches files by sorted position (1st audio = 1st image, etc.)
Supports Weighted Random Repost Mode when all songs have been published once.
"""
import os
import re
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


def normalize_song_title(filename):
    """
    Extract canonical song title from filename:
    Strips leading track numbers (e.g. '01 - ', '17 - ', '12. ')
    and extensions, punctuation, and extra whitespace.
    Example: '17 - When the World Goes Quiet.mp3' -> 'when the world goes quiet'
    """
    base = os.path.splitext(os.path.basename(filename))[0].strip()
    clean = re.sub(r'^\s*\d+[\s\.\-_]+', '', base).strip()
    clean = clean.replace('_', ' ').replace('-', ' ').strip()
    return re.sub(r'\s+', ' ', clean).lower()


def get_publication_history():
    """
    Reads published_songs.json and returns:
    - title_counts: dict {canonical_title: count}
    - recent_titles: list of canonical titles in chronological publish order
    - published_filenames: set of exact lowercase filenames already published
    """
    title_counts = {}
    recent_titles = []
    published_filenames = set()

    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                for item in data:
                    raw_name = item.get('song_name', '').strip()
                    if not raw_name:
                        continue
                    published_filenames.add(raw_name.lower())
                    canon = normalize_song_title(raw_name)
                    if canon:
                        title_counts[canon] = title_counts.get(canon, 0) + 1
                        recent_titles.append(canon)
            except json.JSONDecodeError:
                pass

    return title_counts, recent_titles, published_filenames


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
    """Count how many times each canonical song title has been published."""
    title_counts, _, _ = get_publication_history()
    return title_counts


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


def get_next_unpublished_pair(published=None):
    """
    Smart Weighted Song Selection & Daily Switching:
    1. Normalizes song titles so duplicate numbered files (e.g. 11 vs 12) share history.
    2. Recency Cooldown: Never selects a song published in the last 5 days.
    3. Weighted Selection:
       - Never-published song titles get highest weight (1000).
       - Songs published 1 time get lower weight (100).
       - Songs published 2+ times get exponentially decaying weight.
       - Exact files already published receive a penalty.
    4. Random weighted sampling switches up songs every day so daily releases stay diverse.
    5. Seamlessly recycles songs once the full library has been published once.
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

    title_counts, recent_titles, published_filenames = get_publication_history()
    print(f"\nPublication history: {len(published_filenames)} upload(s) recorded, {len(title_counts)} unique songs.")

    # Recency Cooldown: exclude songs from recent uploads to prevent back-to-back repeats
    COOLDOWN_SIZE = 5
    cooldown_set = set(recent_titles[-COOLDOWN_SIZE:]) if recent_titles else set()
    if cooldown_set:
        print(f"Recent cooldown (blocked from next upload): {cooldown_set}")

    # Build candidates from available audio files
    all_candidates = []
    for i in range(len(audio_files)):
        raw_name = audio_files[i]['name'].strip()
        canon = normalize_song_title(raw_name)
        cnt = title_counts.get(canon, 0)
        is_exact = raw_name.lower() in published_filenames
        all_candidates.append({
            'index': i,
            'audio_info': audio_files[i],
            'raw_name': raw_name,
            'canon_title': canon,
            'pub_count': cnt,
            'is_exact': is_exact
        })

    # Filter candidates: first try excluding cooldown songs
    eligible = [c for c in all_candidates if c['canon_title'] not in cooldown_set]
    if not eligible:
        print("Notice: Cooldown exhausted all songs, relaxing cooldown filter.")
        eligible = all_candidates

    # Compute weights:
    # 0 previous publications -> 1000
    # 1 previous publication  -> 100
    # 2 previous publications -> 20
    # 3+ publications        -> max(1, 1000 // (3 ** min(count, 6)))
    # Exact file already published gets 10x penalty
    weights = []
    for c in eligible:
        cnt = c['pub_count']
        if cnt == 0:
            w = 1000
        elif cnt == 1:
            w = 100
        elif cnt == 2:
            w = 20
        else:
            w = max(1, 1000 // (3 ** min(cnt, 6)))

        if c['is_exact']:
            w = max(1, w // 10)
        weights.append(w)

    print(f"\nSelecting from {len(eligible)} eligible songs using Weighted Random Switching...")

    # Selection with download retry
    while eligible:
        chosen = random.choices(eligible, weights=weights, k=1)[0]
        chosen_idx = chosen['index']
        audio_info = chosen['audio_info']
        song_name = chosen['raw_name']

        print(f"\n🎲 Selected song [{chosen_idx + 1}]: '{song_name}' (Canon: '{chosen['canon_title']}', Published {chosen['pub_count']}x)")

        # Download audio
        Path(LOCAL_AUDIO_DIR).mkdir(parents=True, exist_ok=True)
        audio_path = os.path.join(LOCAL_AUDIO_DIR, audio_info['name'])
        print(f"Downloading audio: {audio_info['name']}")
        if not download_file(service, audio_info, audio_path):
            idx = eligible.index(chosen)
            eligible.pop(idx)
            weights.pop(idx)
            continue

        # Choose image:
        # If matching position image exists and song is unpublished, use it; otherwise pick random image
        if chosen_idx < len(image_files) and not chosen['is_exact']:
            image_info = image_files[chosen_idx]
        else:
            image_info = random.choice(image_files)

        # Download image
        Path(LOCAL_IMAGE_DIR).mkdir(parents=True, exist_ok=True)
        image_path = os.path.join(LOCAL_IMAGE_DIR, image_info['name'])
        print(f"Downloading image: {image_info['name']}")
        if not download_file(service, image_info, image_path):
            idx = eligible.index(chosen)
            eligible.pop(idx)
            weights.pop(idx)
            continue

        song_index = chosen_idx + 1
        print(f"\n✅ Ready for pipeline: '{song_name}' paired with Image '{image_info['name']}'")
        return audio_path, image_path, song_index

    print("\nFailed to download any candidate song.")
    return None


if __name__ == "__main__":
    get_next_unpublished_pair(get_published_songs())

