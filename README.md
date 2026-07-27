# 嵌回签字页 · replace-signature-pages

把**已签签字页 PDF**嵌回合同中的**空白签字页**位置，生成可归档的完整合同电子版。

- **本机工具**：全程无网络、不调用 AI，适合未脱敏合同  
- **Cursor Skill**：在 Cursor 里触发同一流程（仅建议用于已脱敏文件）

当前版本：**0.2.0** · 变更记录：[CHANGELOG.md](./tools/replace-signature-pages/CHANGELOG.md)

---

## 快速开始

```bash
cd /path/to/replace-signature-pages
python3 -m venv .venv
.venv/bin/pip install pypdf

# 交互式 CLI（推荐）
.venv/bin/python tools/replace-signature-pages/cli.py

# 或简易 GUI
.venv/bin/python tools/replace-signature-pages/gui.py
```

默认输出：`<原合同名>_已嵌签字页.pdf`（**不覆盖**原件）。

---

## 目录结构

```
replace-signature-pages/
├── tools/replace-signature-pages/     # 权威实现（CLI / GUI / locate / splice）
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
