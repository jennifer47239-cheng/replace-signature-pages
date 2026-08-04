#!/usr/bin/env python3
"""Interactive CLI: Flow A (splice) or Flow B (duplex print packet). Local only, no AI."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

from locate_signature_pages import DEFAULT_PATTERNS, load_patterns, locate
from prepare_print_packet import prepare_print_packet
from splice_signature_pages import default_output_path, parse_range, splice

CONFIRM_RE = re.compile(
    r"^(?:确认|confirm)\s+(\d+(?:\s*-\s*\d+)?)$",
    re.IGNORECASE,
)

MODE_SPLICE = "splice"
MODE_PRINT = "print-packet"


def _banner(mode: str) -> None:
    if mode == MODE_PRINT:
        title = "双面打印包 · 去签字页 + 隔页（CLI）"
    else:
        title = "嵌回签字页 · 本机工具（CLI）"
    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f" {title}\n"
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
    if re.fullmatch(r"\d+(?:\s*-\s*\d+)?", line):
        return parse_range(line.replace(" ", ""))
    return None


def _collect_replacements(
    signed: list[Path],
) -> list[tuple[int, int, Path]] | None:
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


def _collect_ranges(*, allow_multiple: bool = True) -> list[tuple[int, int]] | None:
    print(
        "\n请确认要去掉的签字页页码（打印包将从正文中移除这些页）：\n"
        "  · 回复「确认 12-13」或「12-13」\n"
        "  · 多段：确认第一段后可继续添加；直接回车结束\n"
        "  · 回复「q」退出"
    )
    ranges: list[tuple[int, int]] = []
    while True:
        prompt = "> " if not ranges else "  下一段（回车结束）: "
        line = input(prompt).strip()
        if line.lower() in {"q", "quit", "exit", "退出"}:
            return None
        if not line:
            if ranges:
                return ranges
            print("  至少需要一段页码")
            continue
        alt = re.match(r"^(?:改用|use|确认|confirm)\s+(.+)$", line, re.I)
        if alt:
            line = alt.group(1).strip()
        parsed = _parse_confirm(line)
        if parsed is None:
            print("  无法解析。示例：确认 12-13")
            continue
        ranges.append(parsed)
        if not allow_multiple:
            return ranges
        # After first range, empty line ends; another range continues


def _show_locate(
    contract: Path,
    signed: list[Path],
    *,
    show_preview: bool,
    patterns_path: Path,
    clean_blank: bool,
    ocr: bool = False,
) -> dict:
    print("\n正在定位签字页候选（只读）…")
    patterns = load_patterns(patterns_path)
    result = locate(
        contract,
        signed,
        patterns,
        clean_signed_blank_pages=clean_blank,
        ocr=ocr,
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
    return result


def run_splice(
    contract: Path | None,
    signed: list[Path],
    *,
    output: Path | None,
    show_preview: bool,
    patterns_path: Path,
) -> int:
    _banner(MODE_SPLICE)

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

    raw = input(
        "\n疑似空白页（双面扫描回传常见）是否自动移除？(默认 y，输入 n 关闭): "
    ).strip().lower()
    clean_blank = raw in {"", "y", "yes", "是"} if raw != "n" else False

    ocr_raw = input(
        "扫描件/低文字页是否启用本机 OCR 辅助定位？(默认 n，输入 y 开启): "
    ).strip().lower()
    use_ocr = ocr_raw in {"y", "yes", "是"}

    _show_locate(
        contract,
        signed,
        show_preview=show_preview,
        patterns_path=patterns_path,
        clean_blank=clean_blank,
        ocr=use_ocr,
    )

    replacements = _collect_replacements(signed)
    if not replacements:
        print("已取消。")
        return 1

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


def run_print_packet(
    contract: Path | None,
    *,
    output_dir: Path | None,
    show_preview: bool,
    patterns_path: Path,
    ranges: list[tuple[int, int]] | None = None,
    ocr: bool = False,
) -> int:
    _banner(MODE_PRINT)

    if contract is None:
        contract = _prompt_path("合同 PDF 路径")
    elif not contract.is_file():
        print(f"合同不存在: {contract}", file=sys.stderr)
        return 1

    if not patterns_path.is_file():
        print(f"patterns.json 不存在: {patterns_path}", file=sys.stderr)
        return 1

    if ranges is None:
        if not ocr:
            ocr_raw = input(
                "扫描件/低文字页是否启用本机 OCR？(默认 n，输入 y 开启): "
            ).strip().lower()
            ocr = ocr_raw in {"y", "yes", "是"}
        _show_locate(
            contract,
            [],
            show_preview=show_preview,
            patterns_path=patterns_path,
            clean_blank=False,
            ocr=ocr,
        )
        ranges = _collect_ranges()
        if not ranges:
            print("已取消。")
            return 1

    out_dir = output_dir or contract.parent
    print(f"\n输出目录: {out_dir}")
    final = input("最后确认，输入 y 生成打印包，其他键取消: ").strip().lower()
    if final not in {"y", "yes", "是"}:
        print("已取消。")
        return 1

    try:
        report = prepare_print_packet(contract, ranges, output_dir=out_dir)
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("\n完成。")
    outs = report["outputs"]
    print(f"  打印正文: {outs['body']}")
    print(f"  待签署签字页: {outs['signature_pages']}")
    print(f"  作业说明: {outs['job_md']}")
    print(
        f"  页数: 原 {report['old_page_count']} → 正文 {report['body_page_count']}"
        f"（隔页 {report['blank_pad_count']}）"
        f" + 签字页 {report['signature_page_count']}"
    )
    for pad in report.get("blank_pads") or []:
        print(f"  隔页: 原第 {pad['after_source_page']} 页后 → 输出第 {pad['output_page']} 页")
    return 0 if report.get("ok", True) else 2


def _choose_mode_interactive() -> str:
    print(
        "请选择模式：\n"
        "  1) 嵌回电子版（流程 A：已签页嵌回合同）\n"
        "  2) 双面打印包（流程 B：去签字页 + 隔页）\n"
    )
    while True:
        raw = input("输入 1 或 2（默认 1）: ").strip() or "1"
        if raw in {"1", "a", "A", "splice"}:
            return MODE_SPLICE
        if raw in {"2", "b", "B", "print", "print-packet"}:
            return MODE_PRINT
        print("  请输入 1 或 2")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="本机签字页工具：嵌回电子版或生成双面打印包（不经过 AI）",
    )
    parser.add_argument(
        "--mode",
        choices=[MODE_SPLICE, MODE_PRINT],
        default=None,
        help="splice=嵌回电子版；print-packet=双面打印包（省略则交互选择）",
    )
    parser.add_argument("--contract", type=Path, help="合同 PDF（省略则交互输入）")
    parser.add_argument(
        "--signed",
        action="append",
        default=[],
        type=Path,
        help="已签签字页 PDF（流程 A；可重复）",
    )
    parser.add_argument(
        "--range",
        action="append",
        default=[],
        dest="ranges",
        help="确认的签字页范围（流程 B 非交互时可重复传入）",
    )
    parser.add_argument("--output", type=Path, help="流程 A 输出路径")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="流程 B 输出目录（默认与合同同目录）",
    )
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
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="定位时对低文字页启用本机 OCR（macOS Vision）",
    )
    parser.add_argument(
        "--batch-dir",
        type=Path,
        help="批量：合同 PDF 所在文件夹（流程 B；需 --output-dir）",
    )
    parser.add_argument(
        "--ranges-file",
        type=Path,
        help="批量：JSON 文件名→页码列表（有则非交互）",
    )
    args = parser.parse_args()

    if args.batch_dir:
        from batch_cli import _load_ranges_file, run_batch_print

        if not args.output_dir:
            print("批量模式需要 --output-dir", file=sys.stderr)
            return 1
        contracts = sorted(args.batch_dir.glob("*.pdf"))
        if not contracts:
            print(f"目录无 PDF: {args.batch_dir}", file=sys.stderr)
            return 1
        ranges_map = None
        if args.ranges_file:
            try:
                ranges_map = _load_ranges_file(args.ranges_file)
            except Exception as exc:  # noqa: BLE001
                print(f"ranges-file 无效: {exc}", file=sys.stderr)
                return 1
        summary = run_batch_print(
            contracts,
            args.output_dir,
            ocr=args.ocr,
            ranges_map=ranges_map,
            interactive=args.ranges_file is None,
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0 if summary.get("ok", 0) else 2

    mode = args.mode or _choose_mode_interactive()

    if mode == MODE_PRINT:
        ranges: list[tuple[int, int]] | None = None
        if args.ranges:
            try:
                ranges = [parse_range(spec) for spec in args.ranges]
            except ValueError as exc:
                print(str(exc), file=sys.stderr)
                return 1
        return run_print_packet(
            args.contract,
            output_dir=args.output_dir,
            show_preview=args.show_preview,
            patterns_path=args.patterns,
            ranges=ranges,
            ocr=args.ocr,
        )

    return run_splice(
        args.contract,
        args.signed,
        output=args.output,
        show_preview=args.show_preview,
        patterns_path=args.patterns,
    )


if __name__ == "__main__":
    sys.exit(main())
