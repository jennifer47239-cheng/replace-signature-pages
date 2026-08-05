# Changelog

本文件记录 **嵌回签字页** 工具与对应 Cursor Skill（`replace-signature-pages`）的变更。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

权威实现目录：`tools/replace-signature-pages/`  
Skill 说明：`.cursor/skills/replace-signature-pages/SKILL.md`

---

## [Unreleased]

### Planned

- 非 macOS OCR 后端
- 流程 A 多段各自缩略图核对页（当前以第一段为例 + 列表确认）
- 继续提升签字页定位精确度（更多版式样本）

---

## [0.7.3] - 2026-08-05

标签工作台重做：先整理标签，再按页分配；修好「分组包没分组」。

### Added

- 标签工作台：缩略图点击可放大到整个左半屏（适宽/适高、上一张/下一张、Esc 关闭），
  工作台缩略图渲染提升到 144 DPI
- 标签工作台改为两步：**① 标签库**（先归纳/编辑/确认签署主体等标签）→
  **② 分配页码**（每行选一页 + 从标签库下拉选标签），避免逐行重复打字
- 页码改为下拉：整段（如 `25-31`）+ 该段每一页 + 「自定义…」
- 行内 ◀ ▶ 翻页；选页 / 翻页 / 回车时，左侧缩略图跟随高亮并滚动（放大视图同步换页）
- 「批量加行」：一个标签 × 多页（如 `25,27-28`）一次生成多行
- 缩略图与放大视图的「本页 → 当前行」；「按页拆行」改为每页一行（不再交叉相乘）
- 候选标签区改为固定高度、内部滚动，不再随候选数量铺满屏幕
- 标签库新增「保存标签草稿」：草稿写入本机工作目录，刷新页面自动恢复标签、
  页码分配、当前步骤与选中行；不会上传

### Fixed

- 标签工作台：点表格会整表重绘导致闪烁/点不动 → 改为行选中不销毁 DOM；芯片就地填值
- 全屏时右侧表格不易见 → 改为整窗左右分栏（`100vh` flex），两侧独立滚动
- **分组包「没分组」**：多页区间被 `coalesce_ranges` 合并成一段后，各行共用同一区间，
  每个分组 PDF 都含整段全部页 → 现支持逐页标注，并在保存前提示
  「多个签署主体共用同一多页区间」；保存时校验区间格式

---

## [0.7.2] - 2026-08-05

签署主体不限于投资方：可为融资方（公司）等。

### Changed

- 标签字段：`party`（签署主体）+ 可选 `party_role`（投资方 / 融资方 / 其他）
- 旧字段 `investor` 仍可读可写（兼容）
- 分组目录：`按签署主体/`（原「按投资方」）
- 工作台 / CLI 文案同步

---

## [0.7.1] - 2026-08-05

分组标签体验：一页多方、本机扫描候选、可视化工作台。

### Added

- `suggest_tags.py`：对本机抽出的签字页做规则扫描，给出投资方 / 签字人 / 身份候选（可选 OCR）
- `tag_workbench.py`：localhost HTML 标签工作台
  - 缩略图 + 候选芯片点选
  - **表格多行** = 同一页多个投资方/签字人
  - 「加一行」追加同区间多方
- GUI 分组流程默认进入工作台；CLI 可选打开工作台或编号点选

### Changed

- `UI_BUILD`：`ui-20260805-tag-workbench`
- 不再依赖「每段只填一次」的对话框串（一页多方场景）

---

## [0.7.0] - 2026-08-05

流程 C+：本机标签按 **投资方 / 签字人** 分组打包。层 A（手填/JSON）权威；无 LLM、不上传。

### Added

- `sig_unit.py`：`SigUnit` + `tags.json`（可选 YAML）读写
- `export_grouped_packet.py`：按 `signatory` / `investor` / `both` 导出
  - `按签字人/`、`按投资方/` 目录 + `manifest.json` + `分组说明.md` + ZIP
  - 可选未分组合并签字页；同页多方可多条 unit（range 相同）
- CLI `--mode packet`（`--tags` / 交互填标签 / `--group`）
- GUI「签字页分组包」：标签文件或逐段手填
- `examples/tags.example.json` 示例

### Changed

- Skill / README 同步流程 C+；`UI_BUILD`：`ui-20260805-packet`

---

## [0.6.0] - 2026-08-04

流程 C 仅提取签字页；多选候选可与手填并存；定位规则收紧。全程本机、不调用 LLM。

### Added

- **流程 C · 提取签字页**：`extract_signature_pages.py`
  - 按确认页码拷贝 → `<stem>_签字页.pdf` + 提取说明（md/json）
  - 可选 `--per-range`：按段各写一份 `stem_签字页_8-9.pdf`
  - 不改正文、不插双面隔页（相对流程 B）
