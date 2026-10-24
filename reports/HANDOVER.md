# 引き継ぎ資料：NIST SP 800 対訳サイトの原本照合・翻訳

2026-10-24 時点。この資料だけで作業を再開できるように、方針・現状・手順・落とし穴・残作業をまとめる。

## 2026-10-24 の追加作業（最新）

- 利用者がCPU方針を更新した。土日も画像生成・OCR・ページ再生成を行ってよいが、重い処理は全体で1並列にする。Sonnetが使えるまで独立レビューは保留し、翻訳と原本照合を進める。
- **7資料・98件を追加翻訳**：12r1（14）、201（13）、206（11）、30r1（14）、53ar5（15）、90b（15）、96（16）。全件`draft`。英語の用語、原文ハッシュ、HTML、要件語を保持した。[作業記録とバッチ](work-in-progress/resume-20261024-2/README.md)を参照。
- **133r2の重複3件を原本で確認し、非表示にした**。PDF 19ページを150dpiで生成して目視確認。U、V、独立性の3項目は原本では各1回。`pdf-p0019-r0003`〜`r0005`に既存の数式ブロックを指す`math_duplicate_of`を設定し、原文・訳文・ハッシュを保持した。原本PDFのSHA-256と両ブロックのハッシュは`math_duplicate_check`に記録した。既存数式とその訳のレビュー状態は変更していない。
- **レビュー用バッチの重複除外**：`scripts/translation_review.py`の候補選定でも`math_duplicate_of`を除外した。前回の`rev/sp800-133r2.001.batch.json`から当該3件を削除したため、前回の有効なレビュー用バッチは77件、今回のバッチは98件となる。`tr/`は反映時の記録として保持。
- **57pt1r5の既存状態不整合9件を修正**：原文が`needs_review`なのに訳が`reviewed`となって再生成に失敗した9件を、`draft`へ戻した。訳文と原文は変更せず、過去のレビュー状態は`translation_review_suspended`へ保存した。原文の構造照合と独立レビューが改めて必要。対象は`pdf-p0070-r0002`〜`r0008`、`pdf-p0135-r0013`・`r0014`。
- **17資料のページ再生成完了**：前回の10資料と今回の7資料、および索引を更新した。今回の2回の作業で追加した訳178件のうち、重複3件を除く175件がHTMLにあることを検査した。全資料の一括再生成はまだ行っていない。
- **検証**：全42テストが通過。変更対象の原文保持・翻訳の取り込み整合性、17資料のデータ監査、HTML内の非公式表示・訳文・重複非表示を検査。ブラウザのローカルファイル表示はURL制限で拒否されたため、ブラウザでの見た目の確認は未実施。画像生成・再生成・テストは同時実行していない。
- **現在の有効なPDF本文**：137,966件。原文照合済み135,555件、未照合2,411件、レビュー済み119,850件。照合済み未翻訳**9,368件**、照合済みの訳レビュー待ち**5,797件**。重複3件の除外と9件のレビュー保留により、本文総数・レビュー済み数が以前と変わっている。
- **追加の残課題**：他資料にも、原文が未照合なのに訳がレビュー済みとなっている本文が91件ある。今回の17資料には残っていない。今後の原本照合・再生成時に、状態を整理する必要がある。

## 2026-10-24 の再開記録

- 以下の10資料の照合済み未翻訳本文80件を翻訳し、`data/`へ反映した。すべて`draft`であり、独立レビューは未実施。
  - 107r1（9）、133r2（6）、150（11）、167（10）、177r1（3）、187（12）、219r1（6）、57pt1r5（6）、61r3（12）、84（5）。
