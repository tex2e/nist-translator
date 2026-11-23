# 原本照合担当（Opus）への指示

非公式の英日対訳サイト（NIST 刊行物）で、PDF から抽出した英文ブロックを原本と照合し、修復指示を JSON で書く。データは直接変更しない。修復指示は `scripts/apply_repair_ops.py` が適用する（使える op は同スクリプトの docstring を参照）。

## 準備

- Python は `$PY`（SKILL.md の 1. で設定）（pdfplumber・pypdfium2 あり）。原本は `data/<key>.pdf`、正本は `data/<key>-trans.json`（`contents` が文書順のブロック配列）。
- 担当ページの画像を pypdfium2 で描画して（scale 2〜3。小さな文字・記号は 4 以上で部分描画）、目で見て照合する。文字層は `pdfplumber` の `extract_text_lines()` で座標とともに読める。文字層だけで判断しない。
- 担当ページのブロックをすべて（reviewed・verified のものも）文書順に並べ、原本の印刷内容と 1 対 1 に対応するか確認する。とくに `extraction_status` が `needs_review` のもの、`page_furniture` のもの、`kind` が `table` のものを重点的に見る。ページをまたぐ段落・箇条書きは次ページも見る。

## 判定と op

- 原本どおり（またはわずかな修正で原本どおり）: `verify`。英文に誤りがあれば `html` に正しい全文を書く（既存の HTML タグ・脚注番号の書き方は、その資料の他のブロックに合わせる）。見出しレベル・種別・番号の誤りは `kind`、`level`、`ordered`、`ordinal` で直す。
- ページをまたいで分かれた 1 段落: `merge`（`into` は前半のブロック、`html` は全文）。
- 1 ブロックに複数の段落・項目・見出しが入っている: `split`。
- 原本にあるのに正本のどこにもない文: `insert`（正本全体を検索して本当にないことを確かめる）。
- 重複・断片・誤抽出（同じ文が別ブロックにもある、表の中身が本文と二重、等）: `retire`。消す前に、内容が残るブロックに全文があることを確かめる。
- 柱・ページ番号・余白の縦書き文字: `furniture`。
- 図の中のラベルが本文ブロックとして抽出されている（図の画像ブロックがない）: op は書かず、`figure_from_text` に `[文書キー, 最初のラベルのブロックID, 最後のラベルのブロックID, キャプションのブロックID]` を追加する（ラベルは文書順に連続していること。キャプションは図の直下の "Figure N: …" のブロック）。並び替えが必要なら先に `order` を書く。
- 表と抽出されたブロック:
  - 本文・用語集・略語表の行の内容が別のブロックに既にある二重抽出なら `retire`。
  - 枠で囲まれた段落や見出しを表と誤認したものは `verify` で `kind` を直す（必要なら `split`）。
  - 本当の表で、すべてのセルを原本と照合できるなら `table` で `<table>` の HTML（`<thead>`/`<tbody>`、`<th>`/`<td>`、結合セルは `rowspan`/`colspan`）を書く。セルの文言・順序・空欄を原本どおりにする。照合しきれない表は op を書かず、`unresolved` に理由を書く。
- 図ブロック（`kind: figure`）は担当外。ただし公的標章（NIST ロゴ、商務省の紋章）、人物写真、他組織のロゴだけの図なら `unresolved` に記す。

ブロックの順序が原本の読み順と違う場合は `order` を書く。脚注はそのページの本文の後に置くのがこのサイトの順序である。

## 出力

指定のファイルへ次の JSON を書く。

```json
{"document": "sp800-130", "pdf_sha256": "<正本の source_sha256>", "checked_by": "Claude Opus",
 "evidence_directory": "<指定のディレクトリ>", "reason": "<1 行の英語の要約>",
 "ops": [ ... ], "figure_from_text": [ ... ], "unresolved": [{"id": "...", "reason": "..."}]}
```

各 op の `note` には、何を原本で確かめたかを短い日本語で書く。照合した範囲で問題がなかったブロックも、`needs_review` のものは必ず `verify` を書く（reviewed・verified で問題のないブロックは書かなくてよい）。推測で文字を確定しない。読めない場合は `unresolved` に入れる。

最後に、`$PY scripts/apply_repair_ops.py <出力ファイル> --dry-run` を実行し、エラーや `text not located` の警告がないか確認する（警告が出たら、その英文が原本の文字と一致するか見直す）。`--dry-run` なしでは実行しない。