- CLI `--mode extract`
- GUI「仅提取签字页」：多选候选 + 缩略图核对
- Agent scenario `signature_extract` / tool `extract_signature_pages`
- `ranges_util.coalesce_ranges`：合并重叠/相邻区间
- Skill / README 同步三流程说明

### Changed

- GUI 启动列表增加流程 C；`UI_BUILD`：`ui-20260804-pick-mix`
- 手动补充项文案改为「额外手动补充页码…（可与上方候选同时勾选）」
- 定位：`甲方/乙方/丙方` 降为 **weak**；密文正文惩罚；合并候选时不以「仅相对方称呼」起块/续块
- 增补中文 strong/medium 信号词（本页为签署页、签字/盖章 等）

### Fixed

- GUI 选页：勾选「手动补充」时**保留**已选 A/B/C 候选，与手填页码合并（先前互斥导致大合同多段签字难选）

---

## [0.5.0] - 2026-08-03

三项增强：GUI 多选候选、扫描件 OCR 定位、批量打印包。

### Added

- **GUI 多选候选**：`choose_from_list_multi`；流程 A/B 可一次勾选多段或手填 `8-9,20-21`
- **流程 B 多段核对页**：各区间缩略图 + 隔页标注
- **OCR 定位**：`page_ocr.py` + `macos_vision_ocr.swift`；`locate --ocr` 仅处理低文字页（本机 Vision）
- **批量**：`batch_cli.py` / `cli.py --batch-dir`；GUI「批量打印包」多选合同；输出 `batch_report.json`
- `--ranges-file` 非交互批量映射
- `ranges_util.py`：多段页码解析与格式化

### Changed

- CLI/GUI 定位可询问或传入 OCR 开关
- Skill / README 同步多选、OCR、批量说明
- GUI 启动流程选择改为 **列表**（嵌回 / 双面打印包 / 批量），`UI_BUILD`：`ui-20260803-multi-ocr-batch`

### Fixed

- **macOS `display dialog` 最多 3 个按钮**：启动菜单原先 4 个按钮触发
  `最多允许使用三个按钮 (-50)`；改为 `choose from list`
- `ask_buttons` 超过 3 个按钮时提前报错，避免笼统的 osascript -50

---

## [0.4.1] - 2026-08-03

流程 B GUI 可视化核对：生成前可看缩略图确认去掉的签字页与双面隔页位置。

### Added

- 流程 B GUI：**浏览器缩略图核对页**（`build_print_packet_review_page`）
  - 红框＝将从正文去掉并抽到「待签署签字页」
  - 灰框＝前后相邻页（保留在打印正文）
  - 紫虚线＝将插入的空白隔页
  - 芯片示意：原合同接合处 vs 双面打印正文顺序
- 向导步骤 3：打开核对页后再「确认并生成 / 改页码」；`UI_BUILD` 更新为 `ui-20260803-print-review`

### Changed

- 流程 B 确认环节由纯文字对话框升级为与流程 A 同级的看图核对

---

## [0.4.0] - 2026-08-03

流程 B：纸质湿签双面打印包（去签字页 + 隔页），形成相对 DocuSign / 通用 PDF skill 的差异化能力。

### Added

- `prepare_print_packet.py`：确认签字页区间后生成
  - `<stem>_打印正文_去签字页.pdf`（去掉签字页；奇数前页接合处插 1 空白隔页）
  - `<stem>_签字页_待签署.pdf`
  - `<stem>_打印作业说明.md` / `.json`
- CLI `--mode splice|print-packet`；GUI 启动时选择「嵌回电子版」或「双面打印包」
- Skill / README 产品叙事：纸电双轨、隐私本机、人在回路；通用 PDF skill 仅作编排层底层能力

### Changed

- CHANGELOG 原「流程 B 尚未实现」项落地为 0.4.0

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
| 0.4.0 | 2026-08-03 | 流程 B 双面打印包（去签字页 + 隔页） |
| 0.4.1 | 2026-08-03 | 流程 B GUI 缩略图核对页 |
| 0.5.0 | 2026-08-03 | 多选/OCR/批量；修 macOS 启动菜单三按钮限制 |
| 0.6.0 | 2026-08-04 | 流程 C 提取；候选+手填并存；定位收紧 |
| 0.7.0 | 2026-08-05 | 按投资方/签字人分组包（本机标签，无 LLM） |
| 0.7.1 | 2026-08-05 | 一页多方 + 扫描候选 + 可视化标签工作台 |
| 0.7.2 | 2026-08-05 | 签署主体含投资方/融资方；角色字段 |
| Unreleased | — | 非 macOS OCR 等 |
