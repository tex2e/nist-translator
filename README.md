# NIST SP 800-63-4 英日対訳サイト

NIST SP 800 資料を段落単位に分解し、原文と日本語訳を並べた静的ページを生成します。SP 800-63 Revision 4 の4巻に加え、PDFで公開されている資料も取り込めます。

NIST の正式版PDFを要件確認の基準にしてください。このサイトは非公式の閲覧用資料です。

| 巻 | 内容 | 生成ページ |
| --- | --- | --- |
| SP 800-63-4 | Digital Identity Guidelines | `html/sp800-63.html` |
| SP 800-63A-4 | Identity Proofing & Enrollment | `html/sp800-63a.html` |
| SP 800-63B-4 | Authentication & Authenticator Management | `html/sp800-63b.html` |
| SP 800-63C-4 | Federation & Assertions | `html/sp800-63c.html` |
| SP 800-131A Rev. 2 | Cryptographic Algorithms and Key Lengths（PDF 原文抽出） | `html/sp800-131ar2.html` |
| SP 800-238 | Fiscal Year 2025 Annual Report for NIST Cybersecurity and Privacy Program（PDF 原文抽出） | `html/sp800-238.html` |
| SP 800-236 | Fiscal Year 2024 Annual Report for NIST Cybersecurity and Privacy Program（PDF 原文抽出） | `html/sp800-236.html` |
| SP 800-234 | High-Performance Computing (HPC) Security Overlay（PDF 原文抽出） | `html/sp800-234.html` |
| SP 800-233 | Service Mesh Proxy Models for Cloud-Native Applications（PDF 原文抽出） | `html/sp800-233.html` |
| SP 800-232 | Ascon-Based Lightweight Cryptography Standards for Constrained Devices（PDF 原文抽出） | `html/sp800-232.html` |
| SP 800-231 | Bug Framework (BF): Formalizing Cybersecurity Weaknesses and Vulnerabilities（PDF 原文抽出） | `html/sp800-231.html` |
| SP 800-229 | Fiscal Year 2023 Cybersecurity and Privacy Annual Report（PDF 原文抽出） | `html/sp800-229.html` |

## セットアップと生成

Python 3.10 以降を使用します。PDF 抽出の動作確認には Python 3.11 を使用しました。

```sh
python3.11 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 main.py update --document 63a
python3 -m http.server 8000 --directory html
```

`--document` には `63`、`63a`、`63b`、`63c`、`131ar2`、`238`、`236`、`234`、`233`、`232`、`231`、`229` を指定します。省略時は従来どおり `63b` です。`update` はNISTから原文を取得し、JSONを作成または更新してHTMLを出力します。各処理は個別にも実行できます。

```sh
python3 main.py fetch --document 63c
python3 main.py parse --document 63c
python3 main.py build --document 63c
```

HTMLは `http://localhost:8000/sp800-63c.html` で確認できます。`fetch` / `update` で原文を取得する場合はネット接続が必要です。取得した HTML は解析成功後に削除されます。

## 現行 Final 資料一覧

`https://csrc.nist.gov/publications/sp800` の現行一覧から、系列が SP、番号が 800 系、ステータスが Final のレコードを抽出します。スナップショットは `data/sp800-final-catalog.json` に保存し、翻訳データがある資料は進捗とJSON/HTMLのパスも記録します。2026年9月26日時点の一覧は195件です。

```sh
python3 scripts/update_sp800_final_catalog.py
```

再取得にはネット接続が必要です。NISTが一覧を更新した後に実行すると、台帳も最新化されます。

## PDF だけの資料

`131ar2`、`238`、`236`、`234`、`233`、`232`、`231`、`229` は PDF 原本から抽出した資料です。訳文は `draft` で、PDF原文の抽出状態は `needs_review` です。表や図は HTML と原本から切り出した画像を併記します。図中の文字や複雑な表を含め、原文と照合してから抽出状態を `verified` にしてください。

```sh
python3 main.py fetch --document 131ar2
python3 main.py parse --document 131ar2
python3 main.py build --document 131ar2
```

`--pages` を省略すると PDF 全ページを抽出します。一部ページだけを確認するときは `--pages 7-8,15,21` を指定します。この場合、出力ページに未収録ページがある旨を表示します。新しい PDF 資料は `src/nist_translater/documents.py` に `source_format: "pdf"` と公式 PDF URL を登録します。PDF 原本は `data/*.pdf` に保持しますが、Git の対象外です。再取得しても訳文は同じ原文ブロックへ引き継がれ、変化したブロックは `stale` になります。

PDF ブロックには `source_page`、`source_refs`（原本中の座標）、`extraction_status` を記録します。抽出直後は `needs_review` です。原本と照合したブロックだけ `verified` に設定してください。訳文の `reviewed` は、原文抽出が `verified` の場合に限って受け付けます。画像だけの PDF は先に OCR で文字層を作り、`data/sp800-<slug>.pdf` に置いてから `parse` を実行します。`fetch` はそのファイルを公式 PDF で上書きします。

## 訳文の追加

### agy による自動翻訳

`agy` が使える環境では、指定した巻の未翻訳ブロックを翻訳できます。完了したバッチは該当する `data/sp800-63*-trans.json` に保存され、再実行すると未翻訳分から再開します。訳は `draft` です。

```sh
python3 main.py translate --document 63a
python3 main.py translate --document 63c --limit 30 --batch-size 8 --timeout 180
python3 main.py translate --document 63a --limit 0 --dry-run
```

既定では1回あたり最大8ブロック・英文5,000文字をまとめます。表のHTMLも翻訳入力に含まれます。全文実行前に `--dry-run` で呼び出し回数と対象量を確認してください。

翻訳依頼時はHTMLタグをプレースホルダーに置き換え、モデルが本文だけを翻訳できるようにしてから元のタグを復元します。返答のID・原文ハッシュ・件数・HTML構造・規範語を検証し、検証に通ったバッチだけを原子的に保存します。JSON検証が保証するのは構造と原文との対応です。訳の意味や規範表現の正確さは人手でレビューしてください。

### 手動で訳文を追加

各巻の `data/sp800-63*-trans.json` の対象要素を編集します。`html_ja` に訳文を入れ、`status` を `draft` または `reviewed` に設定してから、その巻のページを再生成します。

```sh
python3 main.py build --document 63a
```

各要素は原文 `html` と訳文 `html_ja` を持ちます。追加フィールドは `id`、`source_hash`、`status` です。原文が変化した要素は `status: "stale"` となり、公開ページでは旧訳を表示しません。図と脚注は原文を表示します。

## 構成

```text
main.py                    コマンド入口
src/nist_translater/       取得・構造化・訳文管理・ページ生成
data/sp800-*-trans.json    各巻の原文、訳文、原文ハッシュ、レビュー状態
templates/page.html        共通ページテンプレート
static/style.css           スタイル
html/                      生成ページ
tests/                     パーサーと訳文更新の検証
```

## 検証

```sh
python3 -m unittest discover -s tests
```
