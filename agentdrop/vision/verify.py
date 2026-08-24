"""Screenshot verification — "did the screen actually change?"

Every visual action is followed by a new screenshot and a pixel diff
against the pre-action shot. This is what makes the loop honest: a
click that hit nothing, a form that rejected input, a spinner that
never resolved — all of it shows up as "no change" and triggers
recovery instead of being silently assumed as success.
"""
from __future__ import annotations

import hashlib
from typing import Tuple

from PIL import Image
import io

import numpy as np

# Two screenshots are "changed" when EITHER:
#   * the mean absolute grayscale diff (0..255 scale) exceeds
#     MEAN_CHANGE_THRESHOLD — catches navigation, overlays, big repaints
#     (measured: ~5.9 for a page change), OR
#   * at least LOCAL_PIXEL_FRACTION of the pixels differ by more than
#     LOCAL_PIXEL_DELTA — catches small local changes like a few
#     characters typed into an input box (measured: ~0.42 mean diff,
#     which a pure mean test misses on a large viewport).
# Both are comfortably above deterministic-render jitter (0.0) and
# typical browser compositing noise (<0.05 mean, no clustered deltas).
MEAN_CHANGE_THRESHOLD = 0.3
LOCAL_PIXEL_DELTA = 30
LOCAL_PIXEL_FRACTION = 0.0005  # ~500px of a 1280x800 frame
CHANGE_THRESHOLD = MEAN_CHANGE_THRESHOLD  # back-compat name


def _grayscale_small(png: bytes, size: Tuple[int, int] = (256, 256)) -> np.ndarray:
    img = Image.open(io.BytesIO(png)).convert("L").resize(size, Image.BILINEAR)
    return np.asarray(img, dtype=np.float32)


def diff_ratio(a: bytes, b: bytes, size: Tuple[int, int] = (256, 256)) -> float:
    """Mean absolute grayscale difference between two PNGs, 0..255."""
    ga, gb = _grayscale_small(a, size), _grayscale_small(b, size)
    return float(np.mean(np.abs(ga - gb)))


def local_change_fraction(a: bytes, b: bytes, size: Tuple[int, int] = (256, 256)) -> float:
    """Fraction of pixels whose grayscale delta exceeds LOCAL_PIXEL_DELTA."""
    ga, gb = _grayscale_small(a, size), _grayscale_small(b, size)
    d = np.abs(ga - gb)
    return float(np.count_nonzero(d > LOCAL_PIXEL_DELTA)) / d.size


def images_changed(
    a: bytes,
    b: bytes,
    threshold: float = MEAN_CHANGE_THRESHOLD,
    local_fraction: float = LOCAL_PIXEL_FRACTION,
    local_delta: float = LOCAL_PIXEL_DELTA,
) -> bool:
    if diff_ratio(a, b) > threshold:
        return True
    ga = _grayscale_small(a)
    gb = _grayscale_small(b)
    d = np.abs(ga - gb)
    if local_fraction <= 0:
        return False
    return (np.count_nonzero(d > local_delta) / d.size) > local_fraction


def image_hash(png: bytes, size: int = 16) -> str:
    """Perceptual dHash — stable for identical renders, flips on real change.

    Used for loop detection (N identical consecutive screens) and for
    evidence bookkeeping, not as the change detector itself.
    """
    img = Image.open(io.BytesIO(png)).convert("L").resize((size, size), Image.BILINEAR)
    px = np.asarray(img, dtype=np.int16)
    diff = px[:, 1:] > px[:, :-1]
    bits = 0
    for row in diff:
        for bit in row:
            bits = (bits << 1) | int(bit)
    return format(bits, f"0{size * (size - 1) // 4}x")


def is_near_identical(a: bytes, b: bytes, size: int = 16) -> bool:
    ha, hb = image_hash(a, size), image_hash(b, size)
    if ha == hb:
        return True
    dist = bin(int(ha, 16) ^ int(hb, 16)).count("1")
    return dist <= 2


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
