# Changelog

本文件记录 **嵌回签字页** 工具与对应 Cursor Skill（`replace-signature-pages`）的变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

权威实现目录：`tools/replace-signature-pages/`  
Skill 说明：`.cursor/skills/replace-signature-pages/SKILL.md`

---

## [Unreleased]

### Planned

- 纸质插页 / 双面打印隔页作业单（流程 B，尚未实现）
- 批量多合同处理
- OCR 辅助定位（扫描件无文本层）

---

## [0.2.0] - 2026-07-24

隐私优先重构：未脱敏合同走本机工具，不再依赖 Cursor Agent。

### Added

- 交互式 CLI：`cli.py`（选文件 → 定位候选 → 确认 → 嵌回）
- 简易 GUI：`gui.py`（Tk 文件对话框 + 候选列表 + 确认生成）
- 本机工具 README：`tools/replace-signature-pages/README.md`
- locate 支持 `--redact-preview`：JSON 输出可脱敏，避免正文进入对话

### Changed

- **权威实现**从 `.cursor/skills/.../scripts/` 迁至 `tools/replace-signature-pages/`
- Skill 侧脚本改为 **forwarder**，转发到 `tools/` 下同名脚本
- `SKILL.md` 增加 Privacy first：禁止对未脱敏合同使用 Agent / Cloud / 贴正文预览
- 默认推荐路径改为本机 CLI/GUI；Agent 路径仅限已脱敏文件或仅帮写命令

### Security

- 明确：文件只在本机由 `pypdf` 读写；不经网络、不调用模型
- 未脱敏合同禁止上传聊天、禁止 `Read` 合同 PDF 进对话

---

## [0.1.0] - 2026-07-24

首个可用 MVP：辅助定位 + 人工确认 + 确定性嵌回。

### Added

- Cursor Skill：`replace-signature-pages`（触发词含签字页 / 嵌回 / signature page 等）
- `locate_signature_pages.py`：中英文特征打分，输出候选区间与置信度
- `splice_signature_pages.py`：按确认页码区间做页级替换/插入；禁止覆盖原合同
- `patterns.json`：中英文强/中/弱信号与权重
- `reference-signature-page-patterns.md`：特征说明
- L/S 比对：定位页数 `L` vs 已签页数 `S`（`match` / `contract_fewer` / `contract_more` / `no_candidate`）
- 默认输出命名：`<原名>_已嵌签字页.pdf`
- 多段替换：按页码降序依次 splice，避免页码漂移
- 依赖：`pypdf`（仓库 `.venv`）

### Design decisions

- 定位为**辅助**，嵌回前必须人工确认页码
- Skill 只编排流程，不临场编写 PDF 合并代码
- 不做「在空白页上贴签名图」；只做整页嵌回
- 纸质双面打印方案留待后续，不在本版本范围

---

## Version map

| 版本 | 日期 | 一句话 |
|------|------|--------|
| 0.1.0 | 2026-07-24 | Skill + locate/splice 脚本 MVP |
| 0.2.0 | 2026-07-24 | 迁至 tools/ + CLI/GUI + 隐私优先 |
| Unreleased | — | 打印作业单 / OCR / 批量（规划中） |
