#!/usr/bin/env python3
"""Prepare a duplex-safe print packet: body without signature pages + pads + extracted sig pages."""

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

from splice_signature_pages import page_box, parse_range


def needs_duplex_pad(start: int) -> bool:
    """True when page before the signature block is an odd front side (1-based).

    After removing [start, end], page start-1 and end+1 become adjacent. If
    start-1 is odd it is a sheet front, so end+1 would print on its back unless
    a blank is inserted.
    """
    before = start - 1
    return before >= 1 and before % 2 == 1


def validate_ranges(
    ranges: list[tuple[int, int]],
    total_pages: int,
) -> None:
    if not ranges:
        raise SystemExit("At least one confirmed signature range is required.")
    spans = sorted(ranges)
    for start, end in spans:
        if start < 1 or end < start:
            raise SystemExit(f"Invalid page range: {start}-{end}")
        if end > total_pages:
            raise SystemExit(
                f"Range {start}-{end} exceeds contract page count {total_pages}"
            )
    for i in range(len(spans) - 1):
        if spans[i][1] >= spans[i + 1][0]:
            raise SystemExit(
                f"Overlapping ranges not allowed: {spans[i][0]}-{spans[i][1]} "
                f"and {spans[i + 1][0]}-{spans[i + 1][1]}"
            )


def removed_pages(ranges: list[tuple[int, int]]) -> set[int]:
    pages: set[int] = set()
    for start, end in ranges:
        pages.update(range(start, end + 1))
    return pages


def pad_after_pages(ranges: list[tuple[int, int]], total_pages: int) -> set[int]:
    """Original 1-based page numbers after which a blank should be inserted."""
    pads: set[int] = set()
    for start, end in ranges:
        before = start - 1
        after = end + 1
        if needs_duplex_pad(start) and after <= total_pages:
            pads.add(before)
    return pads


def default_output_paths(contract: Path, output_dir: Path | None) -> dict[str, Path]:
    base = output_dir if output_dir is not None else contract.parent
    base.mkdir(parents=True, exist_ok=True)
    stem = contract.stem
    return {
        "body": base / f"{stem}_打印正文_去签字页.pdf",
        "signature_pages": base / f"{stem}_签字页_待签署.pdf",
        "job_json": base / f"{stem}_打印作业说明.json",
        "job_md": base / f"{stem}_打印作业说明.md",
    }


def prepare_print_packet(
    contract: Path,
    ranges: list[tuple[int, int]],
    *,
    output_dir: Path | None = None,
    body_output: Path | None = None,
    signature_output: Path | None = None,
    job_json_output: Path | None = None,
    job_md_output: Path | None = None,
) -> dict[str, Any]:
    """Strip confirmed signature ranges, pad duplex collisions, extract sig pages."""
    paths = default_output_paths(contract, output_dir)
    body_path = body_output or paths["body"]
    sig_path = signature_output or paths["signature_pages"]
    job_json = job_json_output or paths["job_json"]
    job_md = job_md_output or paths["job_md"]

    for out in (body_path, sig_path, job_json, job_md):
        if out.resolve() == contract.resolve():
            raise SystemExit(
                "Refusing to overwrite the contract. Choose a different output path."
            )

    reader = PdfReader(str(contract))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise SystemExit(f"Contract PDF is encrypted and cannot be opened: {exc}") from exc

    total = len(reader.pages)
    validate_ranges(ranges, total)
    remove = removed_pages(ranges)
    pads = pad_after_pages(ranges, total)

    body = PdfWriter()
    sig = PdfWriter()
    blank_inserts: list[dict[str, Any]] = []
    body_page_map: list[dict[str, Any]] = []  # output page provenance

    for idx, page in enumerate(reader.pages):
        page_no = idx + 1
        if page_no in remove:
            sig.add_page(page)
            continue

        body.add_page(page)
        body_page_map.append(
            {
                "output_page": len(body.pages),
                "source_page": page_no,
                "kind": "body",
            }
        )

        if page_no in pads:
            width, height = page_box(page)
            body.add_blank_page(width=width, height=height)
            blank_page_no = len(body.pages)
            blank_inserts.append(
                {
                    "after_source_page": page_no,
                    "output_page": blank_page_no,
                    "reason": "duplex_collision",
                    "detail": (
                        f"原第 {page_no} 页为奇数正面；去掉签字页后下一保留页"
                        f"会打到背面，故插入空白页隔开"
                    ),
                }
            )
            body_page_map.append(
                {
                    "output_page": blank_page_no,
                    "source_page": None,
                    "kind": "blank_pad",
                }
            )

    if len(sig.pages) == 0:
        raise SystemExit("No signature pages extracted; check confirmed ranges.")

    for path in (body_path, sig_path, job_json, job_md):
        path.parent.mkdir(parents=True, exist_ok=True)

    with body_path.open("wb") as f:
        body.write(f)
    with sig_path.open("wb") as f:
        sig.write(f)

    range_specs = [f"{s}-{e}" if s != e else str(s) for s, e in sorted(ranges)]
    report: dict[str, Any] = {
        "ok": True,
        "contract": str(contract),
        "confirmed_ranges": range_specs,
        "removed_pages": sorted(remove),
        "removed_page_count": len(remove),
        "blank_pads": blank_inserts,
        "blank_pad_count": len(blank_inserts),
        "old_page_count": total,
        "body_page_count": len(body.pages),
        "signature_page_count": len(sig.pages),
        "outputs": {
            "body": str(body_path),
            "signature_pages": str(sig_path),
            "job_json": str(job_json),
            "job_md": str(job_md),
        },
        "body_page_map": body_page_map,
        "instructions": [
            "使用双面打印（长边翻转）打印「打印正文」PDF。",
            "单独打印「签字页_待签署」PDF，完成湿签。",
            "将已签签字页物理插入正文中空白隔页所在位置（或替换空白页）。",
            "电子归档时可用流程 A（splice）把已签 PDF 嵌回原合同电子版。",
        ],
    }

    job_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    job_md.write_text(_format_job_md(report), encoding="utf-8")
    return report


