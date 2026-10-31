"""The old FIPS index (html/fips-index.html) now forwards to the shared list.

The top page lists SP 800 and FIPS together; ?series=fips opens it with FIPS selected,
so links to fips-index.html keep working.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = Path("html/fips-index.html")
TARGET = "index.html?series=fips"

PAGE = """<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>FIPS 英日対訳一覧 - NIST Trans</title>
  <link rel="icon" href="favicon.ico" sizes="any">
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <meta http-equiv="refresh" content="0; url=%(target)s">
  <link rel="canonical" href="%(target)s">
  <script>location.replace(%(target)r);</script>
</head>
<body>
  <p>FIPS の一覧は <a href="%(target)s">資料一覧（FIPS）</a> に移りました。</p>
</body>
</html>
"""


def build_fips_index(root=ROOT):
    output = Path(root) / OUTPUT
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(PAGE % {"target": TARGET}, encoding="utf-8")
    return output


if __name__ == "__main__":
    print("Built", build_fips_index())
