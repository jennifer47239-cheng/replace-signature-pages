---
name: replace-signature-pages
description: >-
  Locates blank signature/signatory pages in contract PDFs and splices signed
  signature-page PDFs into those slots to produce a complete electronic contract.
  Use when the user mentions 签字页, 签署页, 嵌回签字页, 空白签字页替换, 完整合同电子版,
  signature page replacement, locating signature pages, or inserting signed pages
  back into a contract PDF.
---

# Replace Signature Pages

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

Assistive locate + confirmed splice. Never overwrite the source contract.

## When to use

- Nest signed signature-page PDFs into blank signature slots in a full contract PDF
- Auto-suggest where signature pages are (Chinese/English cues)
- Compare located page count `L` vs signed page count `S` before splicing

Out of scope: batch *creating* signature pages; pasting signature images onto blanks; paper duplex print plans (future).

## Hard rules

1. **Prefer local CLI/GUI** for real contracts. Agent orchestration is opt-in for sanitized files only.
2. **No splice without confirmed page ranges.** If the user has not confirmed pages, only run locate.
3. **Never overwrite** the contract PDF. Default output: `<stem>_已嵌签字页.pdf`.
4. If `L != S`, explain equal-page vs expand-page options; wait for user choice.
5. Multiple signature blocks → map each signed file to a range, then splice in **descending page order**.
6. Prefer `law-trainer/.venv/bin/python` if it exists; else `python3` with `pypdf`.
7. Do **not** invent one-off merge code. Always call scripts under `tools/replace-signature-pages/`.
8. Pass `--redact-preview` on locate when printing JSON into the chat.

## Workflow (Agent path — sanitized files only)

```
Task Progress:
- [ ] 1. Collect inputs (contract PDF, signed page PDF(s), optional page hints)
- [ ] 2. Locate candidates (unless user already gave exact ranges)
- [ ] 3. Present candidates + L/S comparison; get confirmation
- [ ] 4. Splice with confirmed ranges
- [ ] 5. Report validation (page counts, warnings)
```

### Step 1 — Inputs

Need:

- Contract PDF path (with blank signature pages)
- One or more signed signature-page PDF paths
- Optional: user-specified ranges like `12-13` or `15`

### Step 2 — Locate (assistive)

From repo root:

```bash
.venv/bin/python tools/replace-signature-pages/locate_signature_pages.py \
  --contract "/path/to/contract.pdf" \
  --signed "/path/to/signed_a.pdf" \
  --signed "/path/to/signed_b.pdf" \
  --json --redact-preview
```

Read JSON: `candidates`, `signed_page_count`, `comparison`.

If `low_text` / empty extract: say OCR/manual pages are needed; do not pretend high confidence.

Present **page numbers, confidence, signal labels only** — never contract body text.

### Step 3 — Confirm (required)

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

Do not run splice until the user confirms.

### Step 4 — Splice

```bash
.venv/bin/python tools/replace-signature-pages/splice_signature_pages.py \
  --contract "/path/to/contract.pdf" \
  --replace 12-13:/path/to/signed.pdf \
  --output "/path/to/contract_已嵌签字页.pdf"
```

Pages are **1-based inclusive**.

### Step 5 — Report

- Output path
- `old_page_count` → `new_page_count`
- Any `warnings`

## Scripts (canonical)

| Path | Role |
|------|------|
| `tools/replace-signature-pages/cli.py` | Interactive local CLI |
| `tools/replace-signature-pages/gui.py` | Simple local GUI |
| `tools/replace-signature-pages/locate_signature_pages.py` | Read-only locate + L/S JSON |
| `tools/replace-signature-pages/splice_signature_pages.py` | Confirmed page splice |
| `tools/replace-signature-pages/patterns.json` | CN/EN keyword weights |

`.cursor/skills/.../scripts/*.py` are forwarders only.

Pattern meanings: see `tools/replace-signature-pages/reference-signature-page-patterns.md`

## Dependency

```bash
python3 -m venv .venv
.venv/bin/pip install pypdf
```
