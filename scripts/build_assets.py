"""Generate card face PNGs, multiple card backs, and player avatars.

Outputs to:
  assets/cards/face/  (52 PNGs: 2c.png, 2d.png, ..., As.png, Ah.png)
  assets/cards/backs/ (8 distinct back designs: back_01.png .. back_08.png)
  assets/avatars/     (6 stylized avatar PNGs: 01.png .. 06.png)
  assets/table/       (table felt background: felt.png)
"""

from __future__ import annotations

import os
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"

CARD_W, CARD_H = 86, 124  # standard playing-card aspect

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

SUIT_COLORS = {
    "♣": (20, 20, 20),     # black
    "♦": (200, 30, 30),    # red
    "♥": (200, 30, 30),    # red
    "♠": (20, 20, 20),     # black
}
RANK_SHORT = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6", 7: "7", 8: "8",
    9: "9", 10: "10", 11: "J", 12: "Q", 13: "K", 14: "A",
}
SUIT_GLYPH = {"c": "♣", "d": "♦", "s": "♠", "h": "♥"}
SUIT_LETTER = {"♣": "c", "♦": "d", "♠": "s", "♥": "h"}


def find_font(size: int):
    """Find a usable system font."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def round_rect(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None,
               width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline,
                            width=width)


# ---------------------------------------------------------------------------
# Card faces
# ---------------------------------------------------------------------------

def render_face(rank: int, suit_letter: str) -> Image.Image:
    """Render a single card face with corner indices and a centre pip.

    suit_letter is one of 'c', 'd', 's', 'h'.
    """
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Card body.
    round_rect(draw, (0, 0, CARD_W - 1, CARD_H - 1), radius=10,
               fill=(250, 250, 248), outline=(40, 40, 40), width=2)
    # Inner border.
    round_rect(draw, (3, 3, CARD_W - 4, CARD_H - 4), radius=8,
               fill=None, outline=(180, 180, 180), width=1)
    glyph = SUIT_GLYPH[suit_letter]
    color = SUIT_COLORS[glyph]
    short = RANK_SHORT[rank]
    # Top-left corner.
    small = find_font(18)
    draw.text((6, 4), short, font=small, fill=color)
    draw.text((6, 22), glyph, font=small, fill=color)
    # Bottom-right corner (rotated).
    big = find_font(64)
    # Centre pip — large suit glyph.
    cx, cy = CARD_W // 2, CARD_H // 2 + 6
    bbox = draw.textbbox((0, 0), glyph, font=big)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - tw // 2 - bbox[0], cy - th // 2 - bbox[1]),
              glyph, font=big, fill=color)
    return img


def render_all_faces():
    out = ASSETS / "cards" / "face"
    out.mkdir(parents=True, exist_ok=True)
    for suit_letter in SUIT_GLYPH:
        for rank in range(2, 15):
            img = render_face(rank, suit_letter)
            img.save(out / f"{rank}{suit_letter}.png")
    print(f"  wrote 52 faces → {out}")


# ---------------------------------------------------------------------------
# Card backs — 8 distinct designs
# ---------------------------------------------------------------------------

BACK_PALETTES = [
    ((15, 70, 35), (220, 200, 80), "argyle"),
    ((60, 25, 90), (220, 160, 220), "stars"),
    ((140, 30, 30), (240, 220, 160), "floral"),
    ((20, 45, 80), (200, 230, 250), "waves"),
    ((35, 35, 35), (240, 240, 240), "checker"),
    ((90, 50, 20), (240, 200, 130), "leopard"),
    ((40, 80, 80), (220, 240, 220), "tiles"),
    ((25, 60, 25), (200, 240, 140), "swirl"),
]


def render_back(idx: int, bg, fg, style: str) -> Image.Image:
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    round_rect(draw, (0, 0, CARD_W - 1, CARD_H - 1), radius=10,
               fill=bg, outline=(10, 10, 10), width=2)
    round_rect(draw, (5, 5, CARD_W - 6, CARD_H - 6), radius=7,
               fill=None, outline=fg, width=1)
    # Design layer.
    if style == "argyle":
        # Diagonal lines.
        for i in range(-CARD_H, CARD_W + CARD_H, 18):
            draw.line([(i, 0), (i + CARD_H, CARD_H)], fill=fg, width=1)
        for i in range(-CARD_H, CARD_W + CARD_H, 18):
            draw.line([(i, CARD_H), (i + CARD_H, 0)], fill=fg, width=1)
    elif style == "stars":
        rng = random.Random(idx)
        for _ in range(28):
            x = rng.randint(8, CARD_W - 8)
            y = rng.randint(8, CARD_H - 8)
            r = rng.randint(2, 4)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=fg)
    elif style == "floral":
        # Simple flower pattern.
        cx, cy = CARD_W // 2, CARD_H // 2
        for ang in (0, 60, 120, 180, 240, 300):
            import math
            rad = math.radians(ang)
            x = cx + int(20 * math.cos(rad))
            y = cy + int(20 * math.sin(rad))
            draw.ellipse((x - 10, y - 10, x + 10, y + 10), fill=fg)
        draw.ellipse((cx - 8, cy - 8, cx + 8, cy + 8), fill=bg)
    elif style == "waves":
        for y in range(8, CARD_H - 8, 8):
            pts = []
            for x in range(0, CARD_W + 8, 8):
                pts.append((x, y + 4 * (1 if (x // 8) % 2 == 0 else -1)))
            draw.line(pts, fill=fg, width=1)
    elif style == "checker":
        sz = 12
        for r in range(0, CARD_H, sz):
            for c in range(0, CARD_W, sz):
                if (r // sz + c // sz) % 2 == 0:
                    draw.rectangle((c + 6, r + 6, c + sz, r + sz), fill=fg)
    elif style == "leopard":
        rng = random.Random(idx * 7)
        for _ in range(40):
            x = rng.randint(8, CARD_W - 12)
            y = rng.randint(8, CARD_H - 12)
            r = rng.randint(2, 5)
            draw.ellipse((x - r, y - r, x + r, y + r), fill=fg)
    elif style == "tiles":
        sz = 16
        for r in range(8, CARD_H - 8, sz):
            for c in range(8, CARD_W - 8, sz):
                draw.rectangle((c, r, c + sz - 2, r + sz - 2),
                               outline=fg, width=1)
    elif style == "swirl":
        import math
        for t in range(0, 360, 6):
            rad = math.radians(t)
            x = CARD_W // 2 + int(28 * math.cos(rad + t * 0.05))
            y = CARD_H // 2 + int(40 * math.sin(rad + t * 0.05))
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=fg)
    return img


def render_all_backs():
    out = ASSETS / "cards" / "backs"
    out.mkdir(parents=True, exist_ok=True)
    for i, (bg, fg, style) in enumerate(BACK_PALETTES, start=1):
        img = render_back(i, bg, fg, style)
        img.save(out / f"back_{i:02d}.png")
    print(f"  wrote 8 backs → {out}")


# ---------------------------------------------------------------------------
# Avatars — 6 stylized portraits
# ---------------------------------------------------------------------------

AVATAR_PALETTES = [
    ((200, 120, 90), (60, 30, 20), "warm"),
    ((110, 160, 200), (20, 40, 60), "cool"),
    ((160, 200, 100), (40, 60, 20), "earth"),
    ((220, 180, 90), (60, 40, 20), "sunset"),
    ((180, 100, 200), (40, 20, 60), "royal"),
    ((100, 220, 200), (20, 60, 60), "ocean"),
]


def render_avatar(idx: int, primary, dark, mood: str) -> Image.Image:
    size = 96
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    # Circle background.
    draw.ellipse((2, 2, size - 3, size - 3), fill=primary, outline=dark, width=3)
    # Inner ring decoration.
    draw.ellipse((10, 10, size - 11, size - 11), outline=dark, width=1)
    # Face: simple stylised silhouette.
    cx, cy = size // 2, size // 2 + 4
    # Head.
    head_r = 22
    draw.ellipse((cx - head_r, cy - head_r, cx + head_r, cy + head_r),
                 fill=dark)
    # Body.
    body_top = cy + head_r - 4
    draw.pieslice((cx - 30, body_top, cx + 30, body_top + 60),
                  180, 360, fill=dark)
    # Eyes — tiny dots on the head.
    eye_y = cy - 4
    draw.ellipse((cx - 8 - 2, eye_y - 2, cx - 8 + 2, eye_y + 2),
                 fill=(255, 255, 255))
    draw.ellipse((cx + 8 - 2, eye_y - 2, cx + 8 + 2, eye_y + 2),
                 fill=(255, 255, 255))
    return img


def render_all_avatars():
    out = ASSETS / "avatars"
    out.mkdir(parents=True, exist_ok=True)
    for i, (primary, dark, mood) in enumerate(AVATAR_PALETTES, start=1):
        img = render_avatar(i, primary, dark, mood)
        img.save(out / f"avatar_{i:02d}.png")
    print(f"  wrote 6 avatars → {out}")


# ---------------------------------------------------------------------------
# Table felt
# ---------------------------------------------------------------------------

def render_table():
    out = ASSETS / "table"
    out.mkdir(parents=True, exist_ok=True)
    w, h = 1280, 800
    img = Image.new("RGB", (w, h), (10, 60, 35))
    draw = ImageDraw.Draw(img)
    # Felt noise.
    rng = random.Random(7)
    for _ in range(8000):
        x = rng.randint(0, w - 1)
        y = rng.randint(0, h - 1)
        v = rng.randint(20, 80)
        draw.point((x, y), fill=(8, 50 + v // 4, 28 + v // 6))
    # Vignette — radial darken at the edges using a Gaussian-blurred mask.
    vignette = Image.new("L", (w, h), 255)
    vd = ImageDraw.Draw(vignette)
    max_r = min(w, h) // 2
    for r in range(0, max_r, 8):
        inset = r
        grey = max(0, 255 - r * 2 // 3)
        vd.ellipse((inset, inset, w - inset, h - inset),
                   outline=grey, width=8)
    blurred = vignette.filter(ImageFilter.GaussianBlur(80))
    dark = Image.new("RGB", (w, h), (0, 0, 0))
    img = Image.composite(img, dark, blurred)
    img.save(out / "felt.png")
    print(f"  wrote table felt → {out / 'felt.png'}")


# ---------------------------------------------------------------------------

def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    print("Generating card assets...")
    render_all_faces()
    render_all_backs()
    render_all_avatars()
    render_table()
    print("Done.")


if __name__ == "__main__":
    main()
