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

from blank_page_detector import count_non_blank_pages


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


def locate(
    contract: Path,
    signed: list[Path],
    patterns: dict[str, Any],
    *,
    clean_signed_blank_pages: bool = False,
    signed_blank_nonspace_threshold: int = 15,
    signed_blank_content_bytes_max: int = 800,
    ocr: bool = False,
) -> dict[str, Any]:
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
                "text": text,
            }
        )

    ocr_pages: list[int] = []
    ocr_note = ""
    if ocr:
        low_pages = [p["page"] for p in page_scores if p["low_text"]]
        if low_pages:
            try:
                from page_ocr import ocr_pdf_pages, vision_ocr_available

                if not vision_ocr_available():
                    ocr_note = "OCR requested but macOS Vision helper unavailable"
                else:
                    ocr_map = ocr_pdf_pages(contract, low_pages)
                    ocr_pages = sorted(ocr_map.keys())
                    for p in page_scores:
                        ocr_text = ocr_map.get(p["page"], "")
                        if not ocr_text.strip():
                            continue
                        # Prefer OCR text for scoring when native extract was weak
                        merged = (p["text"] + "\n" + ocr_text).strip()
                        score, signals, low_text = score_page(
                            merged, p["page"] - 1, total, patterns
                        )
                        lines = [ln.strip() for ln in merged.splitlines() if ln.strip()]
                        p["score"] = score
                        p["signals"] = signals + ["source:ocr"]
                        p["preview"] = lines[:4]
                        p["low_text"] = low_text
                        p["text"] = merged
                    ocr_note = f"OCR applied to {len(ocr_pages)} low-text page(s)"
            except Exception as exc:  # noqa: BLE001
                ocr_note = f"OCR failed: {exc}"

    # Drop raw text before returning (privacy / payload size)
    for p in page_scores:
        p.pop("text", None)

    candidates = merge_candidates(page_scores, merge_floor)
    candidates = [c for c in candidates if c["avg_score"] >= min_score]

    signed_total = 0
    signed_cleaning_details: list[dict[str, Any]] = []
    if signed:
        if clean_signed_blank_pages:
            for sp in signed:
                info = count_non_blank_pages(
                    sp,
                    nonspace_threshold=signed_blank_nonspace_threshold,
                    content_bytes_max=signed_blank_content_bytes_max,
                )
                signed_total += int(info["non_blank_page_count"])
                signed_cleaning_details.append(info)
        else:
            signed_total = sum(page_count(p) for p in signed)
    comparison = compare_l_s(candidates, signed_total)

    low_text_pages = [p["page"] for p in page_scores if p["low_text"]]
    removed_blank_total = sum(
        int(d.get("blank_page_count", 0)) for d in signed_cleaning_details
    )
    note = "Assistive only. Confirm page ranges with the user before splicing."
    if ocr_note:
        note = f"{note} {ocr_note}."
    return {
        "contract": str(contract),
        "total_pages": total,
        "signed_files": [str(p) for p in signed],
        "signed_page_count": signed_total,
        "signed_blank_removed_page_count": removed_blank_total,
        "signed_cleaning_details": signed_cleaning_details,
        "candidates": candidates,
        "comparison": comparison,
        "low_text_page_count": len(low_text_pages),
        "ocr_enabled": bool(ocr),
        "ocr_pages": ocr_pages,
        "note": note,
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
        "--clean-signed-blank-pages",
        action="store_true",
        help="Remove疑似空白页 from signed PDFs before counting L/S.",
    )
    parser.add_argument(
        "--signed-blank-nonspace-threshold",
        type=int,
        default=15,
        help="If extracted text has <= this many non-space chars, it may be treated as blank.",
    )
    parser.add_argument(
        "--signed-blank-content-bytes-max",
        type=int,
        default=800,
        help="If the page content stream bytes <= this value and has no image XObjects, treat as blank.",
    )
    parser.add_argument(
        "--redact-preview",
        action="store_true",
        help="Omit page text previews from output (safer for unredacted contracts)",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="OCR low-text/scanned pages via on-device macOS Vision before scoring",
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
    result = locate(
        args.contract,
        args.signed,
        patterns,
        clean_signed_blank_pages=args.clean_signed_blank_pages,
        signed_blank_nonspace_threshold=args.signed_blank_nonspace_threshold,
        signed_blank_content_bytes_max=args.signed_blank_content_bytes_max,
        ocr=args.ocr,
    )
    if args.redact_preview:
        for c in result.get("candidates", []):
            c["preview"] = []
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
