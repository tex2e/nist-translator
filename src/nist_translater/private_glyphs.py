"""Private-use glyphs in specific PDFs: ligatures and symbol-font characters.

Some PDFs map ligatures (Calibri "ti", "tt", "ft") or Wingdings/Symbol glyphs
to Unicode private-use code points, which browsers show as nothing or a box.
The meaning depends on the font, so each mapping is bound to the PDF's SHA-256
and was confirmed against the page images and the surrounding words.
"""

import hashlib
import re

_TT = lambda after: "tti" if after.startswith("n") else "tt"  # sengs -> settings, aributes -> attributes

_WINGDINGS = {"": " ", "": "■", "": "▪", "": "←", "": "→",
              "": "✗", "": "✓"}
_SYMBOL = {"": "−", "": "•"}

PROFILES = {
    # SP 800-53A Rev. 5: Calibri ligatures
    "75665570048b969ad465a4f4f1db425ce505c374951c2c64e462949c6b21be47": {
        "": "ti", "": _TT, "": "ft", "": _TT, "": "tf"},
    "efd3f02258276fb294d62a73bb0a6ec80051fd625d5197584220beaface31718": _WINGDINGS,  # 101r1
    "9a383e711d8dc0ce4500db01b459257c0500e287415c1632a8a027dd8ca7f91e": _WINGDINGS,  # 167
    "72eb105cd5ddb77b9adaadb097dfd1b428d86cf7edd81219c27dde0b437ac8b5": {"": "✓"},  # 121r2, Wingdings 2
    "7d3f0d707b1cbd1bbab4b85aeb67b4a7957f01af608121d1fef6410f0b763b11": _WINGDINGS,  # 73pt1r5
    "6e8d44de32789ecb3267c8a7778eb3088c15f5c860cf6e823243c8030ed3ec09": _SYMBOL,  # 153
    "0adf6e07907d58edf93097cb7b2cd9ce39112f908963a5c4ce57210222f36360": _WINGDINGS,  # 157
    "8a952fdcb07234bb09a0fe43279b6a081dc7a47c0379d44b53918aa51251f82e": _WINGDINGS,  # 147b
    "f8de995cb3df03893dd2683835f616525e805339053707a56bf4a57cde03613b": _WINGDINGS,  # 85a4
    "d2bacbf4053adbbe11628f74f071077d8fd59ba99754a3aab34d7813c1cb3d40": _WINGDINGS,  # 161r1upd1
    "4fc5481b3a7e49cb259a0d7165d67a6cab026ef1b1c1ee34d56f6b8591f03180": {**_WINGDINGS, **_SYMBOL},  # 119
    "e274bf1c58db4f681b0f03bf8545836e33ae391de35b31071fdf5cba9e396c4d": _SYMBOL,  # 152
    "608f554514d381853e24e0b33123b7080fbd757826f460032690aade63394616": {"": "➎"},  # 82r3, Wingdings 2
}

_PRIVATE = re.compile(r"[-]")


def replace_private_glyphs(text, mapping):
    def one(match):
        value = mapping.get(match.group(0))
        if value is None:
            return match.group(0)
        if callable(value):
            after = re.match(r"[A-Za-z]*", text[match.end():]).group(0)
            return value(after)
        return value
    return _PRIVATE.sub(one, text)


def _rehash(block):
    old = block.get("source_hash")
    for tail in ("", "\n"):
        digest = lambda html: hashlib.sha256((block["kind"] + "\n" + html + tail).encode("utf-8")).hexdigest()[:16]
        if old is None:
            break
        if digest(block["_old_html"]) == old:
            block["source_hash"] = digest(block["html"])
            return
    block["source_hash"] = hashlib.sha256(
        (block["kind"] + "\n" + block["html"]).encode("utf-8")).hexdigest()[:16]


def repair_private_glyphs(document):
    """Replace mapped private-use glyphs in the contents of a known PDF; returns the count."""
    mapping = PROFILES.get(document.get("source_sha256"))
    if not mapping:
        return 0
    count = 0
    for block in document.get("contents", []):
        for field in ("html", "html_ja"):
            value = block.get(field)
            if value and _PRIVATE.search(value):
                fixed = replace_private_glyphs(value, mapping)
                if fixed != value:
                    count += len(_PRIVATE.findall(value)) - len(_PRIVATE.findall(fixed))
                    if field == "html":
                        block["_old_html"] = value
                        block["html"] = fixed
                        _rehash(block)
                        del block["_old_html"]
                    else:
                        block[field] = fixed
    return count
