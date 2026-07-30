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
- 图形向导支持一次替换多个不连续区间（当前需用 CLI）

---

## [0.3.0] - 2026-07-30

修复扫描件空白页判定失效与 macOS 上界面完全不显示两个阻塞问题；并把「空白页判定」与「待替换页」两步都改成看得见图、可人工改判的环节。

### Fixed

- **空白页判定对扫描件完全无效**：扫描页整页是一张图片，`is_blank_page()` 里
  `_count_image_xobjects() > 0` 会直接判为「有内容」，因此双面扫描回传的空白背面
  永远检测不出来（实测扫描件返回空列表）。改为在有 `pymupdf` 时按**渲染后的墨迹
  比例**判定（默认 ≤ 0.2% 视为空白；实测空白背面 0.000%、真实签字页约 0.57%），
  无 `pymupdf` 时回退到原文字/内容流规则。
- **图形界面在 macOS 26 上所有文字与输入框不可见**，步骤 4「核对页码」因此完全
  无法使用。根因是本机只有 Apple 系统 Tk 8.5.9（Python 3.9.6 / macOS 26.5.1）：
  控件均已 mapped、尺寸正常、黑字白底，但 Tk 自绘控件（Label / Entry / Listbox /
  LabelFrame）一律不绘制，连 Toplevel 背景色都不画，仅原生按钮可见。改为不依赖 Tk。
- `locate` 的 L/S 页数统计与 `splice` 的实际移除口径统一，避免比对页数与最终结果不一致。

### Added

- `blank_page_detector.py` 逐页判定报告 CLI：`--pdf` 列出每页文字字数、图像数、
  内容流字节、墨迹比例与判定依据；`--ink-ratio-max` 调阈值、
  `--force-blank` / `--force-keep` 手动改判定、`--clean-to` 写出去掉空白页的新 PDF、
  `--json`。报告只输出数字，不打印页面文字。
- 判定与人工覆盖接口，供 GUI / CLI 共用：`page_metrics()`、`detect_blank_pages()`、
  `measure_ink_ratios()`、`resolve_blank_pages()`、`parse_page_list()`。
- 图形向导步骤 2 **空白页判定核对页**（浏览器）：逐页缩略图 + 墨迹比例 + 文字字数，
  蓝框保留、虚线灰框视为空白；可选「手动调整」按文件填写要当作空白的页码
  （支持 `3,5` 与 `2-3`），改完重新出图，确认后才继续。
- 图形向导步骤 4 **待替换页核对页**（浏览器）：红框为将被替换的合同页、灰色为前后
  相邻页、蓝框为将插入的已签页并标注替换后位置，附页数比对与输出信息；页码不对可
  「改页码」重看。
- `splice()` 新增 `signed_blank_pages` 参数：传入即以该列表为准、不再自动检测，
  确保人工核对结果不被覆盖。

### Changed

- `gui.py` 由 Tk 改为**原生 macOS 向导**：AppleScript 对话框负责选文件、选候选、
  确认与保存，两处核对页在浏览器打开；缩略图只写入临时目录，向导退出时删除。
- 空白页相关默认阈值集中为模块常量（`INK_RATIO_MAX` / `NONSPACE_THRESHOLD` 等），
  CLI 与 GUI 均可覆盖。

### Dependency

- 新增可选依赖 `pymupdf`：用于渲染缩略图与按墨迹比例判定空白页；未安装时向导的
  核对页无法出图，空白页判定退回原规则。

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
| 0.3.0 | 2026-07-30 | 扫描件空白页按墨迹判定 + 原生向导 + 两处人工核对 |
| Unreleased | — | 打印作业单 / OCR / 批量（规划中） |
