# 嵌回签字页 · 本机工具

把已签签字页 PDF 嵌回合同中的空白签字页位置。**全程本机、无网络、不调用 AI**，适合处理未脱敏合同。

当前版本：**0.2.0** · 变更记录见 [CHANGELOG.md](./CHANGELOG.md)

## 依赖

```bash
# 在仓库根目录
python3 -m venv .venv
.venv/bin/pip install pypdf
```

macOS 自带 Tk，一般可直接开 GUI；若报错再安装 Python 官方包或 `python-tk`。

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

### 简易 GUI

```bash
.venv/bin/python tools/replace-signature-pages/gui.py
```

窗口应按步骤显示按钮：①选择合同 → ②添加已签页 → ③定位候选页 → ④核对页码 → ⑤确认并生成。

若窗口是空白白屏：先关掉该窗口，重新执行上面命令（已修复 macOS 上 ttk 不显示的问题）。仍空白可改用 CLI。

多段分别替换请用 CLI。

### 底层命令（非交互）

```bash
.venv/bin/python tools/replace-signature-pages/locate_signature_pages.py \
  --contract "/path/合同.pdf" --signed "/path/已签.pdf" --json --redact-preview

.venv/bin/python tools/replace-signature-pages/splice_signature_pages.py \
  --contract "/path/合同.pdf" \
  --replace 12-13:/path/已签.pdf \
  --output "/path/合同_已嵌签字页.pdf"
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
