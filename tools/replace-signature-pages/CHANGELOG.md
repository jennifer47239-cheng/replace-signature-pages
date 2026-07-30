# Changelog

本文件记录 **嵌回签字页** 工具与对应 Cursor Skill（`replace-signature-pages`）的变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

权威实现目录：`tools/replace-signature-pages/`  
Skill 说明：`.cursor/skills/replace-signature-pages/SKILL.md`

---

## [Unreleased]

### Fixed

- 空白页判定对**扫描件无效**：扫描页整页是一张图片，`_count_image_xobjects() > 0`
  会直接判为「有内容」，导致双面扫描的空白背面永远检测不出来。
  改为在可用 `pymupdf` 时按**渲染后的墨迹比例**判定（默认 ≤ 0.2% 视为空白），
  无 `pymupdf` 时回退到原文字/内容流规则。

### Added

- `blank_page_detector.py` 新增逐页判定报告 CLI：`--pdf` 列出每页文字字数、
  图像数、内容流字节、墨迹比例与判定依据；支持 `--ink-ratio-max` 调阈值、
  `--force-blank/--force-keep` 手动改判定、`--clean-to` 写出去空白页的新 PDF、
  `--json`。报告只输出数字，不打印页面文字。
- `page_metrics()` / `detect_blank_pages()` / `resolve_blank_pages()` /
  `parse_page_list()`：供 GUI 与 CLI 共用的判定与人工覆盖接口。
- GUI 步骤 2 新增**空白页判定核对页**：逐页缩略图 + 墨迹比例，可选「手动调整」
  按文件填写要当作空白的页码，改完重新出图；人工结果优先。
- `splice()` 新增 `signed_blank_pages` 参数：传入即以该列表为准，不再自动检测，
  确保人工核对结果不被覆盖。

### Changed

- `gui.py` 改为**原生 macOS 向导**：AppleScript 对话框（选文件 / 选候选 / 确认 / 保存）
  取代 Tk 界面；步骤 4 核对改为浏览器中的可视核对页（页面缩略图、L/S 页数比对、
  空白页检测结果），缩略图写入临时目录并在退出时删除。
  原因：本机为 Apple 系统 Tk 8.5.9（Python 3.9.6 / macOS 26），Tk 自绘控件
  （Label / Entry / Listbox / LabelFrame）完全不绘制，只有原生按钮可见，
  导致步骤 4 及所有文字无法显示。

### Planned

- 纸质插页 / 双面打印隔页作业单（流程 B，尚未实现）
- 批量多合同处理
- OCR 辅助定位（扫描件无文本层）
- 疑似空白已签页自动检测与移除（双面扫描常见），并在 locate/splice 阶段同步 L/S（已实现）
- GUI 上传界面优化：显示页数、已签文件上/下调序、空白页自动移除开关（默认开启）（已实现）

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
