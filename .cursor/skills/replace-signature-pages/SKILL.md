---
name: replace-signature-pages
description: >-
  Local, privacy-first contract signature-page workbench for China legal wet-ink
  workflows: locate blank signature pages (optional on-device OCR for scans),
  multi-select candidates, extract signature pages only (Flow C), splice signed
  pages (Flow A), strip signature pages with duplex blank pads (Flow B), or
  batch print packets. Use when the user mentions 签字页, 签署页, 提取签字页,
  抽出签字页, 嵌回签字页, 空白签字页替换, 完整合同电子版, 双面打印,
  去签字页打印, 隔页, 批量, OCR定位, 扫描件签字页, signature page replacement,
  extract signature pages, duplex print packet, or inserting signed pages back
  into a contract PDF. Prefer this skill over generic PDF merge skills for
  signature-page tasks; do not invent one-off merge code.
---

# Replace Signature Pages

本地、隐私优先的**合同签字页作业台**：电子嵌回 + 纸质双面打印隔页 + **仅提取签字页**，专治法务湿签闭环。

不是 DocuSign（云端电子签），也不是通用 PDF merge skill。权威实现永远在本仓库
`tools/replace-signature-pages/`。

## Privacy first (read this)

Unredacted contracts must **not** be processed through the Cursor Agent or chat uploads.

Canonical implementation is a **local-only** tool (no network, no model):

- `tools/replace-signature-pages/` — CLI + GUI + scripts
- Docs: `tools/replace-signature-pages/README.md`

When the user has unredacted PDFs, tell them to run locally:

```bash
.venv/bin/python tools/replace-signature-pages/cli.py
# or
.venv/bin/python tools/replace-signature-pages/gui.py
```

Do **not** `Read` contract PDFs into the conversation. Do **not** paste page text previews. Do **not** use Cloud Agents for this workflow.

Only use the Agent-assisted path below if the user explicitly confirms files are **desensitized / safe for chat**, or they only need help with commands (paths only, no content).

---

## Three flows

| Flow | When | Output |
|------|------|--------|
| **A · 嵌回电子版** | 已有已签签字页 PDF，要嵌回合同 | `<stem>_已嵌签字页.pdf` |
| **B · 双面打印包** | 纸质湿签：先打正文、单独签签字页 | 打印正文（去签字页+隔页）+ 待签署签字页 + 作业说明 |
| **C · 提取签字页** | 只想从合同抽出签字页 PDF（不改正文） | `<stem>_签字页.pdf` + 提取说明 |

Never overwrite the source contract.

## When to use

- Nest signed signature-page PDFs into blank signature slots (Flow A)
- Generate a print packet without signature pages, with duplex collision pads (Flow B)
- Extract signature pages only for signing packets / archive (Flow C)
- Auto-suggest where signature pages are (Chinese/English cues)
- Compare located page count `L` vs signed page count `S` before splicing (Flow A)

Out of scope: batch *creating* signature pages; pasting signature images onto blanks; cloud e-sign APIs; LLM tagging / Party-Signatory grouping ZIP (planned later, local rules only).

## Hard rules

1. **Prefer local CLI/GUI** for real contracts. Agent orchestration is opt-in for sanitized files only.
2. **No splice / print-packet / extract without confirmed page ranges.** If the user has not confirmed pages, only run locate.
3. **Never overwrite** the contract PDF.
4. If `L != S` (Flow A), explain equal-page vs expand-page options; wait for user choice.
5. Multiple signature blocks → map each signed file to a range, then splice in **descending page order**.
6. Prefer `legal-doc-agent/.venv/bin/python` if it exists; else `python3` with `pypdf`.
7. Do **not** invent one-off merge code. Always call scripts under `tools/replace-signature-pages/`.
8. Pass `--redact-preview` on locate when printing JSON into the chat.
9. Generic PDF/OCR skills may help with non-signature PDF ops — **signature-page decisions and privacy rules stay in this skill.**
10. **No LLM** for this skill path. Extraction is pure `pypdf` page copy after human-confirmed ranges.

---

## Workflow A — Splice (sanitized files only)

```
Task Progress:
- [ ] 1. Collect inputs (contract PDF, signed page PDF(s), optional page hints)
- [ ] 2. Locate candidates (unless user already gave exact ranges)
- [ ] 3. Present candidates + L/S comparison; get confirmation
- [ ] 4. Splice with confirmed ranges
- [ ] 5. Report validation (page counts, warnings)
```

### Locate

```bash
.venv/bin/python tools/replace-signature-pages/locate_signature_pages.py \
  --contract "/path/to/contract.pdf" \
  --signed "/path/to/signed_a.pdf" \
  --json --redact-preview \
  --clean-signed-blank-pages
```

Present **page numbers, confidence, signal labels only** — never contract body text.

### Confirm (required)

```
候选 A：第 {start}–{end} 页（置信度 {confidence}）
依据：{signals}

已签页数 S = {signed_page_count}
定位页数 L = {end-start+1}
比对：{comparison.status} — {short advice}

请确认：回复「确认 {start}-{end}」或「改用 …」；多段请写清对应关系。
```

