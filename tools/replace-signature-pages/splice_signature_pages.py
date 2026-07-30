#!/usr/bin/env python3
"""Splice signed signature pages into a contract PDF at confirmed ranges."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print(
        "Missing dependency: pypdf. From repo root run:\n"
        "  python3 -m venv .venv && .venv/bin/pip install pypdf",
        file=sys.stderr,
    )
    sys.exit(1)

from blank_page_detector import detect_blank_pages


def parse_range(spec: str) -> tuple[int, int]:
    """Parse '12' or '12-13' as 1-based inclusive page numbers."""
    spec = spec.strip()
    if "-" in spec:
        a, b = spec.split("-", 1)
        start, end = int(a.strip()), int(b.strip())
    else:
        start = end = int(spec)
    if start < 1 or end < start:
        raise ValueError(f"Invalid page range: {spec}")
    return start, end


def parse_replace(spec: str) -> tuple[int, int, Path]:
    """Parse '12-13:/path/to/signed.pdf'."""
    if ":" not in spec:
        raise ValueError(
            f"Expected START-END:path, got: {spec!r}. Example: 12-13:/tmp/signed.pdf"
        )
    # Allow Windows drives by splitting on first colon only when path-like;
    # Prefer last colon if range has no slash after first colon... Use rsplit once
    # for '12-13:/path' and '12-13:C:\\x.pdf' → better split on first ':' after range.
    range_part, path_part = spec.split(":", 1)
    # If path_part looks like Windows 'C\\...' after empty, handle '12-13:C:/x'
    start, end = parse_range(range_part)
    path = Path(path_part)
    return start, end, path


def page_box(page) -> tuple[float, float]:
    box = page.mediabox
    return float(box.width), float(box.height)


def splice(
    contract: Path,
    replacements: list[tuple[int, int, Path]],
    output: Path,
    *,
    clean_signed_blank_pages: bool = False,
    signed_blank_nonspace_threshold: int = 15,
    signed_blank_content_bytes_max: int = 800,
    signed_blank_pages: dict[Path, list[int]] | None = None,
) -> dict[str, Any]:
    """Replace contract page ranges with signed pages.

    `signed_blank_pages` maps a signed PDF to the 1-based pages to drop. When a
    signed file appears there its list is authoritative (that is how a
    user-reviewed decision reaches this step); otherwise blank pages are
    detected only if `clean_signed_blank_pages` is set.
    """
    if output.resolve() == contract.resolve():
        raise SystemExit(
            "Refusing to overwrite the contract. Choose a different --output path."
        )

    reader = PdfReader(str(contract))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise SystemExit(f"Contract PDF is encrypted and cannot be opened: {exc}") from exc

    old_count = len(reader.pages)
    warnings: list[str] = []

    # Validate ranges against current (pre-splice) page count; apply high→low
    sorted_reps = sorted(replacements, key=lambda r: r[0], reverse=True)
    for start, end, signed_path in sorted_reps:
        if end > old_count:
            raise SystemExit(
                f"Range {start}-{end} exceeds contract page count {old_count}"
            )
        if not signed_path.is_file():
            raise SystemExit(f"Signed PDF not found: {signed_path}")

    # Build list of pages as PdfReader page objects; we'll reconstruct writer
    # Strategy: work with a list of (source_reader, page_index) or embedded pages.
    # Simpler: clone all contract pages into a list, then for each replace mutate list.

    pages = list(reader.pages)
    ops: list[dict[str, Any]] = []
    total_removed = 0
    total_inserted = 0

    # Re-apply in descending order on the live list using original coordinates
    # After a higher-page replace, lower indices unchanged — good.
    for start, end, signed_path in sorted_reps:
        # Convert to 0-based on *original* indices; since we go high→low,
        # indices still match the original contract for remaining lower pages.
        # BUT after a previous high replace, page count changed above `start`.
        # Descending order keeps `start-1:end` indices valid for lower blocks.
        lo, hi = start - 1, end  # slice [lo:hi)
        l_count = hi - lo
        signed_reader = PdfReader(str(signed_path))
        if signed_reader.is_encrypted:
            try:
                signed_reader.decrypt("")
            except Exception as exc:
                raise SystemExit(f"Signed PDF encrypted: {signed_path}: {exc}") from exc
        signed_pages_all = list(signed_reader.pages)

        removed_blank_pages: list[int] = []
        if signed_blank_pages is not None and signed_path in signed_blank_pages:
            removed_blank_pages = sorted(signed_blank_pages[signed_path])
        elif clean_signed_blank_pages:
            removed_blank_pages = detect_blank_pages(
                signed_path,
                nonspace_threshold=signed_blank_nonspace_threshold,
                content_bytes_max=signed_blank_content_bytes_max,
            )
        blank_set = set(removed_blank_pages)
        signed_pages = [
            p for idx, p in enumerate(signed_pages_all, start=1) if idx not in blank_set
        ]
        s_count = len(signed_pages)
        if s_count == 0:
            raise SystemExit(f"Signed PDF has 0 pages: {signed_path}")

        # Size / rotation warnings vs first replaced page
        if lo < len(pages):
            cw, ch = page_box(pages[lo])
            for i, sp in enumerate(signed_pages):
                sw, sh = page_box(sp)
                if abs(sw - cw) > 5 or abs(sh - ch) > 5:
                    warnings.append(
                        f"Range {start}-{end} signed page {i + 1} size "
                        f"{sw:.1f}x{sh:.1f} differs from contract {cw:.1f}x{ch:.1f}"
                    )
                rot = sp.get("/Rotate", 0)
                if rot not in (0, None):
                    warnings.append(
                        f"Range {start}-{end} signed page {i + 1} has Rotate={rot}"
                    )

        new_slice = signed_pages
        pages[lo:hi] = new_slice
        total_removed += l_count
        total_inserted += s_count
        ops.append(
            {
                "range": f"{start}-{end}",
                "removed_pages": l_count,
                "inserted_pages": s_count,
                "signed": str(signed_path),
                "mode": "equal" if l_count == s_count else ("expand" if s_count > l_count else "shrink"),
                "removed_blank_signed_pages": len(removed_blank_pages),
                "removed_blank_signed_page_indices": (
                    removed_blank_pages[:12] if removed_blank_pages else []
                ),
            }
        )

    writer = PdfWriter()
    for page in pages:
        writer.add_page(page)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as f:
        writer.write(f)

    new_count = len(pages)
    expected = old_count - total_removed + total_inserted
    if new_count != expected:
        warnings.append(
            f"Page count mismatch: got {new_count}, expected {expected}"
        )

    return {
        "contract": str(contract),
        "output": str(output),
        "old_page_count": old_count,
        "new_page_count": new_count,
        "operations": ops,
        "warnings": warnings,
        "ok": new_count == expected,
    }


def default_output_path(contract: Path) -> Path:
    return contract.with_name(f"{contract.stem}_已嵌签字页{contract.suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Replace contract page ranges with signed signature-page PDFs."
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        help="START-END:/path/to/signed.pdf (repeatable). Pages are 1-based inclusive.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output PDF (default: <contract>_已嵌签字页.pdf)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report only")
    parser.add_argument(
        "--clean-signed-blank-pages",
        action="store_true",
        help="Remove疑似空白页 from signed PDFs before inserting.",
    )
    parser.add_argument(
        "--signed-blank-nonspace-threshold",
        type=int,
        default=15,
        help="If extracted text has <= this many non-space chars, it may be blank.",
    )
    parser.add_argument(
        "--signed-blank-content-bytes-max",
        type=int,
        default=800,
        help="If content stream bytes <= this and no image XObjects, treat as blank.",
    )
    args = parser.parse_args()

    if not args.contract.is_file():
        print(f"Contract not found: {args.contract}", file=sys.stderr)
        return 1
    if not args.replace:
        print("At least one --replace START-END:path is required.", file=sys.stderr)
        return 1

    try:
        replacements = [parse_replace(spec) for spec in args.replace]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    # Overlap check on original coordinates
    spans = sorted((s, e) for s, e, _ in replacements)
    for i in range(len(spans) - 1):
        if spans[i][1] >= spans[i + 1][0]:
            print(
                f"Overlapping ranges not allowed: {spans[i][0]}-{spans[i][1]} "
                f"and {spans[i + 1][0]}-{spans[i + 1][1]}",
                file=sys.stderr,
            )
            return 1

    output = args.output or default_output_path(args.contract)
    try:
        report = splice(
            args.contract,
            replacements,
            output,
            clean_signed_blank_pages=args.clean_signed_blank_pages,
            signed_blank_nonspace_threshold=args.signed_blank_nonspace_threshold,
            signed_blank_content_bytes_max=args.signed_blank_content_bytes_max,
        )
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if report["warnings"]:
            print("\nWarnings:", file=sys.stderr)
            for w in report["warnings"]:
                print(f"  - {w}", file=sys.stderr)
    return 0 if report.get("ok", True) else 2


if __name__ == "__main__":
    sys.exit(main())
