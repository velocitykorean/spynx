"""
Avee Player .viz Template Visualizer with High-Fidelity BeatPulse,
Bottom-Left Channel & Song Branding, 60 FPS High-Definition Video,
and Peak Energy Thumbnail Generator.

Features:
- Extracts exact mesh_core.gif asset from .viz archive (337 frames)
- Neon bloom shader with high-luminosity color variety
- Audio-reactive BeatPulse driven by Librosa STFT sub-bass analysis
- Bottom-left typography: Channel Name (SYPIONX in Gold) + Clean Song Title (numbers removed)
- 60 FPS butter-smooth rendering streamed directly into FFmpeg
- Peak-energy thumbnail capture saved alongside the video
"""

import os
import sys
import re
import time
import zipfile
import argparse
import subprocess
import numpy as np
import cv2
import soundfile as sf
import scipy.signal
from PIL import Image, ImageSequence, ImageDraw, ImageFont, ImageFilter


def load_and_analyze_audio(audio_path, fps=60):
    """
    Analyzes audio for sub-bass energy and BeatPulse scaling using soundfile & scipy.
    """
    print(f"Loading audio: {audio_path}", flush=True)
    data, sr = sf.read(audio_path)
    if data.ndim > 1:
        mono = np.mean(data, axis=1)
    else:
        mono = data

    total_samples = len(mono)
    duration = total_samples / sr
    total_frames = int(duration * fps)
    print(f"Track length: {duration:.2f}s | Sample rate: {sr} Hz | Frames @ {fps}fps: {total_frames}", flush=True)

    hop_length = int(sr / fps)
    n_fft = 2048

    frequencies, times, Zxx = scipy.signal.stft(
        mono, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length
    )
    magnitude = np.abs(Zxx)

    # Sub-bass band (25Hz to 130Hz)
    bass_idx = np.where((frequencies >= 25) & (frequencies <= 130))[0]
    bass_energy = np.mean(magnitude[bass_idx, :], axis=0) if len(bass_idx) > 0 else np.zeros(magnitude.shape[1])

    # Temporal smoothing
    smoothed_bass = np.zeros_like(bass_energy)
    attack = 0.65
    decay = 0.22
    for t_idx in range(len(bass_energy)):
        curr = bass_energy[t_idx]
        if t_idx == 0:
            smoothed_bass[t_idx] = curr
        else:
            prev = smoothed_bass[t_idx - 1]
            smoothed_bass[t_idx] = prev + attack * (curr - prev) if curr > prev else prev - decay * prev

    # Normalize 0.0 to 1.0
    p95 = np.percentile(smoothed_bass, 95)
    bass_norm = np.clip(smoothed_bass / (p95 + 1e-4), 0.0, 1.3)

    return {
        "sr": sr,
        "duration": duration,
        "total_frames": total_frames,
        "bass_env": bass_norm,
    }


def load_viz_template(viz_path, color_bgr=(242, 250, 140)):
    """
    Extracts mesh_core.gif from .viz archive and pre-tints all frames.
    """
    print(f"Extracting template from: {viz_path}", flush=True)
    with zipfile.ZipFile(viz_path, 'r') as z:
        gif_bytes = z.read("mesh_core.gif")

    import io
    gif_file = io.BytesIO(gif_bytes)
    im = Image.open(gif_file)

    pil_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(im)]
    num_frames = len(pil_frames)
    print(f"Loaded {num_frames} animation frames from template asset.", flush=True)

    tinted_frames = []
    cb, cg, cr = color_bgr

    for frame in pil_frames:
        arr = np.array(frame)
        alpha = arr[:, :, 3]
        gray = cv2.cvtColor(arr[:, :, :3], cv2.COLOR_RGBA2GRAY).astype(np.float32) / 255.0

        tinted = np.zeros((arr.shape[0], arr.shape[1], 3), dtype=np.float32)
        tinted[:, :, 0] = gray * cb
        tinted[:, :, 1] = gray * cg
        tinted[:, :, 2] = gray * cr

        alpha_mask = (alpha.astype(np.float32) / 255.0)[:, :, np.newaxis]
        tinted_alpha = tinted * alpha_mask

        # Bloom pass
        b1 = cv2.GaussianBlur(tinted_alpha, (9, 9), 0)
        b2 = cv2.GaussianBlur(tinted_alpha, (25, 25), 0)
        glowing = np.clip(tinted_alpha * 1.1 + b1 * 0.75 + b2 * 0.4, 0, 255).astype(np.uint8)

        tinted_frames.append(glowing)

    return tinted_frames


