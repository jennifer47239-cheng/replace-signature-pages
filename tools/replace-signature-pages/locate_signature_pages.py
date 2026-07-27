#!/usr/bin/env python3
"""Locate likely signature-page ranges in a contract PDF (read-only)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    from pypdf import PdfReader
except ImportError:
    print(
        "Missing dependency: pypdf. From repo root run:\n"
        "  python3 -m venv .venv && .venv/bin/pip install pypdf",
        file=sys.stderr,
    )
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PATTERNS = SCRIPT_DIR / "patterns.json"


def load_patterns(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def page_count(pdf: Path) -> int:
    return len(PdfReader(str(pdf)).pages)


def extract_page_text(reader: PdfReader, index: int) -> str:
    try:
        text = reader.pages[index].extract_text() or ""
    except Exception:
        text = ""
    return text.replace("\x00", "")


def blank_ratio(text: str) -> float:
    """Heuristic: fewer non-space chars → more blank-looking page."""
    compact = re.sub(r"\s+", "", text)
    # Cap: treat very short pages as blank-heavy
    if len(compact) <= 40:
        return 1.0
    if len(compact) >= 800:
        return 0.0
    return max(0.0, 1.0 - (len(compact) - 40) / 760.0)


def score_page(
    text: str,
    page_index: int,
    total_pages: int,
    patterns: dict[str, Any],
) -> tuple[float, list[str], bool]:
    weights = patterns["weights"]
    signals: list[str] = []
    score = 0.0
    low_text = len(re.sub(r"\s+", "", text)) < 15

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    head = "\n".join(lines[:5])
    foot = "\n".join(lines[-5:]) if lines else ""
    full = text

    def hit(term: str, where: str) -> bool:
        if not term.isascii():
            return term in where
        # Word-boundary-ish match so "Witness" ≠ "IN WITNESS WHEREOF"
        pattern = re.compile(rf"(?<![A-Za-z]){re.escape(term)}(?![A-Za-z])", re.I)
        return pattern.search(where) is not None

    for lang in ("zh", "en"):
        for term in patterns["strong"].get(lang, []):
            if hit(term, full):
                score += weights["strong"]
                loc = "footer" if hit(term, foot) else ("title" if hit(term, head) else "body")
                signals.append(f"strong:{term}@{loc}")
                if loc == "footer":
                    score += weights["footer_bonus"]
                elif loc == "title":
                    score += weights["title_bonus"]

        for term in patterns["medium"].get(lang, []):
            if hit(term, full):
                score += weights["medium"]
                signals.append(f"medium:{term}")

        alone = True
        for term in patterns["exclude_if_alone"].get(lang, []):
            if hit(term, full):
                # Penalty only when no strong hits yet
                if not any(s.startswith("strong:") for s in signals):
                    score += weights["exclude_penalty"]
                    signals.append(f"exclude:{term}")
                alone = False
                break
        _ = alone

    br = blank_ratio(text)
    if br > 0.35:
        bonus = weights["blank_ratio_bonus_max"] * br
        score += bonus
        signals.append(f"layout:blank_ratio={br:.2f}")

    if total_pages > 1:
        late = page_index / (total_pages - 1)
        if late >= 0.55:
            bonus = weights["late_page_bonus_max"] * late
            score += bonus
            signals.append(f"position:late={late:.2f}")

    # Deduplicate signal labels while keeping order
    seen: set[str] = set()
    uniq: list[str] = []
    for s in signals:
        if s not in seen:
            seen.add(s)
            uniq.append(s)

    return score, uniq, low_text


def merge_candidates(
    page_scores: list[dict[str, Any]],
    min_score: float,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    i = 0
    n = len(page_scores)
    while i < n:
        if page_scores[i]["score"] < min_score:
            i += 1
            continue
        start = i
        end = i
        while end + 1 < n and page_scores[end + 1]["score"] >= min_score:
            end += 1
        block = page_scores[start : end + 1]
        conf_raw = sum(p["score"] for p in block) / len(block)
        confidence = round(min(0.99, conf_raw / 12.0), 2)
        signals: list[str] = []
        for p in block:
            for s in p["signals"]:
                if s not in signals:
                    signals.append(s)
        preview: list[str] = []
        for p in block:
            preview.extend(p["preview"][:3])
        candidates.append(
            {
                "start": start + 1,
                "end": end + 1,
                "page_count": end - start + 1,
                "confidence": confidence,
                "avg_score": round(conf_raw, 2),
                "signals": signals[:12],
                "preview": preview[:6],
                "low_text": any(p["low_text"] for p in block),
            }
        )
        i = end + 1
    candidates.sort(key=lambda c: (-c["confidence"], -c["avg_score"], c["start"]))
    return candidates


def compare_l_s(candidates: list[dict[str, Any]], signed_pages: int) -> dict[str, Any]:
    if not candidates:
        return {
            "status": "no_candidate",
            "best_candidate_pages": 0,
            "signed_pages": signed_pages,
            "advice": "No candidate ranges; ask the user for page numbers.",
        }
    best = candidates[0]
    l_count = best["page_count"]
    if signed_pages <= 0:
        return {
            "status": "no_signed",
            "best_candidate_pages": l_count,
            "signed_pages": 0,
            "best_range": f"{best['start']}-{best['end']}",
            "advice": "Provide --signed PDFs to enable L/S comparison.",
        }
    if l_count == signed_pages:
        status = "match"
        advice = "L == S; equal-page replace is consistent with best candidate."
    elif l_count < signed_pages:
        status = "contract_fewer"
        advice = "L < S; use expand replace or check for another blank block."
    else:
        status = "contract_more"
        advice = "L > S; narrow the range or add missing signed pages."
    return {
        "status": status,
        "best_candidate_pages": l_count,
        "signed_pages": signed_pages,
        "best_range": f"{best['start']}-{best['end']}",
        "advice": advice,
    }


def locate(contract: Path, signed: list[Path], patterns: dict[str, Any]) -> dict[str, Any]:
    reader = PdfReader(str(contract))
    total = len(reader.pages)
    weights = patterns["weights"]
    min_score = float(weights.get("candidate_min_score", 3.0))
    merge_floor = float(weights.get("merge_min_score", 2.5))

    page_scores: list[dict[str, Any]] = []
    for i in range(total):
        text = extract_page_text(reader, i)
        score, signals, low_text = score_page(text, i, total, patterns)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        page_scores.append(
            {
                "page": i + 1,
                "score": score,
                "signals": signals,
                "preview": lines[:4],
                "low_text": low_text,
            }
        )

    # Use merge floor for adjacency; filter display by candidate_min on avg handled in merge
    candidates = merge_candidates(page_scores, merge_floor)
    candidates = [c for c in candidates if c["avg_score"] >= min_score]

    signed_total = sum(page_count(p) for p in signed) if signed else 0
    comparison = compare_l_s(candidates, signed_total)

    low_text_pages = [p["page"] for p in page_scores if p["low_text"]]
    return {
        "contract": str(contract),
        "total_pages": total,
        "signed_files": [str(p) for p in signed],
        "signed_page_count": signed_total,
        "candidates": candidates,
        "comparison": comparison,
        "low_text_page_count": len(low_text_pages),
        "note": (
            "Assistive only. Confirm page ranges with the user before splicing."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Locate likely signature-page ranges (1-based, inclusive)."
    )
    parser.add_argument("--contract", required=True, type=Path, help="Full contract PDF")
    parser.add_argument(
        "--signed",
        action="append",
        default=[],
        type=Path,
        help="Signed signature-page PDF (repeatable)",
    )
    parser.add_argument(
        "--patterns",
        type=Path,
        default=DEFAULT_PATTERNS,
        help="patterns.json path",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON only")
    parser.add_argument(
        "--redact-preview",
        action="store_true",
        help="Omit page text previews from output (safer for unredacted contracts)",
    )
    args = parser.parse_args()

    if not args.contract.is_file():
        print(f"Contract not found: {args.contract}", file=sys.stderr)
        return 1
    for s in args.signed:
        if not s.is_file():
            print(f"Signed PDF not found: {s}", file=sys.stderr)
            return 1
    if not args.patterns.is_file():
        print(f"Patterns not found: {args.patterns}", file=sys.stderr)
        return 1

    patterns = load_patterns(args.patterns)
    result = locate(args.contract, args.signed, patterns)
    if args.redact_preview:
        for c in result.get("candidates", []):
            c["preview"] = []
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
