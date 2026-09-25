# NIST SP 800-63-4 英日対訳サイト

NIST SP 800-63 Revision 4 の4巻（63、63A、63B、63C）を段落単位に分解し、原文と日本語訳を並べた静的ページを生成します。既存の63B訳は `draft`（未レビュー訳）です。新しい巻のページは、訳文を追加するまでは翻訳準備中として原文を表示します。

NIST の正式版PDFを要件確認の基準にしてください。このサイトは非公式の閲覧用資料です。

| 巻 | 内容 | 生成ページ |
| --- | --- | --- |
| SP 800-63-4 | Digital Identity Guidelines | `html/sp800-63.html` |
| SP 800-63A-4 | Identity Proofing & Enrollment | `html/sp800-63a.html` |
| SP 800-63B-4 | Authentication & Authenticator Management | `html/sp800-63b.html` |
| SP 800-63C-4 | Federation & Assertions | `html/sp800-63c.html` |

## セットアップと生成

Python 3.9 以降を使用します。

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 main.py update --document 63a
python3 -m http.server 8000 --directory html
```

`--document` には `63`、`63a`、`63b`、`63c` を指定します。省略時は従来どおり `63b` です。`update` はNISTから原文を取得し、JSONを作成または更新してHTMLを出力します。各処理は個別にも実行できます。

```sh
python3 main.py fetch --document 63c
python3 main.py parse --document 63c
python3 main.py build --document 63c
```

HTMLは `http://localhost:8000/sp800-63c.html` で確認できます。生成時は原文取得のためネット接続が必要です。取得したHTMLは解析成功後に削除されます。

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
