#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pure GIF generation helpers used by the Tkinter UI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from PIL import Image


@dataclass(frozen=True)
class GifOptions:
    width: int = 400
    height: int = 400
    delay: int = 500
    repeat: int = 0
    quality: int = 20
    keep_ratio: bool = True


@dataclass(frozen=True)
class GifResult:
    output_path: str
    processed_count: int
    error_count: int
    cancelled: bool = False


ProgressCallback = Callable[[int, int, str], None]
CancelCallback = Callable[[], bool]


def build_gif_frame(image_path: str, options: GifOptions) -> Image.Image:
    width = max(1, int(options.width))
    height = max(1, int(options.height))

    with Image.open(image_path) as opened:
        image = opened.copy()

    if options.keep_ratio:
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (width, height), (255, 255, 255))
        x = (width - image.width) // 2
        y = (height - image.height) // 2
        if image.mode in ("RGBA", "LA"):
            canvas.paste(image.convert("RGBA"), (x, y), image.convert("RGBA").split()[-1])
        else:
            canvas.paste(image.convert("RGB"), (x, y))
        image = canvas
    else:
        image = image.resize((width, height), Image.Resampling.LANCZOS).convert("RGB")

    if image.mode != "P":
        image = image.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
    return image


def create_gif(
    image_paths: Iterable[str],
    output_path: str,
    options: GifOptions,
    progress: Optional[ProgressCallback] = None,
    cancelled: Optional[CancelCallback] = None,
    logger: Optional[object] = None,
) -> GifResult:
    paths = list(image_paths)
    frames: List[Image.Image] = []
    error_count = 0

    for index, image_path in enumerate(paths, start=1):
        if cancelled and cancelled():
            return GifResult(output_path, len(frames), error_count, cancelled=True)

        if progress:
            progress(index, len(paths), image_path)

        try:
            if index % 5 == 1:
                _raise_if_memory_low()
            frames.append(build_gif_frame(image_path, options))
        except Exception as exc:
            error_count += 1
            if logger:
                logger.error(f"Failed to process GIF frame {image_path}: {exc}")

    if cancelled and cancelled():
        return GifResult(output_path, len(frames), error_count, cancelled=True)

    if not frames:
        raise ValueError("No valid frames to encode")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        frames[0].save(
            output_path,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            duration=max(10, int(options.delay)),
            loop=int(options.repeat) if int(options.repeat) != 0 else 0,
            optimize=True,
            quality=max(1, min(100, int(options.quality))),
        )
    finally:
        for frame in frames:
            frame.close()
    return GifResult(output_path, len(frames), error_count)


def _raise_if_memory_low() -> None:
    try:
        import psutil

        if psutil.virtual_memory().available < 50 * 1024 * 1024:
            raise MemoryError("Not enough memory to continue GIF generation")
    except ImportError:
        return
