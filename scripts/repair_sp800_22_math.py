#!/usr/bin/env python3
"""Repair the stored SP 800-22 extraction and rebuild its reading page."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.nist_translater.cli import build
from src.nist_translater.pdf_math import preserve_sp800_22_math
from src.nist_translater.storage import read_json, write_json
from src.nist_translater.translation import audit_translations

if __name__ == "__main__":
    path = ROOT / "data/sp800-22r1-trans.json"
    repaired = preserve_sp800_22_math(
        read_json(path),
        ROOT / "data/sp800-22r1.pdf",
        ROOT / "html/assets/22r1",
        "assets/22r1",
    )
    audit_translations(repaired)
    write_json(path, repaired)
    build("22r1")
    summary = repaired["math_preservation"]
    print(
        "Preserved %d figure regions; rebuilt %d KaTeX regions; replaced %d extraction blocks."
        % (
            summary["crop_count"],
            summary["equation_region_count"],
            summary["replaced_block_count"],
        )
    )
