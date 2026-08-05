#!/usr/bin/env python3
"""Local heuristics: suggest investor / signatory candidates from signature pages.

No network, no LLM. Text from pypdf; optional on-device OCR for low-text pages.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None  # type: ignore

from ranges_util import format_range
from sig_unit import normalize_label

# Entity-like endings (CN / EN)
_CN_ENTITY = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9（）()\-·.&' ]{2,60}"
    r"(?:有限责任公司|股份有限公司|有限公司|合伙企业（有限合伙）|"
    r"合伙企业\(有限合伙\)|合伙企业|投资中心（有限合伙）|"
    r"投资基金|基金合伙企业))"
)
_EN_ENTITY = re.compile(
    r"\b([A-Z][A-Za-z0-9&.,'\- ]{2,70}"
    r"(?:Limited|Ltd\.?|L\.P\.|LP|LLP|Inc\.?|Corp\.?|Corporation|"
    r"Company|Holdings|Partners|Partnership))\b"
)
_EXECUTED_BY = re.compile(
    r"(?:EXECUTED|SIGNED)\s+(?:as\s+a\s+deed\s+)?(?:by|for\s+and\s+on\s+behalf\s+of)\s*[:：]?\s*"
    r"([^\n\r]{3,80})",
    re.I,
)
_NAME_LINE = re.compile(
    r"(?:^|\n)\s*(?:Name|姓名|签署人|签字人)\s*[:：]\s*([^\n\r]{1,40})",
    re.I,
)
_TITLE_LINE = re.compile(
    r"(?:^|\n)\s*(?:Title|Capacity|Position|职务|职位|身份)\s*[:：]\s*([^\n\r]{1,40})",
    re.I,
)
_PERSON_CN = re.compile(r"^[\u4e00-\u9fff·]{2,4}$")
_PERSON_EN = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}$")

_NOISE = re.compile(
    r"(签字页|签署页|本页无正文|Signature\s+Page|IN\s+WITNESS|目录|附件)",
    re.I,
)


def _page_text(reader: Any, page_index: int) -> str:
    try:
        text = reader.pages[page_index].extract_text() or ""
    except Exception:
        text = ""
    return text.replace("\x00", "")


def _dedupe_keep_order(items: list[str], *, limit: int = 24) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        label = normalize_label(raw)
        label = re.sub(r"\s+", " ", label).strip(" ,;；、")
        if len(label) < 2 or label in seen:
            continue
        if _NOISE.search(label):
            continue
        seen.add(label)
        out.append(label)
        if len(out) >= limit:
            break
    return out


def _looks_like_person(name: str) -> bool:
    n = normalize_label(name)
    if not n or len(n) > 40:
        return False
    if _PERSON_CN.match(n):
        return True
    if _PERSON_EN.match(n):
        return True
    # Reject obvious entities
    if re.search(r"公司|企业|合伙|Limited|Ltd|Inc|Corp|基金", n, re.I):
        return False
    return 2 <= len(n) <= 30 and not re.search(r"\d{4,}", n)


def extract_candidates_from_text(text: str) -> dict[str, list[str]]:
    investors: list[str] = []
    signatories: list[str] = []
    capacities: list[str] = []

    for m in _EXECUTED_BY.finditer(text):
        investors.append(m.group(1))
    for m in _CN_ENTITY.finditer(text):
        investors.append(m.group(1))
    for m in _EN_ENTITY.finditer(text):
        investors.append(m.group(1))

    for m in _NAME_LINE.finditer(text):
        name = m.group(1).strip()
        # Skip blank underlines
        if re.fullmatch(r"[\s_\-—–/／]*", name):
            continue
        if _looks_like_person(name) or len(name) <= 40:
            signatories.append(name)

    for m in _TITLE_LINE.finditer(text):
        title = m.group(1).strip()
        if title and not re.fullmatch(r"[\s_\-—–]*", title):
            capacities.append(title)

    # Heuristic: short CN names near 授权代表 / 法定代表人
    for m in re.finditer(
        r"(?:授权代表|法定代表人|委派代表|Authorized\s+Signatory)[^\n]{0,20}"
        r"([^\n]{2,20})",
        text,
        re.I,
    ):
        chunk = normalize_label(m.group(1))
        chunk = re.split(r"[：:\s]", chunk)[0]
        if _looks_like_person(chunk):
            signatories.append(chunk)

    return {
        "investors": _dedupe_keep_order(investors),
        "signatories": _dedupe_keep_order(
            [s for s in signatories if _looks_like_person(s) or len(s) <= 20]
        ),
        "capacities": _dedupe_keep_order(capacities, limit=12),
    }


def estimate_block_count(text: str) -> int:
    """Guess how many signature blocks are on the page(s)."""
    markers = 0
    markers += len(re.findall(r"EXECUTED\s+by", text, re.I))
    markers += len(re.findall(r"FOR\s+AND\s+ON\s+BEHALF\s+OF", text, re.I))
    markers += len(re.findall(r"（盖章）|\(seal\)|公章|签字/盖章|签字／盖章", text, re.I))
    markers += len(re.findall(r"(?:^|\n)\s*By\s*:", text, re.I))
    # Chinese party labels on sig pages
    markers += len(re.findall(r"(?:甲方|乙方|丙方|投资方|融资方|转让方|受让方|公司)\s*[:：]", text))
    return max(1, min(markers, 12)) if markers else 1


def suggest_tags_for_ranges(
    contract: Path,
    ranges: list[tuple[int, int]],
    *,
    ocr: bool = False,
) -> dict[str, Any]:
    """Scan confirmed ranges; return per-range + global candidate pools."""
    if PdfReader is None:
        raise SystemExit("pypdf is required")

    reader = PdfReader(str(contract))
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise SystemExit(f"encrypted PDF: {exc}") from exc

    total = len(reader.pages)
    per_range: list[dict[str, Any]] = []
    all_investors: list[str] = []
    all_signatories: list[str] = []
    all_capacities: list[str] = []
    ocr_pages: list[int] = []

    for start, end in sorted(ranges):
        if start < 1 or end > total or end < start:
            raise SystemExit(f"invalid range {start}-{end} (contract has {total} pages)")
        texts: list[str] = []
        for page_no in range(start, end + 1):
            text = _page_text(reader, page_no - 1)
            compact = re.sub(r"\s+", "", text)
            if ocr and len(compact) < 15:
                try:
                    from page_ocr import ocr_pdf_pages, vision_ocr_available

                    if vision_ocr_available():
                        ocr_map = ocr_pdf_pages(contract, [page_no])
                        ocr_text = ocr_map.get(page_no, "")
                        if ocr_text.strip():
                            text = (text + "\n" + ocr_text).strip()
                            ocr_pages.append(page_no)
                except Exception:
                    pass
            texts.append(text)
        merged = "\n".join(texts)
        cands = extract_candidates_from_text(merged)
        blocks = estimate_block_count(merged)
        all_investors.extend(cands["investors"])
        all_signatories.extend(cands["signatories"])
        all_capacities.extend(cands["capacities"])
        per_range.append(
            {
                "range": format_range(start, end),
                "start": start,
                "end": end,
                "block_estimate": blocks,
                "investors": cands["investors"],
                "signatories": cands["signatories"],
                "capacities": cands["capacities"],
                "char_count": len(re.sub(r"\s+", "", merged)),
            }
        )

    return {
        "contract": str(contract),
        "ocr_pages": ocr_pages,
        "global": {
            "investors": _dedupe_keep_order(all_investors, limit=40),
            "signatories": _dedupe_keep_order(all_signatories, limit=40),
            "capacities": _dedupe_keep_order(all_capacities, limit=20),
        },
        "ranges": per_range,
    }
