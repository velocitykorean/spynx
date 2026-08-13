"""
Video Processor - High Aesthetic Video Generator
Combines image + audio (MP3) into professional YouTube music videos with:
1. Ultra-Bold & Smooth Dead-Centered Song Title Card (Golden Fire Glow)
2. Ambient Floating Dust/Particle Overlays (Tiny, ultra-slow floating specks)
3. Golden Fire Left-to-Right Equalizers (Golden Glow / Fire Waveform)
4. Dynamic .env Configuration & Force Re-generation
5. Pure Original Color preservation (Vignette disabled by default)
6. Matching Thumbnail Generator (Always updated)
"""
import os
import subprocess
import sys
import math
from pathlib import Path
from PIL import Image
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

LOCAL_OUTPUT_DIR = os.getenv("LOCAL_OUTPUT_DIR", "Processed_Videos")
OVERLAY_PRESET = os.getenv("OVERLAY_PRESET", "modern_glass")
EQUALIZER_STYLE = os.getenv("EQUALIZER_STYLE", "golden_fire_wave").lower()
BG_MOTION = os.getenv("BG_MOTION", "static")
ENABLE_PARTICLES = os.getenv("ENABLE_PARTICLES", "true").lower() == "true"
ENABLE_AUDIO_WAVE = os.getenv("ENABLE_AUDIO_WAVE", "true").lower() == "true"
ENABLE_VIGNETTE = os.getenv("ENABLE_VIGNETTE", "false").lower() == "true"
CHANNEL_NAME = os.getenv("CHANNEL_NAME", "SPYNX MUSIC")


