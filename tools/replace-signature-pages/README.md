# 嵌回签字页 · 本机工具

本地、隐私优先的**合同签字页作业台**（相对 DocuSign / 通用 PDF 工具的差异化）：

| 流程 | 场景 | 产物 |
|------|------|------|
| **A · 嵌回电子版** | 已签签字页 PDF → 嵌回合同 | `<stem>_已嵌签字页.pdf` |
| **B · 双面打印包** | 纸质湿签：打正文、单独签、再物理插页 | 去签字页正文 + 双面隔页 + 待签署签字页 + 作业说明 |
| **C · 提取签字页** | 只要签字页 PDF（不改正文、无隔页） | `<stem>_签字页.pdf` + 提取说明 |

**全程本机、无网络、不调用 AI**，适合处理未脱敏合同。

当前版本：**0.6.0**（流程 C 提取 + 候选与手填并存 + 定位收紧；详见 [CHANGELOG.md](./CHANGELOG.md)）

## 依赖

```bash
# 在仓库根目录
python3 -m venv .venv
.venv/bin/pip install pypdf
```

图形向导还需要 `pymupdf`（用于生成步骤 4 核对页的页面缩略图）：

```bash
.venv/bin/pip install pymupdf
```

向导用 macOS 原生对话框 + 浏览器核对页，**不依赖 Tk**（Apple 系统 Tk 8.5.9 在 macOS 26 上不绘制自绘控件）。

## 用法

### 交互式 CLI（推荐）

```bash
# 仓库根目录 — 交互选择流程 A / B
.venv/bin/python tools/replace-signature-pages/cli.py

# 流程 A：嵌回电子版
.venv/bin/python tools/replace-signature-pages/cli.py --mode splice \
  --contract "/path/合同.pdf" \
  --signed "/path/已签.pdf"

# 流程 B：双面打印包
.venv/bin/python tools/replace-signature-pages/cli.py --mode print-packet \
  --contract "/path/合同.pdf"

# 流程 C：仅提取签字页
.venv/bin/python tools/replace-signature-pages/cli.py --mode extract \
  --contract "/path/合同.pdf" \
  --range 8-9 --range 20-21 \
  --output-dir "/path/out"
```

流程 A：选文件 → 打印候选页码（默认**不**显示正文预览）→ 输入确认 → 嵌回。

流程 B：选合同 → 定位候选 → 确认去掉的签字页 → 生成打印正文（必要时插空白隔页）+ 待签署签字页 + 作业说明。

流程 C：选合同 → 定位候选 → 确认要抽取的页 → 写出签字页 PDF（可选 `--per-range` 按段拆分）+ 提取说明。**不修改合同、不加隔页。**

未脱敏合同时不要加 `--show-preview`。

### 图形向导（原生对话框）

```bash
.venv/bin/python tools/replace-signature-pages/gui.py
```

启动后可选：**嵌回电子版** / **双面打印包** / **仅提取签字页** / **批量打印包**。

- 候选列表支持 **Command 多选**；也可手填 `8-9,20-21`
- 定位前可开 **本机 OCR**（扫描件低文字页）
- 批量：多选多份合同，逐份确认，输出目录含 `batch_report.json`

嵌回流程依次：①选合同 PDF → ②选已签签字页（可多选）+ 空白页判定核对 → ③从定位候选中选择页码 → ④浏览器打开核对页 → ⑤选保存位置并生成。

步骤 2 选择「自动跳过空白页」后，会先在浏览器打开**空白页判定核对页**：每一页都有缩略图、墨迹比例与文字字数，蓝框＝保留插入，虚线灰框＝判定为空白不插入。判定不对就在对话框选「手动调整」，按文件填写要当作空白的页码（如 `3,5` 或 `2-3`，留空表示全部插入）；改完会重新出图，确认后才进入下一步。**手动结果优先于自动判定**，后续步骤不会再重新检测。

