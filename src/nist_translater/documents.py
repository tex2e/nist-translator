"""Metadata and paths for supported NIST SP 800 publications."""

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
    "131ar2": {
        "number": "SP 800-131A Rev. 2",
        "title": "Transitioning the Use of Cryptographic Algorithms and Key Lengths",
        "title_ja": "NIST SP 800-131A 改訂第2版",
        "subtitle_ja": "暗号アルゴリズムおよび鍵長の使用の移行",
        "slug": "131ar2",
        "description": "暗号アルゴリズムと鍵長の移行に関する指針です。",
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-131Ar2.pdf",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-131Ar2",
        "series": "NIST Special Publication · PDF 原文抽出",
    },
    "238": {
        "number": "SP 800-238",
        "title": "Fiscal Year 2025 Annual Report for NIST Cybersecurity and Privacy Program",
        "title_ja": "NIST サイバーセキュリティ・プライバシープログラム 2025 会計年度年次報告書",
        "slug": "238",
        "description": "NIST のサイバーセキュリティおよびプライバシープログラムの 2025 会計年度の活動をまとめた年次報告書です。",
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-238.pdf",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-238",
        "subtitle_ja": "NIST サイバーセキュリティ・プライバシープログラム 2025 会計年度年次報告書",
        "series": "NIST Special Publication · PDF 原文抽出",
    },
    "229": {
        "number": "SP 800-229",
        "title": "Fiscal Year 2023 Cybersecurity and Privacy Annual Report",
        "title_ja": "2023会計年度 サイバーセキュリティ・プライバシー年次報告書",
        "slug": "229",
        "description": "NISTのサイバーセキュリティ・プライバシープログラムの2023会計年度の研究活動と成果をまとめます。",
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-229.pdf",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-229",
        "series": "NIST Special Publication · PDF 原文抽出",
    },
    "236": {
        "number": "SP 800-236",
        "title": "Fiscal Year 2024 Annual Report for NIST Cybersecurity and Privacy Program",
        "title_ja": "NIST サイバーセキュリティ・プライバシープログラム 2024 会計年度年次報告書",
        "slug": "236",
        "description": "NIST のサイバーセキュリティおよびプライバシープログラムの 2024 会計年度の活動をまとめた年次報告書です。",
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-236.pdf",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-236",
        "subtitle_ja": "NIST サイバーセキュリティ・プライバシープログラム 2024 会計年度年次報告書",
        "series": "NIST Special Publication · PDF 原文抽出",
    },
    "234": {
        "number": "SP 800-234",
        "title": "High-Performance Computing (HPC) Security Overlay",
        "title_ja": "高性能計算（HPC）セキュリティオーバーレイ",
        "slug": "234",
        "description": "高性能計算（HPC）環境の特性に合わせたセキュリティ管理策の選択と実装を支援します。",
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-234.pdf",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-234",
        "subtitle_ja": "高性能計算（HPC）セキュリティオーバーレイ",
        "series": "NIST Special Publication · PDF 原文抽出",
    },
    "233": {
        "number": "SP 800-233",
        "title": "Service Mesh Proxy Models for Cloud-Native Applications",
        "title_ja": "クラウドネイティブアプリケーション向けサービスメッシュプロキシモデル",
        "slug": "233",
        "description": "サービスメッシュのデータプレーン構成ごとの脅威を分析し、クラウドネイティブアプリケーションへの適用を支援します。",
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-233.pdf",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-233",
        "subtitle_ja": "クラウドネイティブアプリケーション向けサービスメッシュプロキシモデル",
        "series": "NIST Special Publication · PDF 原文抽出",
    },
    "232": {
        "number": "SP 800-232",
        "title": "Ascon-Based Lightweight Cryptography Standards for Constrained Devices: Authenticated Encryption, Hash, and Extendable Output Functions",
        "title_ja": "制約のあるデバイス向けAsconベース軽量暗号標準：認証付き暗号化、ハッシュ関数、拡張出力関数",
        "slug": "232",
        "description": "制約のあるデバイス向けに、Ascon-AEAD128、Ascon-Hash256、Ascon-XOF128、およびAscon-CXOF128の技術仕様とセキュリティ特性を規定します。",
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-232.pdf",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-232",
        "subtitle_ja": "制約のあるデバイス向けAsconベース軽量暗号標準：認証付き暗号化、ハッシュ関数、拡張出力関数",
        "series": "NIST Special Publication · PDF 原文抽出",
    },
    "231": {
        "number": "SP 800-231",
        "title": "Bug Framework (BF): Formalizing Cybersecurity Weaknesses and Vulnerabilities",
        "title_ja": "バグフレームワーク（BF）：サイバーセキュリティの弱点と脆弱性の形式化",
        "slug": "231",
        "description": "ソフトウェアおよびハードウェアのセキュリティ上のバグ、故障、弱点、脆弱性を形式的に分類・記述する枠組みを示します。",
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-231.pdf",
        "pdf_url": "https://doi.org/10.6028/NIST.SP.800-231",
        "subtitle_ja": "バグフレームワーク（BF）：サイバーセキュリティの弱点と脆弱性の形式化",
        "series": "NIST Special Publication · PDF 原文抽出",
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
    extension = ".pdf" if spec.get("source_format") == "pdf" else ".html"
    return {
        "source": Path(root) / "data" / ("sp800-%s%s" % (slug, extension)),
        "json": Path(root) / "data" / ("sp800-%s-trans.json" % slug),
        "html": Path(root) / "html" / ("sp800-%s.html" % slug),
    }
