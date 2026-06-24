#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "resources" / "data" / "logos"
SIZE = 512

ICONS = {
    "kan11": ("11", "KAN", "#1769AA", "#FFFFFF"),
    "keshet12": ("12", "KESHET", "#E32636", "#FFFFFF"),
    "reshet13": ("13", "RESHET", "#5B3FA3", "#FFFFFF"),
    "now14": ("14", "NOW", "#16324F", "#FFFFFF"),
    "kan_educational": ("K", "EDUCATIONAL", "#F2C230", "#17202A"),
    "makan33": ("33", "MAKAN", "#198A75", "#FFFFFF"),
    "knesset": ("99", "KNESSET", "#1B4D89", "#FFFFFF"),
    "channel24_or_i24_placeholder": ("i24", "HEBREW", "#D71920", "#FFFFFF"),
    "economy10": ("10", "ECONOMY", "#19715B", "#FFFFFF"),
    "ynet_live": ("Y", "YNET LIVE", "#D51F2B", "#FFFFFF"),
    "hidabroot": ("H", "HIDABROOT", "#73539A", "#FFFFFF"),
    "reshet13_comedy": ("13", "COMEDY", "#F15A29", "#FFFFFF"),
    "reshet13_reality": ("13", "REALITY", "#00A7A5", "#FFFFFF"),
    "reshet13_vacation": ("13", "VACATION", "#1687C9", "#FFFFFF"),
}


def _font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    candidates = [
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return ImageFont.truetype(str(candidate), size=size)
    return ImageFont.load_default()


def _fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int) -> ImageFont.FreeTypeFont:
    size = start_size
    while size >= 24:
        font = _font(size)
        bounds = draw.textbbox((0, 0), text, font=font)
        if bounds[2] - bounds[0] <= max_width:
            return font
        size -= 4
    return _font(24)


def render_icon(primary: str, secondary: str, background: str, foreground: str) -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((16, 16, SIZE - 16, SIZE - 16), radius=72, fill=background)
    draw.rounded_rectangle((38, 38, SIZE - 38, SIZE - 38), radius=56, outline=foreground, width=5)

    primary_font = _fit_font(draw, primary, 360, 210)
    primary_box = draw.textbbox((0, 0), primary, font=primary_font)
    primary_width = primary_box[2] - primary_box[0]
    primary_height = primary_box[3] - primary_box[1]
    primary_y = 208 - (primary_height // 2) - primary_box[1]
    draw.text(((SIZE - primary_width) / 2, primary_y), primary, font=primary_font, fill=foreground)

    secondary_font = _fit_font(draw, secondary, 370, 54)
    secondary_box = draw.textbbox((0, 0), secondary, font=secondary_font)
    secondary_width = secondary_box[2] - secondary_box[0]
    draw.text(((SIZE - secondary_width) / 2, 382), secondary, font=secondary_font, fill=foreground)
    return image


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for channel_id, spec in ICONS.items():
        render_icon(*spec).save(OUTPUT_DIR / f"{channel_id}.png", optimize=True)
    print(f"Generated {len(ICONS)} channel icons in {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