- 原文、`source_hash`、抽出照合の記録は変更していない。変更は80件の`html_ja`と`status`のみ。
- 照合済み未翻訳の本文は9,546件から**9,466件**へ減少。今回の80件はレビュー待ちとして残る。
- 土曜日のため、画像生成・OCR・HTML再生成は実行していない。`html/`は従来のまま。
- この再開環境では旧WorkflowツールとSonnetを利用できない。訳文を自分で確認しても独立レビュー済みにはしていない。
- [再開用フォルダ](work-in-progress/resume-20261024/README.md)に、翻訳のバッチ・結果と、今回の80件だけを含むレビュー用バッチを保存した。翻訳結果は反映済みなので、再applyは不要。次は`rev/`の独立レビューから再開できる。
- 検証：80件すべてのID・ハッシュ・HTML構造・LaTeX・要件語・用語集の英語用語の保持を確認。変更対象以外のデータが不変であることを確認。`test_auto_translate.py`の9テストと`git diff --check`が通過。全テストと表示確認は未実施。
- **追加の構造確認候補**：133r2のPDF 19ページ。`pdf-p0019-r0003`〜`r0005`と、既存の`pdf-p0019-math-005`〜`math-007`にはそれぞれU、V、その独立性について同じ英文がある。既存の数式ブロックは旧ID（`b0005`等）を`replaces`で参照するが、組み直し後の`r`ブロックは隠されていない。原本と表示を確認してから重複を整理すること。今回は原文・表示制御・照合状態を変えていない。
- `main`にコミットする方針を継続し、pushは行っていない。下記第3節は再開前の履歴として残している（再開時のHEADは`ce0833b6`、未pushは15コミットだった）。

## 1. 何をしているか

NIST SP 800 シリーズの PDF から本文を抽出し、英日対訳の HTML を作る非公式サイト。今の作業は全資料について、次の 3 点を揃えること。

1. **抽出した英文を原本 PDF と照合する**：文字、段落の区切り、読み順を確かめる。
2. **照合済みの英文を翻訳する**。
3. **訳を独立にレビューする**。

公開ページは `html/`、データは `data/sp800-<key>-trans.json`、原本 PDF は `data/sp800-<key>.pdf`。

## 2. 守るべき方針（利用者の指示）

### 作業の進め方
- **ブランチ**：メインのチェックアウトで `main` に直接コミットする。作業の区切りごとにコミットする。
- **push**：利用者が「push して」と言ったときだけ行う。
- **報告**：日本語で、結論から短く書く。
- **並列度**：エージェントは **1 並列**で流す。
- **CPU・並列度（2026-10-24に利用者が更新）**：土日も画像生成・ページ再生成・OCRを実行してよい。ただし、重い処理は全体で**1並列**にし、本体に負荷をかけない。対象を絞って順番に実行する。
- **モデル**：照合やレビューのエージェントは **Sonnet**、組み直しと翻訳は既定のモデル。
- **独立レビューの保留（2026-10-24に利用者が指定）**：Sonnetが使えるまでは独立レビューを保留し、翻訳・原本照合を進める。他モデルのエージェントに置き換えない。
- **Git の履歴**：書き換えない。

### サイトの内容
- **標章**：NIST のロゴ、商務省の紋章、NIST ロゴが写った図、人物の顔写真、他組織のロゴ、装飾画像は掲載しない。ブロックに `official_mark` を付け、画像ファイルを消す。対象は `scripts/withhold_marks.py` と `reports/official-marks.json` で管理する。
- **公式性の表示**：サイトには、非公式であること、NIST や商務省が承認したものではないことを明記する。「NIST 公式翻訳」と誤認させる表現は使わない。
- **表**：原本と照合していない表は、**原本の画像を正**として表示する。抽出したテキストは参考として折りたたむ。
- **文字化け**：原本を読み直し、正しい原文に直す。
- **SP 800-53 r5 の訳語**：管理策名と拡張名は日本語に訳す。ラベルは次のとおり。
  - 管理策：／考察：／関連管理策：／管理策の拡張：／参考文献：
  - ［割当て：組織が定義する…］、［選択…］、［廃止：…］
- **全大文字の英文**：「MAY 2016」や「COMMENTS MAY BE SUBMITTED」には、要件語の表示（（MAY）など）を付けない。
- **数式**：[スキル](../skills/nist-document-extraction/SKILL.md)の規則に従う。通常の LaTeX で書き、座標を再現する組み方はしない。

プロジェクトの規則は [AGENTS.md](../AGENTS.md) と [skills/nist-document-extraction/SKILL.md](../skills/nist-document-extraction/SKILL.md) にある。必ず読むこと。

## 3. 現状（2026-10-23 12:04 に照合を反映した時点）

- **ブランチ**：`main`。`origin/main` より **14 コミット先行していて、未 push**。
- **最新コミット**：`3c4d8b47 組み直したページの再照合を反映する`。
- **公開ページ（`html/`）**：A（次の 30 資料）を終えた時点のまま。その後のデータ変更は**まだページに反映していない**。