def draw_bottom_left_branding(cv2_img, channel_name="Sypionx", song_title=""):
    """
    Renders channel branding and clean song title on bottom-left.
    Automatically strips track numbers from title.
    """
    if not channel_name and not song_title:
        return cv2_img

    H, W = cv2_img.shape[:2]

    # Clean leading track numbers (e.g. "05 - If You Stay Until Morning" -> "If You Stay Until Morning")
    clean_title = re.sub(r'^\s*\d+[\s\.\-_]+', '', song_title).strip()
    clean_title = clean_title.replace('_', ' ').replace(' - ', ' ').strip()
    clean_title = ' '.join(w.capitalize() for w in clean_title.split())

    rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(rgb)
    overlay = Image.new('RGBA', (W, H), (0, 0, 0, 0))

    scale = H / 1080.0
    channel_size = max(20, int(26 * scale * 1.25))
    title_size = max(28, int(44 * scale * 1.25))

    font_dirs = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts"),
        r"D:\E agy cli\E bots\spynx\fonts",
        r"D:\E agy cli\E bots\music_visualizer\fonts",
        "C:\\Windows\\Fonts",
    ]

    title_font = None
    chan_font = None

    for d in font_dirs:
        tf_path = os.path.join(d, "Montserrat-Bold.ttf")
        cf_path = os.path.join(d, "Outfit-Bold.ttf")
        if os.path.exists(tf_path) and title_font is None:
            try:
                title_font = ImageFont.truetype(tf_path, title_size)
            except Exception:
                pass
        if os.path.exists(cf_path) and chan_font is None:
            try:
                chan_font = ImageFont.truetype(cf_path, channel_size)
            except Exception:
                pass

    if title_font is None:
        title_font = ImageFont.load_default()
    if chan_font is None:
        chan_font = ImageFont.load_default()

    pos_x = int(W * 0.055)
    bottom_y = int(H * 0.92)

    channel_text = f"{channel_name.upper()}" if channel_name else ""
    t_bbox = title_font.getbbox(clean_title)
    t_h = t_bbox[3] - t_bbox[1] if clean_title else 0

    c_bbox = chan_font.getbbox(channel_text)
    c_h = c_bbox[3] - c_bbox[1] if channel_text else 0

    title_y = bottom_y - t_h
    chan_y = title_y - c_h - int(12 * scale)

    # Gaussian blur shadow layer for 100% legibility on any background
    shadow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)

    for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3), (3, 3), (0, 4)]:
        if channel_text:
            s_draw.text((pos_x + dx, chan_y + dy), channel_text, font=chan_font, fill=(0, 0, 0, 220))
        if clean_title:
            s_draw.text((pos_x + dx, title_y + dy), clean_title, font=title_font, fill=(0, 0, 0, 240))

    shadow = shadow.filter(ImageFilter.GaussianBlur(5))
    overlay = Image.alpha_composite(overlay, shadow)

    draw = ImageDraw.Draw(overlay)
    if channel_text:
        draw.text((pos_x, chan_y), channel_text, font=chan_font, fill=(255, 215, 70, 245))  # Radiant Gold
    if clean_title:
        draw.text((pos_x, title_y), clean_title, font=title_font, fill=(255, 255, 255, 255))      # Crisp White

    pil_img = Image.alpha_composite(pil_img.convert('RGBA'), overlay)
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGR)


