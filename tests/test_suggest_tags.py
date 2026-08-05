"""Tests for local tag suggestion heuristics."""

from __future__ import annotations

import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parents[1] / "tools" / "replace-signature-pages"
sys.path.insert(0, str(TOOL_DIR))

from suggest_tags import (  # noqa: E402
    estimate_block_count,
    extract_candidates_from_text,
)


def test_extract_investors_and_signatories_en() -> None:
    text = """
    SIGNATURE PAGE
    EXECUTED by ACME Ventures Limited
    By: ________________
    Name: Jane Smith
    Title: Director
    """
    c = extract_candidates_from_text(text)
    assert any("ACME Ventures Limited" in x for x in c["investors"])
    assert "Jane Smith" in c["signatories"]
    assert any("Director" in x for x in c["capacities"])


def test_extract_cn_entity() -> None:
    text = "甲方（盖章）：某某创业投资合伙企业（有限合伙）\n授权代表 张三"
    c = extract_candidates_from_text(text)
    assert any("某某创业投资合伙企业（有限合伙）" in x for x in c["investors"])
    assert "张三" in c["signatories"]


def test_estimate_blocks() -> None:
    text = "EXECUTED by A\nEXECUTED by B\nBy:\nBy:"
    assert estimate_block_count(text) >= 2