本文ブロック（paragraph、heading、list_item、note、footnote）は 137,969 件。

| 項目 | 件数 | 割合 |
|---|---|---|
| 原本照合済み（`extraction_status: verified`） | 135,558 | 98.3% |
| 訳レビュー済み（`status: reviewed`） | 119,859 | 86.9% |
| 照合済みで未翻訳 | 9,546 | |
| 照合済みで、訳がレビュー待ち（`draft`） | 5,622 | |
| 未照合 | 2,411 | |
| 未解決の訳（`translation_check: claude-issue`） | 2 | |

未照合 2,411 件の内訳は次のとおり。

| 内訳 | 件数 |
|---|---|
| 構造の問題あり（`structural:*`） | 510 |
| 同じページに構造の問題があり保留 | 1,529 |
| 照合役が文字を直したので再確認待ち | 26 |
| 照合の記録がない（仕込みを見逃したバッチなど） | 346 |

未照合が多い資料は、160v1r1（253）、82r3（121）、57pt1r5（118）、94（99）、53r5（94）。

### これまでに終えたこと
- **上位 30 資料、A（次の 30 資料）、残り 56 資料**：ページ単位の照合 → 組み直し → 再照合まで終えた。上位 30 資料と A は、翻訳とレビューも終えた。
- **構造の候補ページ**：照合済みでも用語集の断片などが残っていそうなページ（117 資料・552 ページ）を、指示を強めた照合にかけた。構造の問題が出たページは組み直して再照合した。
  - これまでの組み直しは延べ約 4,700 ページ。最後の回は 142 資料・1,585 ページで、11,942 ブロックになった。
- **年次報告書と 53 r5**：照合・翻訳・レビューまで済み。
- **引用符の文字化け**：119、122、126 r1 は、PDF のテキスト層の段階で “ ” ‘ が ―、‖、‗ に化けていた。`scripts/fix_quote_glyphs.py` で直した。
- **組み直しで消えた抽出記録**：組み直しで置き換えた元の抽出記録は、`math_preservation.rebuilt_blocks` に保存するようにした。すでに消えていた分は Git の履歴から補った。

## 4. データの要点

`data/sp800-<key>-trans.json` の `contents` が、ブロックの配列になっている。

| フィールド | 意味 |
|---|---|
| `id` | `pdf-pNNNN-bNNNN`（元の抽出）、`pdf-pNNNN-rNNNN`（組み直し）、`pdf-pNNNN-math-NNN` など |
| `kind` | paragraph、heading、list_item、note、footnote、figure、table、math、source_excerpt など |
| `html` / `html_ja` | 英文と訳文。数式は `\(...\)` と `\[...\]` で書く |
| `source_hash` | `sha256(kind + "\n" + html + "\n")` の先頭 16 桁。英文を直したら必ず計算し直す |
| `status` | untranslated、draft、reviewed、stale、source_only |
| `extraction_status` | needs_review、verified |
| `extraction_check` | pdfium+ocr（自動照合）、visual、visual-page（ページ単位の目視照合） |
| `source_page`、`source_refs[{page,bbox}]` | 原本での位置 |
| `column_reflow` または `page_check` | ページ照合の記録。`page_proof` に状態が入る（matches_original、structural:…、page_has_structural_problems、text_corrected_by_checker など）。`proof_note` に照合役のメモが入る |
| `translation_check` | claude-review（合格）、claude-fix（修正済みで再レビュー待ち）、claude-issue（2 回直しても未解決） |
| `translation_fix_rounds` | 訳の修正回数。上限は 2 |
| `page_furniture` | 柱、ノンブル、繰り返しの見出しなど。本文として数えない |
| `math_duplicate_of` | 結合して不要になった重複を隠す |
| `duplicate_artifact_of` | 同じページの表への参照だけに使う。表以外を指すとテストが落ちる |
| `official_mark` | 掲載しない標章の種類 |
| `structure_recheck` | 構造確認のために照合済みから戻したブロックで、元の照合方法を残している |
| `math_groups` | 231 で手で組んだ数式のまとまり。メンバーの `source_hashes` を持つ |

## 5. 作業の流れとコマンド

