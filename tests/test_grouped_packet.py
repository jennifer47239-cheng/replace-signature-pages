"""Tests for signature-page tagging and grouped packet export."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

TOOL_DIR = Path(__file__).resolve().parents[1] / "tools" / "replace-signature-pages"
sys.path.insert(0, str(TOOL_DIR))

from export_grouped_packet import export_grouped_packet  # noqa: E402
from sig_unit import (  # noqa: E402
    EMPTY_SIGNATORY,
    SigUnit,
    load_tags_file,
    safe_filename,
)


def _make_pdf(path: Path, n_pages: int) -> None:
    writer = PdfWriter()
    for _ in range(n_pages):
        writer.add_blank_page(width=200, height=200)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        writer.write(f)


def test_load_tags_json(tmp_path: Path) -> None:
    tags = tmp_path / "tags.json"
    tags.write_text(
        json.dumps(
            {
                "units": [
                    {
                        "range": "8-9",
                        "investor": "基金A",
                        "signatory": "张三",
                        "copies": 2,
                    },
                    {
                        "range": "20",
                        "party": "公司B",
                        "signatory": "李四",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    units = load_tags_file(tags)
    assert len(units) == 2
    assert units[0].start == 8 and units[0].end == 9
    assert units[0].copies == 2
    assert units[1].party == "公司B"


def test_safe_filename() -> None:
    assert "/" not in safe_filename("甲/乙")
    assert safe_filename("某某基金") == "某某基金"


def test_export_grouped_both(tmp_path: Path) -> None:
    contract = tmp_path / "deal.pdf"
    _make_pdf(contract, 24)
    units = [
        SigUnit(8, 9, party="基金A", party_role="投资方", signatory="张三", copies=1),
        SigUnit(20, 21, party="基金A", party_role="投资方", signatory="李四", copies=1),
        SigUnit(20, 21, party="公司B", party_role="融资方", signatory="李四", copies=1),
    ]
    report = export_grouped_packet(
        contract,
        units,
        output_dir=tmp_path / "out",
        group="both",
        also_extract=True,
        also_zip=True,
    )
    assert report["ok"]
    assert report["unit_count"] == 3
    packet = Path(report["outputs"]["packet_dir"])
    assert (packet / "按签字人" / "张三.pdf").is_file()
    assert (packet / "按签字人" / "李四.pdf").is_file()
    assert (packet / "按签署主体" / "基金A.pdf").is_file()
    assert (packet / "按签署主体" / "公司B.pdf").is_file()
    # 张三: pages 8-9 → 2 pages
    assert len(PdfReader(str(packet / "按签字人" / "张三.pdf")).pages) == 2
    # 李四: 20-21 twice (two units) → 4 pages
    assert len(PdfReader(str(packet / "按签字人" / "李四.pdf")).pages) == 4
    # 基金A: 8-9 + 20-21 → 4 pages
    assert len(PdfReader(str(packet / "按签署主体" / "基金A.pdf")).pages) == 4
    assert Path(report["outputs"]["zip"]).is_file()
    assert Path(report["outputs"]["tags"]).is_file()
    assert Path(report["outputs"]["guide_md"]).is_file()
    # source unchanged
    assert len(PdfReader(str(contract)).pages) == 24


def test_export_empty_signatory_bucket(tmp_path: Path) -> None:
    contract = tmp_path / "c.pdf"
    _make_pdf(contract, 5)
    units = [SigUnit(2, 2, party="基金A", signatory="")]
    report = export_grouped_packet(
        contract,
        units,
        output_dir=tmp_path / "out",
        group="signatory",
        also_extract=False,
        also_zip=False,
    )
    assert report["unlabeled_group_count"] >= 1
    packet = Path(report["outputs"]["packet_dir"])
    assert (packet / "按签字人" / f"{EMPTY_SIGNATORY}.pdf").is_file()


def test_tags_investor_alias_and_role(tmp_path: Path) -> None:
    tags = tmp_path / "tags.json"
    tags.write_text(
        json.dumps(
            {
                "units": [
                    {
                        "range": "1",
                        "investor": "旧字段基金",
                        "party_role": "投资方",
                        "signatory": "甲",
                    },
                    {
                        "range": "2",
                        "party": "目标公司",
                        "party_role": "融资方",
                        "signatory": "乙",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    units = load_tags_file(tags)
    assert units[0].party == "旧字段基金"
    assert units[0].party_role == "投资方"
    assert units[1].party_role == "融资方"
