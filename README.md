# 嵌回签字页 · replace-signature-pages

把**已签签字页 PDF**嵌回合同中的**空白签字页**位置，生成可归档的完整合同电子版。

- **本机工具**：全程无网络、不调用 AI，适合未脱敏合同  
- **Cursor Skill**：在 Cursor 里触发同一流程（仅建议用于已脱敏文件）

变更记录：[CHANGELOG.md](./tools/replace-signature-pages/CHANGELOG.md)

---

## 快速开始

```bash
cd /path/to/replace-signature-pages
python3 -m venv .venv
.venv/bin/pip install pypdf pymupdf

# 图形向导（macOS 原生对话框 + 浏览器核对页）
.venv/bin/python tools/replace-signature-pages/gui.py

# 或交互式 CLI（纯终端）
.venv/bin/python tools/replace-signature-pages/cli.py
```

`pymupdf` 用于生成核对页缩略图、并按墨迹比例判定扫描件的空白页；缺少它时仍可运行，但空白页判定会退回文字/内容流规则。

默认输出：`<原合同名>_已嵌签字页.pdf`（**不覆盖**原件）。

---

## 流程

图形向导五步：①选合同 PDF → ②选已签签字页 + **空白页判定核对** → ③从定位候选中选页码 → ④**浏览器核对待替换页** → ⑤选保存位置并生成。

两处核对页都在浏览器里出图，可以看清每一页再决定：

- **空白页核对**：逐页缩略图 + 墨迹比例，蓝框＝保留插入，虚线灰框＝判定为空白不插入；判定不对可「手动调整」按页码改，人工结果优先于自动判定。
- **待替换页核对**：红框＝合同中将被替换的页，灰色＝前后相邻页（仅供确认位置），蓝框＝将插入的已签页，并给出页数比对。

单独检查某个 PDF 的空白页判定：

```bash
.venv/bin/python tools/replace-signature-pages/blank_page_detector.py --pdf "/path/已签.pdf"
```

报告只输出数字（文字字数 / 图像数 / 内容流字节 / 墨迹比例 / 判定依据），不打印页面文字。

---

## 目录结构

```
replace-signature-pages/
├── tools/replace-signature-pages/     # 权威实现
│   ├── gui.py                         # 图形向导（原生对话框 + 浏览器核对页）
│   ├── cli.py                         # 交互式终端流程
│   ├── locate_signature_pages.py      # 只读定位候选签字页
│   ├── splice_signature_pages.py      # 按确认页码嵌回
│   ├── blank_page_detector.py         # 空白页判定 + 逐页报告 + 人工覆盖
│   ├── CHANGELOG.md
│   └── README.md
└── .cursor/skills/replace-signature-pages/   # Cursor Skill 说明 + 脚本转发
    └── SKILL.md
```

在 Cursor 中打开本仓库后，Skill 会随项目加载。处理未脱敏合同时请直接跑本机 CLI/GUI，不要把 PDF 上传到聊天。

---

## 安全

| 做法 | 说明 |
|------|------|
| 本机 CLI / GUI | 文件只在本机读写 |
| Cursor Agent / 聊天上传 | **不要**用于未脱敏合同 |
| Git | 本仓库已忽略 `*.pdf`，切勿提交合同 |

---

## License

Private personal tool. Not licensed for redistribution unless you change this.