Python は `.venv/bin/python`。コマンドはリポジトリのルートで実行する。`<dir>` は作業用フォルダ。

### 5.1 ページ単位の照合
```bash
.venv/bin/python scripts/page_proof.py export sp800-<key> <dir>/proof/<key> [--pages 12,13]
```
- 未照合ブロックがあるページの画像（上半分と下半分）と、バッチ（3 ページずつ）を作る。
- 各バッチには、照合役を試すための誤りが 1 つ仕込まれる。答えは `*.key.json` に入っている。

続けて Workflow で照合し、結果を反映する。
- 構造を重視するときは `proof-lanes-h.js`、それ以外は `proof-lanes.js` を使う。
- 引数は `{base, counts:[[key,n]], per:3, lanes:1, note}`。

```bash
.venv/bin/python scripts/page_proof.py apply sp800-<key> <dir>/proof/<key>
```
- 仕込みを見逃したバッチは採用されない。
- 問題がなかったブロックは `verified`、構造の問題があったブロックは `structural:*` になる。

### 5.2 組み直し
```bash
.venv/bin/python scripts/page_proof.py rebuild-export sp800-<key> <dir>/rebuild/<key> --proof-dir <dir>/proof/<key>
```
- 構造の問題があるページの未照合ブロックを書き出す。足りないページ画像はその場で作る。
- `rebuild-lanes.js`（引数 `{base, counts, lanes:1, note}`、既定モデル）で組み直す。

```bash
.venv/bin/python scripts/page_proof.py rebuild-apply sp800-<key> <dir>/rebuild/<key>
```
- 新しいブロックの id は `pdf-pNNNN-rNNNN`。未照合・未翻訳になる。
- 組み直したあとは、5.1 で**必ず再照合する**。

### 5.3 翻訳
```bash
.venv/bin/python scripts/translate_batches.py export <dir>/tr sp800-<key>
```
- 照合済みで未翻訳のブロックを、約 9,000 文字ずつのバッチにする。
- `translate-lanes.js` で翻訳する。引数は `{dir, files, per:2, lanes:1, note}`。

```bash
.venv/bin/python scripts/translate_batches.py apply <dir>/tr sp800-<key>
```
- 要件語（SHALL など）の数が英文と合わない訳は、取り込まずに弾く。

### 5.4 訳レビュー
```bash
.venv/bin/python scripts/translation_review.py export <dir>/rev sp800-<key> ...
```
- `review-chunks.js`（Sonnet）でレビューする。引数は `{dir, files, per:3, lanes:1, note}`。

```bash
.venv/bin/python scripts/translation_review.py apply <dir>/rev
```
- レビューで直した訳を再レビューする手順は次のとおり。
  1. `export --fixed <tmp> <keys>` で書き出す。
  2. 書き出したファイルを `<key>.9NN.batch.json` に**名前を変えて**、新しいフォルダに置く。
  3. もう一度 review-chunks にかけて apply する。
- 再レビューは最大 2 回まで。それでも直らなければ `claude-issue` になる。

### 5.5 ページの再生成とテスト
```bash
.venv/bin/python reports/work-in-progress/build_all.py [<key> ...]
```
- 引数の key には `sp800-` を付けない（例：`22r1`）。

```bash
.venv/bin/python -m unittest discover -s tests
```
- pytest は入っていないので、unittest を使う。42 件すべて通ることを確かめる。

### ワークフローのスクリプト
[reports/work-in-progress/](work-in-progress/) にある。Workflow ツールの `scriptPath` に、作業用フォルダへコピーしたものを渡す。主なものは次の 6 つ。

- proof-lanes.js
- proof-lanes-h.js
- rebuild-lanes.js
- translate-lanes.js
- review-chunks.js
- check-lanes.js

## 6. 落とし穴（実際に起きたもの）

### 環境
- **作業用フォルダの自動削除**：一時フォルダ（scratchpad）の古いファイルは、1 週間ほどで消える。スクリプトの正本は `reports/work-in-progress/` に置き、途中の結果は早めに `data/` へ反映してコミットする。
- **作業場所**：worktree `.claude/worktrees/nist-sp800-pdf-audit-4808f2`（ブランチ `claude/nist-sp800-pdf-audit-4808f2`）は古いまま。作業はメインのチェックアウト（`main`）で行っている。
- **push**：サンドボックスの中では GitHub に SSH でつなげない。push はサンドボックスの外で実行する。`nice` も使えない。

