"""Generate SolarRT Android launcher icons and splash screens (replaces Capacitor's defaults).

Run from anywhere:  python mobile/make_android_assets.py   (needs Pillow)
Uses the same artwork as packaging/make_icon.py (desktop icon) so all editions match.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "packaging"))
from make_icon import arc, bezier, lerp  # noqa: E402  (shared drawing helpers)

RES = HERE / "android" / "app" / "src" / "main" / "res"
BG = (11, 18, 32, 255)          # icon tile colour (#0B1220)
SPLASH_BG = (7, 11, 20, 255)    # app background (#070B14)
S = 1024


def artwork(size: int = S, scale: float = 1.0) -> Image.Image:
    """The aurora arcs + sun on a transparent canvas; scale < 1 shrinks it into the centre."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    green, violet = (43, 217, 138, 255), (138, 92, 255, 255)
    arc(d, bezier((6, 44), (16, 30), (26, 22), (34, 22)), 7 * S // 64, lambda t: lerp(green, violet, t))
    arc(d, bezier((34, 22), (42, 22), (50, 28), (58, 36)), 7 * S // 64, lambda t: lerp(violet, green, t * 0.3))
    arc(d, bezier((10, 52), (19, 43), (27, 38), (34, 38)), 4 * S // 64, lambda t: (43, 217, 138, 150))
    arc(d, bezier((34, 38), (41, 38), (47, 42), (54, 47)), 4 * S // 64, lambda t: (43, 217, 138, 150))
    cx, cy, r = 48 * S / 64, 14 * S / 64, 4 * S / 64
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 209, 102, 255))
    if scale != 1.0:
        inner = img.resize((int(S * scale), int(S * scale)), Image.LANCZOS)
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        img.alpha_composite(inner, ((S - inner.width) // 2, (S - inner.height) // 2))
    return img.resize((size, size), Image.LANCZOS)


def tile(shape: str) -> Image.Image:
    base = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    if shape == "round":
        d.ellipse([0, 0, S - 1, S - 1], fill=BG)
        art = artwork(scale=0.72)
    else:
        d.rounded_rectangle([0, 0, S - 1, S - 1], radius=S // 5, fill=BG)
        art = artwork(scale=0.86)
    base.alpha_composite(art)
    return base


def main() -> None:
    legacy = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    square, round_ = tile("square"), tile("round")
    # Adaptive icon foreground: 108dp canvas, artwork kept inside the 66dp safe zone.
    fg = artwork(scale=0.58)
    for density, px in legacy.items():
        folder = RES / f"mipmap-{density}"
        square.resize((px, px), Image.LANCZOS).save(folder / "ic_launcher.png")
        round_.resize((px, px), Image.LANCZOS).save(folder / "ic_launcher_round.png")
        fg_px = px * 108 // 48
        fg.resize((fg_px, fg_px), Image.LANCZOS).save(folder / "ic_launcher_foreground.png")

    (RES / "values" / "ic_launcher_background.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="ic_launcher_background">#0B1220</color>\n</resources>\n', encoding="utf-8")

    # Notification (status-bar) icon: Android draws it as a white silhouette, so use the
    # artwork's alpha only, in the standard 24dp sizes.
    silhouette = artwork(scale=0.9)
    white = Image.new("RGBA", silhouette.size, (255, 255, 255, 0))
    white.putalpha(silhouette.getchannel("A"))
    for density, px in {"mdpi": 24, "hdpi": 36, "xhdpi": 48, "xxhdpi": 72, "xxxhdpi": 96}.items():
        folder = RES / f"drawable-{density}"
        folder.mkdir(exist_ok=True)
        white.resize((px, px), Image.LANCZOS).save(folder / "ic_stat_solarrt.png")

    # Splash screens: dark background with the icon centred, at every existing size.
    for png in RES.glob("drawable*/splash.png"):
        w, h = Image.open(png).size
        splash = Image.new("RGBA", (w, h), SPLASH_BG)
        icon_px = int(min(w, h) * 0.32)
        icon = square.resize((icon_px, icon_px), Image.LANCZOS)
        splash.alpha_composite(icon, ((w - icon_px) // 2, (h - icon_px) // 2))
        splash.convert("RGB").save(png)
    print("Android icons and splash screens written to", RES)


if __name__ == "__main__":
    main()
