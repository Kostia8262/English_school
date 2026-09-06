#!/usr/bin/env python3
"""Збирає набір іконок сайту з logo.png.

Гугл шукає фавікон окремим краулером (Googlebot-Favicon), і той уміє лише
завантажити файл за URL. data:-URI, який тут стояв раніше, він не бачить
взагалі — тому у видачі був сірий глобус. Файли мають лежати на диску.

  python tools/icons/build.py
"""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "logo.png"

# Тло для iOS: там прозорість заливається чорним, тому кладемо cream.
CREAM = (255, 251, 247, 255)

# 512 не робимо: джерело — 150 px, апскейл вийде мильним. PWA тут немає,
# тому 192 достатньо для Android-ярлика.
PNG_SIZES = [96, 192]
ICO_SIZES = [16, 32, 48]


def load() -> Image.Image:
    return Image.open(SOURCE).convert("RGBA")


def resized(img: Image.Image, size: int) -> Image.Image:
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    src = load()

    # favicon.ico — те, що браузер і Гугл питають навіть без <link>.
    ico = ROOT / "favicon.ico"
    resized(src, 256).save(ico, sizes=[(s, s) for s in ICO_SIZES])

    for size in PNG_SIZES:
        resized(src, size).save(ROOT / f"favicon-{size}x{size}.png", optimize=True)

    # apple-touch-icon — непрозорий, з невеликим полем по краях.
    apple = Image.new("RGBA", (180, 180), CREAM)
    apple.paste(resized(src, 164), (8, 8), resized(src, 164))
    apple.convert("RGB").save(ROOT / "apple-touch-icon.png", optimize=True)

    for path in [ico, ROOT / "apple-touch-icon.png"] + [
        ROOT / f"favicon-{s}x{s}.png" for s in PNG_SIZES
    ]:
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size:>7,} B")


if __name__ == "__main__":
    main()
