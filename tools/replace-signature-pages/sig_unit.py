#!/usr/bin/env python3
"""Signature-page tagging units (party / signatory). Local only, no AI.

「签署主体」(party) = legal entity on the block — may be 投资方 *or* 融资方
(company/issuer), not only investors. 「签字人」= natural person signing.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ranges_util import format_range
from splice_signature_pages import parse_range

EMPTY_PARTY = "（未填签署主体）"
EMPTY_INVESTOR = EMPTY_PARTY  # backward-compatible alias
EMPTY_SIGNATORY = "（未填签字人）"

# Optional role of the legal entity on this signature block
PARTY_ROLES = ("", "投资方", "融资方", "其他")


def normalize_label(value: str) -> str:
    """Collapse whitespace; keep Chinese characters as-is."""
    text = (value or "").strip()
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_party_role(value: str) -> str:
    raw = normalize_label(value)
    aliases = {
        "investor": "投资方",
        "investors": "投资方",
        "company": "融资方",
        "issuer": "融资方",
        "target": "融资方",
        "borrower": "融资方",
        "financing": "融资方",
        "party": "",
        "other": "其他",
    }
    key = raw.lower() if raw.isascii() else raw
    if key in aliases:
        return aliases[key]
    if raw in PARTY_ROLES:
        return raw
    return raw  # allow custom labels


@dataclass
class SigUnit:
    """One taggable signature block (may share pages with another unit)."""

    start: int
    end: int
    party: str = ""
    """Legal entity (签署主体): 投资方 or 融资方 etc."""
    signatory: str = ""
    capacity: str = ""
    party_role: str = ""
    """Optional: 投资方 / 融资方 / 其他."""
    copies: int = 1
    document_name: str = ""
    notes: str = ""
    source_contract: str = ""

    def __post_init__(self) -> None:
        self.start = int(self.start)
        self.end = int(self.end)
        if self.end < self.start:
            raise ValueError(f"invalid range {self.start}-{self.end}")
        self.party = normalize_label(self.party)
        self.signatory = normalize_label(self.signatory)
        self.capacity = normalize_label(self.capacity)
        self.party_role = normalize_party_role(self.party_role)
        self.notes = normalize_label(self.notes)
        self.document_name = normalize_label(self.document_name)
        self.copies = max(1, int(self.copies or 1))

    # Backward-compatible alias used by older call sites / tests
    @property
    def investor(self) -> str:
        return self.party

    @investor.setter
    def investor(self, value: str) -> None:
        self.party = normalize_label(value)

    @property
    def range_label(self) -> str:
        return format_range(self.start, self.end)

    @property
    def page_indices(self) -> list[int]:
        """0-based page indices."""
        return list(range(self.start - 1, self.end))

    def group_key(self, mode: str) -> str:
        if mode in {"party", "investor"}:
            return self.party or EMPTY_PARTY
        if mode == "signatory":
            return self.signatory or EMPTY_SIGNATORY
        raise ValueError(f"unknown group mode: {mode}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "range": self.range_label,
            "party": self.party,
            "party_role": self.party_role,
            # Keep investor key for older tags / docs
            "investor": self.party,
            "signatory": self.signatory,
            "capacity": self.capacity,
            "copies": self.copies,
            "document_name": self.document_name,
            "notes": self.notes,
            "source_contract": self.source_contract,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        *,
        default_document: str = "",
        default_contract: str = "",
    ) -> SigUnit:
        if "range" in data:
            start, end = parse_range(str(data["range"]))
        else:
            start = int(data["start"])
            end = int(data.get("end", start))
        party = data.get("party") or data.get("investor") or ""
        return cls(
            start=start,
            end=end,
            party=str(party),
            party_role=str(data.get("party_role") or data.get("role") or ""),
            signatory=str(data.get("signatory") or ""),
            capacity=str(data.get("capacity") or ""),
            copies=int(data.get("copies") or 1),
            document_name=str(data.get("document_name") or default_document),
            notes=str(data.get("notes") or ""),
            source_contract=str(data.get("source_contract") or default_contract),
        )


def units_from_ranges(
    ranges: list[tuple[int, int]],
    *,
    document_name: str = "",
    source_contract: str = "",
) -> list[SigUnit]:
    """Create blank-tagged units (one per range) for interactive fill."""
    return [
        SigUnit(
            start=s,
            end=e,
            document_name=document_name,
            source_contract=source_contract,
        )
        for s, e in ranges
    ]


def load_tags_file(
    path: Path,
    *,
    default_document: str = "",
    default_contract: str = "",
) -> list[SigUnit]:
    """Load tags from JSON (or YAML if PyYAML is installed)."""
    if not path.is_file():
        raise FileNotFoundError(f"tags file not found: {path}")

    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    data: Any
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise SystemExit(
                "YAML tags require PyYAML. Use tags.json instead, or:\n"
                "  pip install pyyaml"
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)

    if isinstance(data, list):
        raw_units = data
    elif isinstance(data, dict):
        raw_units = data.get("units") or data.get("tags") or []
        if not default_document and data.get("document_name"):
            default_document = str(data["document_name"])
        if not default_contract and data.get("contract"):
            default_contract = str(data["contract"])
    else:
        raise ValueError("tags file must be a list or an object with 'units'")

    if not raw_units:
        raise ValueError("tags file contains no units")

    return [
        SigUnit.from_dict(
            dict(item),
            default_document=default_document,
            default_contract=default_contract,
        )
        for item in raw_units
    ]


def save_tags_file(
    path: Path,
    units: list[SigUnit],
    *,
    contract: str | Path | None = None,
    document_name: str = "",
) -> None:
    """Write tags as JSON (UTF-8)."""
    payload: dict[str, Any] = {
        "contract": str(contract) if contract else "",
        "document_name": document_name,
        "units": [u.to_dict() for u in units],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def safe_filename(label: str, *, max_len: int = 80) -> str:
    """Filesystem-safe name; keep CJK."""
    name = normalize_label(label) or "unnamed"
    name = re.sub(r'[/\\?%*:|"<>]', "_", name)
    name = name.strip(" .")
    if not name:
        name = "unnamed"
    if len(name) > max_len:
        name = name[:max_len].rstrip(" .")
    return name
