"""
NCS (NoCopyrightSounds) & Avee Player Style Music Visualizer
100% Real-Time FFT Audio Reactive Engine.
Zero Canned Loops — Every bar, wave, pulse, and particle strictly driven by the audio spectrum!

Features:
- Pure STFT frequency spectrum analysis (Sub-bass, Midrange, Treble)
- Symmetrical radial spectrum bars or fluid audio wave with rounded caps
- Dynamic sub-bass heartbeat pulse on center circle
- Ambient audio-reactive floating particle field that bursts on kick drums
- Multi-octave neon bloom glow with vibrant light color palette
- Bottom-left channel branding (SYPIONX in Gold) and clean song title (numbers removed)
- 60 FPS ultra-smooth rendering streamed directly into FFmpeg
- Peak audio energy thumbnail saved alongside the video
"""

import os
import sys
import re
import time
import argparse
import subprocess
import numpy as np
import scipy.signal
import soundfile as sf
import cv2
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def load_and_analyze_audio(audio_path, fps=60, num_bands=96):
    """
    Loads audio and extracts frequency bands and bass/beat envelope with millisecond precision.
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
    magnitude = np.abs(Zxx)  # (freq_bins, time_frames)

    # Logarithmic frequency distribution (30 Hz to 12 kHz)
    min_freq = 30.0
    max_freq = min(12000.0, sr / 2.0)
    log_freqs = np.geomspace(min_freq, max_freq, num_bands + 1)
    band_energies = np.zeros((num_bands, magnitude.shape[1]), dtype=np.float32)

    for b in range(num_bands):
        f_low = log_freqs[b]
        f_high = log_freqs[b + 1]
        idx = np.where((frequencies >= f_low) & (frequencies < f_high))[0]
        if len(idx) > 0:
            # Human ear treble loudness curve
            treble_boost = (f_high / 1000.0) ** 0.30
            band_energies[b] = np.mean(magnitude[idx], axis=0) * treble_boost

    # Logarithmic dynamic range compression (enhances quiet nuances while preserving loud peaks)
    band_energies = np.log1p(band_energies * 25.0)

    # Dynamic normalization per frequency band
    b_max = np.percentile(band_energies, 97, axis=1, keepdims=True)
    b_max[b_max < 1e-4] = 1e-4
    band_energies = np.clip(band_energies / b_max, 0.0, 1.6)

    # Transient response: instant attack (0.95), natural decay (0.22)
    smoothed = np.zeros_like(band_energies)
    attack = 0.95
    decay = 0.22

    for t_idx in range(band_energies.shape[1]):
        if t_idx == 0:
            smoothed[:, t_idx] = band_energies[:, t_idx]
        else:
            prev = smoothed[:, t_idx - 1]
            curr = band_energies[:, t_idx]
            smoothed[:, t_idx] = np.where(curr > prev, prev + attack * (curr - prev), prev - decay * prev)

    # Sub-bass/Kick envelope (first 10 bands: ~30-160 Hz)
    bass_env = np.mean(smoothed[:10], axis=0)
    bass_p95 = np.percentile(bass_env, 95)
    bass_env = np.clip(bass_env / (bass_p95 + 1e-4), 0.0, 1.6)

    # RMS volume envelope
    rms_env = np.mean(smoothed, axis=0)
    rms_p95 = np.percentile(rms_env, 95)
    rms_env = np.clip(rms_env / (rms_p95 + 1e-4), 0.0, 1.6)

    return {
        "sr": sr,
        "duration": duration,
        "total_frames": total_frames,
        "smoothed_bands": smoothed,
        "bass_env": bass_env,
        "rms_env": rms_env,
    }


class ParticleSystem:
    """
    Floating audio-reactive particles that emanate outward from the visualizer ring.
    Bursts outward on bass kicks!
    """
    def __init__(self, num_particles=100, base_radius=245, max_dist=240):
        self.num_particles = num_particles
        self.base_radius = base_radius
        self.max_dist = max_dist

        self.angles = np.random.uniform(0, 2 * np.pi, num_particles).astype(np.float32)
        self.dists = np.random.uniform(base_radius + 8, base_radius + max_dist, num_particles).astype(np.float32)
        self.speeds = np.random.uniform(0.8, 2.5, num_particles).astype(np.float32)
        self.swirls = np.random.uniform(-0.015, 0.015, num_particles).astype(np.float32)
        self.sizes = np.random.choice([1, 2, 3], size=num_particles, p=[0.55, 0.35, 0.10]).astype(np.int32)

    def update(self, bass_val, current_R):
        # Shockwave boost on bass kicks
        boost = 1.0 + 2.2 * (bass_val ** 1.5)
        self.dists += self.speeds * boost
        self.angles += self.swirls

        # Respawn particles that drift beyond max distance
        respawn = self.dists > (current_R + self.max_dist)
        if np.any(respawn):
            num_respawn = np.sum(respawn)
            self.dists[respawn] = current_R + np.random.uniform(3, 20, num_respawn)
            self.angles[respawn] = np.random.uniform(0, 2 * np.pi, num_respawn)
            self.speeds[respawn] = np.random.uniform(0.8, 2.2, num_respawn)

    def draw(self, canvas, rcx, rcy, current_R, color=(70, 215, 255)):
        roi_h, roi_w = canvas.shape[:2]
        norm_dist = (self.dists - current_R) / self.max_dist
        alphas = np.clip(1.0 - norm_dist, 0.1, 1.0)

        xs = rcx + self.dists * np.cos(self.angles)
        ys = rcy + self.dists * np.sin(self.angles)

        ix = np.round(xs).astype(np.int32)
        iy = np.round(ys).astype(np.int32)

        valid = (ix >= 0) & (ix < roi_w) & (iy >= 0) & (iy < roi_h)
        for i in np.where(valid)[0]:
            a = alphas[i]
            col = (int(color[0] * a), int(color[1] * a), int(color[2] * a))
            cv2.circle(canvas, (ix[i], iy[i]), int(self.sizes[i]), col, -1, lineType=cv2.LINE_AA)


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


def generate_ncs_video(
    audio_path,
    bg_path,
    output_path,
    fps=60,
    start_sec=0.0,
    duration=None,
    pos_x=None,
    pos_y=None,
    radius=245,
    color="auto",
    num_bars=96,
    max_bar_length=85,
    style="bars",  # 'bars' or 'wave'
    channel_name="Sypionx",
    title=None,
    crf=16,
):
    """
    Renders pure 100% audio-reactive visualizer video.
    Zero canned animations — bars, pulses, and waves directly track the audio spectrum.
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
    if title is None or not title:
        title = os.path.splitext(os.path.basename(audio_path))[0]

    # Draw bottom-left branding onto background
    bg = draw_bottom_left_branding(bg, channel_name=channel_name, song_title=title)

    # Standardized placement: Right-side in the negative space (subject is on the left)
    cx = pos_x if pos_x is not None else int(W * 0.741)
    cy = pos_y if pos_y is not None else int(H * 0.480)
    if radius is None or radius <= 0:
        radius = 245

    print(f"Canvas size: {W}x{H} | NCS Circle Center: ({cx}, {cy}) | Base Radius: {radius} (Diameter: {radius*2}) | FPS: {fps}", flush=True)

    # Audio analysis
    audio_info = load_and_analyze_audio(audio_path, fps=fps, num_bands=num_bars // 2)
    start_frame = int(start_sec * fps)
    if duration is not None and duration > 0:
        num_frames = int(duration * fps)
    else:
        num_frames = audio_info["total_frames"] - start_frame

    end_frame = min(start_frame + num_frames, audio_info["total_frames"])
    actual_frames = end_frame - start_frame
    actual_duration = actual_frames / fps

    print(f"Rendering Real-Time Reactive Visualizer: {start_sec:.2f}s -> {start_sec + actual_duration:.2f}s ({actual_frames} frames)...", flush=True)

    # Bounding ROI for fast local rendering
    max_reach = radius + max_bar_length + 200
    x1 = max(0, int(cx - max_reach))
    x2 = min(W, int(cx + max_reach))
    y1 = max(0, int(cy - max_reach))
    y2 = min(H, int(cy + max_reach))
    roi_w = x2 - x1
    roi_h = y2 - y1
    rcx = cx - x1
    rcy = cy - y1

    bg_roi_static = bg[y1:y2, x1:x2].copy()
    bg_roi_uint16 = (255 - bg_roi_static).astype(np.uint16)

    # Precalculate bar angles: symmetrical from bottom (bass) to top (highs)
    half_bars = num_bars // 2
    angles = np.linspace(-np.pi / 2, 3 * np.pi / 2, num_bars, endpoint=False, dtype=np.float32)
    cos_angles = np.cos(angles)
    sin_angles = np.sin(angles)

    # Symmetrical mapping indices: bass at bottom, highs at top
    mirror_idx = np.concatenate([np.arange(half_bars), np.arange(half_bars - 1, -1, -1)])

    # Initialize particle system
    particles = ParticleSystem(num_particles=100, base_radius=radius, max_dist=200)

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

    smoothed_bands = audio_info["smoothed_bands"]
    bass_env = audio_info["bass_env"]
    rms_env = audio_info["rms_env"]

    frame_out = bg.copy()
    saved_thumb = None
    thumb_target_frame = min(actual_frames - 1, int(max(2.0, min(actual_duration * 0.45, 7.0)) * fps))

    # Luminous light-color palette
    LIGHT_PALETTE = {
        "cyan": (242, 250, 140),       # Electric Cyan (BGR)
        "gold": (70, 215, 255),        # Radiant Daffodil / Sunflower Gold
        "yellow": (70, 235, 255),      # Neon Lemon Yellow
        "mint": (190, 255, 120),       # Cyber Spring Mint
        "pink": (210, 140, 255),       # Neon Rose Pink
        "lavender": (255, 160, 210),   # Soft Glowing Violet / Lavender
        "white": (255, 255, 255),      # Diamond Ice White
        "peach": (120, 190, 255),      # Warm Amber Peach
        "ice_blue": (255, 225, 160),   # Frosted Sky Blue
    }

    if isinstance(color, str):
        c_low = color.lower().strip()
        if c_low in ["auto", "random"]:
            import random
            color_name = random.choice(list(LIGHT_PALETTE.keys()))
            cyan_core = LIGHT_PALETTE[color_name]
            print(f"Auto-selected luminous NCS color: {color_name.upper()} {cyan_core}", flush=True)
        elif c_low in LIGHT_PALETTE:
            cyan_core = LIGHT_PALETTE[c_low]
        else:
            cyan_core = LIGHT_PALETTE["gold"]
    else:
        cyan_core = color

    for i in range(actual_frames):
        global_frame = start_frame + i
        stft_idx = min(global_frame, smoothed_bands.shape[1] - 1)
        frame_bands = smoothed_bands[:, stft_idx]
        bass_val = float(bass_env[stft_idx])
        rms_val = float(rms_env[stft_idx])

        # 1. Bass Heartbeat Pulse (expands tightly with kick drums)
        current_R = radius * (1.0 + 0.10 * bass_val)

        # Map frequencies symmetrically to bars
        # If quiet, bars shrink down to resting zero!
        bar_heights = frame_bands[mirror_idx] * max_bar_length * (0.80 + 0.40 * bass_val)

        # Local visualizer canvas
        vis_roi = np.zeros((roi_h, roi_w, 3), dtype=np.uint8)

        # 2. Draw Floating Particles (burst on bass)
        particles.update(bass_val, current_R)
        particles.draw(vis_roi, rcx, rcy, current_R, color=cyan_core)

        # 3. Draw Radial Audio Spectrum Bars (Classic NCS) or Smooth Wave
        if style == "bars":
            for b in range(num_bars):
                cos_a = cos_angles[b]
                sin_a = sin_angles[b]
                h = bar_heights[b]

                if h < 1.0:
                    continue

                # Base start of bar (right at ring edge)
                r1 = current_R + 3.0
                r2 = r1 + max(h, 4.0)

                p1 = (int(round(rcx + r1 * cos_a)), int(round(rcy + r1 * sin_a)))
                p2 = (int(round(rcx + r2 * cos_a)), int(round(rcy + r2 * sin_a)))

                # Bar thickness
                bar_thickness = 4
                cv2.line(vis_roi, p1, p2, cyan_core, bar_thickness, lineType=cv2.LINE_AA)
                # Rounded cap
                cv2.circle(vis_roi, p2, bar_thickness // 2, cyan_core, -1, lineType=cv2.LINE_AA)

        elif style == "wave":
            # Continuous fluid wave perimeter
            r_outer = current_R + 3.0 + bar_heights
            pts_out = np.stack([rcx + r_outer * cos_angles, rcy + r_outer * sin_angles], axis=1)
            pts_in = np.stack([rcx + current_R * cos_angles, rcy + current_R * sin_angles], axis=1)
            wave_poly = np.vstack([pts_out, pts_in[::-1]]).astype(np.int32)
            cv2.fillPoly(vis_roi, [wave_poly], cyan_core)

        # 4. Draw Center Ring (CLEAN interior, NO lines inside!)
        ring_thickness = int(round(5 + 3 * rms_val))
        cv2.circle(vis_roi, (rcx, rcy), int(round(current_R)), cyan_core, ring_thickness, lineType=cv2.LINE_AA)

        # Subtle inner accent ring
        inner_accent_r = int(round(current_R - 12))
        if inner_accent_r > 10:
            cv2.circle(vis_roi, (rcx, rcy), inner_accent_r, (255, 235, 140), 1, lineType=cv2.LINE_AA)

        # 5. Multi-Octave Neon Bloom
        w4, h4 = max(1, roi_w // 4), max(1, roi_h // 4)
        w8, h8 = max(1, roi_w // 8), max(1, roi_h // 8)

        s4 = cv2.resize(vis_roi, (w4, h4), interpolation=cv2.INTER_LINEAR)
        b4 = cv2.GaussianBlur(s4, (9, 9), 0)

        s8 = cv2.resize(vis_roi, (w8, h8), interpolation=cv2.INTER_LINEAR)
        b8 = cv2.GaussianBlur(s8, (19, 19), 0)

        bloom4 = cv2.resize(b4, (roi_w, roi_h), interpolation=cv2.INTER_LINEAR)
        bloom8 = cv2.resize(b8, (roi_w, roi_h), interpolation=cv2.INTER_LINEAR)

        bloom_pulse = 1.0 + 0.35 * bass_val
        vis_glowing = cv2.add(vis_roi, cv2.scaleAdd(bloom4, 0.85 * bloom_pulse, bloom8))

        # 6. Screen Blend directly onto Background
        vis_inv = (255 - vis_glowing).astype(np.uint16)
        comp_roi = 255 - ((bg_roi_uint16 * vis_inv) >> 8).astype(np.uint8)

        frame_out[y1:y2, x1:x2] = comp_roi

        if i == thumb_target_frame:
            saved_thumb = frame_out.copy()

        # Write frame
        try:
            proc.stdin.write(frame_out.tobytes())
        except (BrokenPipeError, OSError):
            break

        # Progress reporting
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
    parser = argparse.ArgumentParser(description="Render 100% Real-Time FFT Audio Reactive Visualizer")
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
        default=r"D:\E agy cli\E bots\music_visualizer\daffodil_reactive_60fps_15s.mp4",
        help="Path to output MP4",
    )
    parser.add_argument("--fps", type=int, default=60, help="Frames per second (default: 60)")
    parser.add_argument("--start-sec", type=float, default=4.0, help="Start time in seconds")
    parser.add_argument("--duration", type=float, default=15.0, help="Duration in seconds")
    parser.add_argument("--style", choices=["bars", "wave"], default="bars", help="Spectrum style: bars or wave")
    parser.add_argument("--color", default="gold", help="Visualizer neon color: gold, cyan, yellow, mint, pink, lavender, white, peach, ice_blue")
    parser.add_argument("--channel", default="Sypionx", help="Channel name branding (default: Sypionx)")
    parser.add_argument("--title", default="", help="Song title (default: auto from audio filename)")
    parser.add_argument("--pos-x", type=int, default=None, help="Visualizer center X (default: right-side ~74%%)")
    parser.add_argument("--pos-y", type=int, default=None, help="Visualizer center Y (default: ~48%%)")
    parser.add_argument("--radius", type=int, default=245, help="Base visualizer radius (default: 245 -> diameter 490)")

    args = parser.parse_args()

    generate_ncs_video(
        audio_path=args.audio,
        bg_path=args.bg,
        output_path=args.output,
        fps=args.fps,
        start_sec=args.start_sec,
        duration=args.duration,
        pos_x=args.pos_x,
        pos_y=args.pos_y,
        radius=args.radius,
        color=args.color,
        style=args.style,
        channel_name=args.channel,
        title=args.title,
    )


if __name__ == "__main__":
    main()
