"""
Video Processor
Combines a static image + audio (MP3) into a YouTube video.
1. Gets audio duration
2. Creates video from image + audio using FFmpeg
3. Outputs 1080x1080 (square) or 1920x1080 MP4
"""
import os
import subprocess
import sys
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

LOCAL_OUTPUT_DIR = os.getenv("LOCAL_OUTPUT_DIR", "Processed_Videos")


def get_audio_duration(audio_path):
    """Get the duration of an audio file in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        duration = float(subprocess.check_output(cmd).decode("utf-8").strip())
        return duration
    except Exception as e:
        print(f"Failed to get audio duration: {e}")
        return None


def get_image_dimensions(image_path):
    """Get image width and height."""
    try:
        from PIL import Image
        with Image.open(image_path) as img:
            return img.width, img.height
    except Exception as e:
        print(f"Failed to get image dimensions: {e}")
        return None, None


def create_video_from_image_audio(image_path, audio_path, output_path, target_width=1920, target_height=1080):
    """
    Create a video from a static image and audio file.
    The image is displayed for the full duration of the audio.
    """
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        return None

    if not os.path.exists(audio_path):
        print(f"Error: Audio not found: {audio_path}")
        return None

    # Get audio duration
    duration = get_audio_duration(audio_path)
    if not duration:
        print("Failed to get audio duration")
        return None

    print(f"Audio duration: {duration:.2f}s")

    # Get image dimensions
    img_w, img_h = get_image_dimensions(image_path)
    if img_w and img_h:
        print(f"Image dimensions: {img_w}x{img_h}")

    # Ensure output directory exists
    Path(LOCAL_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Build FFmpeg command
    # Scale image to target resolution, loop for audio duration
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]

    print(f"Creating video: {target_width}x{target_height}")
    print(f"Output: {output_path}")

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        # Verify output exists
        if os.path.exists(output_path):
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            print(f"Video created: {output_path} ({size_mb:.1f} MB)")
            return output_path
        else:
            print("FFmpeg reported success but output file not found")
            return None
    else:
        print(f"FFmpeg failed with return code {result.returncode}")
        print(f"Error: {result.stderr}")
        return None


def process_single_song(image_path, audio_path, song_name):
    """Process a single song: combine image + audio into video."""
    # Clean filename for output
    safe_name = os.path.splitext(song_name)[0]
    # Remove characters not safe for filenames
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_name:
        safe_name = "output"

    output_filename = f"{safe_name}.mp4"
    output_path = os.path.join(LOCAL_OUTPUT_DIR, output_filename)

    if os.path.exists(output_path):
        print(f"Skipping {output_filename} - already processed")
        return output_path

    return create_video_from_image_audio(image_path, audio_path, output_path)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python process_videos.py <image_path> <audio_path>")
        sys.exit(1)

    image = sys.argv[1]
    audio = sys.argv[2]
    result = process_single_song(image, audio, os.path.basename(audio))
    if result:
        print(f"\nProcessing complete: {result}")
    else:
        print("\nProcessing failed!")
        sys.exit(1)
