# NIST Trans — NIST SP 800・FIPS 英日対訳（非公式）

NIST（米国国立標準技術研究所）の Special Publication 800 シリーズと FIPS を、段落ごとに英文と日本語訳を並べて読めるようにした静的サイトと、その生成ツールです。

> [!IMPORTANT]
> 有志による**非公式**の日本語訳です。NIST および米国商務省が作成・承認・推奨したものではありません。翻訳の正確性は保証しません。要件の確認には、必ず NIST の正式版を参照してください。

## サイトでできること

- **トップページ（`index.html`）**
  - 収録している SP 800 と FIPS を 1 つの一覧で表示します。
  - 資料番号・英語タイトル・日本語タイトル・要約から探せます。
  - 「すべて／SP 800／FIPS」の切り替えと、廃止された資料の表示・非表示で絞り込めます。
  - 検索条件は URL に残ります（例: `index.html?q=800-53&series=sp800`）。
- **資料ページ（`sp800-*.html`、`fips-*.html`）**
  - 冒頭に資料の情報（番号、英語・日本語タイトル、公開日、原文 URL）と要約を示します。
  - 本文は、英文と日本語訳を段落ごとに左右に並べます。
  - 段落にマウスを乗せると、左に「リンク」（段落へのリンクをコピー）、「原文」（原本 PDF の該当ページ）、「報告」が出ます。「報告」を押すと、その段落の原文と訳を書き込んだ GitHub Issue の作成画面が開きます。
  - 読み進めると上部に「☰ 目次」と現在の節名が出ます。目次は左から開き、日本語・英語で見出しを絞り込めます（階層は節番号から決め、4 段目以降は「深い階層も表示」で開きます）。
  - 数式は KaTeX で表示します。表は HTML の表に組み直しています。
- **ダークモード**: ヘッダー右上の月・太陽のボタンで切り替えます。選んだ設定はブラウザに保存し、選んでいない間は OS の設定に従います。
- **掲載しないもの**: 非公式サイトのため、次のものは画像や文章を載せず、「原本 PDF を参照」という注記に置き換えています。
  - NIST のロゴ、米国商務省の紋章、認証マーク
  - 人物写真
  - NIST が第三者の許諾を得て転載した部分（SP 800-160 Vol. 1 Rev. 1 の ISO/IEC/IEEE 15288 の引用など）

## 原文の権利と出典

