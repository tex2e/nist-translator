# NIST SP 800-63B 英日対訳サイト

NIST の [SP 800-63B-4 HTML](https://pages.nist.gov/800-63-4/sp800-63b.html) を段落単位に分解し、原文と日本語訳を並べた静的ページを生成します。現在の対訳データは全文を `draft`（未レビュー訳）として収録しています。

NIST の[正式版 PDF](https://doi.org/10.6028/NIST.SP.800-63b-4)を要件確認の基準にしてください。このサイトは非公式の閲覧用資料です。

## セットアップと生成

Python 3.9 以降を使用します。

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 main.py parse
python3 main.py build
python3 -m http.server 8000 --directory html
```

ブラウザーで `http://localhost:8000/sp800-63b.html` を開きます。生成時のネット接続は不要です。原文更新時だけ、NIST から `data/sp800-63b.html` を一時取得して段落を抽出し、成功後に削除します。

原文を取り直す場合は `python3 main.py update` を実行します。`fetch`、`parse`、`build` を個別に実行することもできます。

## 訳文の追加

### agy による自動翻訳

`agy` がインストール済みでログインできる環境では、次のコマンドで未翻訳の先頭 10 ブロックを翻訳します。完了したバッチから `sp800-63b-trans.json` に保存され、再実行すると未翻訳分から再開します。訳はすべて `draft` です。`--effort low` を指定すると高速化できますが、規範語やタグの検証に失敗したバッチは標準推論で再試行します。

```sh
python3 main.py translate
```

実行量を指定する例です。既定では1回あたり最大8ブロック・英文5,000文字をまとめます。バッチの応答が壊れた場合は再試行し、それでも失敗すれば小さなバッチに分けます。`--limit 0` は残りすべてを対象にするため、先に少数で出力を確認してください。

```sh
python3 main.py translate --limit 0 --dry-run
python3 main.py translate --limit 30 --batch-size 8 --timeout 180
python3 main.py translate --cli gemini --limit 10
```

全文の実行量は `--dry-run` で確認できます。表の HTML も入力に含むため、呼び出し回数とトークン量は本文だけを渡す場合より増えます。`agy` の固定的なコンテキスト読み込みも大きいため、全文実行前に少数の訳と利用量を確認してください。

`agy` は `--output-format json --json-schema` を指定し、返答の `structured_output` を読みます。公式の `gemini` CLI は `--approval-mode plan --output-format json` の `response` を読みます。どちらも Python の `subprocess` に引数配列を渡し、シェルは使いません。翻訳依頼時はHTMLタグをプレースホルダーに置き換え、モデルが本文だけを翻訳できるようにしてから元のタグを復元します。モデルがツールを要求して拒否された場合、空の応答や不正な JSON を返した場合、ID・原文ハッシュ・件数が一致しない場合はそのバッチを破棄します。規範語 `SHALL` などが原文にある場合、訳文に残っていることも確認します。各バッチは検証後に一時ファイルを介して原子的に保存するため、失敗したバッチで既存の文書 JSON を壊しません。

翻訳対象は本文だけでなく表も含みます。原文の `html` と訳文の `html_ja` は、タグ名・全属性（リンク先を含む）が一致し、閉じタグが正しく対応しなければ保存できません。翻訳が変更できるのは HTML のテキストノードだけです。この検証は `import`、`translate`、`build` のすべてで実行されます。

この検証が保証するのは JSON の構造と原文との対応です。訳の意味や規範表現が正確かどうかは人手でレビューしてください。

### 手動で訳文を追加

`data/sp800-63b-trans.json` の対象要素を直接編集します。`html_ja` へ訳文を入れ、`status` を `draft` または `reviewed` に設定してから、次を実行します。

```sh
python3 main.py build
```

各要素は `html` と `html_ja` を並べて持ちます。原文は重複した `text` を持ちません。追加フィールドは `id`、`source_hash`、`status` です。原文が変化した要素は `status: "stale"` となり、公開ページでは旧訳を表示しません。

表・図・脚注は原文を表示します。外部参照は NIST の URL にリンクします。

## 構成

```text
main.py                    コマンド入口
src/nist_translater/       取得・構造化・訳文管理・ページ生成
data/sp800-63b.html      NIST 原文の一時取得先（Git 管理外・抽出成功後に削除）
data/sp800-63b-trans.json 原文、訳文、原文ハッシュ、レビュー状態
templates/page.html        ページテンプレート
static/style.css           スタイル
html/                      生成ページ（Git 管理対象）
tests/                     パーサーと訳文更新の検証
```

## 検証

```sh
python3 -m unittest discover -s tests
```
