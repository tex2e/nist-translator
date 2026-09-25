"""Metadata and paths for the four volumes in NIST SP 800-63 Revision 4."""

from pathlib import Path


DOCUMENTS = {
    "63": {
        "number": "SP 800-63-4",
        "title": "Digital Identity Guidelines",
        "slug": "63",
        "description": "デジタルIDに関する全体的なガイドラインを示します。",
        "source_url": "https://pages.nist.gov/800-63-4/sp800-63.html",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-63-4",
    },
    "63a": {
        "number": "SP 800-63A-4",
        "title": "Identity Proofing & Enrollment",
        "slug": "63a",
        "description": "本人確認および登録の技術要件を示します。",
        "source_url": "https://pages.nist.gov/800-63-4/sp800-63a.html",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-63a-4",
    },
    "63b": {
        "number": "SP 800-63B-4",
        "title": "Authentication & Authenticator Management",
        "slug": "63b",
        "description": "認証および認証器管理の技術要件を示します。",
        "source_url": "https://pages.nist.gov/800-63-4/sp800-63b.html",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-63b-4",
    },
    "63c": {
        "number": "SP 800-63C-4",
        "title": "Federation & Assertions",
        "slug": "63c",
        "description": "フェデレーションおよびアサーションの技術要件を示します。",
        "source_url": "https://pages.nist.gov/800-63-4/sp800-63c.html",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-63c-4",
    },
}


def get_document(key):
    try:
        return DOCUMENTS[key]
    except KeyError as error:
        raise ValueError("Unknown document: %s (choose %s)" % (
            key, ", ".join(DOCUMENTS))) from error


def document_paths(root, key):
    spec = get_document(key)
    slug = spec["slug"]
    return {
        "source": Path(root) / "data" / ("sp800-%s.html" % slug),
        "json": Path(root) / "data" / ("sp800-%s-trans.json" % slug),
        "html": Path(root) / "html" / ("sp800-%s.html" % slug),
    }
