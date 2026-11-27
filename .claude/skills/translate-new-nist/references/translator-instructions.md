# 翻訳担当（Sonnet）への指示

非公式の英日対訳サイト向けに、NIST の刊行物を日本語へ訳す。`scripts/translate_batches.py export` が書き出した `*.batch.json` を訳し、同じ名前の `*.result.json` を書く。

## 入出力

- バッチは `document`、`title`、`blocks`（文書順の連続ブロック。各ブロックは `id`、`kind`、`source_hash`、`en`）を持つ。ファイル全体を先に読み、前後の文脈を踏まえて訳す。
- 出力は、ブロックと同じ順の JSON 配列 `[{"id", "source_hash"（そのまま写す）, "html_ja"}]`。Python の短いスクリプトか Write ツールで、正しい JSON として書く。
- 書いた後、id・source_hash がバッチと一致し、`html_ja` が空でないことを確認する。ほかのファイルは変更しない。
- 用語をそろえるため、同じ資料の既存の訳（`data/<key>-trans.json` の `html_ja`）を読んで参照してよい（読み取りのみ）。

## 訳し方

- 敬体（です・ます。2026-10-31 依頼者指示、読みやすさのため）。「。」で終わる文の文末を です・ます にする。箇条書きの断片・表のセル・体言止めは、そのままでよい。イ形容詞に「です」を付けた形（「多いです」「難しいです」）は避け、「多くあります」「困難です」などで受ける。見出しは名詞句で終わらせられるものは名詞句にする（"Use Cryptography" →「暗号技術の使用」）。意味を正確に訳し、足さず、落とさない。直訳調を避け、自然な技術日本語にする。
- 要件の強さを保つ。shall は「しなければなりません」、shall not は「してはなりません」、should は「すべきです」（「望ましい」としない）、should not は「すべきではありません」、may は文脈に応じて「してもよいです」「場合があります」、must は「しなければなりません」。大文字の SHALL・SHOULD・MAY 等は英語のまま、同じ回数残す。
- 原語のまま残すもの: 人名、メールアドレス、URL、刊行物の識別子（SP 800-57、FIPS 140、RFC 5246）、刊行物・規格の題名、略語（CKMS、PKI、CA、KDC）。題名は『』で囲まずに英語のままでもよいが、既存の訳に合わせる。
- 参考文献の項目は、著者・題名・発行元・識別子を英語のまま残し、接続語だけを訳す。
- 脚注番号は英文と同じ形で残す（英文が `products62` のように数字を続けて書いていれば、訳でも語の直後に `62` を置く）。
- 箇条書きの末尾の and／or が次項目へのつなぎだけなら、訳では項目を「。」で終えて省いてよい。ただし or が要件を択一にする場合は意味を保つ。
- 段落の途中で切れているブロックは、そこまでだけを訳し、続きに自然につながる形にする。
- HTML: `en` のタグを同じ種類・同じ数だけ `html_ja` に残す。実体参照（`&amp;` など）はエスケープしたままにする。LaTeX の数式は変えない（`\text{...}` の中だけ訳してよい）。

## 固定の訳語（全資料共通）

- 用語表 `data/glossary.json` の訳語に従う（避ける訳語も載っている）。訳し終えたら `scripts/check_glossary.py <stem>` で照合する。
- keying material は「鍵素材」（「鍵材料」としない）。secret keying material は「シークレット鍵素材」。shared secret key は「共有シークレット鍵」。shared secret は「共有シークレット」（「共有秘密」としない。shared secret value は「共有シークレット値」）。
- private key は「秘密鍵」（「私有鍵」「プライベート鍵」としない）。鍵の名前は「署名用秘密鍵」「鍵合意用秘密鍵」「認可用秘密鍵」「認証用秘密鍵」「鍵輸送用秘密鍵」の形にする。
- symmetric は「共通鍵」（共通鍵暗号、共通鍵アルゴリズム。「対称鍵」としない）。asymmetric の暗号方式は「公開鍵暗号」「公開鍵アルゴリズム」。鍵そのもの（asymmetric key、asymmetric key pair）は「非対称鍵」「非対称鍵ペア」。
- secret key（共通鍵）は「共通鍵」とし、private key（秘密鍵）と区別する。
- その他の目安: compromise は「危殆化」（動詞は「危殆化する」）、cryptoperiod は「暗号期間」、key establishment は「鍵確立」、key agreement は「鍵合意」、key transport は「鍵輸送」、key wrapping は「鍵ラッピング」、metadata は「メタデータ」、revocation は「失効」、suspension は「一時停止」、source authentication は「出所認証」、integrity は「完全性」、confidentiality は「機密性」、trust anchor は「トラストアンカー」、Certification Authority は「認証局（CA）」、Registration Authority は「登録局（RA）」。資料の既存の訳に確立した訳語があれば、それに合わせる。
- 原本の誤記（綴り・語の重複や欠け・括弧の不整合・明らかな略語の誤りなど）は、英文の欄では原本どおりに残し、訳文では意味が変わらない範囲で読みやすく直して訳す（例: "credential theft of compromise" → 「認証情報の窃取または侵害」、"that that" の重複は訳に出さない）。意図が一つに決まらない誤記、数値・識別子・数式・節番号の誤りは直さず、英文どおりに訳す。
