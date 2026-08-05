# v0.7.3 — 签字页分组包 + 本机标签工作台

首个对外版本，四流程齐备：**嵌回（A） / 双面打印包（B） / 提取（C） / 分组包（C+）**，全程本机、不上传、不调用大模型。

## 亮点

- **流程 C+ · 签字页分组包**：抽出签字页后，按**签署主体**（可为投资方或融资方）/ **签字人**分包，输出 `按签署主体/`、`按签字人/` 及 ZIP。
- **本机标签工作台**（localhost 网页，两步式）：
  - ① 标签库：先整理 / 确认签署主体、签字人、身份，可点本机扫描候选，也可手填。
  - ② 分配页码：为每一页选一个标签；页码下拉含整段与每一页，行内 ◀ ▶ 翻页，左侧缩略图跟随高亮。
  - 缩略图可放大到左半屏；「批量加行」（一个标签 × 多页）、「按页拆行」（每页一行）；标签可存**本机草稿**，刷新页面自动恢复。
- **修复**：多页区间被合并后各行共用同一区间，导致分组包每份都含整段全部页（看起来「没分组」）——现支持逐页标注并在保存前提示。

## 安装

```bash
python3 -m venv .venv
.venv/bin/pip install pypdf pymupdf
.venv/bin/python tools/replace-signature-pages/gui.py
```

需要 Python 3.9+；macOS 体验最佳（原生对话框 + 系统 OCR）。

## 隐私

所有 PDF 只在本机读写，不联网、不上传、无遥测；分组不调用 LLM。详见 [PRIVACY.md](../PRIVACY.md)。

## 已知限制

- 签字页定位为启发式，生成前请人工核对页码。
- OCR 目前依赖 macOS Vision；非 macOS 需自备 OCR 或仅用文字版 PDF。

完整变更见 [`tools/replace-signature-pages/CHANGELOG.md`](../tools/replace-signature-pages/CHANGELOG.md)。
