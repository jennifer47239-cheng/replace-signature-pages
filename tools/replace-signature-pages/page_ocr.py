#!/usr/bin/env python3
"""On-device OCR for low-text PDF pages via macOS Vision (no upload)."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
SWIFT_SRC = TOOL_DIR / "macos_vision_ocr.swift"
_BIN_CACHE: Path | None = None


def vision_ocr_available() -> bool:
    return sys.platform == "darwin" and SWIFT_SRC.is_file() and shutil.which("swift") is not None


def _compiled_binary() -> Path:
    global _BIN_CACHE
    if _BIN_CACHE is not None and _BIN_CACHE.is_file():
        return _BIN_CACHE
    if not vision_ocr_available():
        raise RuntimeError(
            "OCR requires macOS + swift + macos_vision_ocr.swift in tools/replace-signature-pages/"
        )
    out = TOOL_DIR / ".macos_vision_ocr"
    # Recompile if missing or source newer
    if not out.is_file() or out.stat().st_mtime < SWIFT_SRC.stat().st_mtime:
        proc = subprocess.run(
            ["swiftc", "-O", "-o", str(out), str(SWIFT_SRC)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"swiftc failed: {proc.stderr.strip() or proc.stdout}")
    _BIN_CACHE = out
    return out


def ocr_image(path: Path) -> str:
    binary = _compiled_binary()
    proc = subprocess.run(
        [str(binary), str(path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode not in (0, 3):
        raise RuntimeError(proc.stderr.strip() or f"OCR exit {proc.returncode}")
    return proc.stdout or ""


def ocr_pdf_pages(pdf: Path, page_numbers: list[int], *, dpi: int = 144) -> dict[int, str]:
    """OCR 1-based page numbers; returns page → text. Needs pymupdf."""
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("OCR page render needs pymupdf (pip install pymupdf)") from exc

    results: dict[int, str] = {}
    if not page_numbers:
        return results
    with tempfile.TemporaryDirectory(prefix="sig-ocr-") as tmp:
        tmp_dir = Path(tmp)
        with fitz.open(str(pdf)) as doc:
            for page_no in page_numbers:
                if page_no < 1 or page_no > doc.page_count:
                    continue
                png = tmp_dir / f"p{page_no:04d}.png"
                doc[page_no - 1].get_pixmap(dpi=dpi).save(str(png))
                try:
                    results[page_no] = ocr_image(png)
                except Exception as exc:  # noqa: BLE001
                    results[page_no] = ""
                    sys.stderr.write(f"OCR failed page {page_no}: {exc}\n")
    return results
