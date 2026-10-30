"""Build every document page, then the indexes.

    python scripts/build_all.py [KEY ...]
"""
import contextlib, io, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from nist_translater import cli
from nist_translater.documents import DOCUMENTS, document_paths
from nist_translater.index_page import build_translation_index
only = sys.argv[1:]
built, failed = 0, []
orig = cli.build_translation_index
cli.build_translation_index = lambda root: "(index deferred)"
for key in DOCUMENTS:
    if only and key not in only: continue
    if not document_paths(cli.ROOT, key)["json"].exists(): continue
    try:
        with contextlib.redirect_stdout(io.StringIO()): cli.build(key)
        built += 1
    except Exception as error:
        failed.append((key, repr(error)))
print("built", built, "failed", failed)
print("index", orig(cli.ROOT))
if failed:
    raise SystemExit(1)
