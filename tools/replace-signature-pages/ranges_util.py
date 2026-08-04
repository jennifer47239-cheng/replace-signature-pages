#!/usr/bin/env python3
"""Shared page-range helpers for multi-block signature workflows."""

from __future__ import annotations

from splice_signature_pages import parse_range


def parse_multi_ranges(text: str) -> list[tuple[int, int]]:
    """Parse '8-9,20-21' or '8-9；20' into sorted non-overlapping ranges."""
    raw = text.replace("；", ",").replace("、", ",").replace(" ", "")
    parts = [p for p in raw.split(",") if p]
    if not parts:
        raise ValueError("empty ranges")
    ranges = [parse_range(p) for p in parts]
    spans = sorted(ranges)
    for i in range(len(spans) - 1):
        if spans[i][1] >= spans[i + 1][0]:
            raise ValueError(
                f"overlapping ranges: {spans[i][0]}-{spans[i][1]} and "
                f"{spans[i + 1][0]}-{spans[i + 1][1]}"
            )
    return spans


def format_range(start: int, end: int) -> str:
    return str(start) if start == end else f"{start}-{end}"


def format_ranges(ranges: list[tuple[int, int]]) -> str:
    return ", ".join(format_range(s, e) for s, e in ranges)
