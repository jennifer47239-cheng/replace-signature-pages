# replace-signature-pages

本地、隐私优先的**合同签字页作业台**（Cursor Skill + 本机 CLI/GUI）。

| 流程 | 场景 |
|------|------|
| **A · 嵌回电子版** | 已签页嵌回合同（可多选候选） |
| **B · 双面打印包** | 去签字页 + 双面隔页 + 缩略图核对 |
| **C · 提取签字页** | 只抽出签字页 PDF，不改正文 |
| **C+ · 分组包** | 按签署主体（投资方或融资方）/ 签字人分包 |
| **批量** | 多合同逐份确认；可选本机 OCR 定位扫描件 |

当前版本见 [`tools/replace-signature-pages/CHANGELOG.md`](tools/replace-signature-pages/CHANGELOG.md)（**0.7.3**）。

```bash
python3 -m venv .venv
.venv/bin/pip install pypdf pymupdf

.venv/bin/python tools/replace-signature-pages/gui.py
.venv/bin/python tools/replace-signature-pages/cli.py --mode print-packet
.venv/bin/python tools/replace-signature-pages/cli.py --mode packet --contract ./contract.pdf --tags ./tags.json
.venv/bin/python tools/replace-signature-pages/batch_cli.py --batch-dir ./contracts --output-dir ./out
```

流程 C+ 的标签工作台是本机 localhost 页面，分两步：**① 标签库**整理签署主体 / 签字人，
**② 分配页码**给每一页选一个标签。全程不上传、不调用 AI；标签只来自本机手填或本机文本/OCR 候选。

权威实现：[`tools/replace-signature-pages/`](tools/replace-signature-pages/)  
Skill：[`.cursor/skills/replace-signature-pages/`](.cursor/skills/replace-signature-pages/)