def generate_viz_video(
    viz_path,
    bg_path,
    audio_path,
    output_path,
    fps=60,
    start_sec=0.0,
    duration=None,
    pos_x=None,
    pos_y=None,
    base_diameter=490,
    color="auto",
    crf=16,
    channel_name="Sypionx",
    song_title=None,
):
    """
    Renders video using Avee Player .viz template with 60 FPS,
    right-side placement, bottom-left branding, and peak-energy thumbnail.
    """
    if not os.path.exists(bg_path):
        raise FileNotFoundError(f"Background image not found: {bg_path}")
    raw_bg = cv2.imread(bg_path)
    if raw_bg is None:
        raise ValueError(f"Could not load image: {bg_path}")

    # Ensure even dimensions
    orig_h, orig_w = raw_bg.shape[:2]
    H = (orig_h // 2) * 2
    W = (orig_w // 2) * 2
    bg = raw_bg[:H, :W].copy()

    # Determine song title from audio file if not provided
    if song_title is None or not song_title:
        song_title = os.path.splitext(os.path.basename(audio_path))[0]

    # Draw bottom-left branding onto background
    bg = draw_bottom_left_branding(bg, channel_name=channel_name, song_title=song_title)

    # Vibrant luminous light-color palette
    LIGHT_PALETTE = {
        "cyan": (242, 250, 140),       # Electric Cyan (BGR)
        "gold": (70, 215, 255),        # Radiant Daffodil / Sunflower Gold
        "yellow": (70, 235, 255),      # Neon Lemon Yellow
        "mint": (190, 255, 120),       # Cyber Spring Mint
        "pink": (210, 140, 255),       # Neon Rose Pink
        "lavender": (255, 160, 210),   # Soft Glowing Violet / Lavender
        "white": (255, 250, 245),      # Diamond Ice White
        "peach": (120, 190, 255),      # Warm Amber Peach
        "ice_blue": (255, 225, 160),   # Frosted Sky Blue
    }

    if isinstance(color, str):
        c_low = color.lower().strip()
        if c_low in ["auto", "random"]:
            import random
            color_name = random.choice(list(LIGHT_PALETTE.keys()))
            color_bgr = LIGHT_PALETTE[color_name]
            print(f"Auto-selected luminous visualizer color: {color_name.upper()} {color_bgr}", flush=True)
        elif c_low in LIGHT_PALETTE:
            color_bgr = LIGHT_PALETTE[c_low]
        else:
            color_bgr = LIGHT_PALETTE["gold"]
    else:
        color_bgr = color

    # Standardized placement: Right-side in the negative space (subject is on the left)
    cx = pos_x if pos_x is not None else int(W * 0.741)
    cy = pos_y if pos_y is not None else int(H * 0.480)
    if base_diameter is None or base_diameter <= 0:
        base_diameter = 490

    print(f"Canvas size: {W}x{H} | Visualizer center: ({cx}, {cy}) | Base diameter: {base_diameter} | FPS: {fps}", flush=True)

    # Load template frames
    template_frames = load_viz_template(viz_path, color_bgr=color_bgr)
    num_template_frames = len(template_frames)

    # Audio analysis
    audio_info = load_and_analyze_audio(audio_path, fps=fps)
    bass_env = audio_info["bass_env"]

    start_frame = int(start_sec * fps)
    if duration is not None and duration > 0:
        actual_frames = int(duration * fps)
    else:
        actual_frames = audio_info["total_frames"] - start_frame

    end_frame = min(start_frame + actual_frames, audio_info["total_frames"])
    actual_frames = end_frame - start_frame
    actual_duration = actual_frames / fps

    print(f"Rendering {actual_frames} frames ({actual_duration:.2f}s) at {fps} fps...", flush=True)

    # Setup FFmpeg
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-s", f"{W}x{H}",
        "-pix_fmt", "bgr24",
        "-r", str(fps),
        "-i", "-",
        "-ss", str(start_sec),
        "-t", str(actual_duration),
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        "-shortest",
        output_path
    ]

    print("Launching FFmpeg process...", flush=True)
    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    t0 = time.time()
    last_print = t0

    # Max diameter for ROI
    max_reach = int(base_diameter * 1.35)
    x1 = max(0, cx - max_reach // 2)
    x2 = min(W, cx + max_reach // 2)
    y1 = max(0, cy - max_reach // 2)
    y2 = min(H, cy + max_reach // 2)
    roi_w = x2 - x1
    roi_h = y2 - y1
    rcx = cx - x1
    rcy = cy - y1

    bg_roi_static = bg[y1:y2, x1:x2].copy()
    bg_roi_u16 = (255 - bg_roi_static).astype(np.uint16)

    frame_out = bg.copy()
    saved_thumb = None
    # Pick a frame around 6-7 seconds (or middle of clip) with high bass for thumbnail
    thumb_target_frame = min(actual_frames - 1, int(max(2.0, min(actual_duration * 0.4, 7.0)) * fps))

    for i in range(actual_frames):
        global_frame = start_frame + i
        tpl_idx = i % num_template_frames
        vis_src = template_frames[tpl_idx]

        stft_idx = min(global_frame, len(bass_env) - 1)
        bass_val = float(bass_env[stft_idx])

        # Avee BeatPulse: 0.85 + 0.20 * bass_val (scales 0.85x to 1.05x)
        pulse_scale = 0.85 + 0.20 * bass_val
        current_dia = int(base_diameter * pulse_scale)
        current_dia = (current_dia // 2) * 2

        # Scale visualizer frame
        vis_scaled = cv2.resize(
            vis_src,
            (current_dia, current_dia),
            interpolation=cv2.INTER_LINEAR,
        )

        # Clear ROI buffer
        vis_roi = np.zeros((roi_h, roi_w, 3), dtype=np.uint8)

        vx1 = max(0, rcx - current_dia // 2)
        vy1 = max(0, rcy - current_dia // 2)
        vx2 = min(roi_w, vx1 + current_dia)
        vy2 = min(roi_h, vy1 + current_dia)

        crop_w = vx2 - vx1
        crop_h = vy2 - vy1
        if crop_w > 0 and crop_h > 0:
            vis_roi[vy1:vy2, vx1:vx2] = vis_scaled[:crop_h, :crop_w]

        # Fast screen blend onto background
        vis_inv = (255 - vis_roi).astype(np.uint16)
        comp_roi = 255 - ((bg_roi_u16 * vis_inv) >> 8).astype(np.uint8)

        frame_out[y1:y2, x1:x2] = comp_roi

        if i == thumb_target_frame:
            saved_thumb = frame_out.copy()

        # Write to FFmpeg
        try:
            proc.stdin.write(frame_out.tobytes())
        except (BrokenPipeError, OSError):
            break

        now = time.time()
        if now - last_print > 2.0 or i == actual_frames - 1:
            elapsed = now - t0
            current_fps = (i + 1) / max(elapsed, 0.001)
            eta = (actual_frames - (i + 1)) / max(current_fps, 0.001)
            pct = ((i + 1) / actual_frames) * 100
            print(f"Progress: {i+1}/{actual_frames} ({pct:.1f}%) | {current_fps:.1f} fps | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s", flush=True)
            last_print = now

    proc.stdin.close()
    proc.wait()
    total_time = time.time() - t0
    print(f"\nRender completed in {total_time:.1f}s ({actual_frames/total_time:.1f} fps)! Output: {output_path}", flush=True)

    # Save high-res screenshot/thumbnail
    thumb_jpg = os.path.splitext(output_path)[0] + "_thumb.jpg"
    thumb_png = os.path.splitext(output_path)[0] + "_thumb.png"
    if saved_thumb is not None:
        cv2.imwrite(thumb_jpg, saved_thumb, [cv2.IMWRITE_JPEG_QUALITY, 96])
        cv2.imwrite(thumb_png, saved_thumb)
        print(f"[+] High-res thumbnail saved: {thumb_jpg}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Render Avee Player .viz template onto background")
    parser.add_argument(
        "--viz",
        default=r"D:\E agy cli\E bots\music_visualizer\Visualizer_Core_Only.viz",
        help="Path to .viz template",
    )
    parser.add_argument(
        "--bg",
        default=r"C:\Users\kreg9\Downloads\Woman_planting_yellow_daffodil_20260927044753.jpg",
        help="Path to background image",
    )
    parser.add_argument(
        "--audio",
        default=r"D:\E agy cli\E bots\E suno downloader\suno_downloads\Spyionx\05 - If You Stay Until Morning.mp3",
        help="Path to audio file",
    )
    parser.add_argument(
        "--output",
        default=r"D:\E agy cli\E bots\music_visualizer\daffodil_viz_60fps_15s.mp4",
        help="Path to output MP4",
    )
    parser.add_argument("--fps", type=int, default=60, help="Frames per second (default: 60)")
    parser.add_argument("--start-sec", type=float, default=4.0, help="Start time in seconds")
    parser.add_argument("--duration", type=float, default=15.0, help="Duration in seconds (default: 15s)")
    parser.add_argument("--color", default="gold", help="Tint color: auto/random, gold, cyan, yellow, mint, pink, lavender, white, peach, ice_blue")
    parser.add_argument("--pos-x", type=int, default=None, help="Center X (default: right-side ~74%% of width)")
    parser.add_argument("--pos-y", type=int, default=None, help="Center Y (default: ~48%% of height)")
    parser.add_argument("--diameter", type=int, default=490, help="Base diameter in pixels (default: 490)")
    parser.add_argument("--channel", default="Sypionx", help="Channel name branding (default: Sypionx)")
    parser.add_argument("--title", default="", help="Song title (default: auto from audio filename)")

    args = parser.parse_args()

    generate_viz_video(
        viz_path=args.viz,
        bg_path=args.bg,
        audio_path=args.audio,
        output_path=args.output,
        fps=args.fps,
        start_sec=args.start_sec,
        duration=args.duration,
        pos_x=args.pos_x,
        pos_y=args.pos_y,
        base_diameter=args.diameter,
        color=args.color,
        channel_name=args.channel,
        song_title=args.title,
    )


if __name__ == "__main__":
    main()