- NIST の職員が作成した著作物は、17 U.S.C. §105 により、米国内では一般に著作権保護の対象外です。ただし、米国外では著作権で保護される場合があります。また、第三者が書いた部分は著作権で保護される場合があります。詳しくは NIST の [Copyright, Fair Use, and Licensing Statements](https://www.nist.gov/open/copyright-fair-use-and-licensing-statements-srd-data-software-and-technical-series-publications) を参照してください。
- 各ページには、NIST が推奨する出典表示（原文の書誌情報と “Republished courtesy of the National Institute of Standards and Technology.”）を載せています。
- 「NIST 公式翻訳」「NIST が承認・推奨」と受け取られる表現は使いません。

## 必要な環境

- Python 3.10 以降（動作確認は 3.12）
- `requirements.txt` のパッケージ（BeautifulSoup、Jinja2、pdfplumber、pypdfium2）
- 原文の取得（`fetch`、`update`）にはネット接続が必要です。

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

## ページの生成と確認

翻訳データ（`data/*-trans.json`）はリポジトリに含まれています。次のコマンドで、すべての資料ページとトップページを生成できます。

```sh
python3 scripts/build_all.py
```

1 つの資料だけを生成する場合は、資料のキーを指定します（キーの一覧は `python3 main.py --help`）。トップページも同時に更新されます。

```sh
python3 main.py build --document 53r5
python3 main.py build --document fips-203
python3 main.py index        # トップページだけ
```

ローカルで確認する場合:

```sh
python3 -m http.server 8000 --directory html
```

ブラウザで <http://localhost:8000/> を開きます。

## 資料の追加・更新

1. `src/nist_translater/documents.py`（FIPS は `fips_documents.py`）に、資料の番号・タイトル・原文 URL・`source_format`（`pdf` または `html`）を登録します。
2. 原文を取得・解析し、ページを生成します。

   ```sh
   python3 main.py fetch --document 131ar2   # 原本 PDF を data/ に取得（Git の対象外）
   python3 main.py parse --document 131ar2   # 段落・表・図・数式に分解して JSON を作成・更新
   python3 main.py build --document 131ar2   # HTML を生成
   ```

   `update` は `fetch`・`parse`・`build` を続けて実行します。原文が変わった段落は `stale` になり、古い訳は表示しません。
3. 抽出結果を原本のページ画像と照合し、訳を付けてレビューします。PDF からの抽出、数式の復元、原本との照合、訳語の決まりは [資料の抽出・翻訳スキル](skills/nist-document-extraction/SKILL.md) にまとめています。

SP 800 の現行 Final 資料の一覧（`data/sp800-final-catalog.json`）は、CSRC から取り直せます（ネット接続が必要）。

```sh
python3 scripts/update_sp800_final_catalog.py
```

## データの形式

| ファイル | 内容 |
| --- | --- |
| `data/<資料>-trans.json` | 正本。原文と訳文を段落（ブロック）ごとに持ちます。 |
| `data/<資料>-summary.json` | 資料の要約（`{number, model, created_at, summary: [文, …], review}`）。ページ上部の「[要約]」と meta description、トップページの検索に使います。 |
| `data/sp800-final-catalog.json`、`data/fips-final-catalog.json` | CSRC の資料一覧のスナップショット（公開日などに使います）。 |

`-trans.json` の各ブロックは、次の値を持ちます。

- 中身: `id`、`kind`（`paragraph`・`heading`・`list_item`・`table`・`figure`・`math`・`footnote` など）、`html`（原文）、`html_ja`（訳文）
- 状態:
  - `status`（`reviewed`・`draft`・`source_only`・`stale` など）
  - `extraction_status`（`verified`・`needs_review`）
  - `source_hash`（原文のハッシュ）
- PDF の資料のみ: `source_page`（原本のページ）、`source_refs`（ページ上の位置）

ページ番号の欄外文字や重複の記録などは、データに残したまま表示しません。

## 翻訳とレビューの進め方

- 訳文の作成、レビュー、最終判断は、それぞれ別の役割で行います（作成: Claude Sonnet、レビュー: Codex、数式・表・図と最終判断: Claude Opus）。
  - `scripts/translate_batches.py`: 訳文の作成
  - `scripts/translation_review.py`: レビュー結果の書き出しと反映
  - `scripts/resolve_flagged.py`: 指摘への最終判断
- 原本の誤記は、英文の欄では原本どおりに残し、訳文の欄で直します。数値・識別子・節番号の誤りを直したときは「［訳注: 原本では…］」を付けます。
- 訳文は HTML の構造（タグ・数式・脚注の上付き番号）と要件語（SHALL・SHOULD など）が原文と一致することを、ページ生成時に検査します。

## 検証

```sh
python3 -m unittest discover -s tests
```

公開前には、原文・訳文・生成済み HTML に置換文字（�）が残っていないことも確かめます。

```sh
python3 scripts/audit_source_encoding.py --report reports/source-encoding-audit.json
```

## ディレクトリ構成

```text
main.py                     コマンドの入口（fetch / parse / build / update / index / translate）
src/nist_translater/        取得・PDF 抽出・訳文管理・ページ生成
data/                       資料ごとの翻訳データ（-trans.json）と要約（-summary.json）
templates/                  ページのテンプレート（資料ページ、トップページ、共通ヘッダー）
static/                     CSS と KaTeX（static/vendor/katex、MIT ライセンス）
html/                       生成したサイト（公開するのはこのディレクトリ）
scripts/                    一括生成・抽出の修復・翻訳とレビューの補助
skills/                     抽出・翻訳のルール
reports/                    監査・照合の記録（HANDOVER.md は作業の引き継ぎ資料）
tests/                      テスト
```

## ライセンス

このリポジトリのコードと日本語訳は [MIT ライセンス](LICENSE) です。ただし、原文（NIST の著作物）と、原文に含まれる第三者の著作物はこのライセンスの対象外です。原文の扱いは「[原文の権利と出典](#原文の権利と出典)」を参照してください。同梱の KaTeX（`static/vendor/katex`）は、それ自身の MIT ライセンスに従います。
