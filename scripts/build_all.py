"""Build every document page, then the indexes.

    python scripts/build_all.py [--jobs N] [KEY ...]

Documents are built in parallel worker processes (default: all cores), since each page is
independent and the work is pure Python (threads would wait on the GIL). The indexes are
built once at the end.
"""
import argparse, contextlib, io, os, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from nist_translater import cli
from nist_translater.documents import DOCUMENTS, document_paths


def build_one(key):
    """Build one page in a worker; the index is deferred to the end."""
    cli.build_translation_index = lambda root: "(index deferred)"
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            cli.build(key)
        return key, None
    except Exception as error:
        return key, repr(error)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    parser.add_argument("keys", nargs="*")
    args = parser.parse_args()
    index = cli.build_translation_index
    keys = [key for key in DOCUMENTS
            if (not args.keys or key in args.keys) and document_paths(cli.ROOT, key)["json"].exists()]
    # largest documents first, so a big one does not run alone at the end
    keys.sort(key=lambda key: document_paths(cli.ROOT, key)["json"].stat().st_size, reverse=True)
    built, failed = 0, []
    # --jobs 1 builds in this process (for debugging, and so tests can patch cli)
    with ProcessPoolExecutor(args.jobs) if args.jobs > 1 else contextlib.nullcontext() as pool:
        for key, error in (pool.map if pool else map)(build_one, keys):
            if error:
                failed.append((key, error))
            else:
                built += 1
    print("built", built, "failed", failed)
    print("index", index(cli.ROOT))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
