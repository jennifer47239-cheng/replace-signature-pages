# 贡献指南 · Contributing

感谢关注！这是一个隐私优先的本地工具，贡献时请守住几条底线。

## 隐私红线（不可破）

- **绝不**在 issue / PR / commit / 截图里附带任何真实合同内容或未脱敏页面。
- 复现问题请用虚构样例（如 `tools/replace-signature-pages/examples/tags.example.json`）。
- 不引入联网上传、遥测；分组等核心路径**不接入云端 / LLM**。签署方身份只来自本机确认的标签或本机文本/OCR 候选。

## 开发环境

```bash
python3 -m venv .venv
.venv/bin/pip install pypdf pymupdf pytest
```

## 跑测试

```bash
.venv/bin/python -m pytest tests -q
```

改动定位规则（`patterns.json`）、分组（`export_grouped_packet.py` / `sig_unit.py`）或
标签工作台（`tag_workbench.py`）时，请相应补 / 改 `tests/` 下的用例。

## 提交约定

- 变更记录写入 `tools/replace-signature-pages/CHANGELOG.md`。
- 面向用户的行为变化，请同步更新 `README.md` 与 `tools/replace-signature-pages/README.md`。
- commit message 用一句话说明「为什么」，不只是「改了什么」。

## 分支 / PR

- 从 `main` 切分支，PR 描述里写清动机、影响范围与测试方式。
- 涉及隐私边界的改动请在 PR 里显式说明如何守住本机 / 不上传 / 不调用 LLM。
