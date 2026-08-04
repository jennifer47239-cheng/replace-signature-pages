# replace-signature-pages

本地、隐私优先的**合同签字页作业台**（Cursor Skill + 本机 CLI/GUI）。

| 流程 | 场景 |
|------|------|
| **A · 嵌回电子版** | 已签页嵌回合同（可多选候选） |
| **B · 双面打印包** | 去签字页 + 双面隔页 + 缩略图核对 |
| **批量** | 多合同逐份确认；可选本机 OCR 定位扫描件 |

当前版本见 [`tools/replace-signature-pages/CHANGELOG.md`](tools/replace-signature-pages/CHANGELOG.md)（**0.5.0**）。

```bash
python3 -m venv .venv
.venv/bin/pip install pypdf pymupdf

.venv/bin/python tools/replace-signature-pages/gui.py
.venv/bin/python tools/replace-signature-pages/cli.py --mode print-packet
.venv/bin/python tools/replace-signature-pages/batch_cli.py --batch-dir ./contracts --output-dir ./out
```

权威实现：[`tools/replace-signature-pages/`](tools/replace-signature-pages/)  
Skill：[`.cursor/skills/replace-signature-pages/`](.cursor/skills/replace-signature-pages/)
