"""
Avee Player .viz Template Visualizer Engine (High-Fidelity Audio-Reactive BeatPulse)
Extracts and renders the 3D Topographic Mesh Core from Visualizer_Core_Only.viz
with 60 FPS temporal interpolation, sample-accurate audio synchronization,
radiant neon bloom, and bottom-left channel + song branding.
"""

import os
import sys
import re
import time
import zipfile
import argparse
import subprocess
import tempfile
import numpy as np
import cv2
import soundfile as sf
from PIL import Image, ImageSequence, ImageDraw, ImageFont, ImageFilter


# Luminous color palette designed to pop on any background
LIGHT_PALETTE = {
    "gold": (70, 215, 255),        # Radiant Daffodil / Sunflower Gold (BGR)
    "cyan": (242, 250, 140),       # Electric Cyan / Aqua
    "yellow": (70, 235, 255),      # Neon Lemon Yellow
    "mint": (190, 255, 120),       # Cyber Spring Mint
    "pink": (210, 140, 255),       # Neon Rose Pink
    "lavender": (255, 160, 210),   # Soft Glowing Violet
    "white": (255, 250, 245),      # Diamond Ice White
    "peach": (120, 190, 255),      # Warm Amber Peach
    "ice_blue": (255, 225, 160),   # Frosted Sky Blue
}


def load_viz_template(viz_path, color_bgr=(70, 215, 255)):
    """
    Extracts mesh_core.gif from .viz archive and pre-tints all frames with neon bloom.
    """
    print(f"[VizEngine] Extracting template from: {viz_path}", flush=True)
    with zipfile.ZipFile(viz_path, 'r') as z:
        gif_bytes = z.read("mesh_core.gif")

    import io
    gif_file = io.BytesIO(gif_bytes)
    im = Image.open(gif_file)

    pil_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(im)]
    num_frames = len(pil_frames)
    print(f"[VizEngine] Loaded {num_frames} frames from 3D Topographic Mesh Core.", flush=True)

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

        # Multi-stage bloom pass for high-luminosity neon glow
        b1 = cv2.GaussianBlur(tinted_alpha, (9, 9), 0)
        b2 = cv2.GaussianBlur(tinted_alpha, (25, 25), 0)
        glowing = np.clip(tinted_alpha * 1.15 + b1 * 0.75 + b2 * 0.40, 0, 255).astype(np.uint8)

        tinted_frames.append(glowing)

    return tinted_frames