def _format_job_md(report: dict[str, Any]) -> str:
    ranges = ", ".join(report["confirmed_ranges"])
    pads = report["blank_pads"]
    pad_lines = (
        "\n".join(
            f"- 在原第 {p['after_source_page']} 页之后插入空白"
            f"（输出第 {p['output_page']} 页）：{p['detail']}"
            for p in pads
        )
        if pads
        else "- 无（各签字区前一页均为偶数背面，接合处自然新开一张）"
    )
    steps = "\n".join(f"{i}. {s}" for i, s in enumerate(report["instructions"], 1))
    outs = report["outputs"]
    return (
        f"# 打印作业说明\n\n"
        f"## 输入\n"
        f"- 合同：`{report['contract']}`\n"
        f"- 确认去掉的签字页：{ranges}\n"
        f"- 原页数：{report['old_page_count']} → 正文 "
        f"{report['body_page_count']} 页"
        f"（含空白隔页 {report['blank_pad_count']}）"
        f" + 待签署签字页 {report['signature_page_count']} 页\n\n"
        f"## 双面隔页\n{pad_lines}\n\n"
        f"## 输出文件\n"
        f"- 打印正文：`{outs['body']}`\n"
        f"- 待签署签字页：`{outs['signature_pages']}`\n"
        f"- 本说明（JSON）：`{outs['job_json']}`\n\n"
        f"## 建议步骤\n{steps}\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a duplex-safe print packet: contract body without signature "
            "pages, blank pads at duplex collisions, and extracted signature pages."
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
    parser.add_argument("--body-output", type=Path, default=None)
    parser.add_argument("--signature-output", type=Path, default=None)
    parser.add_argument("--job-json", type=Path, default=None)
    parser.add_argument("--job-md", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    args = parser.parse_args()

    if not args.contract.is_file():
        print(f"Contract not found: {args.contract}", file=sys.stderr)
        return 1
    if not args.ranges:
        print("At least one --range is required (confirmed pages only).", file=sys.stderr)
        return 1

    try:
        ranges = [parse_range(spec) for spec in args.ranges]
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        report = prepare_print_packet(
            args.contract,
            ranges,
            output_dir=args.output_dir,
            body_output=args.body_output,
            signature_output=args.signature_output,
            job_json_output=args.job_json,
            job_md_output=args.job_md,
        )
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if not args.json and report.get("blank_pad_count"):
        print(
            f"\nInserted {report['blank_pad_count']} duplex blank pad(s).",
            file=sys.stderr,
        )
    return 0 if report.get("ok", True) else 2


if __name__ == "__main__":
    sys.exit(main())
