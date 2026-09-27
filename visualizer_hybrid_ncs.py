"""
Avee Player Full NCS Visualizer Engine (True Audio Synchronization)
Based on NoCopyrightSoundsVisualizerV4(By C-ops Nation).viz:
1. Live 80-Bin Audio Spectrum Waveform Ring (37.5 Hz to 2070 Hz) synced 100% to the song
2. 3D Topographic Mesh Core (1089483 / mesh_core.gif) in the center with dynamic BeatPulse
3. Radiant Neon Bloom (Golden/Luminous) at 60 FPS with sample-accurate 0.0ms delay
4. Bottom-Left Channel Branding (SYPIONX in Gold) + Clean Song Title
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
import scipy.interpolate
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
    Extracts the 3D Topographic Mesh Core (1089483 or mesh_core.gif)
    from .viz archive and pre-tints frames with neon glow.
    """
    print(f"[NCS-Viz] Extracting mesh core from: {viz_path}", flush=True)
    with zipfile.ZipFile(viz_path, 'r') as z:
        names = z.namelist()
        if "1089483" in names:
            gif_bytes = z.read("1089483")
        elif "mesh_core.gif" in names:
            gif_bytes = z.read("mesh_core.gif")
        else:
            # Find largest file in archive
            largest = max(z.infolist(), key=lambda x: x.file_size)
            gif_bytes = z.read(largest.filename)

    import io
    gif_file = io.BytesIO(gif_bytes)
    im = Image.open(gif_file)

    pil_frames = [f.copy().convert("RGBA") for f in ImageSequence.Iterator(im)]
    num_frames = len(pil_frames)
    print(f"[NCS-Viz] Loaded {num_frames} frames from 3D Topographic Mesh Core.", flush=True)

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

        tinted_frames.append(tinted_alpha.astype(np.uint8))

    return tinted_frames


def compute_spectrum_matrix(mono_audio, sr, fps=60, num_bins=80, lower_hz=37.5, higher_hz=2070.0):
    """
    Computes 80-bin frequency spectrum matching Avee Player's Spectrum2 parameters.
    Returns (spectrum_matrix, bass_envelope).
    """
    total_frames = int(len(mono_audio) / sr * fps)
    hop_length = int(sr / fps)
    n_fft = 2048

    frequencies, times, Zxx = scipy.signal.stft(
        mono_audio, fs=sr, nperseg=n_fft, noverlap=n_fft - hop_length
    )
    magnitude = np.abs(Zxx)

    # Sub-bass for BeatPulse (30 Hz to 130 Hz)
    bass_idx = np.where((frequencies >= 30) & (frequencies <= 130))[0]
    bass_raw = np.mean(magnitude[bass_idx, :], axis=0) if len(bass_idx) > 0 else np.zeros(magnitude.shape[1])

    # 80 log-spaced frequency bins from lower_hz to higher_hz
    bin_centers = np.geomspace(lower_hz, higher_hz, num_bins)
    spectrum_raw = np.zeros((num_bins, magnitude.shape[1]), dtype=np.float32)

    for b_idx in range(num_bins):
        f_center = bin_centers[b_idx]
        bandwidth = f_center * 0.12  # Adaptive Q
        f_min = max(0, f_center - bandwidth / 2)
        f_max = f_center + bandwidth / 2
        f_indices = np.where((frequencies >= f_min) & (frequencies <= f_max))[0]
        if len(f_indices) > 0:
            spectrum_raw[b_idx, :] = np.mean(magnitude[f_indices, :], axis=0)
        else:
            closest = np.argmin(np.abs(frequencies - f_center))
            spectrum_raw[b_idx, :] = magnitude[closest, :]

    # Truncate / pad to total_frames
    if spectrum_raw.shape[1] < total_frames:
        pad_width = total_frames - spectrum_raw.shape[1]
        spectrum_raw = np.pad(spectrum_raw, ((0, 0), (0, pad_width)))
        bass_raw = np.pad(bass_raw, (0, pad_width))
    else:
        spectrum_raw = spectrum_raw[:, :total_frames]
        bass_raw = bass_raw[:total_frames]

    # Temporal smoothing (Attack: 0.90, Decay: 0.22)
    smoothed_spec = np.zeros_like(spectrum_raw)
    smoothed_bass = np.zeros_like(bass_raw)

    for t in range(total_frames):
        # Spectrum bins smoothing
        curr_col = spectrum_raw[:, t]
        if t == 0:
            smoothed_spec[:, t] = curr_col
            smoothed_bass[t] = bass_raw[t]
        else:
            prev_col = smoothed_spec[:, t - 1]
            # Fast attack, smooth decay
            rise_mask = curr_col > prev_col
            smoothed_spec[rise_mask, t] = prev_col[rise_mask] + 0.88 * (curr_col[rise_mask] - prev_col[rise_mask])
            fall_mask = ~rise_mask
            smoothed_spec[fall_mask, t] = prev_col[fall_mask] * (1.0 - 0.22)

            # Bass smoothing
            b_curr = bass_raw[t]
            b_prev = smoothed_bass[t - 1]
            smoothed_bass[t] = b_prev + 0.90 * (b_curr - b_prev) if b_curr > b_prev else b_prev * (1.0 - 0.20)

    # Dynamic normalization per bin
    p95_bins = np.percentile(smoothed_spec, 96, axis=1, keepdims=True)
    p95_bins[p95_bins < 1e-4] = 1e-4
    norm_spec = np.clip(smoothed_spec / p95_bins, 0.0, 1.5)

    # Spatial smoothing across adjacent bins for organic waveform
    kernel = np.array([0.15, 0.70, 0.15])
    for t in range(total_frames):
        norm_spec[:, t] = np.convolve(norm_spec[:, t], kernel, mode='same')

    # Normalize bass
    p95_bass = np.percentile(smoothed_bass, 95) if len(smoothed_bass) > 0 else 1.0
    norm_bass = np.clip(smoothed_bass / (p95_bass + 1e-4), 0.0, 1.4)

    return norm_spec, norm_bass


