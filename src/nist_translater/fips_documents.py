"""Metadata for the NIST FIPS publications (Federal Information Processing Standards).

Keys and file stems are "fips-<number>", so the files never clash with SP 800
files (data/fips-197.pdf, data/fips-197-trans.json, html/fips-197.html).
"""

SERIES = "Federal Information Processing Standards · PDF 原文抽出"


def _fips(number, title, title_ja, description, pdf_name, record_path, **extra):
    stem = "fips-" + number
    spec = {
        "family": "fips",
        "number": "FIPS " + number,
        "title": title,
        "title_ja": title_ja,
        "subtitle_ja": title_ja,
        "slug": stem,
        "file_stem": stem,
        "home_url": "fips-index.html",
        "description": description,
        "source_format": "pdf",
        "source_url": "https://nvlpubs.nist.gov/nistpubs/FIPS/" + pdf_name,
        "pdf_url": "https://doi.org/10.6028/" + pdf_name[:-4],
        "catalog_record_url": "https://csrc.nist.gov/pubs/fips/" + record_path,
        "series": SERIES,
    }
    spec.update(extra)
    return stem, spec


FIPS_DOCUMENTS = dict([
    _fips("140-3", "Security Requirements for Cryptographic Modules",
          "暗号モジュールのセキュリティ要件",
          "暗号モジュールの設計・実装に求めるセキュリティ要件と、その検証の枠組み（ISO/IEC 19790 と ISO/IEC 24759 の採用）を定めます。",
          "NIST.FIPS.140-3.pdf", "140-3/final", release_date="2019-03-22"),
    _fips("140-2", "Security Requirements for Cryptographic Modules",
          "暗号モジュールのセキュリティ要件（旧版）",
          "暗号モジュールに求める4段階のセキュリティ要件を定めた旧版の規格です。現在は FIPS 140-3 に置き換えられています。",
          "NIST.FIPS.140-2.pdf", "140-2/upd2/final", release_date="2001-05-25", superseded_by="FIPS 140-3"),
    _fips("180-4", "Secure Hash Standard (SHS)",
          "セキュアハッシュ標準（SHS）",
          "SHA-1 と SHA-2 系列（SHA-224、SHA-256、SHA-384、SHA-512 など）のハッシュアルゴリズムを定めます。",
          "NIST.FIPS.180-4.pdf", "180-4/upd1/final", release_date="2015-08-04", math=True),
    _fips("186-5", "Digital Signature Standard (DSS)",
          "デジタル署名標準（DSS）",
          "RSA、ECDSA、EdDSA によるデジタル署名の生成と検証の方法、および鍵ペアの要件を定めます。",
          "NIST.FIPS.186-5.pdf", "186-5/final", release_date="2023-02-03", math=True),
    _fips("197", "Advanced Encryption Standard (AES)",
          "高度暗号化標準（AES）",
          "128ビットのブロックを128、192、256ビットの鍵で暗号化・復号する対称ブロック暗号 AES を定めます（2023年更新版）。",
          "NIST.FIPS.197-upd1.pdf", "197/final", release_date="2023-05-09", math=True),
    _fips("198-1", "The Keyed-Hash Message Authentication Code (HMAC)",
          "鍵付きハッシュメッセージ認証コード（HMAC）",
          "暗号学的ハッシュ関数と秘密鍵を用いてメッセージ認証コードを計算する HMAC を定めます。",
          "NIST.FIPS.198-1.pdf", "198-1/final", release_date="2008-07-16", math=True),
    _fips("199", "Standards for Security Categorization of Federal Information and Information Systems",
          "連邦政府の情報および情報システムのセキュリティ分類に関する標準",
          "機密性・完全性・可用性に対する潜在的影響に基づいて、連邦政府の情報と情報システムをセキュリティ分類する標準を定めます。",
          "NIST.FIPS.199.pdf", "199/final", release_date="2004-02-01"),
    _fips("200", "Minimum Security Requirements for Federal Information and Information Systems",
          "連邦政府の情報および情報システムに対する最低限のセキュリティ要件",
          "連邦政府の情報と情報システムに求める17分野の最低限のセキュリティ要件と、管理策の選択方法を定めます。",
          "NIST.FIPS.200.pdf", "200/final", release_date="2006-03-01"),
    _fips("201-3", "Personal Identity Verification (PIV) of Federal Employees and Contractors",
          "連邦職員および請負業者の個人識別検証（PIV）",
          "連邦職員と請負業者の身元確認、PIV クレデンシャルの発行・管理、認証の仕組みに関する要件を定めます。",
          "NIST.FIPS.201-3.pdf", "201-3/final", release_date="2022-01-24"),
    _fips("202", "SHA-3 Standard: Permutation-Based Hash and Extendable-Output Functions",
          "SHA-3 標準：置換ベースのハッシュ関数および拡張可能出力関数",
          "KECCAK 置換に基づく SHA-3 ハッシュ関数と、拡張可能出力関数 SHAKE128、SHAKE256 を定めます。",
          "NIST.FIPS.202.pdf", "202/final", release_date="2015-08-04", math=True),
    _fips("203", "Module-Lattice-Based Key-Encapsulation Mechanism Standard",
          "モジュール格子ベースの鍵カプセル化メカニズム標準",
          "モジュール格子に基づく耐量子計算機の鍵カプセル化メカニズム ML-KEM を定めます。",
          "NIST.FIPS.203.pdf", "203/final", release_date="2024-08-13", math=True),
    _fips("204", "Module-Lattice-Based Digital Signature Standard",
          "モジュール格子ベースのデジタル署名標準",
          "モジュール格子に基づく耐量子計算機のデジタル署名方式 ML-DSA を定めます。",
          "NIST.FIPS.204.pdf", "204/final", release_date="2024-08-13", math=True),
    _fips("205", "Stateless Hash-Based Digital Signature Standard",
          "ステートレスなハッシュベースのデジタル署名標準",
          "ハッシュ関数のみに安全性の根拠を置く、ステートレスな耐量子計算機デジタル署名方式 SLH-DSA を定めます。",
          "NIST.FIPS.205.pdf", "205/final", release_date="2024-08-13", math=True),
])
