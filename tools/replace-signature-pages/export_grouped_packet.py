#!/usr/bin/env python3
"""Group extracted signature pages by investor or signatory. Local only, no AI."""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from collections import defaultdict
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

from extract_signature_pages import extract_signature_pages
from prepare_print_packet import validate_ranges
from sig_unit import (
    EMPTY_PARTY,
    EMPTY_SIGNATORY,
    SigUnit,
    load_tags_file,
    safe_filename,
    save_tags_file,
)

GROUP_SIGNATORY = "signatory"
GROUP_PARTY = "party"
GROUP_INVESTOR = "investor"  # alias of party
GROUP_BOTH = "both"
GROUP_MODES = (GROUP_SIGNATORY, GROUP_PARTY, GROUP_INVESTOR, GROUP_BOTH)

DIR_LABELS = {
    GROUP_SIGNATORY: "按签字人",
    GROUP_PARTY: "按签署主体",
    GROUP_INVESTOR: "按签署主体",
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


def _sort_units(units: list[SigUnit]) -> list[SigUnit]:
    return sorted(
        units,
        key=lambda u: (
            u.document_name,
            u.start,
            u.end,
            u.party,
            u.party_role,
            u.signatory,
        ),
    )


def build_group_pdf(
    reader: PdfReader,
    units: list[SigUnit],
) -> PdfWriter:
    writer = PdfWriter()
    total = len(reader.pages)
    for unit in _sort_units(units):
        if unit.end > total or unit.start < 1:
            raise SystemExit(
                f"Unit range {unit.range_label} exceeds contract page count {total}"
            )
        for _ in range(unit.copies):
            for idx in unit.page_indices:
                writer.add_page(reader.pages[idx])
    return writer


def _write_group_tree(
    *,
    reader: PdfReader,
    units: list[SigUnit],
    mode: str,
    out_dir: Path,
    contract: Path,
) -> list[dict[str, Any]]:
    groups: dict[str, list[SigUnit]] = defaultdict(list)
    for unit in units:
        groups[unit.group_key(mode)].append(unit)

    dir_name = DIR_LABELS[mode]
    mode_dir = out_dir / dir_name
    mode_dir.mkdir(parents=True, exist_ok=True)

    written: list[dict[str, Any]] = []
    used_names: dict[str, int] = {}

    for key in sorted(groups.keys(), key=lambda k: (k.startswith("（"), k)):
        group_units = groups[key]
        writer = build_group_pdf(reader, group_units)
        base = safe_filename(key)
        n = used_names.get(base, 0)
        used_names[base] = n + 1
        filename = f"{base}.pdf" if n == 0 else f"{base}_{n + 1}.pdf"
        path = mode_dir / filename
        if path.resolve() == contract.resolve():
            raise SystemExit("Refusing to overwrite the contract.")
        with path.open("wb") as f:
            writer.write(f)
        page_count = len(writer.pages)
        written.append(
            {
                "mode": mode,
                "group_key": key,
                "path": str(path),
                "relative": f"{dir_name}/{filename}",
                "page_count": page_count,
                "unit_count": len(group_units),
                "units": [u.to_dict() for u in _sort_units(group_units)],
                "unlabeled": key in {EMPTY_PARTY, EMPTY_SIGNATORY},
            }
        )
    return written


def _format_guide_md(report: dict[str, Any]) -> str:
    lines = [
        "# 签字页分组说明",
        "",
        "## 输入",
        f"- 合同：`{report['contract']}`",
        f"- 签字单元数：{report['unit_count']}",
        f"- 分组模式：{report['group']}",
        "",
        "## 标签一览",
        "",
        "| 区间 | 角色 | 签署主体 | 签字人 | 身份 | 份数 |",
        "|------|------|----------|--------|------|------|",
    ]
    for u in report["units"]:
        lines.append(
            f"| {u['range']} | {u.get('party_role') or '—'} | "
            f"{u.get('party') or u.get('investor') or '—'} | "
            f"{u['signatory'] or '—'} "
            f"| {u['capacity'] or '—'} | {u['copies']} |"
        )
    lines.extend(["", "## 输出", ""])
    for g in report.get("groups") or []:
        flag = " ⚠未填标签" if g.get("unlabeled") else ""
        lines.append(
            f"- `{g['relative']}`：{g['page_count']} 页"
            f"（{g['unit_count']} 段）{flag}"
        )
    if report.get("outputs", {}).get("zip"):
        lines.append(f"- ZIP：`{report['outputs']['zip']}`")
    if report.get("outputs", {}).get("combined_extract"):
        lines.append(f"- 未分组合并签字页：`{report['outputs']['combined_extract']}`")
    lines.extend(
        [
            "",
            "## 说明",
            "1. **签署主体**可以是投资方或融资方（公司）等，不限投资人。",
            "2. 分组仅按本机确认的签署主体 / 签字人标签；未调用 AI。",
            "3. 原合同未修改。",
            "4. 「未填」桶表示该维度标签为空，请人工补标签后重跑。",
            "",
        ]
    )
    return "\n".join(lines)


def export_grouped_packet(
    contract: Path,
    units: list[SigUnit],
    *,
    output_dir: Path | None = None,
    group: str = GROUP_BOTH,
    also_extract: bool = True,
    also_zip: bool = True,
    save_tags_path: Path | None = None,
) -> dict[str, Any]:
    """Write grouped signature PDFs (+ optional combined extract + zip)."""
    if group not in GROUP_MODES:
        raise SystemExit(f"group must be one of {GROUP_MODES}")
    if not units:
        raise SystemExit("At least one tagged signature unit is required.")

    base = output_dir if output_dir is not None else contract.parent
    packet_root = base / f"{contract.stem}_签字页分组包"
    packet_root.mkdir(parents=True, exist_ok=True)

    if packet_root.resolve() == contract.resolve():
        raise SystemExit("Refusing to overwrite the contract.")

    # Fill document defaults
    for u in units:
        if not u.document_name:
            u.document_name = contract.stem
        if not u.source_contract:
            u.source_contract = str(contract)

    reader = _load_reader(contract)
    total = len(reader.pages)
    # Ranges may overlap when one page has multiple parties — validate each alone
    for u in units:
        validate_ranges([(u.start, u.end)], total)

    modes = (
        [GROUP_SIGNATORY, GROUP_PARTY]
        if group == GROUP_BOTH
        else [GROUP_PARTY if group == GROUP_INVESTOR else group]
    )

    all_groups: list[dict[str, Any]] = []
    for mode in modes:
        all_groups.extend(
            _write_group_tree(
                reader=reader,
                units=units,
                mode=mode,
                out_dir=packet_root,
                contract=contract,
            )
        )

    tags_path = save_tags_path or (packet_root / "tags.json")
    save_tags_file(
        tags_path,
        units,
        contract=contract,
        document_name=contract.stem,
    )

    combined_path: Path | None = None
    if also_extract:
        # Unique page ranges for combined extract (coalesce by pages, not labels)
        page_set: set[int] = set()
        for u in units:
            page_set.update(range(u.start, u.end + 1))
        if page_set:
            # Build minimal non-overlapping ranges for extract helper
            pages = sorted(page_set)
            ranges: list[tuple[int, int]] = []
            s = e = pages[0]
            for p in pages[1:]:
                if p == e + 1:
                    e = p
                else:
                    ranges.append((s, e))
                    s = e = p
            ranges.append((s, e))
            extract_report = extract_signature_pages(
                contract,
                ranges,
                output_dir=packet_root,
                signature_output=packet_root / f"{contract.stem}_签字页_未分组.pdf",
                report_json_output=packet_root / f"{contract.stem}_提取说明.json",
                report_md_output=packet_root / f"{contract.stem}_提取说明.md",
            )
            combined_path = Path(extract_report["outputs"]["signature_pages"])

    report: dict[str, Any] = {
        "ok": True,
        "flow": "C+",
        "mode": "packet",
        "contract": str(contract),
        "group": group,
        "unit_count": len(units),
        "units": [u.to_dict() for u in _sort_units(units)],
        "groups": all_groups,
        "outputs": {
            "packet_dir": str(packet_root),
            "tags": str(tags_path),
            "manifest": str(packet_root / "manifest.json"),
            "guide_md": str(packet_root / "分组说明.md"),
            "combined_extract": str(combined_path) if combined_path else None,
            "zip": None,
        },
        "instructions": [
            "分组仅依据本机确认的签署主体（投资方或融资方等）/ 签字人标签。",
            "未调用 AI；原合同未修改。",
            "请检查「未填」桶，补标签后可重跑。",
        ],
    }

    unlabeled = [g for g in all_groups if g.get("unlabeled")]
    report["unlabeled_group_count"] = len(unlabeled)
    report["ok"] = True

    guide = packet_root / "分组说明.md"
    guide.write_text(_format_guide_md(report), encoding="utf-8")
    manifest = packet_root / "manifest.json"
    manifest.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    zip_path: Path | None = None
    if also_zip:
        zip_path = base / f"{contract.stem}_签字页分组包.zip"
        if zip_path.resolve() == contract.resolve():
            raise SystemExit("Refusing to overwrite the contract.")
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in packet_root.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(packet_root.parent)))
        report["outputs"]["zip"] = str(zip_path)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Group signature pages by party (签署主体: investor or company) "
            "and/or signatory (local tags only; no AI)."
        )
    )
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument(
        "--tags",
        required=True,
        type=Path,
        help="JSON tags: units[].range / party|investor / party_role / signatory",
    )
    parser.add_argument(
        "--group",
        choices=list(GROUP_MODES),
        default=GROUP_BOTH,
        help="signatory | party | investor(=party) | both (default)",
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Do not also write combined ungrouped signature PDF",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Do not write zip archive",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.contract.is_file():
        print(f"Contract not found: {args.contract}", file=sys.stderr)
        return 1

    try:
        units = load_tags_file(
            args.tags,
            default_document=args.contract.stem,
            default_contract=str(args.contract),
        )
    except Exception as exc:  # noqa: BLE001
        print(f"tags 无效: {exc}", file=sys.stderr)
        return 1

    try:
        report = export_grouped_packet(
            args.contract,
            units,
            output_dir=args.output_dir,
            group=args.group,
            also_extract=not args.no_extract,
            also_zip=not args.no_zip,
        )
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok", True) else 2


if __name__ == "__main__":
    sys.exit(main())
