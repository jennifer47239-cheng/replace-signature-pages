# 嵌回签字页 · 本机工具

把已签签字页 PDF 嵌回合同中的空白签字页位置。**全程本机、无网络、不调用 AI**，适合处理未脱敏合同。

当前版本：**0.2.0**（已新增疑似空白已签页清理能力，详见 [CHANGELOG.md](./CHANGELOG.md)）

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
# 仓库根目录
.venv/bin/python tools/replace-signature-pages/cli.py

# 或带参数
.venv/bin/python tools/replace-signature-pages/cli.py \
  --contract "/path/合同.pdf" \
  --signed "/path/已签.pdf"
```

流程：选文件 → 打印候选页码（默认**不**显示正文预览）→ 输入确认 → 嵌回。

未脱敏合同时不要加 `--show-preview`。

### 图形向导（原生对话框）

```bash
.venv/bin/python tools/replace-signature-pages/gui.py
```

依次弹出五步：①选合同 PDF → ②选已签签字页（可多选）+ 空白页判定核对 → ③从定位候选中选择页码 → ④浏览器打开核对页 → ⑤选保存位置并生成。

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
```

## 安全说明

| 做法 | 说明 |
|------|------|
| 本工具 CLI / GUI | 文件只在本机读写 |
| Cursor Agent / 聊天上传 | **不要**用于未脱敏合同 |
| `--show-preview` | 会在终端显示页内文字，涉密时关闭 |

永不覆盖原合同；默认输出：`<原名>_已嵌签字页.pdf`。

## 与 Cursor Skill 的关系

权威实现在本目录。`.cursor/skills/replace-signature-pages` 仅作说明/转发；处理未脱敏合同时请直接跑本工具，不要让 Agent 编排。
