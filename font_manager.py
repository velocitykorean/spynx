"""
Font Manager & Downloader
Handles fetching open-source Google Fonts from CDN and providing fallbacks.
"""
import os
import urllib.request
from PIL import ImageFont

FONTS_DIR = os.path.join(os.path.dirname(__file__), "fonts")

FONT_URLS = {
    "Montserrat-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/montserrat@latest/latin-700-normal.ttf",
    "Montserrat-Regular.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/montserrat@latest/latin-400-normal.ttf",
    "Cinzel-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/cinzel@latest/latin-700-normal.ttf",
    "PlayfairDisplay-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/playfair-display@latest/latin-700-normal.ttf",
    "Outfit-Bold.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/outfit@latest/latin-700-normal.ttf",
    "BebasNeue-Regular.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/bebas-neue@latest/latin-400-normal.ttf",
    "Poppins-Medium.ttf": "https://cdn.jsdelivr.net/fontsource/fonts/poppins@latest/latin-500-normal.ttf"
}

SYSTEM_FALLBACKS = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/georgia.ttf",
    "C:/Windows/Fonts/bahnschrift.ttf",
    "C:/Windows/Fonts/arial.ttf"
]


def ensure_fonts_exist():
    """Ensure font files are downloaded locally."""
    os.makedirs(FONTS_DIR, exist_ok=True)
    for font_name, url in FONT_URLS.items():
        dest = os.path.join(FONTS_DIR, font_name)
        if not os.path.exists(dest) or os.path.getsize(dest) == 0:
            try:
                print(f"[FontManager] Downloading {font_name}...")
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as resp, open(dest, 'wb') as f:
                    f.write(resp.read())
            except Exception as e:
                print(f"[FontManager] Could not download {font_name}: {e}")


def get_font(font_filename, size=48):
    """
    Get an ImageFont object for the requested filename,
    falling back gracefully if missing.
    """
    ensure_fonts_exist()
    target_path = os.path.join(FONTS_DIR, font_filename)

    if os.path.exists(target_path):
        try:
            return ImageFont.truetype(target_path, size)
        except Exception as e:
            print(f"[FontManager] Error loading {target_path}: {e}")

    # Fallback to system fonts
    for sys_font in SYSTEM_FALLBACKS:
        if os.path.exists(sys_font):
            try:
                return ImageFont.truetype(sys_font, size)
            except Exception:
                continue

    return ImageFont.load_default()
