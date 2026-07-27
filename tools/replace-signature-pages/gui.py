#!/usr/bin/env python3
"""Simple local GUI: pick PDFs → review candidates → confirm splice (no AI)."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

TOOL_DIR = Path(__file__).resolve().parent
if str(TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(TOOL_DIR))

BG = "#EEEEEE"
FG = "#111111"
BTN_BG = "#DDDDDD"
ACCENT_BG = "#1F4B7A"
ACCENT_FG = "#FFFFFF"
LIST_BG = "#FFFFFF"
OK_BG = "#E6F4EA"
WARN_BG = "#FFF3CD"
ERR_BG = "#F8D7DA"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("嵌回签字页 · 本机工具")
        self.minsize(720, 640)
        self.geometry("780x680")
        self.configure(bg=BG)

        self.contract_path: Path | None = None
        self.signed_paths: list[Path] = []
        self.candidates: list[dict] = []

        self._build()
        self.lift()
        self.focus_force()

    def _button(self, parent, text, command, *, accent=False) -> tk.Button:
        if accent:
            return tk.Button(
                parent,
                text=text,
                command=command,
                bg=ACCENT_BG,
                fg=ACCENT_FG,
                activebackground="#163A5F",
                activeforeground=ACCENT_FG,
                relief="raised",
                padx=12,
                pady=6,
                font=("", 12, "bold"),
            )
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg=BTN_BG,
            fg=FG,
            activebackground="#CCCCCC",
            relief="raised",
            padx=10,
            pady=4,
            font=("", 12),
        )

    def _set_banner(self, text: str, kind: str = "info") -> None:
        colors = {
            "info": (WARN_BG, FG),
            "ok": (OK_BG, "#0B6B2F"),
            "err": (ERR_BG, "#8B1E1E"),
        }
        bg, fg = colors.get(kind, colors["info"])
        self.banner.configure(text=text, bg=bg, fg=fg)
        self.configure(bg=BG)
        print(f"[{kind}] {text}", flush=True)

    def _alert(self, title: str, text: str) -> None:
        self._set_banner(f"❌ {title}：{text}", "err")
        try:
            messagebox.showerror(title, text, parent=self)
        except Exception:
            pass

    def _build(self) -> None:
        pad = 12

        self.banner = tk.Label(
            self,
            text="请先点 ① 选合同，再点 ② 添加已签页，最后才点 ③ 定位",
            bg=WARN_BG,
            fg=FG,
            font=("", 13, "bold"),
            wraplength=740,
            justify="left",
            anchor="w",
            padx=10,
            pady=10,
        )
        self.banner.pack(fill="x", padx=pad, pady=(12, 8))

        # --- ① contract ---
        f1 = tk.LabelFrame(self, text="① 合同 PDF", bg=BG, fg=FG, padx=8, pady=6)
        f1.pack(fill="x", padx=pad, pady=4)
        self._button(f1, "选择合同 PDF…", self._pick_contract).pack(anchor="w")
        self.contract_var = tk.StringVar(value="尚未选择")
        tk.Label(
            f1, textvariable=self.contract_var, bg=BG, fg=FG, wraplength=700, anchor="w"
        ).pack(fill="x", pady=(4, 0))

        # --- ② signed ---
        f2 = tk.LabelFrame(self, text="② 已签签字页", bg=BG, fg=FG, padx=8, pady=6)
        f2.pack(fill="x", padx=pad, pady=4)
        row = tk.Frame(f2, bg=BG)
        row.pack(fill="x")
        self._button(row, "添加已签签字页…", self._add_signed).pack(side="left")
        self._button(row, "清空", self._clear_signed).pack(side="left", padx=8)
        self.signed_list = tk.Listbox(
            f2,
            height=3,
            bg=LIST_BG,
            fg=FG,
            relief="solid",
            borderwidth=1,
            exportselection=False,
            font=("", 12),
        )
        self.signed_list.pack(fill="x", pady=(6, 0))
        self.signed_list.insert(tk.END, "（这里会出现已选文件名）")

        # --- ③ locate ---
        f3 = tk.LabelFrame(self, text="③ 定位候选页", bg=BG, fg=FG, padx=8, pady=6)
        f3.pack(fill="both", expand=True, padx=pad, pady=4)
        self._button(f3, "定位候选页", self._run_locate).pack(anchor="w")
        self.cmp_var = tk.StringVar(value="")
        tk.Label(
            f3, textvariable=self.cmp_var, bg=BG, fg=FG, wraplength=700, anchor="w"
        ).pack(fill="x", pady=(4, 0))
        self.cand_list = tk.Listbox(
            f3,
            height=6,
            bg=LIST_BG,
            fg=FG,
            relief="solid",
            borderwidth=1,
            exportselection=False,
            font=("", 12),
        )
        self.cand_list.pack(fill="both", expand=True, pady=(6, 0))
        self.cand_list.insert(tk.END, "（定位成功后，候选页码会出现在这里）")
        self.cand_list.bind("<<ListboxSelect>>", self._on_cand_select)

        # --- ④ range + output ---
        f4 = tk.LabelFrame(self, text="④ 页码与输出", bg=BG, fg=FG, padx=8, pady=6)
        f4.pack(fill="x", padx=pad, pady=4)
        r = tk.Frame(f4, bg=BG)
        r.pack(fill="x")
        tk.Label(r, text="替换页码:", bg=BG, fg=FG).pack(side="left")
        self.range_var = tk.StringVar()
        tk.Entry(
            r, textvariable=self.range_var, width=16, bg=LIST_BG, fg=FG, font=("", 12)
        ).pack(side="left", padx=8)
        tk.Label(r, text="例如 12 或 12-13", bg=BG, fg="#555555").pack(side="left")

        r2 = tk.Frame(f4, bg=BG)
        r2.pack(fill="x", pady=(6, 0))
        tk.Label(r2, text="输出:", bg=BG, fg=FG).pack(side="left")
        self.output_var = tk.StringVar()
        tk.Entry(r2, textvariable=self.output_var, bg=LIST_BG, fg=FG, font=("", 12)).pack(
            side="left", fill="x", expand=True, padx=8
        )
        self._button(r2, "浏览…", self._pick_output).pack(side="left")

        # --- ⑤ ---
        self._button(self, "⑤ 确认并生成", self._run_splice, accent=True).pack(
            pady=12
        )

    def _pick_contract(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="选择合同 PDF",
            filetypes=[("PDF", "*.pdf"), ("All", "*.*")],
        )
        if not path:
            self._set_banner("未选择合同（可再点 ①）", "info")
            return
        from splice_signature_pages import default_output_path

        self.contract_path = Path(path)
        self.contract_var.set(str(self.contract_path))
        self.output_var.set(str(default_output_path(self.contract_path)))
        self._set_banner(f"已选合同：{self.contract_path.name} → 请继续 ②", "ok")

    def _add_signed(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self,
            title="选择已签签字页 PDF（可多选）",
            filetypes=[("PDF", "*.pdf"), ("All", "*.*")],
        )
        if not paths:
            self._set_banner("未添加已签页（可再点 ②）", "info")
            return
        if self.signed_list.size() == 1 and self.signed_list.get(0).startswith("（"):
            self.signed_list.delete(0, tk.END)
        for p in paths:
            path = Path(p)
            if path not in self.signed_paths:
                self.signed_paths.append(path)
                self.signed_list.insert(tk.END, path.name)
        self._set_banner(
            f"已签文件 {len(self.signed_paths)} 份 → 现在可以点 ③ 定位", "ok"
        )

    def _clear_signed(self) -> None:
        self.signed_paths.clear()
        self.signed_list.delete(0, tk.END)
        self.signed_list.insert(tk.END, "（这里会出现已选文件名）")
        self._set_banner("已清空已签列表", "info")

    def _pick_output(self) -> None:
        from splice_signature_pages import default_output_path

        path = filedialog.asksaveasfilename(
            parent=self,
            title="保存输出 PDF",
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
            initialfile=(
                default_output_path(self.contract_path).name
                if self.contract_path
                else "合同_已嵌签字页.pdf"
            ),
        )
        if path:
            self.output_var.set(path)

    def _run_locate(self) -> None:
        if not self.contract_path or not self.contract_path.is_file():
            self._alert("还不能定位", "请先点 ① 选择合同 PDF")
            return
        if not self.signed_paths:
            self._alert("还不能定位", "请先点 ② 添加至少一份已签签字页 PDF")
            return

        self._set_banner("正在定位，请稍候…", "info")
        self.update_idletasks()

        try:
            from locate_signature_pages import DEFAULT_PATTERNS, load_patterns, locate

            patterns = load_patterns(DEFAULT_PATTERNS)
            result = locate(self.contract_path, self.signed_paths, patterns)
        except Exception as exc:
            self._alert("定位失败", f"{type(exc).__name__}: {exc}")
            return

        for c in result["candidates"]:
            c["preview"] = []

        self.candidates = result["candidates"]
        self.cand_list.delete(0, tk.END)

        if not self.candidates:
            self.cand_list.insert(tk.END, "未找到自动候选 — 请在下方手动填写页码")
            self.cmp_var.set(
                f"S={result['signed_page_count']}｜无候选，请人工填页码"
            )
            self._set_banner(
                "未找到候选页。请打开合同核对签字页页码，在 ④ 手动填写后点 ⑤",
                "info",
            )
            return

        for i, c in enumerate(self.candidates):
            self.cand_list.insert(
                tk.END,
                f"{chr(ord('A') + i)}. 第 {c['start']}–{c['end']} 页｜"
                f"{c['page_count']} 页｜置信度 {c['confidence']}｜"
                f"{', '.join((c.get('signals') or [])[:3])}",
            )

        cmp_ = result["comparison"]
        advice = {
            "match": "页数一致，可确认后嵌回",
            "contract_fewer": "定位页少于已签页，请检查是否漏页或扩大范围",
            "contract_more": "定位页多于已签页，请缩小范围或补已签文件",
            "no_candidate": "无自动候选",
            "no_signed": "无已签页",
        }.get(cmp_.get("status", ""), "")
        self.cmp_var.set(
            f"已签页数 S={result['signed_page_count']}｜{cmp_.get('status')} — {advice}"
        )

        self.cand_list.selection_set(0)
        self._on_cand_select()
        self._set_banner(
            f"定位完成：{len(self.candidates)} 个候选。"
            "请点击列表选一档，核对 ④ 页码后点 ⑤",
            "ok",
        )

    def _on_cand_select(self, _event=None) -> None:
        sel = self.cand_list.curselection()
        if not sel or not self.candidates:
            return
        idx = sel[0]
        if idx >= len(self.candidates):
            return
        c = self.candidates[idx]
        self.range_var.set(
            str(c["start"]) if c["start"] == c["end"] else f"{c['start']}-{c['end']}"
        )

    def _run_splice(self) -> None:
        from pypdf import PdfReader, PdfWriter
        from splice_signature_pages import parse_range, splice

        if not self.contract_path or not self.contract_path.is_file():
            self._alert("无法生成", "请先点 ① 选择合同 PDF")
            return
        if not self.signed_paths:
            self._alert("无法生成", "请先点 ② 添加已签签字页")
            return

        range_text = self.range_var.get().strip()
        if not range_text:
            self._alert("无法生成", "请先点 ③ 定位并选择候选，或在 ④ 手动填写页码")
            return
        try:
            start, end = parse_range(range_text.replace(" ", ""))
        except ValueError as exc:
            self._alert("页码无效", str(exc))
            return

        out_raw = self.output_var.get().strip()
        if not out_raw:
            self._alert("无法生成", "请填写输出路径")
            return
        output = Path(out_raw).expanduser()

        cleanup: Path | None = None
        if len(self.signed_paths) > 1:
            ok = messagebox.askokcancel(
                "多份已签 PDF",
                "将把所有已签 PDF 合并后，替换合同该页码范围。\n"
                "多段分别替换请用 CLI。\n\n是否继续？",
                parent=self,
            )
            if not ok:
                return
            merged = output.parent / f".{output.stem}_signed_merged_tmp.pdf"
            writer = PdfWriter()
            for p in self.signed_paths:
                for page in PdfReader(str(p)).pages:
                    writer.add_page(page)
            with merged.open("wb") as f:
                writer.write(f)
            signed_for_splice = merged
            cleanup = merged
        else:
            signed_for_splice = self.signed_paths[0]

        confirm = messagebox.askyesno(
            "确认嵌回",
            f"合同：{self.contract_path.name}\n"
            f"替换第 {start}–{end} 页\n"
            f"输出：{output}\n\n不会覆盖原合同。是否继续？",
            parent=self,
        )
        if not confirm:
            if cleanup and cleanup.is_file():
                cleanup.unlink(missing_ok=True)
            self._set_banner("已取消生成", "info")
            return

        self._set_banner("正在嵌回…", "info")
        self.update_idletasks()
        report = None
        try:
            report = splice(
                self.contract_path,
                [(start, end, signed_for_splice)],
                output,
            )
        except SystemExit as exc:
            self._alert("嵌回失败", str(exc))
            return
        except Exception as exc:
            self._alert("嵌回失败", f"{type(exc).__name__}: {exc}")
            return
        finally:
            if cleanup and cleanup.is_file():
                cleanup.unlink(missing_ok=True)

        if report is None:
            return

        warn = "\n".join(report.get("warnings") or []) or "无"
        self._set_banner(
            f"完成：{report['output']}（{report['old_page_count']}→{report['new_page_count']} 页）",
            "ok",
        )
        messagebox.showinfo(
            "完成",
            f"已生成：\n{report['output']}\n\n"
            f"页数：{report['old_page_count']} → {report['new_page_count']}\n"
            f"警告：{warn}",
            parent=self,
        )


def main() -> int:
    try:
        app = App()
        app.mainloop()
    except Exception as exc:
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("启动失败", f"{type(exc).__name__}: {exc}")
            root.destroy()
        except Exception:
            print(f"启动失败: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
