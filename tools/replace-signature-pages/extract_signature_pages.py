#!/usr/bin/env python3
"""Flow C: extract confirmed signature-page ranges into PDF(s). Local only, no AI."""

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

from prepare_print_packet import removed_pages, validate_ranges
from ranges_util import format_range
from splice_signature_pages import parse_range


def default_output_paths(contract: Path, output_dir: Path | None) -> dict[str, Path]:
    base = output_dir if output_dir is not None else contract.parent
    base.mkdir(parents=True, exist_ok=True)
    stem = contract.stem
    return {
        "signature_pages": base / f"{stem}_签字页.pdf",
        "report_json": base / f"{stem}_提取说明.json",
        "report_md": base / f"{stem}_提取说明.md",
    }


def _load_reader(contract: Path) -> PdfReader:
    reader = PdfReader(str(contract))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise SystemExit(
                f"Contract PDF is encrypted and cannot be opened: {exc}"
            ) from exc
    return reader


def extract_signature_pages(
    contract: Path,
    ranges: list[tuple[int, int]],
    *,
    output_dir: Path | None = None,
    signature_output: Path | None = None,
    report_json_output: Path | None = None,
    report_md_output: Path | None = None,
    per_range: bool = False,
) -> dict[str, Any]:
    """Copy confirmed signature ranges into PDF(s); never overwrites the contract.

    Default: one combined PDF with all ranges in page order.
    With per_range=True: also write one PDF per range (e.g. stem_签字页_8-9.pdf).
    """
    paths = default_output_paths(contract, output_dir)
    sig_path = signature_output or paths["signature_pages"]
    report_json = report_json_output or paths["report_json"]
    report_md = report_md_output or paths["report_md"]

    for out in (sig_path, report_json, report_md):
        if out.resolve() == contract.resolve():
            raise SystemExit(
                "Refusing to overwrite the contract. Choose a different output path."
            )

    reader = _load_reader(contract)
    total = len(reader.pages)
    validate_ranges(ranges, total)
    page_set = removed_pages(ranges)
    spans = sorted(ranges)

    combined = PdfWriter()
    page_map: list[dict[str, Any]] = []
    for page_no in sorted(page_set):
        combined.add_page(reader.pages[page_no - 1])
        page_map.append(
            {
                "output_page": len(combined.pages),
                "source_page": page_no,
            }
        )

    if len(combined.pages) == 0:
        raise SystemExit("No signature pages extracted; check confirmed ranges.")

    base = sig_path.parent
    base.mkdir(parents=True, exist_ok=True)

    with sig_path.open("wb") as f:
        combined.write(f)

    per_range_outputs: list[dict[str, Any]] = []
    if per_range:
        for start, end in spans:
            label = format_range(start, end)
            part_path = base / f"{contract.stem}_签字页_{label}.pdf"
            if part_path.resolve() == contract.resolve():
                raise SystemExit(
                    "Refusing to overwrite the contract. Choose a different output path."
                )
            part = PdfWriter()
            for page_no in range(start, end + 1):
                part.add_page(reader.pages[page_no - 1])
            with part_path.open("wb") as f:
                part.write(f)
            per_range_outputs.append(
                {
                    "range": label,
                    "path": str(part_path),
                    "page_count": end - start + 1,
                }
            )

    range_specs = [format_range(s, e) for s, e in spans]
    report: dict[str, Any] = {
        "ok": True,
        "flow": "C",
        "mode": "extract",
        "contract": str(contract),
        "confirmed_ranges": range_specs,
        "extracted_pages": sorted(page_set),
        "extracted_page_count": len(page_set),
        "old_page_count": total,
        "signature_page_count": len(combined.pages),
        "per_range": per_range,
        "outputs": {
            "signature_pages": str(sig_path),
            "report_json": str(report_json),
            "report_md": str(report_md),
        },
        "per_range_outputs": per_range_outputs,
        "page_map": page_map,
        "instructions": [
            "本文件仅含已确认的签字页（从合同原件按页拷贝）。",
            "原合同未修改。",
            "若需去签字页正文 + 双面隔页，请使用流程 B（print-packet）。",
            "已签后嵌回完整电子版请使用流程 A（splice）。",
        ],
    }

    report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    report_md.write_text(_format_report_md(report), encoding="utf-8")
    return report


def _format_report_md(report: dict[str, Any]) -> str:
    ranges = ", ".join(report["confirmed_ranges"])
    outs = report["outputs"]
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(report["instructions"], 1))
    per_lines = ""
    if report.get("per_range_outputs"):
        items = "\n".join(
            f"- 区间 {p['range']}：`{p['path']}`（{p['page_count']} 页）"
            for p in report["per_range_outputs"]
        )
        per_lines = f"\n## 按段拆分\n{items}\n"
    return (
        f"# 签字页提取说明\n\n"
        f"## 输入\n"
        f"- 合同：`{report['contract']}`\n"
        f"- 确认抽取页码：{ranges}\n"
        f"- 原页数：{report['old_page_count']} → 抽出签字页 "
        f"{report['signature_page_count']} 页\n\n"
        f"## 输出文件\n"
        f"- 签字页 PDF：`{outs['signature_pages']}`\n"
        f"- 本说明（JSON）：`{outs['report_json']}`\n"
        f"{per_lines}\n"
        f"## 说明\n{steps}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract confirmed signature page ranges into a PDF "
            "(Flow C; local only, no AI)."
        )
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument(
        "--range",
        action="append",
        default=[],
        dest="ranges",
        help="Confirmed signature page range (1-based), e.g. 12-13 (repeatable)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for outputs (default: same folder as contract)",
    )
    parser.add_argument("--signature-output", type=Path, default=None)
    parser.add_argument("--report-json", type=Path, default=None)
    parser.add_argument("--report-md", type=Path, default=None)
    parser.add_argument(
        "--per-range",
        action="store_true",
        help="Also write one PDF per range (stem_签字页_8-9.pdf)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    args = parser.parse_args()

    if not args.contract.is_file():
        print(f"Contract not found: {args.contract}", file=sys.stderr)
        return 1
    if not args.ranges:
        print(
            "At least one --range is required (confirmed pages only).",
            file=sys.stderr,
        )
        return 1

    try:
        ranges = [parse_range(spec) for spec in args.ranges]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        report = extract_signature_pages(
            args.contract,
            ranges,
            output_dir=args.output_dir,
            signature_output=args.signature_output,
            report_json_output=args.report_json,
            report_md_output=args.report_md,
            per_range=args.per_range,
        )
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok", True) else 2


if __name__ == "__main__":
    sys.exit(main())
