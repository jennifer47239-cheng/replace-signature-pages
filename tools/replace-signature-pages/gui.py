#!/usr/bin/env python3
"""Local wizard: Flow A (splice) or Flow B (duplex print packet). No AI.

Apple's system Tk (8.5.9) does not paint Tk-owned widgets on current macOS, so
the UI is built from AppleScript dialogs plus an HTML review page opened in the
browser. Page thumbnails stay in a temp dir that is deleted when the tool exits.
"""

from __future__ import annotations

import html
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

# If dialogs lack this stamp in their title, you are not running this file.
UI_BUILD = "ui-20260803-print-review"


class UserCancelled(Exception):
    """Raised when a dialog is dismissed with Cancel or Esc."""


def _log(text: str, kind: str = "info") -> None:
    print(f"[{kind}] {text}", flush=True)


# --- AppleScript plumbing ---------------------------------------------------


def _as_literal(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _osascript(*lines: str) -> str:
    args: list[str] = ["osascript"]
    for line in lines:
        args += ["-e", line]
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()
        if "-128" in err or "User canceled" in err or "用户取消" in err:
            raise UserCancelled()
        raise RuntimeError(err or f"osascript exited {proc.returncode}")
    return proc.stdout.strip()


def choose_pdf(prompt: str) -> Path:
    out = _osascript(
        f"POSIX path of (choose file with prompt {_as_literal(prompt)} "
        'of type {"com.adobe.pdf"})',
    )
    return Path(out)


def choose_pdfs(prompt: str) -> list[Path]:
    out = _osascript(
        f"set picked to choose file with prompt {_as_literal(prompt)} "
        'of type {"com.adobe.pdf"} with multiple selections allowed',
        'set acc to ""',
        "repeat with f in picked",
        "set acc to acc & POSIX path of f & linefeed",
        "end repeat",
        "return acc",
    )
    return [Path(line) for line in out.splitlines() if line.strip()]


def ask_buttons(text: str, buttons: list[str], default: str, title: str) -> str:
    button_list = ", ".join(_as_literal(b) for b in buttons)
    return _osascript(
        f"button returned of (display dialog {_as_literal(text)} "
        f"with title {_as_literal(title)} buttons {{{button_list}}} "
        f"default button {_as_literal(default)})",
    )


def ask_text(text: str, default_answer: str, title: str) -> str:
    return _osascript(
        f"text returned of (display dialog {_as_literal(text)} "
        f"with title {_as_literal(title)} default answer {_as_literal(default_answer)})",
    )


def choose_from_list(items: list[str], prompt: str, title: str) -> str:
    item_list = ", ".join(_as_literal(i) for i in items)
    out = _osascript(
        f"set chosen to choose from list {{{item_list}}} "
        f"with prompt {_as_literal(prompt)} with title {_as_literal(title)} "
        f"default items {{{_as_literal(items[0])}}}",
        "if chosen is false then error number -128",
        "return item 1 of chosen",
    )
    return out


def ask_save_path(default_name: str, default_dir: Path, prompt: str) -> Path:
    out = _osascript(
        f"POSIX path of (choose file name with prompt {_as_literal(prompt)} "
        f"default name {_as_literal(default_name)} "
        f"default location (POSIX file {_as_literal(str(default_dir))}))",
    )
    path = Path(out)
    return path if path.suffix.lower() == ".pdf" else path.with_suffix(".pdf")


def alert(text: str, title: str = "嵌回签字页") -> None:
    try:
        ask_buttons(text, ["好"], "好", title)
    except Exception:
        _log(text, "err")


# --- Browser review pages ---------------------------------------------------

_PAGE_CSS = """
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin: 0; padding: 32px 40px 64px; background: #F5F5F7; color: #1D1D1F;
  font: 15px/1.6 -apple-system, "PingFang SC", "Helvetica Neue", sans-serif; }
h1 { font-size: 24px; margin: 0 0 4px; }
.build { color: #86868B; font-size: 12px; margin-bottom: 24px; }
.panel { background: #FFF; border-radius: 14px; padding: 20px 24px; margin-bottom: 24px;
  box-shadow: 0 1px 3px rgba(0,0,0,.08); }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 7px 0; border-bottom: 1px solid #F0F0F2;
  vertical-align: top; font-weight: 400; }
th { width: 140px; color: #6E6E73; }
tr:last-child th, tr:last-child td { border-bottom: 0; }
.verdict { border-radius: 10px; padding: 14px 18px; font-weight: 600; margin-bottom: 24px; }
.verdict.ok { background: #E3F6E8; color: #1B5E20; }
.verdict.warn { background: #FFF4E0; color: #8A5200; }
h2 { font-size: 17px; margin: 0 0 14px; }
.hint { color: #6E6E73; font-size: 13px; margin: -8px 0 16px; }
.grid { display: grid; gap: 18px; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); }
.card { margin: 0; background: #FFF; border: 2px solid #E5E5EA; border-radius: 12px;
  overflow: hidden; }
.card img { display: block; width: 100%; background: #FFF; }
.card .missing { padding: 48px 12px; text-align: center; color: #86868B; }
figcaption { padding: 10px 12px; font-size: 13px; display: flex; flex-direction: column; gap: 2px; }
figcaption span { color: #6E6E73; font-size: 12px; }
.card.replace { border-color: #FF3B30; }
.card.replace figcaption { background: #FFF0EF; }
.card.context { border-color: #E5E5EA; opacity: .72; }
.card.insert { border-color: #0071E3; }
.card.insert figcaption { background: #EDF5FF; }
.card.blank { border-style: dashed; border-color: #AEAEB2; opacity: .62; }
.card.blank figcaption { background: #F5F5F7; }
.card.pad { border-style: dashed; border-color: #AF52DE; }
.card.pad figcaption { background: #F8F0FF; }
.card.pad .missing { background: #FAF5FF; color: #6E6E73; }
.seq { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.seq .chip { padding: 8px 12px; border-radius: 8px; background: #F0F0F2; font-size: 13px; }
.seq .chip.remove { background: #FFF0EF; color: #C62828; text-decoration: line-through; }
.seq .chip.pad { background: #F8F0FF; color: #6A1B9A; border: 1px dashed #AF52DE; }
.seq .chip.keep { background: #E3F6E8; color: #1B5E20; }
.seq .arrow { color: #86868B; }
footer { color: #86868B; font-size: 12px; margin-top: 32px; }
"""


def _html_document(title: str, verdict_class: str, verdict: str, body: str, footer: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>{_PAGE_CSS}</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="build">{html.escape(UI_BUILD)} · 本页仅在本机生成，关闭工具后自动删除</div>
<div class="verdict {verdict_class}">{html.escape(verdict)}</div>
{body}
<footer>{html.escape(footer)}</footer>
</body></html>
"""


def _render_page_pngs(pdf: Path, pages: list[int], out_dir: Path, tag: str) -> dict[int, Path]:
    """Rasterise 1-based `pages` of `pdf` into out_dir. Returns page → png path."""
    import fitz

    rendered: dict[int, Path] = {}
    with fitz.open(str(pdf)) as doc:
        for page_no in pages:
            if page_no < 1 or page_no > doc.page_count:
                continue
            png = out_dir / f"{tag}_{page_no:04d}.png"
            doc[page_no - 1].get_pixmap(dpi=72).save(str(png))
            rendered[page_no] = png
    return rendered


def _card(png: Path | None, caption: str, note: str, css_class: str) -> str:
    img = (
        f'<img src="{html.escape(png.name)}" alt="">'
        if png is not None
        else '<div class="missing">无法渲染此页</div>'
    )
    return (
        f'<figure class="card {css_class}">{img}'
        f'<figcaption><strong>{html.escape(caption)}</strong>'
        f'<span>{html.escape(note)}</span></figcaption></figure>'
    )


def build_review_page(
    *,
    review_dir: Path,
    contract: Path,
    contract_pages: int,
    start: int,
    end: int,
    signed_paths: list[Path],
    signed_blank_map: dict[Path, list[int]],
    signed_total: int,
    output: Path | None,
    locate_note: str,
) -> Path:
    """Write review.html (with thumbnails) and return its path."""
    for stale in review_dir.glob("*.png"):
        stale.unlink(missing_ok=True)

    target_pages = list(range(start, end + 1))
    context_pages = [p for p in (start - 1, end + 1) if 1 <= p <= contract_pages]
    contract_pngs = _render_page_pngs(
        contract, sorted(set(target_pages + context_pages)), review_dir, "c",
    )

    contract_cards: list[str] = []
    for page_no in sorted(set(target_pages + context_pages)):
        if page_no in target_pages:
            contract_cards.append(
                _card(contract_pngs.get(page_no), f"第 {page_no} 页", "将被替换", "replace"),
            )
        else:
            contract_cards.append(
                _card(contract_pngs.get(page_no), f"第 {page_no} 页", "上下文，保留不动", "context"),
            )

    import fitz

    signed_cards: list[str] = []
    insert_seq = 0
    for f_idx, sp in enumerate(signed_paths, start=1):
        blanks = set(signed_blank_map.get(sp, []))
        with fitz.open(str(sp)) as doc:
            page_total = doc.page_count
        pngs = _render_page_pngs(sp, list(range(1, page_total + 1)), review_dir, f"s{f_idx}")
        for page_no in range(1, page_total + 1):
            if page_no in blanks:
                signed_cards.append(
                    _card(
                        pngs.get(page_no),
                        f"{sp.name} · 第 {page_no} 页",
                        "判定为空白，不会插入",
                        "blank",
                    ),
                )
                continue
            insert_seq += 1
            signed_cards.append(
                _card(
                    pngs.get(page_no),
                    f"{sp.name} · 第 {page_no} 页",
                    f"将插入，替换后位置：第 {start + insert_seq - 1} 页",
                    "insert",
                ),
            )

    located = end - start + 1
    if located == signed_total:
        verdict_class, verdict = "ok", f"页数一致：待替换 {located} 页 = 已签 {signed_total} 页"
    elif located < signed_total:
        verdict_class, verdict = (
            "warn",
            f"待替换 {located} 页 少于 已签 {signed_total} 页；生成后总页数会增加 "
            f"{signed_total - located} 页",
        )
    else:
        verdict_class, verdict = (
            "warn",
            f"待替换 {located} 页 多于 已签 {signed_total} 页；生成后总页数会减少 "
            f"{located - signed_total} 页",
        )

    blank_total = sum(len(v) for v in signed_blank_map.values())
    rows = [
        ("合同文件", contract.name),
        ("合同总页数", f"{contract_pages} 页"),
        ("待替换页码", f"第 {start}–{end} 页（共 {located} 页）"),
        ("已签文件", "、".join(p.name for p in signed_paths)),
        ("实际插入页数", f"{signed_total} 页"),
        ("空白页检测", f"已签文件中判定为空白并跳过 {blank_total} 页" if blank_total else "未发现空白页"),
        ("输出文件", output.name if output else "下一步选择"),
    ]
    rows_html = "".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in rows
    )

    body = f"""<div class="panel"><table>{rows_html}</table></div>
<div class="panel">
  <h2>合同中将被替换的页</h2>
  <p class="hint">红框为将被替换的空白签字页；灰色为前后相邻页，仅供确认位置，不会改动。</p>
  <div class="grid">{"".join(contract_cards)}</div>
</div>
<div class="panel">
  <h2>将插入的已签签字页</h2>
  <p class="hint">蓝框按插入顺序排列；虚线灰框为判定为空白的页，不会插入。</p>
  <div class="grid">{"".join(signed_cards)}</div>
</div>"""
    review_html = review_dir / "review.html"
    review_html.write_text(
        _html_document("步骤 4 · 核对待替换签字页", verdict_class, verdict, body, locate_note),
        encoding="utf-8",
    )
    return review_html


def build_blank_review_page(
    *,
    review_dir: Path,
    signed_paths: list[Path],
    metrics_map: dict[Path, list[dict]],
    blank_map: dict[Path, list[int]],
) -> Path:
    """Write blank.html showing every signed page and its blank/keep verdict."""
    for stale in review_dir.glob("*.png"):
        stale.unlink(missing_ok=True)

    sections: list[str] = []
    total_pages = 0
    total_blank = 0
    for f_idx, sp in enumerate(signed_paths, start=1):
        metrics = metrics_map.get(sp, [])
        blanks = set(blank_map.get(sp, []))
        total_pages += len(metrics)
        total_blank += len(blanks)
        pngs = _render_page_pngs(
            sp, [m["page"] for m in metrics], review_dir, f"b{f_idx}",
        )
        cards: list[str] = []
        for m in metrics:
            page_no = m["page"]
            ink = "—" if m["ink_ratio"] is None else f"{m['ink_ratio']:.3%}"
            detail = f"墨迹 {ink}｜文字 {m['nonspace_len']} 字"
            if page_no in blanks:
                cards.append(
                    _card(pngs.get(page_no), f"第 {page_no} 页 · 移除", detail, "blank"),
                )
            else:
                cards.append(
                    _card(pngs.get(page_no), f"第 {page_no} 页 · 保留", detail, "insert"),
                )
        blank_text = "、".join(str(p) for p in sorted(blanks)) if blanks else "无"
        sections.append(
            f'<div class="panel"><h2>{html.escape(sp.name)}</h2>'
            f'<p class="hint">共 {len(metrics)} 页；判定为空白：{html.escape(blank_text)}。'
            f"蓝框保留并插入，虚线灰框视为空白不插入。</p>"
            f'<div class="grid">{"".join(cards)}</div></div>',
        )

    keep = total_pages - total_blank
    if total_blank:
        verdict_class = "ok"
        verdict = f"判定为空白 {total_blank} 页，将插入 {keep} 页（共 {total_pages} 页）"
    else:
        verdict_class = "warn"
        verdict = f"未判定出空白页，将插入全部 {total_pages} 页"

    blank_html = review_dir / "blank.html"
    blank_html.write_text(
        _html_document(
            "步骤 2 · 核对空白页判定",
            verdict_class,
            verdict,
            "".join(sections),
            "判定可人工调整：回到对话框选「手动调整」，直接填写要移除的页码。",
        ),
        encoding="utf-8",
    )
    return blank_html


def build_print_packet_review_page(
    *,
    review_dir: Path,
    contract: Path,
    contract_pages: int,
    start: int,
    end: int,
    locate_note: str = "",
) -> Path:
    """Write print-review.html: pages to strip, neighbors, and duplex blank pad."""
    for stale in review_dir.glob("*.png"):
        stale.unlink(missing_ok=True)

    from prepare_print_packet import needs_duplex_pad

    target_pages = list(range(start, end + 1))
    before = start - 1
    after = end + 1
    context_pages = [p for p in (before, after) if 1 <= p <= contract_pages]
    will_pad = needs_duplex_pad(start) and after <= contract_pages

    try:
        contract_pngs = _render_page_pngs(
            contract,
            sorted(set(target_pages + context_pages)),
            review_dir,
            "p",
        )
        render_ok = True
    except Exception as exc:  # noqa: BLE001
        _log(f"缩略图渲染失败（需 pymupdf）：{exc}", "err")
        contract_pngs = {}
        render_ok = False

    contract_cards: list[str] = []
    # Show in reading order: before → removed block → [pad marker] → after
    if before >= 1:
        contract_cards.append(
            _card(
                contract_pngs.get(before),
                f"第 {before} 页",
                "签字页前一页 · 保留在打印正文",
                "context",
            ),
        )
    for page_no in target_pages:
        contract_cards.append(
            _card(
                contract_pngs.get(page_no),
                f"第 {page_no} 页",
                "将从正文去掉 · 抽到「待签署签字页」",
                "replace",
            ),
        )
    if will_pad:
        contract_cards.append(
            _card(
                None,
                "空白隔页",
                f"插在原第 {before} 页之后，避免与第 {after} 页打到同一张纸正反面",
                "pad",
            ),
        )
    if after <= contract_pages:
        contract_cards.append(
            _card(
                contract_pngs.get(after),
                f"第 {after} 页",
                "签字页后一页 · 保留在打印正文",
                "context",
            ),
        )

    # Sequence chips: original junction vs print body
    remove_label = (
        f"第 {start} 页"
        if start == end
        else f"第 {start}–{end} 页"
    )
    orig_chips = []
    if before >= 1:
        orig_chips.append(f'<span class="chip keep">原第 {before} 页</span>')
        orig_chips.append('<span class="arrow">→</span>')
    orig_chips.append(f'<span class="chip remove">{html.escape(remove_label)}（去掉）</span>')
    if after <= contract_pages:
        orig_chips.append('<span class="arrow">→</span>')
        orig_chips.append(f'<span class="chip keep">原第 {after} 页</span>')

    body_chips = []
    if before >= 1:
        side = "正面" if before % 2 == 1 else "背面"
        body_chips.append(f'<span class="chip keep">原第 {before} 页（{side}）</span>')
        body_chips.append('<span class="arrow">→</span>')
    if will_pad:
        body_chips.append(
            f'<span class="chip pad">空白隔页'
            f'（{"背面" if before % 2 == 1 else "正面"}）</span>'
        )
        body_chips.append('<span class="arrow">→</span>')
    if after <= contract_pages:
        # After pad (or if no pad and before even), after starts new sheet front
        if will_pad or before < 1 or before % 2 == 0:
            after_side = "新张正面"
        else:
            after_side = "背面（有碰撞风险，本应已插隔页）"
        body_chips.append(
            f'<span class="chip keep">原第 {after} 页（{after_side}）</span>'
        )

    removed_count = end - start + 1
    if will_pad:
        verdict_class, verdict = (
            "ok",
            f"将去掉签字页 {removed_count} 页，并在原第 {before} 页后插入 1 页空白隔页",
        )
    elif before >= 1 and after <= contract_pages:
        verdict_class, verdict = (
            "ok",
            f"将去掉签字页 {removed_count} 页；接合处无需隔页"
            f"（原第 {before} 页已是偶数背面）",
        )
    else:
        verdict_class, verdict = (
            "ok",
            f"将去掉签字页 {removed_count} 页（位于文件首/尾，无双面接合）",
        )

    if not render_ok:
        verdict_class = "warn"
        verdict += "｜缩略图未生成：请 pip install pymupdf 后重试"

    rows = [
        ("合同文件", contract.name),
        ("合同总页数", f"{contract_pages} 页"),
        ("去掉的签字页", f"第 {start}–{end} 页（共 {removed_count} 页）"),
        ("双面隔页", "是，插入 1 页" if will_pad else "否"),
        (
            "打印正文页数",
            f"{contract_pages - removed_count + (1 if will_pad else 0)} 页"
            f"（原 {contract_pages} − {removed_count}"
            f"{' + 1 隔页' if will_pad else ''}）",
        ),
        ("待签署签字页", f"{removed_count} 页（单独打印）"),
    ]
    rows_html = "".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in rows
    )

    body = f"""<div class="panel"><table>{rows_html}</table></div>
<div class="panel">
  <h2>接合处示意（原合同）</h2>
  <p class="hint">红删除线为将去掉的签字页；绿为保留页。</p>
  <div class="seq">{"".join(orig_chips)}</div>
</div>
<div class="panel">
  <h2>双面打印正文顺序（生成后）</h2>
  <p class="hint">紫虚线为空白隔页，用于把「前一页」与「后一页」拆到不同纸张。</p>
  <div class="seq">{"".join(body_chips) if body_chips else '<span class="chip">（无后续正文接合）</span>'}</div>
</div>
<div class="panel">
  <h2>页缩略图</h2>
  <p class="hint">红框＝去掉并抽到待签署 PDF；灰框＝保留在打印正文；紫虚线＝将插入的空白隔页。</p>
  <div class="grid">{"".join(contract_cards)}</div>
</div>"""

    review_html = review_dir / "print-review.html"
    review_html.write_text(
        _html_document(
            "流程 B · 核对双面打印包",
            verdict_class,
            verdict,
            body,
            locate_note or "确认无误后回到对话框点「确认并生成」。",
        ),
        encoding="utf-8",
    )
    return review_html


# --- Wizard ----------------------------------------------------------------


def parse_range_text(text: str) -> tuple[int, int]:
    from splice_signature_pages import parse_range

    return parse_range(text.replace(" ", "").replace("–", "-").replace("—", "-"))


def review_blank_pages(
    blank_dir: Path,
    signed_paths: list[Path],
    metrics_map: dict[Path, list[dict]],
    blank_map: dict[Path, list[int]],
    title: str,
) -> dict[Path, list[int]]:
    """Show the blank-page verdicts and let the user correct them by page number."""
    from blank_page_detector import parse_page_list

    current = {sp: list(pages) for sp, pages in blank_map.items()}
    while True:
        page = build_blank_review_page(
            review_dir=blank_dir,
            signed_paths=signed_paths,
            metrics_map=metrics_map,
            blank_map=current,
        )
        subprocess.run(["open", str(page)], check=False)
        removed = sum(len(v) for v in current.values())
        total = sum(len(metrics_map[sp]) for sp in signed_paths)
        _log(f"步骤 2 核对：空白判定页已在浏览器打开（移除 {removed} 页）", "ok")

        choice = ask_buttons(
            "步骤 2 核对：浏览器已打开空白页判定结果。\n\n"
            f"共 {total} 页，判定为空白 {removed} 页，将插入 {total - removed} 页。\n\n"
            "判定不对可以手动改。",
            ["手动调整", "取消", "判定正确"],
            "判定正确",
            title,
        )
        if choice == "判定正确":
            return current
        if choice == "取消":
            raise UserCancelled()

        for sp in signed_paths:
            page_total = len(metrics_map[sp])
            existing = ",".join(str(p) for p in current.get(sp, []))
            answer = ask_text(
                f"{sp.name}（共 {page_total} 页）\n\n"
                "填写要当作空白、不插入的页码，例如 3,5 或 2-3。\n"
                "留空表示这份文件全部页都插入。",
                existing,
                title,
            )
            try:
                current[sp] = parse_page_list(answer, max_page=page_total)
            except ValueError as exc:
                alert(f"{sp.name}：{exc}\n本文件判定保持不变。", title)


def run_print_wizard(review_dir: Path) -> int:
    """Flow B: strip signature pages + duplex blank pads + extract sig pages."""
    from locate_signature_pages import DEFAULT_PATTERNS, load_patterns, locate
    from prepare_print_packet import prepare_print_packet
    from pypdf import PdfReader

    title = f"双面打印包 · {UI_BUILD}"
    print_dir = review_dir / "print"
    print_dir.mkdir(parents=True, exist_ok=True)

    contract = choose_pdf("步骤 1：选择合同 PDF（将去掉签字页并生成打印正文）")
    contract_pages = len(PdfReader(str(contract)).pages)
    _log(f"步骤 1 完成：{contract.name}（{contract_pages} 页）", "ok")

    result = locate(contract, [], load_patterns(DEFAULT_PATTERNS))
    candidates = result["candidates"]
    _log(f"步骤 2 完成：{len(candidates)} 个候选", "ok")

    manual_label = "手动输入页码…"
    range_text = ""
    if candidates:
        options = [
            f"{chr(ord('A') + i)}. 第 {c['start']}–{c['end']} 页｜{c['page_count']} 页｜"
            f"置信度 {c['confidence']}"
            for i, c in enumerate(candidates)
        ] + [manual_label]
        picked = choose_from_list(
            options,
            "步骤 2：选择要从正文去掉的签字页区间",
            title,
        )
        if picked != manual_label:
            c = candidates[options.index(picked)]
            range_text = (
                str(c["start"]) if c["start"] == c["end"] else f"{c['start']}-{c['end']}"
            )

    while True:
        if not range_text:
            range_text = ask_text(
                f"步骤 3：填写要去掉的合同签字页页码（1–{contract_pages}）。\n"
                "例如 12 或 12-13。",
                range_text or "",
                title,
            )
        try:
            start, end = parse_range_text(range_text)
        except ValueError as exc:
            alert(f"页码无效：{exc}", title)
            range_text = ""
            continue
        if end > contract_pages:
            alert(f"页码超出范围：合同只有 {contract_pages} 页。", title)
            range_text = ""
            continue

        review_html = build_print_packet_review_page(
            review_dir=print_dir,
            contract=contract,
            contract_pages=contract_pages,
            start=start,
            end=end,
            locate_note=str(result.get("note") or ""),
        )
        subprocess.run(["open", str(review_html)], check=False)
        _log(f"步骤 3：核对页已在浏览器打开（去掉第 {start}–{end} 页）", "ok")

        choice = ask_buttons(
            "步骤 3 核对：浏览器已打开双面打印包核对页（含缩略图与隔页示意）。\n\n"
            f"将去掉：第 {start}–{end} 页（共 {end - start + 1} 页）\n\n"
            "确认无误后生成打印正文 + 待签署签字页 + 作业说明。",
            ["改页码", "取消", "确认并生成"],
            "确认并生成",
            title,
        )
        if choice == "确认并生成":
            break
        if choice == "取消":
            _log("用户在步骤 3 取消", "info")
            return 1
        range_text = ""

    out_dir = contract.parent
    try:
        report = prepare_print_packet(
            contract,
            [(start, end)],
            output_dir=out_dir,
        )
    except SystemExit as exc:
        alert(f"生成失败：{exc}", title)
        return 1
    except Exception as exc:
        alert(f"生成失败：{type(exc).__name__}: {exc}", title)
        return 1

    outs = report["outputs"]
    _log(f"步骤 4 完成：正文 {report['body_page_count']} 页，隔页 {report['blank_pad_count']}", "ok")
    summary = (
        f"已生成打印包\n\n"
        f"正文：{Path(outs['body']).name}\n"
        f"签字页：{Path(outs['signature_pages']).name}\n"
        f"说明：{Path(outs['job_md']).name}\n\n"
        f"原 {report['old_page_count']} 页 → 正文 {report['body_page_count']} 页"
        f"（隔页 {report['blank_pad_count']}）"
        f" + 签字页 {report['signature_page_count']} 页"
    )
    action = ask_buttons(
        summary,
        ["在 Finder 中显示", "完成", "打开作业说明"],
        "打开作业说明",
        title,
    )
    if action == "打开作业说明":
        subprocess.run(["open", str(outs["job_md"])], check=False)
    elif action == "在 Finder 中显示":
        subprocess.run(["open", "-R", str(outs["body"])], check=False)
    return 0


def run_wizard(review_dir: Path) -> int:
    from blank_page_detector import page_metrics
    from locate_signature_pages import DEFAULT_PATTERNS, load_patterns, locate
    from pypdf import PdfReader, PdfWriter
    from splice_signature_pages import default_output_path, splice

    title = f"嵌回签字页 · {UI_BUILD}"
    blank_dir = review_dir / "blank"
    step4_dir = review_dir / "step4"
    blank_dir.mkdir(parents=True, exist_ok=True)
    step4_dir.mkdir(parents=True, exist_ok=True)

    # 1. Contract
    contract = choose_pdf("步骤 1：选择合同 PDF（含待替换的空白签字页）")
    contract_pages = len(PdfReader(str(contract)).pages)
    _log(f"步骤 1 完成：{contract.name}（{contract_pages} 页）", "ok")

    # 2. Signed pages
    signed_paths = choose_pdfs("步骤 2：选择已签字的签字页 PDF（可多选）")
    if not signed_paths:
        alert("没有选择已签字的签字页，流程结束。", title)
        return 1
    clean_blank = ask_buttons(
        f"已选 {len(signed_paths)} 份已签文件。\n\n"
        "双面扫描常会多出空白页。是否自动跳过判定为空白的页？\n"
        "（下一步可以看图核对，并手动改判定）",
        ["保留全部页", "自动跳过空白页"],
        "自动跳过空白页",
        title,
    ) == "自动跳过空白页"

    metrics_map: dict[Path, list[dict]] = {sp: page_metrics(sp) for sp in signed_paths}
    signed_blank_map: dict[Path, list[int]] = {
        sp: ([m["page"] for m in metrics_map[sp] if m["blank"]] if clean_blank else [])
        for sp in signed_paths
    }
    if clean_blank:
        signed_blank_map = review_blank_pages(
            blank_dir, signed_paths, metrics_map, signed_blank_map, title,
        )
    signed_total = sum(
        len(metrics_map[sp]) - len(signed_blank_map.get(sp, [])) for sp in signed_paths
    )
    _log(
        f"步骤 2 完成：{len(signed_paths)} 份，"
        f"移除空白 {sum(len(v) for v in signed_blank_map.values())} 页，"
        f"将插入 {signed_total} 页",
        "ok",
    )

    # 3. Locate
    result = locate(
        contract,
        signed_paths,
        load_patterns(DEFAULT_PATTERNS),
        clean_signed_blank_pages=clean_blank,
    )
    candidates = result["candidates"]
    _log(f"步骤 3 完成：{len(candidates)} 个候选，已签实际 {signed_total} 页", "ok")

    manual_label = "手动输入页码…"
    range_text = ""
    if candidates:
        options = [
            f"{chr(ord('A') + i)}. 第 {c['start']}–{c['end']} 页｜{c['page_count']} 页｜"
            f"置信度 {c['confidence']}"
            for i, c in enumerate(candidates)
        ] + [manual_label]
        picked = choose_from_list(
            options,
            f"步骤 3：选择要被替换的签字页（已签实际 {signed_total} 页）",
            title,
        )
        if picked != manual_label:
            c = candidates[options.index(picked)]
            range_text = (
                str(c["start"]) if c["start"] == c["end"] else f"{c['start']}-{c['end']}"
            )

    # 4. Review, with the option to correct the range and look again
    while True:
        if not range_text:
            range_text = ask_text(
                f"步骤 4：填写要被替换的合同页码（1–{contract_pages}）。\n"
                "例如 12 或 12-13。",
                range_text or "",
                title,
            )
        try:
            start, end = parse_range_text(range_text)
        except ValueError as exc:
            alert(f"页码无效：{exc}", title)
            range_text = ""
            continue
        if end > contract_pages:
            alert(f"页码超出范围：合同只有 {contract_pages} 页。", title)
            range_text = ""
            continue

        review_html = build_review_page(
            review_dir=step4_dir,
            contract=contract,
            contract_pages=contract_pages,
            start=start,
            end=end,
            signed_paths=signed_paths,
            signed_blank_map=signed_blank_map,
            signed_total=signed_total,
            output=None,
            locate_note=str(result.get("note") or ""),
        )
        subprocess.run(["open", str(review_html)], check=False)
        _log(f"步骤 4：核对页已在浏览器打开（第 {start}–{end} 页）", "ok")

        located = end - start + 1
        choice = ask_buttons(
            f"步骤 4 核对：浏览器已打开核对页。\n\n"
            f"将替换：第 {start}–{end} 页（{located} 页）\n"
            f"将插入：{signed_total} 页\n\n"
            "确认无误后继续生成。",
            ["改页码", "取消", "确认并生成"],
            "确认并生成",
            title,
        )
        if choice == "确认并生成":
            break
        if choice == "取消":
            _log("用户在步骤 4 取消", "info")
            return 1
        range_text = ""

    # 5. Output path, splice
    default_out = default_output_path(contract)
    output = ask_save_path(default_out.name, contract.parent, "步骤 5：选择输出位置")

    # The reviewed decision is authoritative: pages dropped here are never
    # re-detected inside splice.
    removed_blank = sum(len(v) for v in signed_blank_map.values())
    if len(signed_paths) > 1:
        merged_tmp = review_dir / "signed_merged.pdf"
        writer = PdfWriter()
        for sp in signed_paths:
            blanks = set(signed_blank_map.get(sp, []))
            for page_no, page in enumerate(PdfReader(str(sp)).pages, start=1):
                if page_no not in blanks:
                    writer.add_page(page)
        with merged_tmp.open("wb") as f:
            writer.write(f)
        signed_for_splice = merged_tmp
        blank_pages_arg = {merged_tmp: []}
    else:
        signed_for_splice = signed_paths[0]
        blank_pages_arg = {signed_for_splice: signed_blank_map.get(signed_for_splice, [])}

    try:
        report = splice(
            contract,
            [(start, end, signed_for_splice)],
            output,
            clean_signed_blank_pages=clean_blank,
            signed_blank_pages=blank_pages_arg,
        )
    except SystemExit as exc:
        alert(f"生成失败：{exc}", title)
        return 1
    except Exception as exc:
        alert(f"生成失败：{type(exc).__name__}: {exc}", title)
        return 1

    warnings = report.get("warnings") or []
    _log(f"步骤 5 完成：{report['output']}", "ok")

    summary = (
        f"已生成：{Path(report['output']).name}\n\n"
        f"页数：{report['old_page_count']} → {report['new_page_count']}\n"
        f"跳过的空白已签页：{removed_blank} 页\n"
        f"提示：{('；'.join(warnings)) if warnings else '无'}"
    )
    action = ask_buttons(summary, ["在 Finder 中显示", "完成", "打开 PDF"], "打开 PDF", title)
    if action == "打开 PDF":
        subprocess.run(["open", str(output)], check=False)
    elif action == "在 Finder 中显示":
        subprocess.run(["open", "-R", str(output)], check=False)
    return 0


def main() -> int:
    print(f"[replace-signature-pages] {UI_BUILD}", flush=True)
    print(f"[replace-signature-pages] loaded from: {Path(__file__).resolve()}", flush=True)

    title = f"签字页作业台 · {UI_BUILD}"
    try:
        mode = ask_buttons(
            "请选择流程：\n\n"
            "嵌回电子版：把已签签字页嵌回合同 PDF。\n"
            "双面打印包：去掉签字页生成打印正文，并在双面碰撞处插入空白隔页。",
            ["取消", "双面打印包", "嵌回电子版"],
            "嵌回电子版",
            title,
        )
    except UserCancelled:
        _log("已取消", "info")
        return 1

    if mode == "取消":
        return 1

    review_dir = Path(tempfile.mkdtemp(prefix="sigpage-review-"))
    try:
        if mode == "双面打印包":
            return run_print_wizard(review_dir)
        return run_wizard(review_dir)
    except UserCancelled:
        _log("已取消", "info")
        return 1
    except Exception as exc:
        _log(f"{type(exc).__name__}: {exc}", "err")
        alert(f"出错了：{type(exc).__name__}: {exc}")
        return 1
    finally:
        shutil.rmtree(review_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
