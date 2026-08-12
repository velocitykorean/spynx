"""
Titles & Descriptions Parser
Parses the text file containing song titles and descriptions.
Matches songs by index (01-10) to pair with audio files.
"""
import os
import re
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


def parse_titles_descriptions(filepath="titles_descriptions.txt"):
    """
    Parse the titles/descriptions text file.
    Returns a dict: {1: {"title": "...", "description": "..."}, 2: {...}, ...}
    """
    if not os.path.exists(filepath):
        print(f"Error: Titles file not found: {filepath}")
        return {}

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    songs = {}
    # Split by SONG XX markers
    sections = re.split(r'={50,}', content)

    for section in sections:
        section = section.strip()
        if not section:
            continue

        # Find song number
        song_match = re.search(r'SONG\s+(\d+)', section, re.IGNORECASE)
        if not song_match:
            continue

        song_num = int(song_match.group(1))

        # Extract title
        title_match = re.search(r'TITLE:\s*(.+)', section)
        title = title_match.group(1).strip() if title_match else f"Song {song_num:02d}"

        # Extract description
        desc_match = re.search(r'DESCRIPTION:\s*\n([\s\S]+)', section)
        description = desc_match.group(1).strip() if desc_match else ""

        songs[song_num] = {
            "title": title,
            "description": description
        }

    print(f"Parsed {len(songs)} song(s) from titles file")
    return songs


def get_song_metadata(song_index, filepath="titles_descriptions.txt"):
    """Get title and description for a specific song index."""
    songs = parse_titles_descriptions(filepath)
    if song_index in songs:
        return songs[song_index]
    else:
        print(f"Warning: No metadata found for song index {song_index}")
        return {
            "title": f"Song {song_index:02d}",
            "description": "New music release."
        }


if __name__ == "__main__":
    songs = parse_titles_descriptions()
    for idx, data in sorted(songs.items()):
        print(f"\n{'='*60}")
        print(f"Song {idx:02d}")
        print(f"Title: {data['title']}")
        print(f"Description preview: {data['description'][:100]}...")
