#!/usr/bin/env python3
"""Generate Home Assistant brand assets from the official Biamp wordmark."""

from __future__ import annotations

import re
import base64
from pathlib import Path

from PIL import Image, ImageDraw

BRAND_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "biamp_tesira" / "brand"
SOURCE_SVG = BRAND_DIR / "_source_logo.svg"
SOURCE_PNG = BRAND_DIR / "_source_biamp_wordmark.png"
BLOG_LOGO_SVG_URL = "https://blog.biamp.com/wp-content/themes/snap_child/logo.svg"

# Biamp brand colors (from official wordmark usage)
NAVY = (27, 54, 93, 255)
RED_DOT = (230, 0, 18, 255)


def ensure_source_png() -> Image.Image:
    """Load official wordmark PNG, extracting from Biamp blog SVG if needed."""
    if not SOURCE_PNG.exists():
        ensure_source_svg()
        svg = SOURCE_SVG.read_text(encoding="utf-8")
        match = re.search(r"base64,([A-Za-z0-9+/=]+)", svg)
        if not match:
            raise RuntimeError("Could not extract PNG from Biamp logo SVG")
        SOURCE_PNG.write_bytes(base64.b64decode(match.group(1)))
    image = Image.open(SOURCE_PNG).convert("RGBA")
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    return image


def ensure_source_svg() -> None:
    """Download Biamp blog theme logo SVG (official site)."""
    if SOURCE_SVG.exists():
        return
    import urllib.request

    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(BLOG_LOGO_SVG_URL, timeout=30) as resp:
        SOURCE_SVG.write_bytes(resp.read())


def _is_red_dot(r: int, g: int, b: int, a: int) -> bool:
    return a > 128 and r > 180 and g < 80 and b < 80


def _is_wordmark_white(r: int, g: int, b: int, a: int) -> bool:
    return a > 128 and (r + g + b) > 600 and not _is_red_dot(r, g, b, a)


def recolor_for_light_background(image: Image.Image) -> Image.Image:
    """White wordmark -> navy for light HA themes; preserve red dot."""
    out = image.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if _is_red_dot(r, g, b, a):
                px[x, y] = RED_DOT
            elif _is_wordmark_white(r, g, b, a):
                px[x, y] = (NAVY[0], NAVY[1], NAVY[2], a)
    return out


def fit_on_canvas(
    image: Image.Image,
    canvas_size: tuple[int, int],
    *,
    background: tuple[int, int, int, int] | None = None,
    padding_ratio: float = 0.12,
) -> Image.Image:
    """Scale image to fit canvas with padding."""
    cw, ch = canvas_size
    canvas = Image.new("RGBA", canvas_size, background or (0, 0, 0, 0))
    pad_w = int(cw * padding_ratio)
    pad_h = int(ch * padding_ratio)
    max_w, max_h = cw - 2 * pad_w, ch - 2 * pad_h
    scale = min(max_w / image.width, max_h / image.height)
    new_size = (max(1, int(image.width * scale)), max(1, int(image.height * scale)))
    resized = image.resize(new_size, Image.Resampling.LANCZOS)
    x = (cw - new_size[0]) // 2
    y = (ch - new_size[1]) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def render_icon(size: int, *, light: bool) -> Image.Image:
    """Square icon: light theme uses navy tile; dark theme uses transparent + white mark."""
    wordmark = ensure_source_png()
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    if light:
        draw = ImageDraw.Draw(canvas)
        margin = size // 14
        draw.rounded_rectangle(
            (margin, margin, size - margin, size - margin),
            radius=size // 8,
            fill=NAVY,
        )
    overlay = fit_on_canvas(
        wordmark,
        (size, size),
        padding_ratio=0.18 if light else 0.14,
    )
    return Image.alpha_composite(canvas, overlay)


def render_logo(width: int, height: int, *, light: bool) -> Image.Image:
    """Landscape logo on transparent background."""
    wordmark = ensure_source_png() if not light else recolor_for_light_background(
        ensure_source_png()
    )
    return fit_on_canvas(wordmark, (width, height), padding_ratio=0.1)


def _save(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG", optimize=True)
    print(f"Wrote {path}")


def main() -> None:
    ensure_source_png()
    _save(render_icon(256, light=True), BRAND_DIR / "icon.png")
    _save(render_icon(512, light=True), BRAND_DIR / "icon@2x.png")
    _save(render_icon(256, light=False), BRAND_DIR / "dark_icon.png")
    _save(render_icon(512, light=False), BRAND_DIR / "dark_icon@2x.png")

    _save(render_logo(512, 128, light=True), BRAND_DIR / "logo.png")
    _save(render_logo(1024, 256, light=True), BRAND_DIR / "logo@2x.png")
    _save(render_logo(512, 128, light=False), BRAND_DIR / "dark_logo.png")
    _save(render_logo(1024, 256, light=False), BRAND_DIR / "dark_logo@2x.png")


if __name__ == "__main__":
    main()
