# replace-signature-pages · 合同签字页作业台

> 本地、隐私优先的合同**签字页**处理工具，专治中国法务 / 投融资交易里的**湿签闭环**。
> 全程在本机运行：**不联网、不上传、不调用大模型**，未脱敏合同也能放心处理。

这不是电子签（不是 DocuSign），也不是通用 PDF 合并工具。它只解决一件事，并把它做细：**合同里的签字页**——找到它们、抽出来、按签署方分包、纸质湿签后再嵌回或按双面打印规则去掉。

以 [Cursor](https://cursor.com) Skill 形式提供（律师用自然语言触发），真正干活的是本机 CLI / GUI，可脱离 Cursor 独立运行。

## 为什么做这个

律所和投融资交易里，签字页的琐事真实又高频：

- 一份融资协议几十上百页，签字页散落在多处，要**逐一定位**。
- 纸质湿签要先打正文、单独打签字页去签，双面打印还得防止**签字页和正文印在同一张纸正反面**。
- 多个投资方 / 融资方各签各的页，签完要**按签署主体分包**归档。
- 签完的扫描件要**嵌回**电子版合同，空白背面别混进去。

这些都能用 PDF 工具手动做，但慢、易错，而且——**合同大多不能上传到云端**。这个工具把上面四类活儿固化成可复用流程，且数据不出本机。

## 四个流程

| 流程 | 场景 | 产物 |
|------|------|------|
| **A · 嵌回电子版** | 已签签字页 PDF → 嵌回原合同 | `<原名>_已嵌签字页.pdf` |
| **B · 双面打印包** | 纸质湿签：打正文、单独签、再物理插页 | 去签字页正文 + 双面隔页 + 待签署签字页 + 作业说明 |
| **C · 提取签字页** | 只要签字页 PDF（不改正文、无隔页） | `<原名>_签字页.pdf` + 提取说明 |
| **C+ · 分组包** | 抽出后按**签署主体 / 签字人**分包 | `*_签字页分组包/`（按签署主体 + 按签字人）+ ZIP |

还支持**批量**（多份合同逐份确认）和**本机 OCR**（扫描件低文字页辅助定位）。

## 一分钟上手

需要本机 Python 3.9+；macOS 体验最佳（原生对话框 + 系统 OCR）。

```bash
git clone https://github.com/jennifer47239-cheng/replace-signature-pages.git
cd replace-signature-pages

python3 -m venv .venv
.venv/bin/pip install pypdf pymupdf   # pymupdf 用于缩略图核对页

# 图形向导（推荐，原生对话框 + 浏览器核对页）
.venv/bin/python tools/replace-signature-pages/gui.py

# 或交互式 CLI
.venv/bin/python tools/replace-signature-pages/cli.py
```

常用命令：

```bash
# 流程 B：双面打印包
.venv/bin/python tools/replace-signature-pages/cli.py --mode print-packet --contract ./contract.pdf

# 流程 C：仅提取签字页
.venv/bin/python tools/replace-signature-pages/cli.py --mode extract --contract ./contract.pdf --range 8-9 --range 20-21

# 流程 C+：按签署主体 / 签字人分组（标签来自本机确认）
.venv/bin/python tools/replace-signature-pages/cli.py --mode packet \
  --contract ./contract.pdf \
  --tags tools/replace-signature-pages/examples/tags.example.json

# 批量
.venv/bin/python tools/replace-signature-pages/batch_cli.py --batch-dir ./contracts --output-dir ./out
```

流程 C+ 的**标签工作台**是本机 localhost 页面，分两步：**① 标签库**先把签署主体（可为投资方或融资方）/ 签字人整理确认好；**② 分配页码**给每一页选一个标签。缩略图可放大到左半屏，当前行对应页会高亮；行多时可「批量加行」或「按页拆行」；标签可存草稿，刷新页面自动恢复。

完整参数、双面隔页规则、空白页判定、底层非交互命令见
[`tools/replace-signature-pages/README.md`](tools/replace-signature-pages/README.md)。

## 隐私红线（务必先读）

- 所有 PDF 只在本机读写；**不联网、不上传、无遥测**。
- 分组**不调用大模型**，只依据本机确认的标签或本机文本/OCR 候选。
- **不要**把未脱敏合同拖进 Cursor 聊天或交给云端 Agent，直接跑本机 CLI/GUI。
- `--show-preview` 会在终端打印页面文字，涉密时关闭。

详见 [PRIVACY.md](PRIVACY.md)。

## 已知限制

- **签字页定位是启发式的**，不同版式可能漏判 / 误判——生成前请人工核对页码（工具默认要求确认）。
- **OCR 目前依赖 macOS Vision**；非 macOS 需自行提供 OCR，或只用文字版 PDF。
- GUI 用 macOS 原生对话框；Windows / Linux 建议用 CLI。
- 页码需要人工确认，不追求「全自动」。

## 依赖

- [`pypdf`](https://pypi.org/project/pypdf/) — PDF 读写（必需）
- [`pymupdf`](https://pypi.org/project/PyMuPDF/) — 缩略图核对页 / 渲染（GUI 与部分核对页需要）

## 项目结构

```
tools/replace-signature-pages/    # 权威实现（CLI / GUI / 脚本）
  ├─ cli.py  gui.py  batch_cli.py
  ├─ locate_/splice_/prepare_/extract_signature_pages.py
  ├─ sig_unit.py  suggest_tags.py  export_grouped_packet.py  tag_workbench.py
  ├─ examples/tags.example.json   # 虚构样例标签
  └─ README.md  CHANGELOG.md
.cursor/skills/replace-signature-pages/   # Cursor Skill 说明（触发词 + 隐私硬规则）
```

## 版本

当前 **0.7.3**，变更记录见
[`tools/replace-signature-pages/CHANGELOG.md`](tools/replace-signature-pages/CHANGELOG.md)。

## 贡献 & 反馈

欢迎 issue / PR。请**不要**在 issue、PR 或截图里附带任何真实合同内容——用虚构样例复现即可。

## 许可

[MIT](LICENSE)
