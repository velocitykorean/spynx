"""
Titles & Descriptions Parser
Parses the text file containing song titles and descriptions.
Matches songs by name extracted from the title line.
"""
import os
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def parse_titles_descriptions(filepath="titles_descriptions.txt"):
    """
    Parse the titles/descriptions text file.
    Returns a dict keyed by the song name (first part of title before ' | ').
    Example: {"The Shape of Your Absence": {"title": "...", "description": "..."}}
    """
    if not os.path.exists(filepath):
        print(f"Error: Titles file not found: {filepath}")
        return {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    songs = {}
    sections = re.split(r'={50,}', content)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        song_match = re.search(r'SONG\s+(\d+)', section, re.IGNORECASE)
        if not song_match:
            continue

        song_num = int(song_match.group(1))

        title_match = re.search(r'TITLE:\s*(.+)', section)
        title = title_match.group(1).strip() if title_match else f"Song {song_num:02d}"

        desc_match = re.search(r'DESCRIPTION:\s*\n([\s\S]+)', section)
        description = desc_match.group(1).strip() if desc_match else ""

        # Extract song name: part before " | " if present
        song_name = title.split('|')[0].strip() if '|' in title else title

        songs[song_num] = {
            "title": title,
            "description": description,
            "song_name": song_name
        }

    print(f"Parsed {len(songs)} song(s) from titles file")
    return songs


def match_audio_to_metadata(audio_filename, songs_dict):
    """
    Match an audio filename to a song in the metadata dict.
    Tries exact match, then partial match on song name.
    Returns (song_index, metadata) or None.
    """
    # Clean audio filename: remove extension
    audio_name = os.path.splitext(audio_filename)[0].strip()

    for idx, data in songs_dict.items():
        song_name = data['song_name']

        # Exact match (case-insensitive)
        if audio_name.lower() == song_name.lower():
            return idx, data

        # Audio name contains song name
        if song_name.lower() in audio_name.lower():
            return idx, data

        # Song name contains audio name
        if audio_name.lower() in song_name.lower():
            return idx, data

    return None


def get_song_metadata_by_name(audio_filename, filepath="titles_descriptions.txt"):
    """Get title and description for a song based on audio filename."""
    songs = parse_titles_descriptions(filepath)
    result = match_audio_to_metadata(audio_filename, songs)

    if result:
        idx, metadata = result
        print(f"Matched '{audio_filename}' -> Song {idx}: {metadata['title']}")
        return metadata
    else:
        print(f"Warning: No metadata match for '{audio_filename}'")
        return {
            "title": os.path.splitext(audio_filename)[0],
            "description": "New music release."
        }


if __name__ == "__main__":
    songs = parse_titles_descriptions()
    for idx, data in sorted(songs.items()):
        print(f"\n{'='*60}")
        print(f"Song {idx:02d}")
        print(f"Name: {data['song_name']}")
        print(f"Title: {data['title']}")
        print(f"Description preview: {data['description'][:100]}...")
