"""
Particle Overlay Generator - Ultra Subtle Ambient Dust & Light Specks
Generates tiny, delicate, slow-floating ambient dust motes that drift peacefully.
"""
import os
import random
import math
import subprocess
from PIL import Image, ImageDraw, ImageFilter


def generate_particle_loop_video(output_mp4="particles_loop.mp4", width=1920, height=1080, fps=30, duration=8, num_particles=130):
    """
    Generates a seamless 8-second MP4 video of tiny, ultra-slow floating dust specks.
    """
    if os.path.exists(output_mp4):
        print(f"[Particles] Removing old particle loop for fresh generation: {output_mp4}")
        try:
            os.remove(output_mp4)
        except Exception:
            pass

    print(f"[Particles] Generating {duration}s ultra-slow ambient dust loop ({width}x{height}, {num_particles} specks)...")

    frames_dir = "_temp_particle_frames"
    os.makedirs(frames_dir, exist_ok=True)

    total_frames = fps * duration

    # Generate tiny, slow particle seeds
    particles = []
    for _ in range(num_particles):
        particles.append({
            'x_base': random.randint(20, width - 20),
            'y_start': random.randint(0, height),
            'radius': random.uniform(1.0, 2.5),        # Tiny specks
            'speed_y': random.uniform(5.0, 16.0),       # Very slow upward drift
            'sway_amp': random.uniform(10.0, 30.0),     # Soft horizontal sway
            'sway_freq': random.uniform(0.2, 0.8),      # Slow gentle sway speed
            'alpha': random.randint(40, 140),           # Soft subtle opacity
            'color': random.choice([
                (255, 245, 220),  # Soft warm gold
                (230, 240, 255),  # Soft starlight white
                (255, 230, 210),  # Subtle amber
                (210, 235, 255)   # Subtle cyan
            ])
        })

    for f in range(total_frames):
        t = f / fps
        img = Image.new('RGB', (width, height), (0, 0, 0))
        draw = ImageDraw.Draw(img)

        for p in particles:
            # Y position (seamless vertical wrap)
            y = (p['y_start'] - p['speed_y'] * t) % height
            # X position with gentle sinusoidal sway
            x = (p['x_base'] + math.sin(t * p['sway_freq'] * math.pi * 2) * p['sway_amp']) % width

            # Pulsing alpha for twinkling effect
            pulse = (math.sin(t * 1.2 + p['x_base']) + 1) / 2
            current_alpha = int(p['alpha'] * (0.5 + 0.5 * pulse))

            r = p['radius']
            r_glow = r * 2.2
            r_color = p['color']

            # Soft outer halo
            halo_color = (int(r_color[0] * current_alpha / 255 * 0.3),
                          int(r_color[1] * current_alpha / 255 * 0.3),
                          int(r_color[2] * current_alpha / 255 * 0.3))
            draw.ellipse([x - r_glow, y - r_glow, x + r_glow, y + r_glow], fill=halo_color)

            # Tiny core speck
            core_color = (int(r_color[0] * current_alpha / 255),
                          int(r_color[1] * current_alpha / 255),
                          int(r_color[2] * current_alpha / 255))
            draw.ellipse([x - r, y - r, x + r, y + r], fill=core_color)

        # Subtle blur for organic glow
        img = img.filter(ImageFilter.GaussianBlur(0.6))

        frame_path = os.path.join(frames_dir, f"frame_{f:04d}.png")
        img.save(frame_path)

    # Encode frames with FFmpeg to MP4
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(frames_dir, "frame_%04d.png"),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        output_mp4
    ]

    subprocess.run(cmd, capture_output=True)

    # Cleanup temp frame images
    for f in range(total_frames):
        fp = os.path.join(frames_dir, f"frame_{f:04d}.png")
        if os.path.exists(fp):
            os.remove(fp)
    if os.path.exists(frames_dir):
        try:
            os.rmdir(frames_dir)
        except Exception:
            pass

    print(f"[Particles] Ambient particle loop created: {output_mp4}")
    return output_mp4


if __name__ == "__main__":
    generate_particle_loop_video()
