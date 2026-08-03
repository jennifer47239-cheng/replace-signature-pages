#!/usr/bin/env python3
"""Forwarder → tools/replace-signature-pages/splice_signature_pages.py"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[4]
_TARGET = _REPO / "tools" / "replace-signature-pages" / "splice_signature_pages.py"
if not _TARGET.is_file():
    sys.stderr.write(f"Canonical script not found: {_TARGET}\n")
    sys.exit(1)
sys.path.insert(0, str(_TARGET.parent))
sys.argv[0] = str(_TARGET)
runpy.run_path(str(_TARGET), run_name="__main__")
