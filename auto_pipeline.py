"""
Main Automation Pipeline
1. Fetch NEXT unpublished audio + image pair from Google Drive
2. Parse title/description from text file
3. Combine image + audio into video (FFmpeg)
4. Upload to YouTube with correct metadata
"""
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

PUBLISHED_LOG = "published_songs.json"
TITLES_FILE = "titles_descriptions.txt"


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


def mark_as_published(song_name, metadata):
    """Record a song as published."""
    published = get_published_songs()
    if os.path.exists(PUBLISHED_LOG):
        with open(PUBLISHED_LOG, 'r', encoding='utf-8') as f:
            try:
                history = json.load(f)
            except json.JSONDecodeError:
                history = []
    else:
        history = []

    history.append({
        "song_name": song_name,
        "metadata": metadata
    })

    with open(PUBLISHED_LOG, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4)


def run_pipeline():
    """
    Complete automation pipeline:
    Google Drive (audio + image) → Combine into video → Upload to YouTube
    """
    print("\n" + "=" * 60)
    print("SPYNX YOUTUBE AUTOMATION PIPELINE")
    print("=" * 60 + "\n")

    # Step 1: Fetch next unpublished audio + image from Google Drive
    print("STEP 1: Fetching audio + image from Google Drive...")
    from google_drive_fetch import get_next_unpublished_pair

    published = get_published_songs()
    pair = get_next_unpublished_pair(published)

    if not pair:
        print("\nNo unpublished songs available. Pipeline complete.")
        return

    audio_path, image_path, song_index = pair
    print(f"\nStep 1 complete: Audio={audio_path}, Image={image_path}, Index={song_index}")

    # Step 2: Get title/description from text file
    print("\nSTEP 2: Loading title and description...")
    from titles_descriptions_parser import get_song_metadata

    metadata = get_song_metadata(song_index, TITLES_FILE)
    title = metadata['title']
    description = metadata['description']

    print(f"Title: {title}")
    print(f"Description preview: {description[:120]}...")

    # Step 3: Combine image + audio into video
    print("\nSTEP 3: Creating video from image + audio...")
    from process_videos import process_single_song

    song_name = os.path.basename(audio_path)
    video_path = process_single_song(image_path, audio_path, song_name)

    if not video_path or not os.path.exists(video_path):
        print("\nVideo creation failed!")
        sys.exit(1)

    print(f"\nStep 3 complete: Video created at {video_path}")

    # Step 4: Upload to YouTube
    print("\nSTEP 4: Uploading to YouTube...")
    from publish_youtube import upload_to_youtube

    tags = ['music', 'song', 'cinematic', 'emotional', 'pop', 'newmusic',
            'femalevocals', 'piano', 'dreamy', 'romantic']

    try:
        result = upload_to_youtube(video_path, title, description, tags=tags, category_id='10')
        upload_success = True
    except Exception as e:
        print(f"YouTube upload failed: {e}")
        upload_success = False

    # Step 5: Record as published
    print("\nSTEP 5: Recording song as published...")
    mark_as_published(song_name, {
        "title": title,
        "description": description,
        "song_index": song_index,
        "uploaded": upload_success
    })

    # Move published video to archive
    published_dir = "Published_Videos"
    Path(published_dir).mkdir(parents=True, exist_ok=True)

    try:
        import shutil
        dest_path = os.path.join(published_dir, os.path.basename(video_path))
        shutil.move(video_path, dest_path)
        print(f"Moved video to {dest_path}")
    except Exception as e:
        print(f"Failed to move video: {e}")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    run_pipeline()
