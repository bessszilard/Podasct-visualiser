"""Frame renderer using PIL/Pillow"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import os


W, H = 1920, 1080

FONT_CACHE = {}


def _get_font(family: str, size: int, bold: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    key = (family, size, bold, italic)
    if key in FONT_CACHE:
        return FONT_CACHE[key]

    # Try system fonts
    candidates = []
    if bold and italic:
        candidates = [f"{family}-BoldItalic.ttf", f"{family}BoldItalic.ttf",
                      f"{family}-Bold-Italic.ttf"]
    elif bold:
        candidates = [f"{family}-Bold.ttf", f"{family}Bold.ttf", f"{family}-Heavy.ttf"]
    elif italic:
        candidates = [f"{family}-Italic.ttf", f"{family}Italic.ttf"]
    candidates.append(f"{family}.ttf")
    candidates.append(f"{family.lower()}.ttf")

    font_dirs = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
        os.path.expanduser("~/.fonts"),
        os.path.expanduser("~/.local/share/fonts"),
    ]

    for d in font_dirs:
        for root, _, files in os.walk(d):
            for c in candidates:
                if c in files:
                    try:
                        f = ImageFont.truetype(os.path.join(root, c), size)
                        FONT_CACHE[key] = f
                        return f
                    except Exception:
                        pass

    # Fallback: default font
    try:
        f = ImageFont.load_default(size=size)
    except Exception:
        f = ImageFont.load_default()
    FONT_CACHE[key] = f
    return f


def render_frame(config, bar_heights: np.ndarray) -> Image.Image:
    """
    Render a single 1920×1080 frame.
    bar_heights: array of floats 0-1, length = soundwave.bar_count
    """
    img = Image.new("RGB", (W, H), config.background_color)
    draw = ImageDraw.Draw(img)

    # --- Title ---
    _draw_text_block(draw, config.title, W, H)

    # --- Subtitle ---
    _draw_text_block(draw, config.subtitle, W, H)

    # --- Images ---
    for img_el in config.images:
        if img_el.path and Path(img_el.path).exists():
            _draw_image(img, img_el, W, H)

    # --- Soundwave ---
    _draw_soundwave(draw, config.soundwave, bar_heights, W, H)

    return img


def _draw_text_block(draw: ImageDraw.Draw, el, W: int, H: int):
    if not el.text.strip():
        return
    font = _get_font(el.font_family, el.font_size, el.bold, el.italic)
    x = int(el.x * W)
    y = int(el.y * H)
    max_w = int(el.width * W)

    # Word-wrap
    words = el.text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_w:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    for line in lines:
        draw.text((x, y), line, font=font, fill=el.color)
        bbox = draw.textbbox((x, y), line, font=font)
        y += (bbox[3] - bbox[1]) + int(el.font_size * 0.15)


def _draw_image(base: Image.Image, el, W: int, H: int):
    try:
        src = Image.open(el.path).convert("RGBA")
        tw = int(el.width * W)
        th = int(el.height * H)
        src = src.resize((tw, th), Image.LANCZOS)
        px = int(el.x * W)
        py = int(el.y * H)
        if el.opacity < 1.0:
            r, g, b, a = src.split()
            a = a.point(lambda v: int(v * el.opacity))
            src.putalpha(a)
        base.paste(src, (px, py), src)
    except Exception as e:
        print(f"Image error: {e}")


def _draw_soundwave(draw: ImageDraw.Draw, sw, bar_heights: np.ndarray, W: int, H: int):
    x0 = int(sw.x * W)
    y0 = int(sw.y * H)
    sw_w = int(sw.width * W)
    sw_h = int(sw.height * H)
    cx_y = y0 + sw_h // 2

    n = len(bar_heights)
    if n == 0:
        return

    color = sw.color

    # ── helpers ──────────────────────────────────────────────
    def bar_metrics():
        bw = max(2, sw_w // n - 2)
        gp = max(1, (sw_w - bw * n) // max(1, n - 1))
        return bw, gp

    def pt(i, h, offset=0.45):
        bx = x0 + int(i / max(1, n - 1) * sw_w)
        by = cx_y - int(h * sw_h * offset)
        return bx, by

    # ── styles ───────────────────────────────────────────────
    if sw.style == "bars":
        bar_w, gap = bar_metrics()
        for i, h in enumerate(bar_heights):
            bh = max(2, int(h * sw_h * 0.9))
            bx = x0 + i * (bar_w + gap)
            draw.rectangle([bx, cx_y - bh // 2, bx + bar_w, cx_y + bh // 2], fill=color)
        # dashed continuation line
        lx = x0 + n * (bar_w + gap)
        while lx < x0 + sw_w:
            draw.line([(lx, cx_y), (min(lx + 8, x0 + sw_w), cx_y)], fill=color, width=3)
            lx += 14

    elif sw.style == "mirror":
        bar_w, gap = bar_metrics()
        for i, h in enumerate(bar_heights):
            bh = max(2, int(h * sw_h * 0.45))
            bx = x0 + i * (bar_w + gap)
            draw.rectangle([bx, cx_y - bh, bx + bar_w, cx_y], fill=color)
            draw.rectangle([bx, cx_y, bx + bar_w, cx_y + bh], fill=color)

    elif sw.style == "line":
        pts = [pt(i, h) for i, h in enumerate(bar_heights)]
        if len(pts) > 1:
            draw.line(pts, fill=color, width=3)

    elif sw.style == "smooth":
        # Cubic bezier approximation via many small segments
        from PIL import ImageDraw as _ID
        pts = [pt(i, h) for i, h in enumerate(bar_heights)]
        if len(pts) > 2:
            smooth = []
            for i in range(len(pts) - 1):
                x1, y1 = pts[i]
                x2, y2 = pts[i + 1]
                mx = (x1 + x2) // 2
                smooth.append((x1, y1))
                smooth.append((mx, y1))
                smooth.append((mx, y2))
            smooth.append(pts[-1])
            draw.line(smooth, fill=color, width=4)

    elif sw.style == "filled":
        pts_top = [pt(i, h) for i, h in enumerate(bar_heights)]
        # Build polygon: top curve + bottom baseline
        poly = pts_top + [(x0 + sw_w, cx_y), (x0, cx_y)]
        if len(poly) > 2:
            draw.polygon(poly, fill=color)

    elif sw.style == "filled mirror":
        pts_top = [pt(i, h, 0.45) for i, h in enumerate(bar_heights)]
        pts_bot = [pt(i, h, -0.45) for i, h in enumerate(bar_heights)]
        poly = pts_top + list(reversed(pts_bot))
        if len(poly) > 2:
            draw.polygon(poly, fill=color)

    elif sw.style == "dots":
        for i, h in enumerate(bar_heights):
            bx, by = pt(i, h)
            r = max(3, sw_h // 20)
            draw.ellipse([bx - r, by - r, bx + r, by + r], fill=color)
            # mirror dot
            by2 = cx_y + (cx_y - by)
            draw.ellipse([bx - r, by2 - r, bx + r, by2 + r], fill=color)

    elif sw.style == "blocks":
        # Bars anchored to the bottom edge
        bar_w, gap = bar_metrics()
        bottom = y0 + sw_h
        for i, h in enumerate(bar_heights):
            bh = max(2, int(h * sw_h * 0.95))
            bx = x0 + i * (bar_w + gap)
            draw.rectangle([bx, bottom - bh, bx + bar_w, bottom], fill=color)

    elif sw.style == "outline bars":
        bar_w, gap = bar_metrics()
        for i, h in enumerate(bar_heights):
            bh = max(4, int(h * sw_h * 0.9))
            bx = x0 + i * (bar_w + gap)
            t = max(2, bar_w // 4)
            # top cap
            draw.rectangle([bx, cx_y - bh // 2, bx + bar_w, cx_y - bh // 2 + t], fill=color)
            # bottom cap
            draw.rectangle([bx, cx_y + bh // 2 - t, bx + bar_w, cx_y + bh // 2], fill=color)
            # left edge
            draw.rectangle([bx, cx_y - bh // 2, bx + t, cx_y + bh // 2], fill=color)
            # right edge
            draw.rectangle([bx + bar_w - t, cx_y - bh // 2, bx + bar_w, cx_y + bh // 2], fill=color)

    elif sw.style == "heartbeat":
        # ECG-style: flat line with sharp spikes at loud moments
        pts = []
        for i, h in enumerate(bar_heights):
            bx = x0 + int(i / max(1, n - 1) * sw_w)
            if h > 0.3:
                # spike up then down
                mid_x = bx
                pts.append((mid_x - 4, cx_y))
                pts.append((mid_x, cx_y - int(h * sw_h * 0.85)))
                pts.append((mid_x + 4, cx_y + int(h * sw_h * 0.25)))
                pts.append((mid_x + 8, cx_y))
            else:
                pts.append((bx, cx_y))
        if len(pts) > 1:
            draw.line(pts, fill=color, width=3)

    elif sw.style == "circle":
        import math
        cx = x0 + sw_w // 2
        cy = cx_y
        base_r = min(sw_w, sw_h) // 2 - 10
        for i, h in enumerate(bar_heights):
            angle = (i / n) * 2 * math.pi - math.pi / 2
            r_inner = base_r
            r_outer = base_r + int(h * sw_h * 0.4)
            x1 = cx + int(r_inner * math.cos(angle))
            y1 = cy + int(r_inner * math.sin(angle))
            x2 = cx + int(r_outer * math.cos(angle))
            y2 = cy + int(r_outer * math.sin(angle))
            draw.line([(x1, y1), (x2, y2)], fill=color, width=max(2, sw_w // (n * 2)))
