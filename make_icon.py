# -*- coding: utf-8 -*-
"""Create a multi-size .ico file and a few PNG preview suggestions for Desktop Icon Studio."""
from PIL import Image, ImageDraw


def rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def design_1(size=256):
    """Dark modern monitor with colorful desktop icons."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size // 12
    # background rounded square gradient-ish (solid dark)
    rounded_rect(d, (pad, pad, size - pad, size - pad), size // 10,
                 fill=(28, 30, 38, 255), outline=(60, 65, 80, 255), width=size // 80)
    # monitor stand
    mw = size * 0.6
    mh = size * 0.42
    mx = (size - mw) / 2
    my = size * 0.22
    rounded_rect(d, (mx, my, mx + mw, my + mh), size // 40,
                 fill=(16, 18, 24, 255), outline=(90, 95, 110, 255), width=size // 120)
    # stand base
    bw = mw * 0.3
    bh = size * 0.05
    bx = (size - bw) / 2
    by = my + mh
    rounded_rect(d, (bx, by, bx + bw, by + bh), size // 80, fill=(90, 95, 110, 255))
    # colorful icons inside monitor
    icon_s = size * 0.08
    colors = [(255, 99, 132), (54, 162, 235), (255, 206, 86),
              (75, 192, 192), (153, 102, 255), (255, 159, 64)]
    cols = 4
    start_x = mx + mw * 0.12
    start_y = my + mh * 0.12
    gap_x = (mw * 0.76 - icon_s) / (cols - 1)
    gap_y = size * 0.09
    for idx in range(8):
        c = idx % cols
        r = idx // cols
        ix = start_x + c * gap_x
        iy = start_y + r * gap_y
        rounded_rect(d, (ix, iy, ix + icon_s, iy + icon_s), size // 80,
                     fill=colors[idx % len(colors)], outline=(255, 255, 255, 80), width=1)
    return img


def design_2(size=256):
    """Glassmorphism circle with floating icon grid."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # circle bg
    r = size * 0.42
    cx = cy = size / 2
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(20, 30, 60, 255),
              outline=(80, 120, 200, 255), width=size // 50)
    # grid of small squares
    icon_s = size * 0.07
    colors = [(255, 107, 107), (78, 205, 196), (69, 183, 209),
              (150, 206, 180), (254, 202, 87), (199, 121, 208)]
    cols = 3
    start_x = cx - (cols * icon_s + (cols - 1) * icon_s * 0.4) / 2
    start_y = cy - (2 * icon_s + icon_s * 0.4) / 2
    for idx in range(6):
        c = idx % cols
        ridx = idx // cols
        ix = start_x + c * icon_s * 1.4
        iy = start_y + ridx * icon_s * 1.4
        d.rounded_rectangle((ix, iy, ix + icon_s, iy + icon_s), radius=size // 60,
                            fill=colors[idx % len(colors)])
    return img


def design_3(size=256):
    """Neon minimalist monitor outline with orbiting squares."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # outer glow circle
    d.ellipse((size * 0.05, size * 0.05, size * 0.95, size * 0.95),
              fill=(10, 10, 18, 255), outline=(0, 245, 212, 255), width=size // 60)
    # monitor outline
    mw = size * 0.5
    mh = size * 0.32
    mx = (size - mw) / 2
    my = size * 0.26
    rounded_rect(d, (mx, my, mx + mw, my + mh), size // 40, fill=None,
                 outline=(0, 245, 212, 255), width=size // 55)
    # stand
    d.rectangle((size * 0.45, my + mh, size * 0.55, my + mh + size * 0.06),
                fill=(0, 245, 212, 255))
    # orbiting squares
    colors = [(0, 245, 212), (255, 0, 110), (255, 190, 11), (58, 134, 255)]
    orbit_r = size * 0.38
    for i, col in enumerate(colors):
        angle = 3.14159 / 2 + i * (2 * 3.14159 / len(colors))
        x = size / 2 + orbit_r * __import__('math').cos(angle)
        y = size / 2 + orbit_r * __import__('math').sin(angle)
        s = size * 0.07
        d.rounded_rectangle((x - s / 2, y - s / 2, x + s / 2, y + s / 2),
                            radius=size // 80, fill=col)
    return img


def save_ico(src_img, path):
    sizes = [16, 32, 48, 64, 128, 256]
    imgs = [src_img.resize((s, s), Image.LANCZOS) for s in sizes]
    imgs[0].save(path, format='ICO', sizes=[(s, s) for s in sizes],
                 append_images=imgs[1:])


def main():
    base = __import__('os').path.dirname(__import__('os').path.abspath(__file__))
    d1 = design_1(256)
    d2 = design_2(256)
    d3 = design_3(256)
    d1.save(__import__('os').path.join(base, "icon_suggestion_1.png"))
    d2.save(__import__('os').path.join(base, "icon_suggestion_2.png"))
    d3.save(__import__('os').path.join(base, "icon_suggestion_3.png"))
    save_ico(d1, __import__('os').path.join(base, "icon.ico"))
    print("Created icon.ico + 3 PNG suggestions in", base)


if __name__ == "__main__":
    main()
