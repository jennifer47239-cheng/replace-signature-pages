"""Tests for the local tag workbench HTML (two-step: label library → pages)."""

from __future__ import annotations

import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parents[1] / "tools" / "replace-signature-pages"
sys.path.insert(0, str(TOOL_DIR))

from tag_workbench import build_workbench_html  # noqa: E402

SUGGESTIONS = {
    "ranges": [
        {
            "range": "25-27",
            "block_estimate": 2,
            "investors": ["甲基金", "乙资本"],
            "signatories": ["张三"],
            "capacities": [],
        }
    ],
    "global": {"investors": ["甲基金", "乙资本"], "signatories": ["张三"], "capacities": []},
}


def _html() -> str:
    return build_workbench_html(
        contract_name="合同.pdf",
        ranges=[(25, 27)],
        suggestions=SUGGESTIONS,
        thumb_rel={str(p): f"p{p}.png" for p in range(25, 28)},
    )


def test_page_options_cover_whole_block_and_each_page() -> None:
    html = _html()
    assert '"25-27", "25", "26", "27"' in html.replace("'", '"')


def test_two_step_panes_and_bulk_controls_present() -> None:
    html = _html()
    for marker in ('id="pane-lib"', 'id="pane-assign"', 'id="lib-rows"', 'id="bulk-add"'):
        assert marker in html


def test_candidates_scroll_and_draft_survives_refresh() -> None:
    html = _html()
    assert "max-height: 150px; overflow-y: auto" in html
    assert 'id="global-chips"' in html
    assert "max-height: 120px; overflow-y: auto" in html
    assert 'id="draft-save"' in html
    assert "fetch('/draft'" in html
    assert "已恢复保存的标签草稿" in html


def test_thumbnails_can_zoom_and_target_the_current_row() -> None:
    html = _html()
    assert 'class="thumb"' in html
    assert 'data-page="26"' in html
    assert "本页 → 当前行" in html
    assert 'id="zoom-pane"' in html
