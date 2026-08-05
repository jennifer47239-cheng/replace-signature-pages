# 隐私说明 · Privacy

这是一个**本地、隐私优先**的合同签字页作业工具。设计目标之一就是让**未脱敏合同**也能安全处理。

## 中文

### 数据不出本机

- 所有 PDF 只在**你自己的电脑上**读写，工具不联网、不上传、不回传任何遥测。
- 页面定位、双面隔页、提取、分组、缩略图渲染、OCR 全部在**本机**完成。
- OCR 使用 macOS 系统自带的 Vision 框架（离线），不调用云端 OCR。
- 标签工作台是一个只监听 `127.0.0.1`（localhost）的本机网页，别人无法从网络访问。
- 「保存标签草稿」只写到本机工作目录，不上传。

### 不调用大模型

- 本工具路径**不使用任何 LLM / 云端 AI**。
- 签署主体 / 签字人的分组，只依据你在本机**手动确认的标签**，或本机文本 / OCR 抽取的**候选**（需你确认），不做云端身份识别。

### 与 Cursor Agent / 聊天的边界（重要）

- **不要**把未脱敏合同拖进 Cursor 聊天、让 Agent `Read`、或上传到任何云端 Agent。
- 需要处理真实合同时，请直接运行本机 CLI / GUI（见 README）。
- 只有在文件确认已脱敏、或你只需要命令帮助（仅路径、无内容）时，才使用 Agent 辅助。

### 你仍需注意

- `--show-preview`（CLI）会在终端打印页面文字，涉密时**不要**开启。
- 生成的分组包 / 草稿文件里会包含你填写的真实签署主体名称，请按贵所的保密要求存放与清理。
- 本仓库的示例（`examples/`、文档截图）只使用**虚构**的公司与人名，请勿提交任何真实合同或签字页。

## English

- All PDFs are read and written **only on your machine**. No network calls, no uploads, no telemetry.
- Locating pages, duplex pad insertion, extraction, grouping, thumbnail rendering, and OCR all run **locally**.
- OCR uses the offline macOS Vision framework — no cloud OCR.
- The tag workbench is a local web page bound to `127.0.0.1` (localhost) only.
- **No LLM / cloud AI** is used in this tool path. Grouping relies solely on locally confirmed tags (hand-entered, or local text/OCR candidates you approve).
- Do **not** feed unredacted contracts to the Cursor Agent, chat uploads, or any cloud agent. Run the local CLI/GUI instead.
- `--show-preview` prints page text to the terminal; keep it off for confidential files.
- Generated packets and draft files contain the real party names you typed — store and clean them per your firm's confidentiality policy. All bundled examples use fictional names only.

---

发现隐私相关问题？请开 issue（不要附带任何真实合同内容），或私下联系维护者。