步骤 4 的核对页会显示：待替换页与前后相邻页的缩略图（红框＝将被替换）、将插入的已签页（蓝框＝按插入顺序，虚线灰框＝判定为空白不插入）、页数比对与输出信息。核对无误点「确认并生成」；页码不对点「改页码」可重填后再看一次。

缩略图只写入本机临时目录，向导退出时自动删除。

多段分别替换请用 CLI。

### 单独检查空白页判定

扫描件的空白背面本身是一整张图片，只看文字/内容流会把它当成「有内容」。现在改为按**渲染后的墨迹比例**判定，并可单独检查：

```bash
# 逐页列出：文字字数 / 图像数 / 内容流字节 / 墨迹比例 / 判定依据
.venv/bin/python tools/replace-signature-pages/blank_page_detector.py --pdf "/path/已签.pdf"

# 判定太松或太严时调阈值（墨迹比例低于该值算空白，默认 0.002 = 0.2%）
.venv/bin/python tools/replace-signature-pages/blank_page_detector.py \
  --pdf "/path/已签.pdf" --ink-ratio-max 0.005

# 手动改判定，并写出去掉空白页的新 PDF
.venv/bin/python tools/replace-signature-pages/blank_page_detector.py \
  --pdf "/path/已签.pdf" --force-blank 3,5 --force-keep 2 \
  --clean-to "/path/已签_去空白.pdf"
```

报告只输出数字，不打印页面文字。

### 底层命令（非交互）

```bash
.venv/bin/python tools/replace-signature-pages/locate_signature_pages.py \
  --contract "/path/合同.pdf" --signed "/path/已签.pdf" --json --redact-preview \
  --clean-signed-blank-pages

.venv/bin/python tools/replace-signature-pages/splice_signature_pages.py \
  --contract "/path/合同.pdf" \
  --replace 12-13:/path/已签.pdf \
  --output "/path/合同_已嵌签字页.pdf" \
  --clean-signed-blank-pages

# 流程 B：双面打印包
.venv/bin/python tools/replace-signature-pages/cli.py --mode print-packet \
  --contract "/path/合同.pdf" --range 8-9 --range 20-21

# 流程 C：仅提取签字页（合并 PDF；可选 --per-range 按段拆分）
.venv/bin/python tools/replace-signature-pages/extract_signature_pages.py \
  --contract "/path/合同.pdf" --range 8-9 --range 20-21 --output-dir "/path/out"

# 扫描件 OCR 辅助定位
.venv/bin/python tools/replace-signature-pages/locate_signature_pages.py \
  --contract "/path/扫描合同.pdf" --json --redact-preview --ocr

# 批量打印包（交互确认每份；或 --ranges-file 非交互）
.venv/bin/python tools/replace-signature-pages/batch_cli.py \
  --batch-dir "/path/contracts" \
  --output-dir "/path/out" \
  --ocr
```

**双面隔页规则（长边翻转、1-based）**：去掉签字区 `[start,end]` 后，若前一页 `start-1` 为奇数正面且后面还有正文，则在接合处插入 1 页空白，避免「签字页前一页」与「后一页」打到同一张纸正反面。

## 安全说明

| 做法 | 说明 |
|------|------|
| 本工具 CLI / GUI | 文件只在本机读写 |
| Cursor Agent / 聊天上传 | **不要**用于未脱敏合同 |
| `--show-preview` | 会在终端显示页内文字，涉密时关闭 |

永不覆盖原合同；流程 A 默认输出：`<原名>_已嵌签字页.pdf`；流程 C：`<原名>_签字页.pdf`。

## 与 Cursor Skill / 通用 PDF skill 的关系

权威实现在本目录。`.cursor/skills/replace-signature-pages` 仅作说明/转发；处理未脱敏合同时请直接跑本工具，不要让 Agent 编排。

通用 PDF/OCR skill（merge/split/OCR）可作为底层能力由 Agent 编排，但**签字页定位、确认、嵌回、提取、双面隔页与隐私边界**仍归本工具；不要用通用 merge 临场替代本目录脚本。
