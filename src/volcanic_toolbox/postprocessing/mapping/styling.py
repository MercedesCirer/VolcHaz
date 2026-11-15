"""Styling helpers."""

from __future__ import annotations

import re


def safe_token(value) -> str:
    return re.sub(
        r"[^A-Za-z0-9_.-]+",
        "_",
        str(value),
    ).strip("_")


def expand_colors(colors, n):
    if not colors:
        colors = ("#d9d9d9", "#969696", "#252525")
    colors = list(colors)
    while len(colors) < n:
        colors.append(colors[-1])
    return colors[:n]
