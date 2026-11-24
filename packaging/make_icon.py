"""Render the SolarRT app icon (same design as static/favicon.svg) to packaging/solarrt.ico."""

from pathlib import Path

from PIL import Image, ImageDraw

S = 1024  # draw large, then downsample for smooth edges


def lerp(a, b, t):
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


def arc(draw, pts, width, color_fn):
    for i in range(len(pts) - 1):
        draw.line([pts[i], pts[i + 1]], fill=color_fn(i / (len(pts) - 1)), width=width)
        r = width // 2
        x, y = pts[i]
        draw.ellipse([x - r, y - r, x + r, y + r], fill=color_fn(i / (len(pts) - 1)))


def bezier(p0, p1, p2, p3, n=200):
    out = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t ** 2 * p2[0] + t ** 3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t ** 2 * p2[1] + t ** 3 * p3[1]
        out.append((x * S / 64, y * S / 64))
    return out


def main() -> None:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, S - 1, S - 1], radius=14 * S // 64, fill=(11, 18, 32, 255))
    green, violet = (43, 217, 138, 255), (138, 92, 255, 255)
    arc(d, bezier((6, 44), (16, 30), (26, 22), (34, 22)), 7 * S // 64, lambda t: lerp(green, violet, t))
    arc(d, bezier((34, 22), (42, 22), (50, 28), (58, 36)), 7 * S // 64, lambda t: lerp(violet, green, t * 0.3))
    arc(d, bezier((10, 52), (19, 43), (27, 38), (34, 38)), 4 * S // 64, lambda t: (43, 217, 138, 150))
    arc(d, bezier((34, 38), (41, 38), (47, 42), (54, 47)), 4 * S // 64, lambda t: (43, 217, 138, 150))
    cx, cy, r = 48 * S / 64, 14 * S / 64, 4 * S / 64
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 209, 102, 255))

    out = Path(__file__).with_name("solarrt.ico")
    img.resize((256, 256), Image.LANCZOS).save(
        out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    img.resize((256, 256), Image.LANCZOS).save(out.with_suffix(".png"))
    print("wrote", out)


if __name__ == "__main__":
    main()
