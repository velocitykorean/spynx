"""
Text Overlay Generator - Sleek Centered Typography (spyionx)
Includes channel name & official release tag with pixel-perfect center alignment (anchor='mm') and equidistant margins.
"""
import os
import sys
from PIL import Image, ImageDraw, ImageFilter
from font_manager import get_font


def create_viral_centered_overlay(song_name, channel_name="sypionx", width=1920, height=1080):
    """
    Equidistant & Dead-Centered Typography:
    1. Subtitle: SYPIONX   •   OFFICIAL RELEASE (Gold fill, Montserrat-Bold 18px)
    2. Song Name: Pure centered song title (Outfit-Bold 42px)
    3. Mathematical dead-center alignment (anchor='mm')
    """
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    # Refined Fonts
    title_font = get_font("Outfit-Bold.ttf", 42)
    subtitle_font = get_font("Montserrat-Bold.ttf", 18)

    subtitle_text = f"{channel_name.upper()}   •   OFFICIAL RELEASE"
    title_text = song_name.upper()

    # Exact bounding box measurements
    t_bbox = title_font.getbbox(title_text)
    t_w = t_bbox[2] - t_bbox[0]
    t_h = t_bbox[3] - t_bbox[1]

    s_bbox = subtitle_font.getbbox(subtitle_text)
    s_w = s_bbox[2] - s_bbox[0]
    s_h = s_bbox[3] - s_bbox[1]

    max_w = max(t_w, s_w)

    # Equidistant padding and spacing
    pad_h = 48   # Left & Right padding
    pad_v = 24   # Top & Bottom padding
    gap_v = 14   # Vertical gap between subtitle and main song title

    card_w = max_w + pad_h * 2
    card_h = s_h + gap_v + t_h + pad_v * 2

    cx, cy = width // 2, height // 2
    card_x1 = cx - card_w // 2
    card_y1 = cy - card_h // 2
    card_x2 = cx + card_w // 2
    card_y2 = cy + card_h // 2

    # 1. Subtle Gaussian Blur Shadow
    shadow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    box_rect = [card_x1, card_y1, card_x2, card_y2]
    s_draw.rounded_rectangle(box_rect, radius=16, fill=(0, 0, 0, 170))
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    img = Image.alpha_composite(img, shadow)

    draw = ImageDraw.Draw(img)

    # 2. Sleek Equidistant Dark Capsule Badge
    draw.rounded_rectangle(box_rect, radius=14, fill=(12, 14, 22, 140), outline=(255, 200, 40, 150), width=2)

    # 3. Y positions with exact vertical center distribution
    sub_center_y = card_y1 + pad_v + s_h // 2
    title_center_y = sub_center_y + s_h // 2 + gap_v + t_h // 2

    # 4. Render Subtitle with PIL anchor='mm' (Middle-Middle Dead Center)
    draw.text((cx, sub_center_y), subtitle_text, font=subtitle_font, fill=(255, 200, 40, 240), anchor="mm")

    # 5. Render Main Song Title with PIL anchor='mm' (Middle-Middle Dead Center)
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        draw.text((cx + dx, title_center_y + dy), title_text, font=title_font, fill=(0, 0, 0, 230), anchor="mm")
    draw.text((cx, title_center_y), title_text, font=title_font, fill=(255, 255, 255, 255), anchor="mm")

    return img


import re

def create_bottom_left_overlay(song_name, channel_name="sypionx", width=1920, height=1080):
    """
    Bottom-Left Typography:
    1. Channel Branding: SYPIONX • OFFICIAL RELEASE (Radiant Gold, Outfit-Bold)
    2. Song Title: Clean Song Name without track numbers (Crisp White, Montserrat-Bold)
    3. Positioned at bottom-left corner with glowing shadow for 100% legibility on any background.
    """
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    # Strip leading track numbers like "05 - ", "01. ", "02_"
    clean_title = re.sub(r'^\s*\d+[\s\.\-_]+', '', song_name).strip()
    clean_title = clean_title.replace('_', ' ').replace(' - ', ' ').strip()
    clean_title = ' '.join(w.capitalize() for w in clean_title.split())

    scale = height / 1080.0
    channel_size = max(18, int(22 * scale * 1.15))
    title_size = max(24, int(42 * scale * 1.15))

    title_font = get_font("Montserrat-Bold.ttf", title_size)
    channel_font = get_font("Outfit-Bold.ttf", channel_size)

    channel_text = f"{channel_name.upper()}   •   OFFICIAL RELEASE"
    title_text = clean_title

    pos_x = int(width * 0.055)
    bottom_y = int(height * 0.92)

    t_bbox = title_font.getbbox(title_text)
    t_h = t_bbox[3] - t_bbox[1]

    c_bbox = channel_font.getbbox(channel_text)
    c_h = c_bbox[3] - c_bbox[1]

    title_y = bottom_y - t_h
    chan_y = title_y - c_h - int(12 * scale)

    # 1. Subtle Gaussian Blur Shadow Layer
    shadow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)

    for dx, dy in [(-3, 0), (3, 0), (0, -3), (0, 3), (-3, -3), (3, 3), (0, 4)]:
        s_draw.text((pos_x + dx, chan_y + dy), channel_text, font=channel_font, fill=(0, 0, 0, 220))
        s_draw.text((pos_x + dx, title_y + dy), title_text, font=title_font, fill=(0, 0, 0, 240))

    shadow = shadow.filter(ImageFilter.GaussianBlur(6))
    img = Image.alpha_composite(img, shadow)

    draw = ImageDraw.Draw(img)

    # 2. Render Text
    # Gold Channel Branding
    draw.text((pos_x, chan_y), channel_text, font=channel_font, fill=(255, 215, 70, 245))
    # Crisp White Song Title
    draw.text((pos_x, title_y), title_text, font=title_font, fill=(255, 255, 255, 255))

    return img


def create_stretched_text_image(text, output_path, width=1920, height=1080, preset="bottom_left", channel_name="sypionx", **kwargs):
    """
    Main entry point for generating text overlay image.
    Defaults to bottom-left layout to leave subject and visualizer unobstructed.
    """
    print(f"[TextOverlay] Generating bottom-left overlay for song: '{text}' (Channel: {channel_name})")
    if preset == "centered":
        img = create_viral_centered_overlay(text, channel_name, width, height)
    else:
        img = create_bottom_left_overlay(text, channel_name, width, height)

    img.save(output_path, 'PNG')
    print(f"[TextOverlay] Text overlay saved to {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python create_text_overlay.py 'Song Name' [output_path] [preset]")
        sys.exit(1)

    text = sys.argv[1]
    output = sys.argv[2] if len(sys.argv) > 2 else "text_overlay.png"
    preset = sys.argv[3] if len(sys.argv) > 3 else "modern_glass"
    create_stretched_text_image(text, output, preset=preset)