### 反映と照合
- **apply を 2 回流さない**：訳レビューの apply を同じフォルダで 2 回流すと二重に数えられる。一度、約 450 件の誤った未解決が出た。そのときは `git checkout <直前のコミット> -- data reports/translation-review-issues.json` で戻し、1 回だけ流し直した。
- **書き出したあとにデータを直さない**：英文を直すとハッシュが変わる。書き出したあとに直すと、apply が「書き出し後に変更あり」として飛ばす。照合中の資料には触らない。
- **231 の数式グループ**：照合でメンバーの英文が直ると、グループの `source_hashes` が合わなくなり apply が落ちる。グループのメンバーはページ照合の対象から外してある。
- **目視の照合も用語集の断片を見逃していた**：用語と定義が別々のブロックに分かれていても、1 つずつの文字が合っていれば「一致」としていた。用語集、まとまった箇条書き、平文の数式を問題として扱うよう指示を強めた `proof-lanes-h.js` を使う。

### テストと表示
- **22r1 の数式テスト**：組み直しで元の抽出記録が消えると、再抽出のテストが落ちる。`rebuild_apply` は消える記録を `math_preservation.rebuilt_blocks` に残すようにしてある。
- **数式の候補の誤検出**：機械的に拾うと誤検出が多い。原因は、化けた引用符、行内の箇条書き記号（私用領域の文字、76-2 の「―」）、16 進数の表、目次など。

## 7. 残作業（推奨順）

1. **翻訳**：照合済みで未翻訳の約 9,500 ブロック（5.3）。用語集は、組み直したあと「用語 — 定義」の 1 行 1 ブロックになっている。用語は英語のまま残し、定義を訳す。
2. **訳レビュー**：新しく訳した分と、レビュー待ちの約 5,600 ブロック（5.4）。再レビューは最大 2 回まで。
3. **ページの再生成**とテスト（5.5）。平日に行う。
4. **構造の問題が残る約 2,000 ブロック**：5.2 → 5.1 → 5.3 → 5.4 の順に流す。照合の記録がない 346 件も、5.1 で照合にかける。
5. **数式の候補 20 ブロック**：[math-candidates.json](math-candidates.json) にある。142、226、168、182、38d、38f、95、128、78r5。最後の組み直しで一部は LaTeX で書かれているはず。スキルの規則で照合して確定する。
6. **図の説明文**：約 1,000 点。figure ブロックの `html_ja` の `<img alt>` が説明文になる。
7. **未解決の訳 2 件と保留分**：
   - 218 と 218a の表は、原本画像を正としているので後回し。
   - 83 r1 の脚注 18 はページをまたいでいて、組み直しの対象。
   - [unresolved-translations.md](unresolved-translations.md) と [translation-review-issues.json](translation-review-issues.json) も見る。

### 規模の目安（これまでの実績）
| 工程 | 規模 | トークン | 時間（1 並列） |
|---|---|---|---|
| ページ照合 | 約 700 バッチ | 約 2,500 万 | 約 4 時間 |
| 組み直し | 約 580 バッチ | 約 4,300 万 | 約 5 時間 |
| 翻訳 | 約 4,300 ブロック | 約 350 万 | 約 1 時間 |
| 訳レビュー | 約 4,600 ブロック | 約 350 万 | 約 35 分 |

残作業 1〜3 は、合わせて 1,500 万〜2,000 万トークン、7〜9 時間の見込み。

## 8. 関連資料

- [reports/structure-candidates.json](structure-candidates.json)：構造の確認が必要そうだったページの候補
- [reports/math-candidates.json](math-candidates.json)：平文になっている数式の候補
- [reports/official-marks.json](official-marks.json)：掲載しない標章の一覧
- [reports/translation-review-issues.json](translation-review-issues.json)：訳レビューの記録
- [reports/unresolved-translations.md](unresolved-translations.md)：以前の未解決の訳
- [reports/extraction-audit.md](extraction-audit.md)：抽出監査の記録
- [reports/work-in-progress/](work-in-progress/)：ワークフローのスクリプトと補助スクリプト
