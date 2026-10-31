#!/usr/bin/env python3
"""Generate the top page (html/index.html): the searchable list of SP 800 and FIPS pages."""

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.nist_translater.index_page import build_translation_index


if __name__ == "__main__":
    print("Built", build_translation_index(ROOT))
