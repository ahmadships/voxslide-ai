"""Generate a proper multi-size Windows icon.ico for VoxSlide AI.

Reads icon_source_backup.png (the artwork) if present, otherwise falls
back to regenerating the legacy mic glyph. Always writes a real ICO with
sizes 16/32/48/64/128/256 next to this script.
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
OUT = HERE / "icon.ico"
SOURCE = HERE / "icon_source_backup.png"

BG = (15, 23, 42, 255)        # #0F172A - dark background (legacy fallback)
ACCENT = (37, 99, 235, 255)   # #2563EB - blue (legacy fallback)

SIZES = [16, 32, 48, 64, 128, 256]


def rounded_rect(draw, xy, radius, fill):
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def draw_mic_icon(size: int) -> Image.Image:
    """Draw the legacy microphone glyph (fallback only)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(1, int(size * 0.08))
    radius = max(2, int(size * 0.22))

    rounded_rect(
        draw,
        (pad, pad, size - pad, size - pad),
        radius=radius,
        fill=BG,
    )

    cx = size / 2
    cap_w = size * 0.30
    cap_h = size * 0.42
    cap_top = size * 0.18
    cap_x0 = cx - cap_w / 2
    cap_x1 = cx + cap_w / 2
    cap_y0 = cap_top
    cap_y1 = cap_top + cap_h
    cap_radius = cap_w / 2
    rounded_rect(draw, (cap_x0, cap_y0, cap_x1, cap_y1), radius=cap_radius, fill=ACCENT)

    arc_pad = size * 0.06
    arc_box = (cap_x0 - arc_pad, cap_y0 + arc_pad * 0.3, cap_x1 + arc_pad, cap_y1 + cap_h * 0.55)
    arc_w = max(2, int(size * 0.075))
    draw.arc(arc_box, start=20, end=160, fill=ACCENT, width=arc_w)

    stem_w = max(2, int(size * 0.075))
    stem_top = arc_box[3] - arc_w
    stem_bottom = size * 0.82
    draw.rectangle(
        (cx - stem_w / 2, stem_top, cx + stem_w / 2, stem_bottom),
        fill=ACCENT,
    )

    base_w = size * 0.30
    base_h = max(2, int(size * 0.075))
    draw.rectangle(
        (cx - base_w / 2, stem_bottom - base_h / 2, cx + base_w / 2, stem_bottom + base_h / 2),
        fill=ACCENT,
    )

    return img


def from_source_png(path: Path) -> Image.Image:
    """Crop white background from source art and pad to a transparent square."""
    src = Image.open(path).convert("RGBA")
    w, h = src.size
    pixels = src.load()

    def is_bg(p):
        return p[0] > 245 and p[1] > 245 and p[2] > 245

    minx, miny, maxx, maxy = w, h, 0, 0
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    op = out.load()
    for y in range(h):
        for x in range(w):
            p = pixels[x, y]
            if is_bg(p):
                continue
            op[x, y] = p
            if x < minx:
                minx = x
            if y < miny:
                miny = y
            if x > maxx:
                maxx = x
            if y > maxy:
                maxy = y

    cropped = out.crop((minx, miny, maxx + 1, maxy + 1))
    cw, ch = cropped.size
    side = max(cw, ch)
    pad = int(side * 0.06)
    side = side + pad * 2
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(cropped, ((side - cw) // 2, (side - ch) // 2), cropped)
    return square


def main():
    if SOURCE.is_file():
        base = from_source_png(SOURCE)
        print(f"Using source artwork: {SOURCE}")
    else:
        base = draw_mic_icon(256)
        print("No source PNG found; using legacy mic glyph")

    base.save(OUT, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Wrote {OUT} with sizes {SIZES}")


if __name__ == "__main__":
    main()
