# Signature page patterns (CN / EN)

Used by `patterns.json` and `locate_signature_pages.py`. Assistive only — always confirm page ranges before splicing.

## Strong signals (highest weight)

### Chinese

- Titles: 签字页、签署页、签章页、签字盖章页
- Footer / header: `《…》之签字页`、`之签署页`、`本页无正文`、`以下无正文`、`为签字盖章页`、`为签署页`

### English

- Titles: `SIGNATURE PAGE(S)`, `EXECUTION PAGE(S)`
- Footer: `Signature Page to [Agreement]`
- Closing: `IN WITNESS WHEREOF`

## Medium signals (signature block structure)

### Chinese

- 法定代表人、授权代表、签字、盖章、公章、合同专用章、签署日期、特此为证
- Party labels: 甲方、乙方、丙方 (only boost when combined with other hits)

### English

- `FOR AND ON BEHALF OF`, `Authorized/Authorised Signatory`, `duly authorized`
- `By:` / `Name:` / `Title:`, `Affix Corporate Seal`, `Company Chop` / `Company Seal`
- `Witness`, `executed as a deed`, `signed by`

## Layout / position (computed, not in JSON list)

- Higher blank / whitespace ratio → bonus
- Later pages in the document → small bonus (not “last page only”)
- Adjacent high-scoring pages → merge into one range

## Exclude / downrank

Do not treat as signature pages when *only* these appear:

- Body effectiveness clauses: 自双方盖章之日起生效、本协议自签署之日起生效、`shall become effective upon signing`
- 附件清单、目录、`Table of Contents`

## L vs S check

- `L` = pages in a candidate range
- `S` = total pages of signed PDFs supplied to locate
- `L == S` raises confidence but does **not** prove correctness alone
