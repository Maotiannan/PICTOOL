#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure watermark processing helpers used by the Tkinter UI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

from utils import contains_chinese, get_exif_datetime


Position = Tuple[int, int]


@dataclass(frozen=True)
class WatermarkOptions:
    text: str
    font_size: int = 40
    opacity: int = 80
    color: Tuple[int, int, int] = (255, 255, 0)
    position: str = "\u4e2d\u5fc3"
    multi_size: bool = True
    high_contrast: bool = True
    chinese_font: Any = "simhei.ttf"
    english_font: Any = "arial.ttf"
    margin: int = 10


class WatermarkRenderer:
    """Reusable renderer with a small font cache for batch jobs."""

    def __init__(self, options: WatermarkOptions):
        self.options = options
        self._font_cache: Dict[Tuple[str, int], ImageFont.ImageFont] = {}

    def add_watermark(self, image: Image.Image, text: str | None = None) -> Image.Image:
        text = self.process_dynamic_text(text if text is not None else self.options.text, image)

        if image.mode != "RGBA":
            image = image.convert("RGBA")

        watermark = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark)

        font_size = (
            self.calculate_adaptive_font_size(text, image.size)
            if self.options.multi_size
            else max(1, int(self.options.font_size))
        )
        font = self.get_font(text, font_size)

        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x, y = self.calculate_position(image.size, (text_width, text_height))

        color = self.options.color
        if self.options.high_contrast:
            color = self.calculate_contrast_color_for_region(image, x, y, text_width, text_height)

        opacity = max(0, min(100, int(self.options.opacity)))
        draw.text((x, y), text, font=font, fill=(*color, int(opacity * 255 / 100)))

        return Image.alpha_composite(image, watermark)

    def process_dynamic_text(self, text: str, image: Image.Image) -> str:
        if "{exif_date}" not in text:
            return text
        exif_date = get_exif_datetime(image)
        return text.replace("{exif_date}", exif_date if exif_date else "N/A")

    def calculate_adaptive_font_size(self, text: str, image_size: Tuple[int, int]) -> int:
        img_w, img_h = image_size
        target_width = img_w * 0.8
        min_size = max(10, int(min(img_w, img_h) * 0.02))
        max_size = max(min_size, int(min(img_w, img_h) * 0.3))

        best_size = min_size
        low, high = min_size, max_size
        temp_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))

        for _ in range(10):
            if low > high:
                break
            mid = (low + high) // 2
            font = self.get_font(text, mid)
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            if bbox[2] - bbox[0] <= target_width:
                best_size = mid
                low = mid + 1
            else:
                high = mid - 1

        return max(min_size, min(best_size, max_size))

    def get_font(self, text: str, size: int) -> ImageFont.ImageFont:
        font_source = self.options.chinese_font if contains_chinese(text) else self.options.english_font
        cache_key = (repr(font_source), max(1, int(size)))
        cached = self._font_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            if isinstance(font_source, str):
                font = ImageFont.truetype(font_source, cache_key[1])
            else:
                font = ImageFont.load_default()
        except Exception:
            font = ImageFont.load_default()

        self._font_cache[cache_key] = font
        return font

    def calculate_position(self, image_size: Tuple[int, int], text_size: Tuple[int, int]) -> Position:
        img_w, img_h = image_size
        text_w, text_h = text_size
        margin = max(0, int(self.options.margin))
        position = self.options.position

        if position == "\u5de6\u4e0a\u89d2":
            return margin, margin
        if position == "\u53f3\u4e0a\u89d2":
            return img_w - text_w - margin, margin
        if position == "\u5de6\u4e0b\u89d2":
            return margin, img_h - text_h - margin
        if position == "\u53f3\u4e0b\u89d2":
            return img_w - text_w - margin, img_h - text_h - margin
        if position == "\u4e2d\u5fc3":
            return (img_w - text_w) // 2, (img_h - text_h) // 2
        return margin, margin

    def calculate_contrast_color_for_region(
        self,
        image: Image.Image,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> Tuple[int, int, int]:
        try:
            left = max(0, x)
            top = max(0, y)
            right = max(left + 1, min(image.width, x + width))
            bottom = max(top + 1, min(image.height, y + height))
            region = image.crop((left, top, right, bottom))
            if region.mode != "RGB":
                region = region.convert("RGB")

            mean = ImageStat.Stat(region).mean
            luminance = 0.299 * mean[0] + 0.587 * mean[1] + 0.114 * mean[2]
            return (0, 0, 0) if luminance > 128 else (255, 255, 255)
        except Exception:
            return self.options.color


def save_watermarked_image(image: Image.Image, output_path: str, original_format: str | None) -> str:
    save_format = (original_format or "PNG").upper()

    if save_format in ("JPEG", "JPG"):
        if image.mode == "RGBA":
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[-1])
            image = background
        image.save(output_path, "JPEG", quality=95)
        return output_path

    if save_format == "PNG":
        image.save(output_path, "PNG")
        return output_path

    if save_format == "WEBP":
        image.save(output_path, "WEBP")
        return output_path

    try:
        image.save(output_path, save_format)
        return output_path
    except Exception:
        fallback_path = output_path
        if not fallback_path.lower().endswith(".png"):
            fallback_path = os.path.splitext(output_path)[0] + ".png"
        image.save(fallback_path, "PNG")
        return fallback_path


def process_watermark_file(
    image_path: str,
    output_folder: str,
    renderer: WatermarkRenderer,
) -> str:
    with Image.open(image_path) as opened:
        original_format = opened.format
        image = ImageOps.exif_transpose(opened)
        watermarked = renderer.add_watermark(image)

    output_path = os.path.join(output_folder, os.path.basename(image_path))
    return save_watermarked_image(watermarked, output_path, original_format)

