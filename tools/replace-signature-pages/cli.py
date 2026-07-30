#!/usr/bin/env python3
"""Interactive CLI: locate signature pages → confirm → splice (local only, no AI)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from locate_signature_pages import DEFAULT_PATTERNS, load_patterns, locate
from splice_signature_pages import default_output_path, parse_range, splice

CONFIRM_RE = re.compile(
    r"^(?:确认|confirm)\s+(\d+(?:\s*-\s*\d+)?)$",
    re.IGNORECASE,
)


def _banner() -> None:
    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        " 嵌回签字页 · 本机工具（CLI）\n"
        " 全程本机 · 无网络上传 · 不调用 AI\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )


def _prompt_path(label: str, *, must_exist: bool = True) -> Path:
    while True:
        raw = input(f"{label}: ").strip().strip("'\"")
        if not raw:
            print("  （路径不能为空）")
            continue
        path = Path(raw).expanduser()
        if must_exist and not path.is_file():
            print(f"  找不到文件: {path}")
            continue
        return path


def _prompt_signed_paths() -> list[Path]:
    paths: list[Path] = []
    print("已签签字页 PDF（可多份；直接回车结束添加）")
    while True:
        n = len(paths) + 1
        raw = input(f"  已签文件 #{n}（回车结束）: ").strip().strip("'\"")
        if not raw:
            if not paths:
                print("  至少需要一份已签 PDF")
                continue
            break
        path = Path(raw).expanduser()
        if not path.is_file():
            print(f"  找不到文件: {path}")
            continue
        paths.append(path)
    return paths


def _format_candidate(i: int, c: dict, *, show_preview: bool) -> str:
    lines = [
        f"候选 {chr(ord('A') + i)}：第 {c['start']}–{c['end']} 页"
        f"（共 {c['page_count']} 页，置信度 {c['confidence']}）",
        f"  依据：{', '.join(c.get('signals') or []) or '（无）'}",
    ]
    if c.get("low_text"):
        lines.append("  注意：部分页几乎无文字，可能需人工核页码")
    if show_preview and c.get("preview"):
        for p in c["preview"][:4]:
            lines.append(f"  预览：{p}")
    return "\n".join(lines)


def _advice_zh(comparison: dict) -> str:
    status = comparison.get("status", "")
    mapping = {
        "match": "L == S，等页替换一致，可确认后嵌回",
        "contract_fewer": "L < S，需扩大替换范围，或检查是否漏定位空白签字页",
        "contract_more": "L > S，需缩小范围，或补充已签 PDF",
        "no_candidate": "未找到候选，请手动输入页码",
        "no_signed": "未提供已签页，无法做 L/S 比对",
    }
    return mapping.get(status, comparison.get("advice", ""))


def _parse_confirm(line: str) -> tuple[int, int] | None:
    line = line.strip()
    m = CONFIRM_RE.match(line)
    if m:
        return parse_range(m.group(1).replace(" ", ""))
    # Bare range also accepted: 12-13 or 12
    if re.fullmatch(r"\d+(?:\s*-\s*\d+)?", line):
        return parse_range(line.replace(" ", ""))
    return None


def _collect_replacements(
    signed: list[Path],
) -> list[tuple[int, int, Path]] | None:
    """Ask user to confirm range(s) and map to signed file(s)."""
    replacements: list[tuple[int, int, Path]] = []

    if len(signed) == 1:
        print(
            "\n请确认要替换的合同页码：\n"
            "  · 回复「确认 12-13」或「12-13」\n"
            "  · 回复「改用 15」等自定义范围\n"
            "  · 回复「q」退出"
        )
        while True:
            line = input("> ").strip()
            if line.lower() in {"q", "quit", "exit", "退出"}:
                return None
            # 「改用 12-13」
            alt = re.match(r"^(?:改用|use)\s+(.+)$", line, re.I)
            if alt:
                line = alt.group(1).strip()
            parsed = _parse_confirm(line)
            if parsed is None:
                print("  无法解析。示例：确认 12-13")
                continue
            start, end = parsed
            replacements.append((start, end, signed[0]))
            return replacements

    # Multiple signed files: map each
    print(
        f"\n共 {len(signed)} 份已签 PDF，请为每一份指定合同中的替换页码"
        "（示例：12-13；输入 q 退出）"
    )
    for path in signed:
        print(f"\n→ {path.name}")
        while True:
            line = input("  页码范围: ").strip()
            if line.lower() in {"q", "quit", "exit", "退出"}:
                return None
            alt = re.match(r"^(?:确认|confirm|改用|use)\s+(.+)$", line, re.I)
            if alt:
                line = alt.group(1).strip()
            try:
                start, end = parse_range(line.replace(" ", ""))
            except ValueError:
                print("  格式示例：12 或 12-13")
                continue
            replacements.append((start, end, path))
            break
    return replacements


def run_interactive(
    contract: Path | None,
    signed: list[Path],
    *,
    output: Path | None,
    show_preview: bool,
    patterns_path: Path,
) -> int:
    _banner()

    if contract is None:
        contract = _prompt_path("合同 PDF 路径")
    elif not contract.is_file():
        print(f"合同不存在: {contract}", file=sys.stderr)
        return 1

    if not signed:
        signed = _prompt_signed_paths()
    else:
        for s in signed:
            if not s.is_file():
                print(f"已签 PDF 不存在: {s}", file=sys.stderr)
                return 1

    if not patterns_path.is_file():
        print(f"patterns.json 不存在: {patterns_path}", file=sys.stderr)
        return 1

    clean_blank_default = "y"
    raw = input(
        "\n疑似空白页（双面扫描回传常见）是否自动移除？(默认 y，输入 n 关闭): "
    ).strip().lower()
    clean_blank = raw in {"", "y", "yes", "是"} if raw != "n" else False

    print("\n正在定位签字页候选（只读）…")
    patterns = load_patterns(patterns_path)
    result = locate(
        contract,
        signed,
        patterns,
        clean_signed_blank_pages=clean_blank,
    )
    if not show_preview:
        for c in result["candidates"]:
            c["preview"] = []

    candidates = result["candidates"]
    comparison = result["comparison"]
    s_count = result["signed_page_count"]

    print(f"\n合同共 {result['total_pages']} 页｜已签页数 S = {s_count}")
    if not candidates:
        print("未找到自动候选。你仍可手动输入页码继续。")
    else:
        print()
        for i, c in enumerate(candidates[:8]):
            print(_format_candidate(i, c, show_preview=show_preview))
            print()
    print(f"比对：{comparison.get('status')} — {_advice_zh(comparison)}")

    replacements = _collect_replacements(signed)
    if not replacements:
        print("已取消。")
        return 1

    # Overlap check
    spans = sorted((s, e) for s, e, _ in replacements)
    for i in range(len(spans) - 1):
        if spans[i][1] >= spans[i + 1][0]:
            print(
                f"页码范围重叠，已中止: {spans[i][0]}-{spans[i][1]} "
                f"与 {spans[i + 1][0]}-{spans[i + 1][1]}",
                file=sys.stderr,
            )
            return 1

    out = output or default_output_path(contract)
    print(f"\n即将写入: {out}")
    final = input("最后确认，输入 y 执行嵌回，其他键取消: ").strip().lower()
    if final not in {"y", "yes", "是"}:
        print("已取消。")
        return 1

    try:
        report = splice(
            contract,
            replacements,
            out,
            clean_signed_blank_pages=clean_blank,
        )
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("\n完成。")
    print(f"  输出: {report['output']}")
    print(f"  页数: {report['old_page_count']} → {report['new_page_count']}")
    for op in report.get("operations", []):
        print(
            f"  替换 {op['range']}: 移除 {op['removed_pages']} / "
            f"插入 {op['inserted_pages']}（{op['mode']}）"
        )
    if report.get("warnings"):
        print("\n警告:")
        for w in report["warnings"]:
            print(f"  - {w}")
    return 0 if report.get("ok", True) else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description="本机交互式嵌回签字页（不经过 AI）",
    )
    parser.add_argument("--contract", type=Path, help="合同 PDF（省略则交互输入）")
    parser.add_argument(
        "--signed",
        action="append",
        default=[],
        type=Path,
        help="已签签字页 PDF（可重复；省略则交互输入）",
    )
    parser.add_argument("--output", type=Path, help="输出路径")
    parser.add_argument(
        "--show-preview",
        action="store_true",
        help="显示页内文字预览（未脱敏合同时不建议开启）",
    )
    parser.add_argument(
        "--patterns",
        type=Path,
        default=DEFAULT_PATTERNS,
        help="patterns.json 路径",
    )
    args = parser.parse_args()
    return run_interactive(
        args.contract,
        args.signed,
        output=args.output,
        show_preview=args.show_preview,
        patterns_path=args.patterns,
    )


if __name__ == "__main__":
    sys.exit(main())
