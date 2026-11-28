# 脚注と抽出の照合（2026-11-28）

## 原本の文字層にあってデータにない行

全資料（PDF が原本のもの）について、原本の文字層の行のうち、データのどのブロックの本文にも範囲にも入らず、第三者の著作物として非掲載にしたページにもないものを洗い出しました（1320 行）。1 行ずつの理由は `text-layer-residual.json` にあります（著者・連絡先の行は、個人の名前や連絡先を載せないため本文を省いています）。

| 理由 | 行数 |
|---|---|
| running header | 749 |
| present in another order or form (table/figure/math) | 215 |
| staff contact list (not published) | 110 |
| author / affiliation list (two-column order) | 82 |
| watermark (doubled glyphs) | 80 |
| table on the page (row read in another order) | 27 |
| table continued from an earlier page (rows are in that table block) | 13 |
| retired on purpose by the earlier proof (text hidden under a white box) | 13 |
| every word is in the data (two-column list or glossary read across columns) | 10 |
| back-of-book index | 9 |
| rotated or doubled text (figure/watermark) | 5 |
| figure on the page (label inside the picture) | 3 |
| no local PDF (HTML/verified earlier) | 2 |
| every entry is in the data (two-column acronym list read across columns; "Bufer Overfow" lost its ff ligature) | 2 |

本文の抜けとして見つかったものは、このブランチで補いました（FIPS 201-3、FIPS 186-5、FIPS 204、IR 4250、IR 7987r1、SP 800-37r2 ほか、SP 800-38C の注）。

## リンクされない上付きの数字

ページ生成後に脚注へリンクされていない `<sup>` の数字（脚注の中を含む 177 件）について、原本の前後 3 ページに同じ番号の脚注が印刷されているかを調べ、1 件ずつ判定しました。判定は `unlinked-superscripts.json` にあります。脚注の参照であるものは 0 件です。

| 判定 | 件数 |
|---|---|
| exponent or version number (follows a digit) | 117 |
| part of a label or name (follows a capital: DS³, S²A, MDS²) | 34 |
| unit (m², km², µm²) | 9 |
| number inside the affiliation list itself (the link target) | 8 |
| exponent in a formula (follows a bracket) | 5 |
| mark printed inside footnote 1 itself (as in the original) | 1 |
| exponent (O(n²)) | 1 |
| part of a paper title (Hash³) | 1 |
| exponent in a formula (|E|², f²) | 1 |