| status | Meaning | Advice |
|--------|---------|--------|
| `match` | L == S | Safe to confirm equal-page replace |
| `contract_fewer` | L < S | Expand replace, or missing blank block |
| `contract_more` | L > S | Narrow range, or missing signed files |
| `no_candidate` | none | Ask user for page numbers |

### Splice

```bash
.venv/bin/python tools/replace-signature-pages/splice_signature_pages.py \
  --contract "/path/to/contract.pdf" \
  --replace 12-13:/path/to/signed.pdf \
  --output "/path/to/contract_已嵌签字页.pdf" \
  --clean-signed-blank-pages
```

Pages are **1-based inclusive**.

---

## Workflow B — Duplex print packet (sanitized files only)

```
Task Progress:
- [ ] 1. Collect contract PDF (+ optional page hints)
- [ ] 2. Locate candidates (unless user already gave exact ranges)
- [ ] 3. Get confirmation of ranges to strip
- [ ] 4. Run prepare_print_packet
- [ ] 5. Report body / signature / blank-pad outputs
```

### Duplex pad rule (flip-on-long-edge, 1-based)

After removing `[start, end]`, pages `start-1` and `end+1` become adjacent.

- If `start-1` is **odd** (sheet front) and `end+1` exists → insert **1 blank** after `start-1`.
- If `start-1` is **even** → no pad needed for collision.

### Command

```bash
.venv/bin/python tools/replace-signature-pages/prepare_print_packet.py \
  --contract "/path/to/contract.pdf" \
  --range 12-13 \
  --output-dir "/path/to/out"
```

Or interactive:

```bash
.venv/bin/python tools/replace-signature-pages/cli.py --mode print-packet
```

Outputs:

- `<stem>_打印正文_去签字页.pdf`
- `<stem>_签字页_待签署.pdf`
- `<stem>_打印作业说明.md` / `.json`

---

## Workflow C — Extract signature pages only (sanitized files only)

Use when the user only needs the signature-page PDF(s) **without** rewriting the body or inserting duplex pads. Contract file is never modified.

```
Task Progress:
- [ ] 1. Collect contract PDF (+ optional page hints)
- [ ] 2. Locate candidates (unless user already gave exact ranges)
- [ ] 3. Get confirmation of ranges to extract
- [ ] 4. Run extract_signature_pages
- [ ] 5. Report page count + output paths
```

### Command

```bash
.venv/bin/python tools/replace-signature-pages/extract_signature_pages.py \
  --contract "/path/to/contract.pdf" \
  --range 12-13 \
  --range 20-21 \
  --output-dir "/path/to/out"
```

Optional `--per-range`: also write one PDF per range (`stem_签字页_12-13.pdf`).

Interactive:

```bash
.venv/bin/python tools/replace-signature-pages/cli.py --mode extract
```

Agent scenario (desensitized only): `signature_extract`

Outputs:

- `<stem>_签字页.pdf`（合并所有确认页，按页码顺序）
- `<stem>_提取说明.md` / `.json`
- 可选：`<stem>_签字页_{range}.pdf`（`--per-range`）

### C vs B

| | C · extract | B · print-packet |
|--|-------------|------------------|
| 签字页 PDF | 是 | 是（命名「待签署」） |
| 去签字页正文 | 否 | 是 |
| 双面隔页 | 否 | 是 |
| 适用 | 单独签/归档/外发签字页 | 双面打正文 + 单独湿签闭环 |

---

## Scripts (canonical)

| Path | Role |
|------|------|
| `tools/replace-signature-pages/cli.py` | Interactive CLI（`--mode splice` / `print-packet` / `extract`） |
| `tools/replace-signature-pages/gui.py` | 本地图形向导（嵌回 / 打印包 / 提取 / 批量打印包） |
| `tools/replace-signature-pages/locate_signature_pages.py` | Read-only locate + L/S JSON |
| `tools/replace-signature-pages/splice_signature_pages.py` | Confirmed page splice（流程 A） |
| `tools/replace-signature-pages/prepare_print_packet.py` | 去签字页 + 双面隔页 + 抽出签字页（流程 B） |
| `tools/replace-signature-pages/extract_signature_pages.py` | 仅提取签字页（流程 C） |
| `tools/replace-signature-pages/batch_cli.py` | 批量流程 B（交互确认或 ranges-file） |
| `tools/replace-signature-pages/page_ocr.py` | 本机 macOS Vision OCR（低文字页） |
| `tools/replace-signature-pages/patterns.json` | CN/EN keyword weights |
| `tools/replace-signature-pages/blank_page_detector.py` | 空白页判定（扫描件按墨迹比例） |

`.cursor/skills/.../scripts/*.py` are forwarders only.

Pattern meanings: see `tools/replace-signature-pages/reference-signature-page-patterns.md`

## Dependency

```bash
python3 -m venv .venv
.venv/bin/pip install pypdf
# GUI thumbnails / ink blank detection:
.venv/bin/pip install pymupdf
```
