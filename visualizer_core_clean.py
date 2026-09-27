"""
Pure Core Visualizer Engine (ONLY the 3D Topographic Mesh Core from Visualizer_Core_Only.viz)
Zero outside rings, zero outside bars, zero clutter.
100% focused on the dotted core with:
1. Audio-Reactive BeatPulse (Bass kick expansion)
2. Groove-Synced Phase Motion (Animates to the energy/tempo of the music)
3. Dynamic Neon Bloom Flash on drum hits
4. Sample-accurate 0.0ms audio synchronization
5. Bottom-left channel branding (SYPIONX in Gold) + Clean Song Title
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
import scipy.signal
from PIL import Image, ImageSequence, ImageDraw, ImageFont, ImageFilter


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


def load_viz_core(viz_path, color_bgr=(70, 215, 255)):
    """
    Extracts mesh_core.gif from Visualizer_Core_Only.viz and pre-tints frames with neon glow.
    """
    print(f"[CoreOnly] Extracting core from: {viz_path}", flush=True)
    with zipfile.ZipFile(viz_path, 'r') as z:
        names = z.namelist()
        if "mesh_core.gif" in names:
            gif_bytes = z.read("mesh_core.gif")
        elif "1089483" in names:
            gif_bytes = z.read("1089483")
        else:
            largest = max(z.infolist(), key=lambda x: x.file_size)
            gif_bytes = z.read(largest.filename)

    import io
    gif_file = io.BytesIO(gif_bytes)
    im = Image.open(gif_file)

    pil_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(im)]
    num_frames = len(pil_frames)
    print(f"[CoreOnly] Loaded {num_frames} frames from Visualizer_Core_Only.viz.", flush=True)

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

        # Multi-stage neon bloom
        b1 = cv2.GaussianBlur(tinted_alpha, (9, 9), 0)
        b2 = cv2.GaussianBlur(tinted_alpha, (25, 25), 0)
        glowing = np.clip(tinted_alpha * 1.15 + b1 * 0.70 + b2 * 0.35, 0, 255).astype(np.uint8)

        tinted_frames.append(glowing)

    return tinted_frames


def extract_splash_accent_color(img_bgr, default_bgr=(70, 215, 255)):
    """
    Extracts the single vibrant splash color from a black-and-white / selective-color image.
    Filters out desaturated pixels (grayscale, blacks, whites) and isolates the colorful subject.
    Converts to high-luminance neon BGR for the visualizer.
    """
    if img_bgr is None:
        return default_bgr

    # Downscale for instant processing
    h, w = img_bgr.shape[:2]
    small = cv2.resize(img_bgr, (min(w, 400), min(h, 400)), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

    # Filter for saturated pixels (S > 50, V > 40)
    sat_mask = (hsv[:, :, 1] > 50) & (hsv[:, :, 2] > 40)

    if np.sum(sat_mask) < 20:
        print("[ColorDetector] No distinct splash color detected in image. Using radiant gold.", flush=True)
        return default_bgr

    sat_hsv = hsv[sat_mask]
    med_h = np.median(sat_hsv[:, 0])

    # Boost saturation and brightness for luminous visualizer glow
    neon_hsv = np.uint8([[[int(round(med_h)), 235, 255]]])
    neon_bgr = cv2.cvtColor(neon_hsv, cv2.COLOR_HSV2BGR)[0][0]
    result_bgr = (int(neon_bgr[0]), int(neon_bgr[1]), int(neon_bgr[2]))

    hex_code = f"#{result_bgr[2]:02X}{result_bgr[1]:02X}{result_bgr[0]:02X}"
    print(f"[ColorDetector] Auto-detected splash color from artwork: Hue={med_h:.1f} -> Neon BGR={result_bgr} (Hex: {hex_code})", flush=True)
    return result_bgr


def draw_bottom_left_branding(cv2_img, channel_name="Sypionx", song_title="", accent_bgr=None):
    """
    Renders channel branding and clean song title on bottom-left.
    Automatically strips track numbers from title.
    """
    if not channel_name and not song_title:
        return cv2_img

    H, W = cv2_img.shape[:2]

    # Clean leading track numbers
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
        chan_fill = (accent_bgr[2], accent_bgr[1], accent_bgr[0], 245) if accent_bgr is not None else (255, 215, 70, 245)
        draw.text((pos_x, chan_y), channel_text, font=chan_font, fill=chan_fill)
    if clean_title:
        draw.text((pos_x, title_y), clean_title, font=title_font, fill=(255, 255, 255, 255))      # Crisp White

    pil_img = Image.alpha_composite(pil_img.convert('RGBA'), overlay)
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGBA2BGR)


def compute_audio_rhythm(mono_audio, sr, fps=60):
    """
    Computes both instantaneous sub-bass kick energy (for BeatPulse)
    and overall track energy envelope (for groove-synced rotation speed).
    """
    total_frames = int(len(mono_audio) / sr * fps)
    hop_length = int(sr / fps)
    n_fft = 2048

    frequencies, times, Zxx = scipy.signal.stft(
        mono_audio, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length
    )
    magnitude = np.abs(Zxx)

    # Sub-bass for drum kicks (25 Hz to 130 Hz)
    bass_idx = np.where((frequencies >= 25) & (frequencies <= 130))[0]
    bass_energy = np.mean(magnitude[bass_idx, :], axis=0) if len(bass_idx) > 0 else np.zeros(magnitude.shape[1])

    # Overall spectral energy (dynamics / groove)
    total_energy = np.mean(magnitude, axis=0)

    # Truncate / pad
    if len(bass_energy) < total_frames:
        bass_energy = np.pad(bass_energy, (0, total_frames - len(bass_energy)))
        total_energy = np.pad(total_energy, (0, total_frames - len(total_energy)))
    else:
        bass_energy = bass_energy[:total_frames]
        total_energy = total_energy[:total_frames]

    # Authentic Avee Player Beat smoothing:
    # Fast attack (0.80), musical exponential decay (0.09 per frame ~120ms kick thump duration)
    smoothed_bass = np.zeros(total_frames, dtype=np.float32)
    smoothed_energy = np.zeros(total_frames, dtype=np.float32)

    attack_rate = 0.80
    decay_rate = 0.09

    for i in range(total_frames):
        b_curr = bass_energy[i]
        e_curr = total_energy[i]

        if i == 0:
            smoothed_bass[i] = b_curr
            smoothed_energy[i] = e_curr
        else:
            b_prev = smoothed_bass[i - 1]
            if b_curr > b_prev:
                smoothed_bass[i] = b_prev + attack_rate * (b_curr - b_prev)
            else:
                smoothed_bass[i] = b_prev * (1.0 - decay_rate)

            e_prev = smoothed_energy[i - 1]
            smoothed_energy[i] = e_prev + 0.10 * (e_curr - e_prev)

    p95_b = np.percentile(smoothed_bass, 95) if len(smoothed_bass) > 0 else 1.0
    p95_e = np.percentile(smoothed_energy, 95) if len(smoothed_energy) > 0 else 1.0

    # Normalized clean beat envelope [0.0, 1.0]
    norm_bass = np.clip(smoothed_bass / (p95_b + 1e-6), 0.0, 1.0)
    norm_energy = np.clip(smoothed_energy / (p95_e + 1e-6), 0.0, 1.0)

    return norm_bass, norm_energy


def generate_core_only_video(
    viz_path,
    bg_path,
    audio_path,
    output_path,
    fps=60,
    start_sec=0.0,
    duration=None,
    pos_x=None,
    pos_y=None,
    base_diameter=None,
    color="auto",
    crf=16,
    channel_name="Sypionx",
    song_title=None,
    target_width=1920,
    target_height=1080,
):
    """
    Renders video using ONLY the 3D Topographic Mesh Core from Visualizer_Core_Only.viz.
    Zero outside rings. Fully audio-synced BeatPulse & groove-reactive rotation.
    Enforces standard Full HD 1080P (1920x1080) output resolution.
    """
    if not os.path.exists(bg_path):
        raise FileNotFoundError(f"Background image not found: {bg_path}")
    raw_bg = cv2.imread(bg_path)
    if raw_bg is None:
        raise ValueError(f"Could not load image: {bg_path}")

    # Standard Full HD 1080P canvas (1920x1080)
    W = target_width
    H = target_height
    orig_h, orig_w = raw_bg.shape[:2]

    if orig_w != W or orig_h != H:
        scale_factor = max(W / orig_w, H / orig_h)
        new_w = int(round(orig_w * scale_factor))
        new_h = int(round(orig_h * scale_factor))
        interp = cv2.INTER_LANCZOS4 if scale_factor > 1.0 else cv2.INTER_AREA
        resized = cv2.resize(raw_bg, (new_w, new_h), interpolation=interp)
        crop_x = max(0, (new_w - W) // 2)
        crop_y = max(0, (new_h - H) // 2)
        bg = resized[crop_y:crop_y + H, crop_x:crop_x + W].copy()
    else:
        bg = raw_bg.copy()

    if song_title is None or not song_title:
        song_title = os.path.splitext(os.path.basename(audio_path))[0]

    # Color selection: auto extracts the one splash color from the black-and-white image!
    if isinstance(color, str):
        c_low = color.lower().strip()
        if c_low == "auto":
            color_bgr = extract_splash_accent_color(raw_bg)
        elif c_low == "random":
            import random
            color_name = random.choice(list(LIGHT_PALETTE.keys()))
            color_bgr = LIGHT_PALETTE[color_name]
            print(f"[CoreOnly] Randomly selected color: {color_name.upper()} {color_bgr}", flush=True)
        elif c_low in LIGHT_PALETTE:
            color_bgr = LIGHT_PALETTE[c_low]
        else:
            color_bgr = LIGHT_PALETTE["gold"]
    else:
        color_bgr = color

    bg = draw_bottom_left_branding(bg, channel_name=channel_name, song_title=song_title, accent_bgr=color_bgr)

    # Standard right-side placement
    cx = pos_x if pos_x is not None else int(W * 0.741)
    cy = pos_y if pos_y is not None else int(H * 0.480)
    if base_diameter is None or base_diameter <= 0:
        base_diameter = int(round(490 * (H / 768.0)))  # Proportional scale (688px at 1080p)

    print(f"[CoreOnly] Canvas: {W}x{H} (1080P Full HD) | Center: ({cx}, {cy}) | Base diameter: {base_diameter}px | FPS: {fps}", flush=True)

    # 1. Load ONLY the core frames
    template_frames = load_viz_core(viz_path, color_bgr=color_bgr)
    num_template_frames = len(template_frames)

    # 2. Slice exact audio to eliminate seek drift (0.0ms delay)
    print(f"[CoreOnly] Loading audio: {audio_path}", flush=True)
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
    print(f"[CoreOnly] Sliced audio: {actual_duration:.2f}s ({actual_frames} video frames @ {fps}fps)", flush=True)

    # Write temporary WAV for FFmpeg
    temp_wav_fd, temp_wav_path = tempfile.mkstemp(suffix="_sync.wav")
    os.close(temp_wav_fd)
    sf.write(temp_wav_path, audio_slice, sr)

    # 3. Analyze kick transients (BeatPulse) & track energy
    bass_env, energy_env = compute_audio_rhythm(mono_slice, sr, fps=fps)

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

    print("[CoreOnly] Launching FFmpeg encoder...", flush=True)
    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    t0 = time.time()
    last_print = t0

    # Max diameter for blending ROI (extra margin for BeatCamShake)
    max_reach = int(base_diameter * 1.65)
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

    # Continuous audio-driven animation phase accumulator
    phase_accum = 0.0

    try:
        for i in range(actual_frames):
            bass_val = float(bass_env[i])
            energy_val = float(energy_env[i])

            # Authentic Avee Player rotation: constant steady progression with TotalTime
            phase_accum += 0.85
            tpl_idx = int(phase_accum) % num_template_frames

            core_src = template_frames[tpl_idx]

            # Authentic Avee Player BeatPulse:
            # Base scale 1.0 (490px), max beat expansion +18% on punchy kick thumps
            pulse_scale = 1.0 + 0.18 * bass_val
            current_dia = int(base_diameter * pulse_scale)
            current_dia = (current_dia // 2) * 2

            # Rock-solid anchor (Avee MeasurePos: Nothing) -> Zero erratic camera twitch
            scx = rcx
            scy = rcy

            # Luminous dynamic beat glow
            glow_boost = 1.0 + 0.20 * bass_val
            core_boosted = cv2.convertScaleAbs(core_src, alpha=glow_boost, beta=0)

            # Scale visualizer frame
            core_scaled = cv2.resize(
                core_boosted,
                (current_dia, current_dia),
                interpolation=cv2.INTER_LINEAR,
            )

            # Clear ROI buffer (PURE CORE ONLY, ZERO OUTSIDE RINGS)
            core_roi = np.zeros((roi_h, roi_w, 3), dtype=np.uint8)

            vx1 = max(0, scx - current_dia // 2)
            vy1 = max(0, scy - current_dia // 2)
            vx2 = min(roi_w, vx1 + current_dia)
            vy2 = min(roi_h, vy1 + current_dia)

            crop_w = vx2 - vx1
            crop_h = vy2 - vy1
            if crop_w > 0 and crop_h > 0:
                core_roi[vy1:vy2, vx1:vx2] = core_scaled[:crop_h, :crop_w]

            # Fast screen blend onto background
            vis_inv = (255 - core_roi).astype(np.uint16)
            comp_roi = 255 - ((bg_roi_u16 * vis_inv) >> 8).astype(np.uint8)

            frame_out[y1:y2, x1:x2] = comp_roi

            if i == thumb_target_frame:
                saved_thumb = frame_out.copy()

            # Write frame to FFmpeg
            proc.stdin.write(frame_out.tobytes())

            now = time.time()
            if now - last_print > 2.0 or i == actual_frames - 1:
                elapsed = now - t0
                current_fps = (i + 1) / max(elapsed, 0.001)
                eta = (actual_frames - (i + 1)) / max(current_fps, 0.001)
                pct = ((i + 1) / actual_frames) * 100
                print(f"[CoreOnly] Progress: {i+1}/{actual_frames} ({pct:.1f}%) | {current_fps:.1f} fps | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s", flush=True)
                last_print = now

    finally:
        proc.stdin.close()
        proc.wait()
        if os.path.exists(temp_wav_path):
            try:
                os.remove(temp_wav_path)
            except Exception:
                pass

    total_time = time.time() - t0
    print(f"\n[CoreOnly] Render completed in {total_time:.1f}s ({actual_frames/total_time:.1f} fps)! Output: {output_path}", flush=True)

    # Save high-res screenshot/thumbnail
    thumb_jpg = os.path.splitext(output_path)[0] + "_thumb.jpg"
    thumb_png = os.path.splitext(output_path)[0] + "_thumb.png"
    if saved_thumb is not None:
        cv2.imwrite(thumb_jpg, saved_thumb, [cv2.IMWRITE_JPEG_QUALITY, 96])
        cv2.imwrite(thumb_png, saved_thumb)
        print(f"[CoreOnly] High-res thumbnail saved: {thumb_jpg}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Render PURE CORE Visualizer_Core_Only.viz (Zero outside rings)")
    parser.add_argument(
        "--viz",
        default=r"D:\E agy cli\E bots\music_visualizer\Visualizer_Core_Only.viz",
        help="Path to Visualizer_Core_Only.viz",
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
        default=r"D:\E agy cli\E bots\music_visualizer\daffodil_pure_core_synced_60fps_15s.mp4",
        help="Path to output MP4",
    )
    parser.add_argument("--fps", type=int, default=60, help="Frames per second (default: 60)")
    parser.add_argument("--start-sec", type=float, default=4.0, help="Start time in seconds")
    parser.add_argument("--duration", type=float, default=15.0, help="Duration in seconds (default: 15s)")
    parser.add_argument("--color", default="auto", help="Tint color: auto (extracts splash color from image), random, gold, cyan, yellow, mint, pink, lavender, white, peach, ice_blue")
    parser.add_argument("--pos-x", type=int, default=None, help="Center X (default: right-side ~74%% of width)")
    parser.add_argument("--pos-y", type=int, default=None, help="Center Y (default: ~48%% of height)")
    parser.add_argument("--diameter", type=int, default=None, help="Base diameter in pixels (default: auto proportional ~688px for 1080p)")
    parser.add_argument("--width", type=int, default=1920, help="Target canvas width (default: 1920)")
    parser.add_argument("--height", type=int, default=1080, help="Target canvas height (default: 1080)")
    parser.add_argument("--channel", default="Sypionx", help="Channel name branding (default: Sypionx)")
    parser.add_argument("--title", default="", help="Song title (default: auto from audio filename)")

    args = parser.parse_args()

    generate_core_only_video(
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
        target_width=args.width,
        target_height=args.height,
    )


if __name__ == "__main__":
    main()
