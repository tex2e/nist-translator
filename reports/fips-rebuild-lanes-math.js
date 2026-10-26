export const meta = {
  name: 'rebuild-pages-math',
  description: 'Lay out again the text blocks of PDF pages whose extraction was wrongly divided or ordered',
  phases: [{ title: 'Rebuild' }],
}
// args: { base, counts: [[key, n, skip?]], lanes }
const items = []
for (const [key, n, skip] of args.counts) for (let i = 1; i <= n; i++) if (!(skip || []).includes(i)) items.push([key, i])
const pad = n => String(n).padStart(3, '0')
let next = 0
const out = []
phase('Rebuild')
const lane = async () => {
  while (next < items.length) {
    const [key, n] = items[next++]
    const file = `${args.base}/${key}/rebuild.${pad(n)}.batch.json`
    const r = await agent(
`You are repairing text extracted from PDF pages of a NIST Special Publication for an English–Japanese parallel-text site. ${args.note || ''} An automatic extraction split each page into text blocks, and a checker found that on these pages some blocks are wrongly divided, joined, ordered or classified. Produce the correct list of text blocks for each page, checked against images of the original page.

Input: ${file}
"pages" is a list. Each page has:
- "images": two overlapping PNG files (top and bottom half of the page). Read both with the Read tool. The images are the authority.
- "blocks": the current extracted blocks in the extractor's reading order, each {n, kind, text, checker_note?, runs_on_to_page?}. The wording is usually right (it comes from the PDF text layer) but may have a wrong or missing space, a misread fi/fl/ff ligature, a wrong line-end hyphen, or text from two places mixed together.
- "already_covered_at_top": the ends of paragraphs that started on the previous page and finish at the top of this page. That text is already stored with the previous page: do NOT output it again.
- "already_verified": the beginnings of blocks on this page that are already correct and stored. Do NOT output them again; they only show you what is already covered.
- "checker_missing_text": body text the checker saw on the page but found in no block; include it in the right place if it really is body text.

For each page output the blocks as a reader would read them: column by column (left column top to bottom, then the next column), with full-width headings and banners where they occur. Rules:
- One block per paragraph, heading, list item (one bullet or numbered item, including its wrapped lines), figure caption, footnote, or contact entry (one person: name, phone, e-mail joined with ", "). A run-in bold heading and the paragraph after it are two blocks. Never join text from different columns or unrelated places. Entries of an acronym list or other two-column table of terms: one block per row, as "TERM — definition".
- "kind": "heading", "paragraph", "list_item" (without the bullet glyph; for a numbered item keep the number in "ordinal" and leave it out of the text), "footnote" (start the text with its number), "math" or "code".
- MATHEMATICS. The extraction flattened subscripts and superscripts into separate fragments (e.g. "b x7 + b x6" with "7 6" on another line), split matrices into pieces and mangled brackets. Rebuild every formula from the image as structural LaTeX (KaTeX): subscripts _ , superscripts ^ , \\oplus, \\bullet, \\cdot, \\leftarrow, \\lfloor/\\rfloor, \\bmod or \\mod, \\begin{bmatrix}…\\end{bmatrix} (or pmatrix) for matrices and column vectors, \\{…\\} for braces, \\tilde{b}, \\mathrm{GF}(2^8), \\textsc{SubBytes}() or \\mathrm{SUBBYTES}() for function names in small caps, \\text{…} for words inside a formula. No coordinates, \\raisebox, \\kern, \\phantom, \\mathrlap or \\htmlStyle.
  * A formula displayed on its own line(s) is one block of kind "math" whose text is the LaTeX inside \\[ and \\], with the printed equation number at the right as \\tag{3.1}. Several lines that belong to one display (an aligned derivation, the three equivalent forms of an example) go into one "math" block using \\begin{aligned}…\\end{aligned} (or \\begin{array}).
  * Mathematics inside a sentence stays in the paragraph, written as inline LaTeX inside \\( and \\) (e.g. "the bytes \\(a_j\\) for \\(0 \\le j \\le k-1\\)"). Byte values such as {10100011} or {a3} are written \\(\\{10100011\\}\\) when they are part of mathematics, plain otherwise.
  * Check every subscript, superscript, index and operator against the image, character by character.
- ALGORITHMS (pseudocode boxes such as "Algorithm 1 Pseudocode for CIPHER()"): one block of kind "heading" for the algorithm title line, then one block of kind "code" whose text holds the numbered lines exactly as printed, one printed line per text line separated by "\\n", keeping the line numbers ("1:", "2:"…), keeping indentation with leading spaces (two per level), using Unicode symbols as printed (←, ⊕, ∗, ≤, ▷) and writing comments as "▷ See Sec. 3.4" at the end of the line they belong to. Do not use LaTeX in "code".
- TABLES (e.g. "Table 3. Key-Block-Round Combinations", the S-box tables, tables of test values): one block of kind "table" right after the block holding its caption. Its text holds one table row per text line (separated by "\n"), cells separated by " | " (an empty cell is an empty string between the separators), and "header_rows": the number of leading header rows. Keep every value exactly as printed (hexadecimal digits, spacing inside a value removed). A table may be listed among the input blocks as kind "table" with garbled cells, or as several paragraph blocks; rebuild it from the image either way. Mathematics inside a cell may use inline LaTeX \( … \).
- A drawing, diagram or illustration (e.g. a picture of the state array or of a transformation) is not body text: list its labels as one block with "not_content": true.
- "text": exactly the printed words, in order, joined with single spaces; rejoin a word that is hyphenated only by a line break, keep real hyphens; no words added or dropped. Type what the image shows when the extracted wording is wrong.
- "from": the list of input block numbers "n" whose text this block takes (all of them, even when only a part is used; several output blocks may name the same input block). Empty only for text that is in no input block.
- "not_content": true for running headers, footers, page numbers, the repeated "THIS PUBLICATION IS AVAILABLE FREE OF CHARGE FROM …" line, decorative banner text that only repeats a heading, and stray text that belongs inside a figure, photo or diagram (labels, logo text). Such items are still listed (with their "from"), so that every input block is accounted for.
- "continues_from_previous_page": true only for a first block that is the continuation of a paragraph or list item cut by the page break and NOT listed in "already_covered_at_top".
- An input block with "runs_on_to_page" also holds the end of its paragraph printed on a later page: keep that tail at the end of the block's text unchanged.
- Every input block number must appear in the "from" of at least one output block.

Output: write ${args.base}/${key}/rebuild.${pad(n)}.result.json with the Write tool:
{"pages":[{"page":12,"blocks":[{"kind":"heading","text":"…","from":[1]},{"kind":"list_item","ordinal":null,"text":"…","from":[2,3]}]}]}
Then validate with a short Python script: the JSON parses; every page of the batch is present; each block has a non-empty text and a valid kind; every input n of the page occurs in some "from"; and, as a sanity check, the multiset of words of all output texts of a page differs from the multiset of words of all input texts only where you deliberately corrected something (print the differing words and make sure each one is a correction you intended, a tail kept, or text you deliberately added). Fix and re-validate if not. Do not read *.key.json and do not modify any other file.
Reply with one line per page: page number, number of output blocks.`,
      { label: `rebuild:${key}/${n}`, phase: 'Rebuild', agentType: 'general-purpose' })
    out.push([key, n, r ? String(r).slice(0, 120) : null])
  }
}
await parallel(Array.from({ length: Math.min(args.lanes || 2, items.length) }, () => lane))
return out
