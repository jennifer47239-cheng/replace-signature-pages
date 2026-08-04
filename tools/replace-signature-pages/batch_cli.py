#!/usr/bin/env python3
"""Batch Flow B (and locate) over a folder of contracts — confirm or ranges-file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from locate_signature_pages import DEFAULT_PATTERNS, load_patterns, locate
from prepare_print_packet import prepare_print_packet
from ranges_util import format_ranges, parse_multi_ranges
from splice_signature_pages import parse_range


def _load_ranges_file(path: Path) -> dict[str, list[tuple[int, int]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[tuple[int, int]]] = {}
    if not isinstance(data, dict):
        raise ValueError("ranges file must be a JSON object: filename -> ranges")
    for name, specs in data.items():
        if isinstance(specs, str):
            specs = [specs]
        out[name] = [parse_range(str(s)) if isinstance(s, str) else tuple(s) for s in specs]  # type: ignore[misc]
        # normalize
        out[name] = [(int(a), int(b)) for a, b in out[name]]
    return out


def run_batch_print(
    contracts: list[Path],
    output_dir: Path,
    *,
    ocr: bool = False,
    ranges_map: dict[str, list[tuple[int, int]]] | None = None,
    interactive: bool = True,
) -> dict:
    patterns = load_patterns(DEFAULT_PATTERNS)
    output_dir.mkdir(parents=True, exist_ok=True)
    report: list[dict] = []

    for contract in contracts:
        entry: dict = {"contract": str(contract), "name": contract.name}
        result = locate(contract, [], patterns, ocr=ocr)
        entry["candidates"] = [
            {"start": c["start"], "end": c["end"], "confidence": c["confidence"]}
            for c in result.get("candidates") or []
        ]
        entry["low_text_page_count"] = result.get("low_text_page_count")
        entry["ocr_pages"] = result.get("ocr_pages")

        ranges = None
        if ranges_map is not None:
            ranges = ranges_map.get(contract.name) or ranges_map.get(str(contract))
        if ranges is None and interactive:
            print(f"\n=== {contract.name} ===")
            print(f"候选：{entry['candidates'] or '无'}")
            raw = input(
                "确认页码（如 8-9 或 8-9,20-21；回车跳过；q 结束批量）: "
            ).strip()
            if raw.lower() in {"q", "quit", "exit"}:
                entry["status"] = "aborted"
                report.append(entry)
                break
            if not raw:
                entry["status"] = "skipped"
                report.append(entry)
                continue
            try:
                ranges = parse_multi_ranges(raw)
            except ValueError as exc:
                entry["status"] = "error"
                entry["error"] = str(exc)
                report.append(entry)
                continue
        if not ranges:
            entry["status"] = "skipped"
            entry["reason"] = "no_ranges"
            report.append(entry)
            continue

        dest = output_dir / contract.stem
        try:
            pkt = prepare_print_packet(contract, ranges, output_dir=dest)
            entry["status"] = "ok"
            entry["ranges"] = format_ranges(ranges)
            entry["outputs"] = pkt.get("outputs")
            entry["blank_pad_count"] = pkt.get("blank_pad_count")
        except SystemExit as exc:
            entry["status"] = "error"
            entry["error"] = str(exc)
        except Exception as exc:  # noqa: BLE001
            entry["status"] = "error"
            entry["error"] = f"{type(exc).__name__}: {exc}"
        report.append(entry)

    summary = {
        "ok": sum(1 for r in report if r.get("status") == "ok"),
        "total": len(report),
        "items": report,
    }
    out_json = output_dir / "batch_report.json"
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary["report_path"] = str(out_json)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch duplex print packets (confirm per file or use --ranges-file)",
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        required=True,
        help="Folder of contract PDFs",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Output folder for packets + batch_report.json",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="OCR low-text pages during locate (macOS Vision)",
    )
    parser.add_argument(
        "--ranges-file",
        type=Path,
        help='JSON map: {"a.pdf": ["8-9","20-21"], ...} for non-interactive run',
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; requires --ranges-file",
    )
    args = parser.parse_args()

    if not args.batch_dir.is_dir():
        print(f"Not a directory: {args.batch_dir}", file=sys.stderr)
        return 1
    contracts = sorted(args.batch_dir.glob("*.pdf")) + sorted(args.batch_dir.glob("*.PDF"))
    # de-dupe
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in contracts:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            unique.append(p)
    if not unique:
        print(f"No PDFs in {args.batch_dir}", file=sys.stderr)
        return 1

    ranges_map = None
    if args.ranges_file:
        try:
            ranges_map = _load_ranges_file(args.ranges_file)
        except Exception as exc:  # noqa: BLE001
            print(f"Bad ranges file: {exc}", file=sys.stderr)
            return 1
    if args.non_interactive and not ranges_map:
        print("--non-interactive requires --ranges-file", file=sys.stderr)
        return 1

    summary = run_batch_print(
        unique,
        args.output_dir,
        ocr=args.ocr,
        ranges_map=ranges_map,
        interactive=not args.non_interactive,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary.get("ok", 0) > 0 else 2


if __name__ == "__main__":
    sys.exit(main())