def get_audio_duration(audio_path):
    """Retrieve audio duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        audio_path
    ]
    try:
        return float(subprocess.check_output(cmd).decode("utf-8").strip())
    except Exception as e:
        print(f"[VideoProcessor] Failed to get audio duration: {e}")
        return None


def create_text_overlay_image(song_name, output_path, width=1920, height=1080, preset=OVERLAY_PRESET):
    """Create typography overlay image using PIL."""
    from create_text_overlay import create_stretched_text_image
    return create_stretched_text_image(song_name, output_path, width, height,
                                        preset=preset, channel_name=CHANNEL_NAME)


def get_equalizer_filter(style=EQUALIZER_STYLE):
    """
    Returns (filter_str, overlay_pos_str) for the chosen equalizer style.
    """
    if style in ["ncs_circle_green", "ncs_green"]:
        # Iconic NCS Glowing Neon Green Circle Equalizer Ring
        fstr = "[1:a]avectorscope=s=550x550:m=polar:rc=0:gc=255:bc=30:rf=0:gf=255:bf=30:zoom=1.5,format=rgba[wave]"
        pos = "overlay=1050:H/2-275:format=auto"
    elif style in ["ncs_circle_gold", "ncs_gold"]:
        # Iconic NCS Glowing Golden Fire Circle Equalizer Ring
        fstr = "[1:a]avectorscope=s=550x550:m=polar:rc=255:gc=180:bc=20:rf=255:gf=180:bf=20:zoom=1.5,format=rgba[wave]"
        pos = "overlay=1050:H/2-275:format=auto"
    elif style in ["golden_fire_bars", "golden_bars", "spectrum_bars"]:
        # Golden Fire Graphic Equalizer Bars (1920px Left to Right)
        fstr = "[1:a]showfreqs=s=1920x105:mode=bar:cmode=combined:ascale=log:fscale=log:colors=0xffb300@0.85:win_func=hanning,format=rgba[wave]"
        pos = "overlay=0:H-130:format=auto"
    elif style in ["golden_cqt", "musical_cqt"]:
        # Golden Fire Musical Note Spectrum (1920px Left to Right)
        fstr = "[1:a]showcqt=s=1920x120:bar_g=2:timeclamp=0.1:tc=0xFFB300@0.85:axis=0,format=rgba[wave]"
        pos = "overlay=0:H-140:format=auto"
    elif style in ["golden_vector_orb", "vector_circle"]:
        # Golden Fire Circular Pulsing Stereo Vector Scope Orb
        fstr = "[1:a]avectorscope=s=220x220:m=polar:rc=255:gc=170:bc=30,format=rgba[wave]"
        pos = "overlay=850:H-240:format=auto"
    elif style in ["cyan_wave"]:
        # Cyan Waveform Line (Left to Right)
        fstr = "[1:a]showwaves=s=1920x120:mode=line:colors=0x00e5ff@0.85,format=rgba[wave]"
        pos = "overlay=0:H-140:format=auto"
    elif style in ["white_bars"]:
        # Crisp White Equalizer Bars (Left to Right)
        fstr = "[1:a]showfreqs=s=1920x100:mode=bar:cmode=combined:ascale=log:fscale=log:colors=0xffffff@0.85:win_func=hanning,format=rgba[wave]"
        pos = "overlay=0:H-125:format=auto"
    else:
        # Default: Golden Fire Full-Width Waveform Line (1920px Left to Right across bottom!)
        fstr = "[1:a]showwaves=s=1920x120:mode=line:colors=0xffb300@0.85,format=rgba[wave]"
        pos = "overlay=0:H-140:format=auto"

    return fstr, pos


def create_video_with_effects(image_path, audio_path, output_path, song_name,
                                target_width=1920, target_height=1080,
                                preset=OVERLAY_PRESET, eq_style=EQUALIZER_STYLE,
                                bg_motion=BG_MOTION, particles=ENABLE_PARTICLES,
                                audio_wave=ENABLE_AUDIO_WAVE, vignette=ENABLE_VIGNETTE):
    """
    Create a video with smooth centered song title card & Golden Fire equalizer.
    """
    preset = os.getenv("OVERLAY_PRESET", preset)
    eq_style = os.getenv("EQUALIZER_STYLE", eq_style)
    bg_motion = os.getenv("BG_MOTION", bg_motion)
    particles = os.getenv("ENABLE_PARTICLES", "true").lower() == "true"
    audio_wave = os.getenv("ENABLE_AUDIO_WAVE", "true").lower() == "true"
    vignette = os.getenv("ENABLE_VIGNETTE", "false").lower() == "true"

    if not os.path.exists(image_path):
        print(f"[VideoProcessor] Error: Image not found: {image_path}")
        return None

    if not os.path.exists(audio_path):
        print(f"[VideoProcessor] Error: Audio not found: {audio_path}")
        return None

    duration = get_audio_duration(audio_path)
    if not duration:
        return None

    print(f"[VideoProcessor] Audio duration: {duration:.2f}s")

    # Ensure output directory exists
    Path(LOCAL_OUTPUT_DIR).mkdir(parents=True, exist_ok=True)

    # Step 1: Create centered text overlay PNG with song title
    text_overlay_path = os.path.join(LOCAL_OUTPUT_DIR, "text_overlay.png")
    create_text_overlay_image(song_name, text_overlay_path, target_width, target_height, preset=preset)

    # Step 2: Prepare particle loop if enabled
    particle_mp4 = None
    if particles:
        try:
            from particle_overlay import generate_particle_loop_video
            particle_mp4 = os.path.join(LOCAL_OUTPUT_DIR, "particles_loop.mp4")
            generate_particle_loop_video(particle_mp4, width=target_width, height=target_height)
        except Exception as e:
            print(f"[VideoProcessor] Particle generation failed ({e}), continuing without particles.")
            particles = False

    fps = 30
    total_frames = int(duration * fps)

    print(f"[VideoProcessor] Rendering Viral Music Video ({target_width}x{target_height})")
    print(f"  - Song Title: '{song_name}' (Position: DEAD CENTER, Wide & Smooth)")
    print(f"  - Preset: {preset}")
    print(f"  - Equalizer: {eq_style} (Golden Fire Glow, Full-Width Left to Right)")
    print(f"  - Motion: {bg_motion}")
    print(f"  - Ambient Specks: {particles}")
    print(f"  - Vignette: {vignette} (False = Original pure image colors)")

    # Build FFmpeg command inputs
    inputs = ["-loop", "1", "-i", image_path]  # Stream 0: Image
    inputs.extend(["-i", audio_path])           # Stream 1: Audio
    next_input_idx = 2

    filter_chains = []
    current_v = "[0:v]"

    # Scale/Crop base image to target dimensions
    filter_chains.append(f"{current_v}scale={target_width}:{target_height}:force_original_aspect_ratio=increase,crop={target_width}:{target_height}[scaled]")
    current_v = "[scaled]"

    # Background Motion Filter
    if bg_motion == "ken_burns":
        zoom_expr = f"if(eq(on,1),1.0,1.0+0.12*on/{total_frames})"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
        filter_chains.append(f"{current_v}zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s={target_width}x{target_height}:fps={fps}[motion]")
        current_v = "[motion]"
    elif bg_motion == "breathing":
        zoom_expr = f"1.015+0.015*sin(on*0.05)"
        x_expr = "iw/2-(iw/zoom/2)"
        y_expr = "ih/2-(ih/zoom/2)"
        filter_chains.append(f"{current_v}zoompan=z='{zoom_expr}':x='{x_expr}':y='{y_expr}':d={total_frames}:s={target_width}x{target_height}:fps={fps}[motion]")
        current_v = "[motion]"

    # Optional Vignette
    if vignette:
        filter_chains.append(f"{current_v}vignette=PI/5[vignetted]")
        current_v = "[vignetted]"

    # Ambient Particles Screen Blend
    if particles and particle_mp4 and os.path.exists(particle_mp4):
        particle_idx = next_input_idx
        inputs.extend(["-stream_loop", "-1", "-i", particle_mp4])
        next_input_idx += 1
        filter_chains.append(f"[{particle_idx}:v]scale={target_width}:{target_height}[part_scaled]")
        filter_chains.append(f"{current_v}[part_scaled]blend=all_mode='screen':all_opacity=0.60[part_blended]")
        current_v = "[part_blended]"

    # Full-Width Left-to-Right Golden Fire Equalizer Filter Chain
    if audio_wave:
        fstr, pos = get_equalizer_filter(eq_style)
        filter_chains.append(fstr)
        filter_chains.append(f"{current_v}[wave]{pos}[waved]")
        current_v = "[waved]"

    # Centered Song Title Text Overlay with smooth fade in/out
    text_idx = next_input_idx
    inputs.extend(["-loop", "1", "-i", text_overlay_path])
    next_input_idx += 1


    fade_in = 1.5
    fade_out_st = max(0, duration - 2.5)
    filter_chains.append(f"[{text_idx}:v]format=rgba,fade=t=in:st=0:d={fade_in}:alpha=1,fade=t=out:st={fade_out_st}:d=2.5:alpha=1[txt]")
    filter_chains.append(f"{current_v}[txt]overlay=0:0:format=auto[final_v]")

    filter_complex_str = ";".join(filter_chains)

    cmd = ["ffmpeg", "-y"] + inputs + [
        "-filter_complex", filter_complex_str,
        "-map", "[final_v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-movflags", "+faststart",
        output_path
    ]

    print("[VideoProcessor] Rendering video with FFmpeg...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0 and os.path.exists(output_path):
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[VideoProcessor] Video created successfully: {output_path} ({size_mb:.1f} MB)")
        return output_path
    else:
        print(f"[VideoProcessor] FFmpeg video rendering failed (code {result.returncode})")
        if result.stderr:
            for line in result.stderr.strip().split('\n')[-6:]:
                print(f"  FFmpeg: {line}")
        return None


def generate_thumbnail(image_path, audio_path, output_thumb_path, song_name,
                        target_width=1920, target_height=1080, preset=OVERLAY_PRESET):
    """
    Generate a high-aesthetic YouTube thumbnail with bold glowing song title.
    """
    if not os.path.exists(image_path):
        print(f"[VideoProcessor] Error: Image not found: {image_path}")
        return None

    print(f"[VideoProcessor] Generating high-impact thumbnail for song '{song_name}'...")

    # Step 1: Create centered text overlay image
    text_overlay_path = os.path.join(LOCAL_OUTPUT_DIR, "text_overlay_thumb.png")
    create_text_overlay_image(song_name, text_overlay_path, target_width, target_height, preset=preset)

    # Step 2: Load base background image
    try:
        bg = Image.open(image_path).convert('RGBA')

        bg_w, bg_h = bg.size
        target_ratio = target_width / target_height
        bg_ratio = bg_w / bg_h

        if bg_ratio > target_ratio:
            new_w = int(bg_h * target_ratio)
            left = (bg_w - new_w) // 2
            bg = bg.crop((left, 0, left + new_w, bg_h))
        else:
            new_h = int(bg_w / target_ratio)
            top = (bg_h - new_h) // 2
            bg = bg.crop((0, top, bg_w, top + new_h))

        bg = bg.resize((target_width, target_height), Image.LANCZOS)

        # Composite centered text overlay onto background
        txt = Image.open(text_overlay_path).convert('RGBA')
        result_img = Image.alpha_composite(bg, txt)
        result_img = result_img.convert('RGB')
        result_img.save(output_thumb_path, 'JPEG', quality=98)

        # Cleanup temp
        if os.path.exists(text_overlay_path):
            os.remove(text_overlay_path)

        if os.path.exists(output_thumb_path):
            size_kb = os.path.getsize(output_thumb_path) / 1024
            print(f"[VideoProcessor] Thumbnail created: {output_thumb_path} ({size_kb:.0f} KB)")
            return output_thumb_path
    except Exception as e:
        print(f"[VideoProcessor] Thumbnail generation error: {e}")
        return None


def process_single_song(image_path, audio_path, song_filename, display_name=None, force_rebuild=True):
    """
    Process a single song: create video + thumbnail.
    force_rebuild: Always regenerate thumbnail & video if requested.
    """
    safe_name = os.path.splitext(song_filename)[0]
    safe_name = "".join(c for c in safe_name if c.isalnum() or c in (' ', '-', '_')).strip()
    if not safe_name:
        safe_name = "output"

    text_name = display_name if display_name else safe_name

    # Create video
    output_filename = f"{safe_name}.mp4"
    output_path = os.path.join(LOCAL_OUTPUT_DIR, output_filename)

    if os.path.exists(output_path) and not force_rebuild:
        print(f"[VideoProcessor] Skipping {output_filename} - already processed")
    else:
        if os.path.exists(output_path):
            os.remove(output_path)
        result = create_video_with_effects(image_path, audio_path, output_path, text_name)
        if not result:
            return None

    # ALWAYS Create/Update thumbnail with song title
    thumb_filename = f"{safe_name}_thumb.jpg"
    thumb_path = os.path.join(LOCAL_OUTPUT_DIR, thumb_filename)
    generate_thumbnail(image_path, audio_path, thumb_path, text_name)

    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python process_videos.py <image_path> <audio_path> <song_name>")
        sys.exit(1)

    image = sys.argv[1]
    audio = sys.argv[2]
    name = sys.argv[3]
    result = process_single_song(image, audio, name, display_name=name, force_rebuild=True)
    if result:
        print(f"\n[VideoProcessor] Processing complete: {result}")
        sys.exit(0)
    else:
        print("\n[VideoProcessor] Processing failed!")
        sys.exit(1)
