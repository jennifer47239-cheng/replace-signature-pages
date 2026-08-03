# replace-signature-pages

本地、隐私优先的**合同签字页作业台**（Cursor Skill + 本机 CLI/GUI）。

| 流程 | 场景 |
|------|------|
| **A · 嵌回电子版** | 已签签字页 PDF 嵌回合同 |
| **B · 双面打印包** | 去签字页打印正文 + 双面碰撞处插空白隔页 + 抽出待签署页（含浏览器缩略图核对） |

权威实现：[`tools/replace-signature-pages/`](tools/replace-signature-pages/)  
Skill：[`.cursor/skills/replace-signature-pages/`](.cursor/skills/replace-signature-pages/)

```bash
python3 -m venv .venv
.venv/bin/pip install pypdf pymupdf

.venv/bin/python tools/replace-signature-pages/cli.py --mode print-packet
# 或
.venv/bin/python tools/replace-signature-pages/gui.py
```

详见 [`tools/replace-signature-pages/README.md`](tools/replace-signature-pages/README.md) 与 [CHANGELOG](tools/replace-signature-pages/CHANGELOG.md)。