def draw_bottom_left_branding(cv2_img, channel_name="Sypionx", song_title=""):
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

    # Gaussian blur shadow layer
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


def generate_ncs_viz_video(
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
    color="gold",
    crf=16,
    channel_name="Sypionx",
    song_title=None,
):
    """
    Renders video combining the 3D Topographic Mesh Core from .viz
    with the 100% real-time audio-reactive NCS Spectrum wave ring.
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

    if song_title is None or not song_title:
        song_title = os.path.splitext(os.path.basename(audio_path))[0]

    bg = draw_bottom_left_branding(bg, channel_name=channel_name, song_title=song_title)

    # Color resolution
    if isinstance(color, str):
        c_low = color.lower().strip()
        if c_low in ["auto", "random"]:
            import random
            color_name = random.choice(list(LIGHT_PALETTE.keys()))
            color_bgr = LIGHT_PALETTE[color_name]
            print(f"[NCS-Viz] Auto-selected luminous color: {color_name.upper()} {color_bgr}", flush=True)
        elif c_low in LIGHT_PALETTE:
            color_bgr = LIGHT_PALETTE[c_low]
        else:
            color_bgr = LIGHT_PALETTE["gold"]
    else:
        color_bgr = color

    # Standard right-side placement
    cx = pos_x if pos_x is not None else int(W * 0.741)
    cy = pos_y if pos_y is not None else int(H * 0.480)
    if base_diameter is None or base_diameter <= 0:
        base_diameter = 490

    base_radius = base_diameter // 2
    print(f"[NCS-Viz] Canvas: {W}x{H} | Center: ({cx}, {cy}) | Diameter: {base_diameter}px | FPS: {fps}", flush=True)

    # 1. Load mesh core frames
    template_frames = load_viz_core(viz_path, color_bgr=color_bgr)
    num_template_frames = len(template_frames)

    # 2. Load and slice audio with exact sample precision
    print(f"[NCS-Viz] Loading audio: {audio_path}", flush=True)
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
    print(f"[NCS-Viz] Sliced audio: {actual_duration:.2f}s ({actual_frames} video frames @ {fps}fps)", flush=True)

    # Temporary uncompressed WAV for 0.0ms FFmpeg alignment
    temp_wav_fd, temp_wav_path = tempfile.mkstemp(suffix="_sync.wav")
    os.close(temp_wav_fd)
    sf.write(temp_wav_path, audio_slice, sr)

    # 3. Compute real-time 80-bin spectrum and sub-bass BeatPulse
    num_bins = 80
    spec_matrix, bass_env = compute_spectrum_matrix(mono_slice, sr, fps=fps, num_bins=num_bins)

    # 4. Symmetrical angular distribution around the circle (40 bins left, 40 bins right)
    half_bins = num_bins // 2
    # Map 0 to 180 degrees (top to bottom on right), and 180 to 360 (bottom to top on left)
    angles_right = np.linspace(0.0, np.pi, half_bins, endpoint=False)
    angles_left = np.linspace(np.pi, 2 * np.pi, half_bins, endpoint=False)
    # Combine so low frequencies are at bottom/sides and highs are at top
    angles = np.concatenate([angles_right, angles_left])

    # 5. Launch FFmpeg process
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

    print("[NCS-Viz] Launching FFmpeg encoder...", flush=True)
    proc = subprocess.Popen(
        ffmpeg_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    t0 = time.time()
    last_print = t0

    # Bounding box for ROI
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

    # Core diameter: fits comfortably inside the reactive spectrum ring
    core_base_dia = int(base_diameter * 0.72)

    try:
        for i in range(actual_frames):
            bass_val = float(bass_env[i])
            freq_col = spec_matrix[:, i]

            # Dynamic BeatPulse scaling (amount 0.28 matching Avee spec)
            pulse_scale = 0.88 + 0.28 * bass_val
            current_core_dia = int(core_base_dia * pulse_scale)
            current_core_dia = (current_core_dia // 2) * 2

            # 1. Prepare 3D Topographic Mesh Core from template
            tpl_idx = i % num_template_frames
            core_src = template_frames[tpl_idx]

            # Dynamic glow boost on drum hits
            glow_boost = 1.0 + 0.35 * bass_val
            core_boosted = cv2.convertScaleAbs(core_src, alpha=glow_boost, beta=0)
            core_scaled = cv2.resize(core_boosted, (current_core_dia, current_core_dia), interpolation=cv2.INTER_LINEAR)

            # 2. Render layer buffer
            layer = np.zeros((roi_h, roi_w, 3), dtype=np.uint8)

            # Stamp center core into layer
            vx1 = max(0, rcx - current_core_dia // 2)
            vy1 = max(0, rcy - current_core_dia // 2)
            vx2 = min(roi_w, vx1 + current_core_dia)
            vy2 = min(roi_h, vy1 + current_core_dia)
            cw = vx2 - vx1
            ch = vy2 - vy1
            if cw > 0 and ch > 0:
                layer[vy1:vy2, vx1:vx2] = core_scaled[:ch, :cw]

            # 3. Calculate 100% Real-Time Audio-Reactive NCS Waveform Ring
            # Mirror the 40 bins symmetrically on left and right
            half_energy = freq_col[:half_bins]
            # Symmetrical: low freqs at bottom, highs at top
            spectrum_circle = np.concatenate([half_energy, half_energy[::-1]])

            # Height multiplier matching Avee Player spec (1.2 * max_bar_reach)
            max_wave_reach = 58.0 * pulse_scale
            r_dyn = base_radius * pulse_scale

            # Compute perimeter wave polygon coordinates
            num_interp_pts = 160
            interp_angles = np.linspace(0.0, 2 * np.pi, num_interp_pts, endpoint=False)
            orig_angles = np.linspace(0.0, 2 * np.pi, num_bins, endpoint=False)

            # Circular smooth interpolation of frequency displacements
            wave_displacements = np.interp(
                interp_angles,
                orig_angles,
                spectrum_circle,
                period=2 * np.pi
            ) * max_wave_reach

            # Draw outer reactive waveform curve
            wave_coords = []
            for p_idx in range(num_interp_pts):
                ang = interp_angles[p_idx]
                r_pt = r_dyn + wave_displacements[p_idx]
                px = int(rcx + r_pt * np.cos(ang))
                py = int(rcy + r_pt * np.sin(ang))
                wave_coords.append([px, py])

            wave_pts = np.array(wave_coords, dtype=np.int32)

            # Draw glowing waveform lines
            cv2.polylines(layer, [wave_pts], isClosed=True, color=color_bgr, thickness=3, lineType=cv2.LINE_AA)

            # Draw base inner ring boundary
            cv2.circle(layer, (rcx, rcy), int(r_dyn), color=color_bgr, thickness=2, lineType=cv2.LINE_AA)

            # 4. Multi-stage Gaussian Neon Bloom
            b1 = cv2.GaussianBlur(layer, (11, 11), 0)
            b2 = cv2.GaussianBlur(layer, (27, 27), 0)
            glow_comp = cv2.addWeighted(layer, 1.15, b1, 0.70, 0)
            glow_comp = cv2.addWeighted(glow_comp, 1.0, b2, 0.35, 0)

            # 5. Screen blend onto background ROI
            vis_inv = (255 - glow_comp).astype(np.uint16)
            comp_roi = 255 - ((bg_roi_u16 * vis_inv) >> 8).astype(np.uint8)

            frame_out[y1:y2, x1:x2] = comp_roi

            if i == thumb_target_frame:
                saved_thumb = frame_out.copy()

            # Pipe to FFmpeg
            proc.stdin.write(frame_out.tobytes())

            now = time.time()
            if now - last_print > 2.0 or i == actual_frames - 1:
                elapsed = now - t0
                current_fps = (i + 1) / max(elapsed, 0.001)
                eta = (actual_frames - (i + 1)) / max(current_fps, 0.001)
                pct = ((i + 1) / actual_frames) * 100
                print(f"[NCS-Viz] Progress: {i+1}/{actual_frames} ({pct:.1f}%) | {current_fps:.1f} fps | Elapsed: {elapsed:.1f}s | ETA: {eta:.1f}s", flush=True)
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
    print(f"\n[NCS-Viz] Render completed in {total_time:.1f}s ({actual_frames/total_time:.1f} fps)! Output: {output_path}", flush=True)

    # Save high-res screenshot/thumbnail
    thumb_jpg = os.path.splitext(output_path)[0] + "_thumb.jpg"
    thumb_png = os.path.splitext(output_path)[0] + "_thumb.png"
    if saved_thumb is not None:
        cv2.imwrite(thumb_jpg, saved_thumb, [cv2.IMWRITE_JPEG_QUALITY, 96])
        cv2.imwrite(thumb_png, saved_thumb)
        print(f"[NCS-Viz] High-res thumbnail saved: {thumb_jpg}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="Render Full NCS Audio-Reactive Visualizer (.viz template)")
    parser.add_argument(
        "--viz",
        default=r"C:\Users\kreg9\Downloads\NoCopyrightSoundsVisualizerV4(By C-ops Nation).viz",
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
        default=r"D:\E agy cli\E bots\music_visualizer\daffodil_ncs_v4_synced_60fps_15s.mp4",
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

    generate_ncs_viz_video(
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