def analyze_audio_envelope(audio_mono, sr, fps=60):
    """
    Calculates sample-accurate sub-bass and RMS beat envelope aligned frame-by-frame.
    """
    total_frames = int(len(audio_mono) / sr * fps)
    hop_samples = sr / fps
    window_size = int(sr * 0.05)  # 50ms window
    window_size = max(window_size, 512)
    hann = np.hanning(window_size)

    raw_bass = np.zeros(total_frames, dtype=np.float32)

    for i in range(total_frames):
        center_s = int(i * hop_samples)
        s_start = max(0, center_s - window_size // 2)
        s_end = min(len(audio_mono), s_start + window_size)
        chunk = audio_mono[s_start:s_end]
        if len(chunk) < window_size:
            chunk = np.pad(chunk, (0, window_size - len(chunk)))

        windowed = chunk * hann
        # FFT magnitude
        fft_mag = np.abs(np.fft.rfft(windowed))
        freqs = np.fft.rfftfreq(window_size, d=1.0 / sr)

        # Sub-bass range (25 Hz to 140 Hz) - drum kicks & 808s
        bass_bins = np.where((freqs >= 25) & (freqs <= 140))[0]
        if len(bass_bins) > 0:
            raw_bass[i] = np.mean(fft_mag[bass_bins])

    # Dynamic attack & decay smoothing for punchy kick response
    smoothed_bass = np.zeros(total_frames, dtype=np.float32)
    attack = 0.90
    decay = 0.22
    for i in range(total_frames):
        curr = raw_bass[i]
        if i == 0:
            smoothed_bass[i] = curr
        else:
            prev = smoothed_bass[i - 1]
            if curr > prev:
                smoothed_bass[i] = prev + attack * (curr - prev)
            else:
                smoothed_bass[i] = prev * (1.0 - decay)

    # Normalize based on 95th percentile
    p95 = np.percentile(smoothed_bass, 95) if len(smoothed_bass) > 0 else 1.0
    norm_bass = np.clip(smoothed_bass / (p95 + 1e-6), 0.0, 1.4)
    return norm_bass


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
    smooth 3D topographic terrain interpolation, right-side placement,
    bottom-left branding, and peak-energy thumbnail.
    """
    if not os.path.exists(bg_path):
        raise FileNotFoundError(f"Background image not found: {bg_path}")
    raw_bg = cv2.imread(bg_path)
    if raw_bg is None:
        raise ValueError(f"Could not load image: {bg_path}")

    orig_h, orig_w = raw_bg.shape[:2]
    H = (orig_h // 2) * 2
    W = (orig_w // 2) * 2
    bg = raw_bg[:H, :W].copy()

    # Determine song title from audio file if not provided
    if song_title is None or not song_title:
        song_title = os.path.splitext(os.path.basename(audio_path))[0]

    # Draw bottom-left branding onto background
    bg = draw_bottom_left_branding(bg, channel_name=channel_name, song_title=song_title)

    # Resolve color
    if isinstance(color, str):
        c_low = color.lower().strip()
        if c_low in ["auto", "random"]:
            import random
            color_name = random.choice(list(LIGHT_PALETTE.keys()))
            color_bgr = LIGHT_PALETTE[color_name]
            print(f"[VizEngine] Auto-selected luminous visualizer color: {color_name.upper()} {color_bgr}", flush=True)
        elif c_low in LIGHT_PALETTE:
            color_bgr = LIGHT_PALETTE[c_low]
        else:
            color_bgr = LIGHT_PALETTE["gold"]
    else:
        color_bgr = color

    # Standardized placement: Right-side negative space
    cx = pos_x if pos_x is not None else int(W * 0.741)
    cy = pos_y if pos_y is not None else int(H * 0.480)
    if base_diameter is None or base_diameter <= 0:
        base_diameter = 490

    print(f"[VizEngine] Canvas: {W}x{H} | Center: ({cx}, {cy}) | Base diameter: {base_diameter} | FPS: {fps}", flush=True)

    # 1. Load template frames
    template_frames = load_viz_template(viz_path, color_bgr=color_bgr)
    num_template_frames = len(template_frames)
    mesh_gif_fps = 6.0  # Original GIF speed: 166.67ms per frame = 6.0 FPS

    # 2. Load & slice exact audio to guarantee 0.0ms delay
    print(f"[VizEngine] Loading audio: {audio_path}", flush=True)
    audio_full, sr = sf.read(audio_path)
    if audio_full.ndim > 1:
        mono_full = np.mean(audio_full, axis=1)
    else:
        mono_full = audio_full

    total_duration = len(mono_full) / sr
    start_sample = int(start_sec * sr)
    if duration is not None and duration > 0:
        actual_duration = min(duration, total_duration - start_sec)
        num_samples = int(actual_duration * sr)
        audio_slice = audio_full[start_sample : start_sample + num_samples]
        mono_slice = mono_full[start_sample : start_sample + num_samples]
    else:
        actual_duration = total_duration - start_sec
        audio_slice = audio_full[start_sample:]
        mono_slice = mono_full[start_sample:]

    actual_frames = int(actual_duration * fps)
    print(f"[VizEngine] Sliced audio: {actual_duration:.2f}s ({actual_frames} video frames @ {fps}fps)", flush=True)

    # Save exact audio slice to a temporary uncompressed WAV for FFmpeg
    temp_wav_fd, temp_wav_path = tempfile.mkstemp(suffix="_sync.wav")
    os.close(temp_wav_fd)
    sf.write(temp_wav_path, audio_slice, sr)

    # 3. Analyze beat envelope
    bass_env = analyze_audio_envelope(mono_slice, sr, fps=fps)

    # 4. Setup FFmpeg
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
        "-i", temp_wav_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "320k",
        "-shortest",
        output_path
    ]

    print("[VizEngine] Launching FFmpeg encoder...", flush=True)
    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    t0 = time.time()
    last_print = t0

    # Bounding box for visualizer blending
    max_reach = int(base_diameter * 1.45)
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
    thumb_target_frame = min(actual_frames - 1, int(max(2.0, min(actual_duration * 0.45, 7.0)) * fps))

    try:
        for i in range(actual_frames):
            time_now = i / fps
            stft_idx = min(i, len(bass_env) - 1)
            bass_val = float(bass_env[stft_idx])

            # Smooth 60 FPS interpolation of 3D topographic terrain at true GIF speed
            frame_float = (time_now * mesh_gif_fps) % num_template_frames
            f0 = int(frame_float) % num_template_frames
            f1 = (f0 + 1) % num_template_frames
            frac = frame_float - int(frame_float)

            vis_0 = template_frames[f0]
            vis_1 = template_frames[f1]
            vis_interp = cv2.addWeighted(vis_0, 1.0 - frac, vis_1, frac, 0)

            # Avee BeatPulse scaling (0.88x baseline up to 1.18x on kick peaks)
            pulse_scale = 0.88 + 0.28 * bass_val
            current_dia = int(base_diameter * pulse_scale)
            current_dia = (current_dia // 2) * 2

            # Dynamic glow intensity boosted on beat punch
            glow_boost = 1.0 + 0.35 * bass_val
            vis_boosted = cv2.convertScaleAbs(vis_interp, alpha=glow_boost, beta=0)

            # Resize visualizer frame
            vis_scaled = cv2.resize(
                vis_boosted,
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

            # Pipe frame to FFmpeg
            proc.stdin.write(frame_out.tobytes())

            now = time.time()
            if now - last_print > 2.0 or i == actual_frames - 1:
                elapsed = now - t0
                current_fps = (i + 1) / max(elapsed, 0.001)
                eta = (actual_frames - (i + 1)) / max(current_fps, 0.001)
                pct = ((i + 1) / actual_frames) * 100
                print(f"[VizEngine] Progress: {i+1}/{actual_frames} ({pct:.1f}%) | {current_fps:.1f} fps | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s", flush=True)
                last_print = now

    finally:
        proc.stdin.close()
        proc.wait()
        # Clean up temporary WAV
        if os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except Exception:
                pass

    total_time = time.time() - t0
    print(f"\n[VizEngine] Render completed in {total_time:.1f}s ({actual_frames/total_time:.1f} fps)! Output: {output_path}", flush=True)

    # Save high-res screenshot/thumbnail
    thumb_jpg = os.path.splitext(output_path)[0] + "_thumb.jpg"
    thumb_png = os.path.splitext(output_path)[0] + "_thumb.png"
    if saved_thumb is not None:
        cv2.imwrite(thumb_jpg, saved_thumb, [cv2.IMWRITE_JPEG_QUALITY, 96])
        cv2.imwrite(thumb_png, saved_thumb)
        print(f"[VizEngine] High-res thumbnail saved: {thumb_jpg}", flush=True)


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
        default=r"D:\E agy cli\E bots\music_visualizer\daffodil_viz_smooth_60fps_15s.mp4",
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
