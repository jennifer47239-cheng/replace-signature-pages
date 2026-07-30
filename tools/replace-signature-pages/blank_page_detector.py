#!/usr/bin/env python3
"""Detect and (optionally) remove blank pages in signed signature PDFs.

Goal: handle double-sided scanning where "back side" becomes an empty page.

Scanned pages are a full-page image, so text/content-stream heuristics alone
call every scanned page "not blank". When PyMuPDF is available each page is
rendered small and judged by how much ink it actually carries.

Privacy: local-only utility; does not print or log page text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    from pypdf import PdfReader, PdfWriter
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Missing dependency: pypdf. From repo root run:\n"
        "  python3 -m venv .venv && .venv/bin/pip install pypdf"
    ) from exc

# Defaults tuned for scanned signature pages; every caller can override them.
NONSPACE_THRESHOLD = 15
CONTENT_BYTES_MAX = 800
INK_RATIO_MAX = 0.002
INK_DARK_LEVEL = 200
INK_BORDER_FRACTION = 0.04
INK_RENDER_DPI = 50

_DARK_LUT_CACHE: dict[int, bytes] = {}


def _nonspace_len(text: str) -> int:
    compact = re.sub(r"\s+", "", text or "")
    return len(compact)


def _count_image_xobjects(page: Any) -> int:
    """Heuristic: scanned pages usually contain image XObjects.

    If there are images, we should not treat the page as "blank" even when
    OCR/text extraction returns nothing.
    """

    try:
        resources = page.get("/Resources")
        if not resources:
            return 0
        xobj = resources.get("/XObject")
        if not xobj:
            return 0

        # xobj is a dictionary: {name -> obj}
        count_img = 0
        for name in xobj.keys():
            try:
                obj = xobj[name]
                obj_dict = obj.get_object() if hasattr(obj, "get_object") else obj
                subtype = obj_dict.get("/Subtype") if hasattr(obj_dict, "get") else None
                if subtype == "/Image":
                    count_img += 1
            except Exception:
                # If the structure is unknown, err on the side of "not blank".
                # (We don't remove real signature pages.)
                return 1
        return count_img
    except Exception:
        return 0


def _content_bytes_len(page: Any) -> int:
    try:
        contents = page.get_contents()
        if contents is None:
            return 0
        if isinstance(contents, list):
            total = 0
            for c in contents:
                if hasattr(c, "get_data"):
                    total += len(c.get_data())
                else:
                    total += len(str(c).encode("utf-8", errors="ignore"))
            return total
        if hasattr(contents, "get_data"):
            return len(contents.get_data())
        return len(str(contents).encode("utf-8", errors="ignore"))
    except Exception:
        return 0


def _dark_lut(dark_level: int) -> bytes:
    lut = _DARK_LUT_CACHE.get(dark_level)
    if lut is None:
        lut = bytes(1 if v < dark_level else 0 for v in range(256))
        _DARK_LUT_CACHE[dark_level] = lut
    return lut


def measure_ink_ratios(
    pdf: Path,
    *,
    dark_level: int = INK_DARK_LEVEL,
    border_fraction: float = INK_BORDER_FRACTION,
    dpi: int = INK_RENDER_DPI,
) -> dict[int, float] | None:
    """Fraction of dark pixels per page (1-based), ignoring scan edges.

    Returns None when PyMuPDF is unavailable, so callers can fall back to the
    text/content-stream heuristic.
    """
    try:
        import fitz
    except ImportError:
        return None

    lut = _dark_lut(dark_level)
    ratios: dict[int, float] = {}
    try:
        with fitz.open(str(pdf)) as doc:
            for index in range(doc.page_count):
                pix = doc[index].get_pixmap(dpi=dpi, colorspace=fitz.csGRAY)
                width, height = pix.width, pix.height
                if width < 8 or height < 8:
                    ratios[index + 1] = 1.0
                    continue
                mx = int(width * border_fraction)
                my = int(height * border_fraction)
                samples = pix.samples
                dark = 0
                total = 0
                for y in range(my, height - my):
                    row = samples[y * width + mx : y * width + (width - mx)]
                    total += len(row)
                    dark += row.translate(lut).count(1)
                ratios[index + 1] = (dark / total) if total else 1.0
    except Exception:
        return None
    return ratios


def page_metrics(
    pdf: Path,
    *,
    nonspace_threshold: int = NONSPACE_THRESHOLD,
    content_bytes_max: int = CONTENT_BYTES_MAX,
    ink_ratio_max: float = INK_RATIO_MAX,
    dark_level: int = INK_DARK_LEVEL,
) -> list[dict[str, Any]]:
    """Per-page blankness evidence (1-based). Never includes page text."""
    reader = PdfReader(str(pdf))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"PDF encrypted and cannot be opened: {exc}") from exc

    ink = measure_ink_ratios(pdf, dark_level=dark_level)
    metrics: list[dict[str, Any]] = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            text_len = _nonspace_len(page.extract_text() or "")
        except Exception:
            text_len = 0
        images = _count_image_xobjects(page)
        content_bytes = _content_bytes_len(page)
        ink_ratio = ink.get(i) if ink else None

        if text_len > nonspace_threshold:
            blank, reason = False, "text"
        elif ink_ratio is not None:
            blank = ink_ratio <= ink_ratio_max
            reason = "ink"
        elif images > 0:
            blank, reason = False, "image"
        else:
            blank = content_bytes <= content_bytes_max
            reason = "content_bytes"

        metrics.append(
            {
                "page": i,
                "nonspace_len": text_len,
                "image_xobject_count": images,
                "content_bytes": content_bytes,
                "ink_ratio": round(ink_ratio, 6) if ink_ratio is not None else None,
                "blank": blank,
                "reason": reason,
            }
        )

    return metrics


def resolve_blank_pages(
    auto_blank: Iterable[int],
    *,
    force_blank: Iterable[int] = (),
    force_keep: Iterable[int] = (),
) -> list[int]:
    """Apply manual overrides on top of automatic detection (1-based pages)."""
    pages = set(int(p) for p in auto_blank)
    pages |= {int(p) for p in force_blank}
    pages -= {int(p) for p in force_keep}
    return sorted(pages)


def parse_page_list(spec: str, *, max_page: int | None = None) -> list[int]:
    """Parse '3,5,8-9' into [3, 5, 8, 9]. Empty input yields []."""
    pages: set[int] = set()
    for chunk in re.split(r"[,\s、]+", (spec or "").replace("–", "-").replace("—", "-")):
        if not chunk:
            continue
        if "-" in chunk:
            a, b = chunk.split("-", 1)
            start, end = int(a), int(b)
            if end < start:
                raise ValueError(f"页码范围无效：{chunk}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(chunk))
    for p in pages:
        if p < 1 or (max_page is not None and p > max_page):
            raise ValueError(f"页码超出范围：{p}")
    return sorted(pages)


def is_blank_page(
    page: Any,
    *,
    nonspace_threshold: int = NONSPACE_THRESHOLD,
    content_bytes_max: int = CONTENT_BYTES_MAX,
) -> bool:
    """Return True if page looks like an empty scan-back page.

    Rules:
    - If OCR/text has meaningful content → not blank.
    - If the page has image XObjects → not blank (common for scanned signatures).
    - Otherwise require small content stream (to avoid false positives).
    """

    text = ""
    try:
        text = page.extract_text() or ""
    except Exception:
        text = ""

    if _nonspace_len(text) > nonspace_threshold:
        return False

    # If there are images, it's very likely not an empty back-side.
    if _count_image_xobjects(page) > 0:
        return False

    # No images + very small content stream → treat as blank.
    return _content_bytes_len(page) <= content_bytes_max


def detect_blank_pages_in_reader(
    reader: PdfReader,
    *,
    nonspace_threshold: int = NONSPACE_THRESHOLD,
    content_bytes_max: int = CONTENT_BYTES_MAX,
) -> list[int]:
    """Return 1-based blank page indices from an open reader.

    Text/content-stream evidence only. Prefer `detect_blank_pages()` when the
    file path is known: it can also weigh rendered ink, which is what scanned
    pages need.
    """

    blank_pages: list[int] = []
    for i, page in enumerate(reader.pages):
        if is_blank_page(
            page,
            nonspace_threshold=nonspace_threshold,
            content_bytes_max=content_bytes_max,
        ):
            blank_pages.append(i + 1)
    return blank_pages


def detect_blank_pages(
    pdf: Path,
    *,
    nonspace_threshold: int = NONSPACE_THRESHOLD,
    content_bytes_max: int = CONTENT_BYTES_MAX,
    ink_ratio_max: float = INK_RATIO_MAX,
    force_blank: Iterable[int] = (),
    force_keep: Iterable[int] = (),
) -> list[int]:
    """Return 1-based blank page indices, honouring manual overrides."""

    auto = [
        m["page"]
        for m in page_metrics(
            pdf,
            nonspace_threshold=nonspace_threshold,
            content_bytes_max=content_bytes_max,
            ink_ratio_max=ink_ratio_max,
        )
        if m["blank"]
    ]
    return resolve_blank_pages(auto, force_blank=force_blank, force_keep=force_keep)


def clean_pdf_remove_blank_pages(
    input_pdf: Path,
    output_pdf: Path,
    *,
    nonspace_threshold: int = NONSPACE_THRESHOLD,
    content_bytes_max: int = CONTENT_BYTES_MAX,
    ink_ratio_max: float = INK_RATIO_MAX,
    force_blank: Iterable[int] = (),
    force_keep: Iterable[int] = (),
) -> dict[str, Any]:
    """Write a cleaned PDF without blank pages. Pages are 1-based in report."""

    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    reader = PdfReader(str(input_pdf))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"PDF encrypted and cannot be opened: {exc}") from exc

    blank_pages = detect_blank_pages(
        input_pdf,
        nonspace_threshold=nonspace_threshold,
        content_bytes_max=content_bytes_max,
        ink_ratio_max=ink_ratio_max,
        force_blank=force_blank,
        force_keep=force_keep,
    )
    blank_set = set(blank_pages)

    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        p_no = i + 1
        if p_no in blank_set:
            continue
        writer.add_page(page)

    with output_pdf.open("wb") as f:
        writer.write(f)

    return {
        "input": str(input_pdf),
        "output": str(output_pdf),
        "old_page_count": len(reader.pages),
        "new_page_count": len(reader.pages) - len(blank_pages),
        "removed_blank_pages": blank_pages,
    }


def count_non_blank_pages(
    input_pdf: Path,
    *,
    nonspace_threshold: int = NONSPACE_THRESHOLD,
    content_bytes_max: int = CONTENT_BYTES_MAX,
    ink_ratio_max: float = INK_RATIO_MAX,
    force_blank: Iterable[int] = (),
    force_keep: Iterable[int] = (),
) -> dict[str, Any]:
    reader = PdfReader(str(input_pdf))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:  # pragma: no cover
            raise SystemExit(f"PDF encrypted and cannot be opened: {exc}") from exc

    blank_pages = detect_blank_pages(
        input_pdf,
        nonspace_threshold=nonspace_threshold,
        content_bytes_max=content_bytes_max,
        ink_ratio_max=ink_ratio_max,
        force_blank=force_blank,
        force_keep=force_keep,
    )
    return {
        "input": str(input_pdf),
        "old_page_count": len(reader.pages),
        "blank_page_count": len(blank_pages),
        "non_blank_page_count": len(reader.pages) - len(blank_pages),
        "removed_blank_pages": blank_pages,
    }


def _report(pdf: Path, metrics: list[dict[str, Any]], ink_ratio_max: float) -> None:
    blank = [m["page"] for m in metrics if m["blank"]]
    ink_available = any(m["ink_ratio"] is not None for m in metrics)
    print(f"文件：{pdf.name}｜共 {len(metrics)} 页")
    print(
        "判定依据："
        + ("渲染墨迹比例（适用于扫描件）" if ink_available else "文字长度 + 内容流大小")
        + f"｜空白阈值 ink ≤ {ink_ratio_max:.4%}"
    )
    print()
    print(f"{'页':>4}  {'文字字数':>8}  {'图像数':>6}  {'内容流字节':>10}  {'墨迹比例':>9}  判定")
    for m in metrics:
        ink = "—" if m["ink_ratio"] is None else f"{m['ink_ratio']:.4%}"
        verdict = "空白（将移除）" if m["blank"] else "有内容（保留）"
        print(
            f"{m['page']:>4}  {m['nonspace_len']:>8}  {m['image_xobject_count']:>6}  "
            f"{m['content_bytes']:>10}  {ink:>9}  {verdict}［{m['reason']}］"
        )
    print()
    print(f"判定为空白：{', '.join(str(p) for p in blank) if blank else '无'}")
    print(f"实际插入页数：{len(metrics) - len(blank)} 页")
    if not ink_available:
        print(
            "\n提示：未安装 pymupdf，扫描件无法按墨迹判定。"
            "安装后更准确：.venv/bin/pip install pymupdf",
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="检查 PDF 每页的空白判定依据（本机运行，不输出页面文字）",
    )
    parser.add_argument("--pdf", required=True, type=Path, help="要检查的 PDF")
    parser.add_argument(
        "--ink-ratio-max",
        type=float,
        default=INK_RATIO_MAX,
        help=f"墨迹比例阈值，低于该值视为空白（默认 {INK_RATIO_MAX}）",
    )
    parser.add_argument(
        "--nonspace-threshold",
        type=int,
        default=NONSPACE_THRESHOLD,
        help="文字字数超过该值即视为有内容",
    )
    parser.add_argument(
        "--force-blank",
        default="",
        help="手动指定为空白的页码，如 3,5 或 8-9",
    )
    parser.add_argument(
        "--force-keep",
        default="",
        help="手动指定必须保留的页码，如 2",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument(
        "--clean-to",
        type=Path,
        default=None,
        help="按判定结果写出去掉空白页的新 PDF",
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        print(f"找不到文件：{args.pdf}", file=sys.stderr)
        return 1

    metrics = page_metrics(
        args.pdf,
        nonspace_threshold=args.nonspace_threshold,
        ink_ratio_max=args.ink_ratio_max,
    )
    try:
        force_blank = parse_page_list(args.force_blank, max_page=len(metrics))
        force_keep = parse_page_list(args.force_keep, max_page=len(metrics))
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    blank_pages = resolve_blank_pages(
        [m["page"] for m in metrics if m["blank"]],
        force_blank=force_blank,
        force_keep=force_keep,
    )
    blank_set = set(blank_pages)
    for m in metrics:
        if m["page"] in blank_set and not m["blank"]:
            m["blank"], m["reason"] = True, "manual_blank"
        elif m["page"] not in blank_set and m["blank"]:
            m["blank"], m["reason"] = False, "manual_keep"

    if args.json:
        print(
            json.dumps(
                {
                    "pdf": str(args.pdf),
                    "page_count": len(metrics),
                    "blank_pages": blank_pages,
                    "non_blank_page_count": len(metrics) - len(blank_pages),
                    "ink_ratio_max": args.ink_ratio_max,
                    "pages": metrics,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        _report(args.pdf, metrics, args.ink_ratio_max)

    if args.clean_to:
        result = clean_pdf_remove_blank_pages(
            args.pdf,
            args.clean_to,
            nonspace_threshold=args.nonspace_threshold,
            ink_ratio_max=args.ink_ratio_max,
            force_blank=force_blank,
            force_keep=force_keep,
        )
        print(
            f"\n已写出：{result['output']}"
            f"（{result['old_page_count']} → {result['new_page_count']} 页）"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

