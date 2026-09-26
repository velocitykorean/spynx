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


def generate_viral_metadata(audio_filename, channel_name="Sypionx"):
    """
    Generates a viral, high-CTR YouTube title, poetic description, and tags
    when a song does not have a manual entry in titles_descriptions.txt.
    """
    base = os.path.splitext(os.path.basename(audio_filename))[0].strip()
    clean_title = re.sub(r'^\s*\d+[\s\.\-_]+', '', base).strip()
    clean_title = clean_title.replace('_', ' ').replace(' - ', ' ').strip()
    # Normalize title case
    clean_title = ' '.join(w.capitalize() for w in clean_title.split())

    viral_title = f"{clean_title} | {channel_name} [Official Audio Visualizer]"

    viral_description = f"""✨ "{clean_title}" — {channel_name}

Some feelings are hard to put into words, but you can feel them through the sound.
A delicate blend of warm melodic emotion, atmospheric textures, and a heartbeat bassline.

🎧 Best experienced with headphones at high volume.

🎵 Track Information:
• Track: {clean_title}
• Artist / Project: {channel_name}
• Visualizer: 60 FPS Audio-Reactive Core
• Genre: Cinematic Emotional Pop / Chill Electronic

⏱️ Chapters:
0:00 - Introduction & Melodic Dawn
0:42 - Heartbeat Bass Pulse
1:35 - Emotional Peak
2:40 - Peaceful Fading Horizon

✨ Join {channel_name}:
Subscribe and tap the notification bell (🔔) to explore nocturnal soundscapes, cinematic beats, and daily audio-reactive visualizers.

#sypionx #music #visualizer #chill #electronic #cinematic #pop #newmusic #aesthetic #60fps"""

    tags = [
        channel_name.lower(),
        clean_title.lower(),
        f"{channel_name.lower()} visualizer",
        "music visualizer",
        "official audio",
        "cinematic pop",
        "chill beats",
        "electronic music",
        "60fps visualizer",
        "aesthetic music",
        "deep bass"
    ]

    return {
        "song_name": clean_title,
        "title": viral_title,
        "description": viral_description,
        "tags": tags,
    }


def match_audio_to_metadata(audio_filename, songs_dict):
    """
    Match an audio filename to a song in the metadata dict.
    Tries exact match, then stripped number match, then partial match.
    """
    audio_name = os.path.splitext(audio_filename)[0].strip()
    clean_audio_name = re.sub(r'^\s*\d+[\s\.\-_]+', '', audio_name).strip()

    for idx, data in songs_dict.items():
        song_name = data['song_name']

        # Exact match (case-insensitive)
        if audio_name.lower() == song_name.lower() or clean_audio_name.lower() == song_name.lower():
            return idx, data

        # Audio name contains song name
        if song_name.lower() in audio_name.lower() or song_name.lower() in clean_audio_name.lower():
            return idx, data

        # Song name contains audio name
        if clean_audio_name.lower() in song_name.lower():
            return idx, data

    return None


def get_song_metadata_by_name(audio_filename, filepath="titles_descriptions.txt", channel_name="Sypionx"):
    """Get title and description for a song based on audio filename, with viral fallback."""
    songs = parse_titles_descriptions(filepath)
    result = match_audio_to_metadata(audio_filename, songs)

    if result:
        idx, metadata = result
        print(f"Matched '{audio_filename}' -> Song {idx}: {metadata['title']}")
        # Ensure song_name is clean
        if 'song_name' not in metadata or not metadata['song_name']:
            metadata['song_name'] = re.sub(r'^\s*\d+[\s\.\-_]+', '', metadata['title'].split('|')[0]).strip()
        return metadata
    else:
        print(f"Notice: No manual entry found for '{audio_filename}'. Generating viral metadata package...")
        return generate_viral_metadata(audio_filename, channel_name=channel_name)


if __name__ == "__main__":
    songs = parse_titles_descriptions()
    for idx, data in sorted(songs.items()):
        print(f"\n{'='*60}")
        print(f"Song {idx:02d}")
        print(f"Name: {data['song_name']}")
        print(f"Title: {data['title']}")
        print(f"Description preview: {data['description'][:100]}...")
