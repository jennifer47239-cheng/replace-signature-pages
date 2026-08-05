#!/usr/bin/env python3
"""Local HTML tag workbench: multi-row units + suggested chips + thumbnails.

Runs a short-lived localhost server. No cloud, no LLM.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from ranges_util import format_range
from sig_unit import SigUnit, normalize_label
from splice_signature_pages import parse_range


def _esc(s: str) -> str:
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_workbench_html(
    *,
    contract_name: str,
    ranges: list[tuple[int, int]],
    suggestions: dict[str, Any],
    thumb_rel: dict[str, str],
    initial_units: list[dict[str, Any]] | None = None,
) -> str:
    """thumb_rel: key 'start-end' or page no str -> relative url path under /files/."""
    range_meta = {format_range(s, e): (s, e) for s, e in ranges}
    sug_by_range = {r["range"]: r for r in suggestions.get("ranges") or []}
    global_sug = suggestions.get("global") or {}

    # Seed rows: prefer initial_units; else one empty row per estimated block
    seed: list[dict[str, Any]] = []
    if initial_units:
        seed = list(initial_units)
    else:
        for r in suggestions.get("ranges") or []:
            n = max(1, int(r.get("block_estimate") or 1))
            invs = r.get("investors") or []
            sigs = r.get("signatories") or []
            caps = r.get("capacities") or []
            for i in range(n):
                seed.append(
                    {
                        "range": r["range"],
                        "party": invs[i] if i < len(invs) else "",
                        "party_role": "",
                        "signatory": sigs[i] if i < len(sigs) else "",
                        "capacity": caps[i] if i < len(caps) else "",
                        "copies": 1,
                    }
                )

    blocks_html: list[str] = []
    for label, (start, end) in range_meta.items():
        meta = sug_by_range.get(label) or {}
        thumbs = []
        for p in range(start, end + 1):
            rel = thumb_rel.get(str(p))
            if rel:
                src = f"/files/{_esc(rel)}"
                thumbs.append(
                    f'<figure class="thumb" data-src="{src}" data-page="{p}" '
                    f'title="点击放大到左半屏">'
                    f'<img src="{src}" alt="第 {p} 页"/>'
                    f'<figcaption>第 {p} 页 · 点击放大<br/>'
                    f'<button type="button" class="mini set-page" data-page="{p}">'
                    f'本页 → 当前行</button></figcaption></figure>'
                )
        inv_chips = "".join(
            f'<button type="button" class="chip inv" data-range="{_esc(label)}" '
            f'data-field="party" data-value="{_esc(v)}">{_esc(v)}</button>'
            for v in (meta.get("investors") or global_sug.get("investors") or [])[:16]
        )
        sig_chips = "".join(
            f'<button type="button" class="chip sig" data-range="{_esc(label)}" '
            f'data-field="signatory" data-value="{_esc(v)}">{_esc(v)}</button>'
            for v in (meta.get("signatories") or global_sug.get("signatories") or [])[:16]
        )
        cap_chips = "".join(
            f'<button type="button" class="chip cap" data-range="{_esc(label)}" '
            f'data-field="capacity" data-value="{_esc(v)}">{_esc(v)}</button>'
            for v in (meta.get("capacities") or global_sug.get("capacities") or [])[:8]
        )
        blocks_html.append(
            f"""
<section class="block" data-range="{_esc(label)}">
  <header>
    <h2>区间 {_esc(label)} 页</h2>
    <p class="hint">本机扫描建议约 {int(meta.get('block_estimate') or 1)} 个签字块 ·
      点候选芯片填入<strong>当前标签</strong>；右侧每行页码可精确到单页（如 {start}），
      不同主体落在不同页，分组包才会真的分开</p>
    <p class="hint">
      <button type="button" class="mini split-block" data-start="{start}" data-end="{end}">
        本区间按页拆成 {end - start + 1} 行（每页一行）</button>
    </p>
  </header>
  <div class="thumbs">{''.join(thumbs) or '<p class="muted">（无缩略图，可仍编辑标签）</p>'}</div>
  <div class="chips">
    <div><span class="lab">签署主体候选</span> {inv_chips or '<span class="muted">无自动候选，请手填（可为投资方或融资方）</span>'}</div>
    <div><span class="lab">签字人候选</span> {sig_chips or '<span class="muted">无自动候选（空白待签常见）</span>'}</div>
    <div><span class="lab">身份候选</span> {cap_chips or '<span class="muted">—</span>'}</div>
  </div>
</section>
"""
        )

    seed_json = json.dumps(seed, ensure_ascii=False)
    ranges_json = json.dumps([format_range(s, e) for s, e in ranges], ensure_ascii=False)
    global_json = json.dumps(global_sug, ensure_ascii=False)

    all_pages = sorted({p for s, e in ranges for p in range(s, e + 1)})
    # Datalist: whole blocks first, then every single page (per-party grouping)
    range_options: list[str] = []
    for s, e in ranges:
        label = format_range(s, e)
        if label not in range_options:
            range_options.append(label)
    for p in all_pages:
        if str(p) not in range_options:
            range_options.append(str(p))
    options_json = json.dumps(range_options, ensure_ascii=False)
    pages_json = json.dumps(all_pages)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>签字页标签工作台 · 本机</title>
<style>
:root {{
  --bg: #f4f1ec; --ink: #1c1917; --muted: #78716c; --line: #d6d3d1;
  --accent: #0f766e; --accent2: #b45309; --card: #fffcf8; --danger: #b91c1c;
  --header-h: 58px;
}}
* {{ box-sizing: border-box; }}
html, body {{ height: 100%; margin: 0; }}
body {{
  font-family: "Iowan Old Style", "Songti SC", "Source Han Serif SC", system-ui, sans-serif;
  background: linear-gradient(160deg, #efe8df, var(--bg));
  color: var(--ink);
  display: flex; flex-direction: column;
  overflow: hidden; /* full-window split; panes scroll inside */
}}
header.top {{
  flex: 0 0 auto; z-index: 5;
  background: rgba(255,252,248,.96);
  border-bottom: 1px solid var(--line);
  padding: 10px 18px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
  min-height: var(--header-h);
}}
header.top h1 {{ font-size: 1.05rem; margin: 0; font-weight: 600; }}
header.top .sub {{ color: var(--muted); font-size: .85rem; }}
.actions {{ margin-left: auto; display: flex; gap: 8px; flex-wrap: wrap; }}
button, .btn {{
  font: inherit; cursor: pointer; border-radius: 6px; border: 1px solid var(--line);
  background: var(--card); padding: 8px 14px;
}}
button.primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
button.danger {{ color: var(--danger); }}
main {{
  flex: 1 1 auto; min-height: 0;
  display: grid; grid-template-columns: minmax(0, 1fr) minmax(320px, 1fr);
  gap: 0; overflow: hidden;
}}
@media (max-width: 900px) {{
  main {{ grid-template-columns: 1fr; grid-template-rows: 40% 60%; }}
}}
.left, .panel {{
  min-height: 0; min-width: 0;
}}
.left {{
  border-right: 1px solid var(--line);
  position: relative;
  overflow: hidden; /* zoom overlay fills column; list scrolls inside */
  padding: 0;
}}
#left-list {{
  height: 100%;
  overflow: auto;
  padding: 14px 16px;
}}
.panel {{
  background: var(--card);
  display: flex; flex-direction: column;
  overflow: auto;
  padding: 14px 16px;
}}
.panel h2 {{ margin: 0 0 8px; font-size: 1.05rem; flex: 0 0 auto; }}
.panel #status {{ flex: 0 0 auto; margin: 0 0 8px; }}
.table-wrap {{
  flex: 1 1 auto; min-height: 120px; overflow: auto;
  border: 1px solid var(--line); border-radius: 8px;
  background: #fff;
}}
.block {{
  background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 14px 16px; margin-bottom: 14px;
}}
.block h2 {{ margin: 0 0 4px; font-size: 1.05rem; }}
.hint {{ margin: 0 0 10px; color: var(--muted); font-size: .88rem; }}
.thumbs {{ display: flex; gap: 10px; overflow-x: auto; padding-bottom: 8px; }}
.thumbs figure.thumb {{
  margin: 0; flex: 0 0 auto; cursor: zoom-in;
}}
.thumbs figure.thumb:hover img {{
  outline: 2px solid var(--accent); outline-offset: 2px;
}}
.thumbs img {{
  height: 200px; width: auto; max-width: 160px; object-fit: contain;
  border: 2px solid #9f1239; border-radius: 6px; background: #fff; display: block;
}}
.thumbs figcaption {{ font-size: .75rem; color: var(--muted); text-align: center; }}
.thumbs figure.thumb.cur img {{
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(15,118,110,.25);
}}
.thumbs figure.thumb.cur figcaption {{ color: var(--accent); font-weight: 600; }}
button.mini {{
  font-size: .72rem; padding: 2px 8px; margin-top: 3px; border-radius: 999px;
}}
button.mini:hover {{ border-color: var(--accent); color: var(--accent); }}
.tabs {{ flex: 0 0 auto; display: flex; gap: 6px; margin-bottom: 8px; }}
.tab {{ padding: 6px 14px; border-radius: 999px; font-size: .9rem; }}
.tab.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.tabpane {{
  flex: 1 1 auto; min-height: 0; display: flex; flex-direction: column; gap: 8px;
}}
.tabpane.hidden {{ display: none; }}
.row-actions {{ flex: 0 0 auto; display: flex; gap: 8px; flex-wrap: wrap; }}
.bulk {{
  flex: 0 0 auto; display: flex; gap: 6px; align-items: center; flex-wrap: wrap;
  background: #f5f5f4; border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px;
}}
.bulk select {{ width: auto; min-width: 10em; max-width: 18em; }}
.bulk input {{ width: 11em; }}
td.idx {{ color: var(--muted); font-size: .8rem; width: 2.2em; }}
td.nav {{ white-space: nowrap; }}
td.nav button {{ margin-top: 0; padding: 4px 6px; }}
/* Full left-pane zoom */
#zoom-pane {{
  display: none;
  position: absolute; inset: 0; z-index: 20;
  background: #1c1917;
  flex-direction: column;
}}
#zoom-pane.open {{ display: flex; }}
#zoom-toolbar {{
  flex: 0 0 auto; display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 12px; background: #292524; color: #fafaf9;
}}
#zoom-toolbar .title {{ flex: 1 1 auto; font-size: .95rem; }}
#zoom-toolbar button {{
  background: #44403c; color: #fafaf9; border-color: #57534e;
}}
#zoom-toolbar button.primary {{ background: var(--accent); border-color: var(--accent); }}
#zoom-stage {{
  flex: 1 1 auto; min-height: 0; overflow: auto;
  display: flex; align-items: flex-start; justify-content: center;
  padding: 12px;
}}
#zoom-stage img {{
  max-width: 100%; height: auto; width: auto;
  background: #fff; box-shadow: 0 8px 40px rgba(0,0,0,.45);
  border-radius: 4px;
}}
#zoom-stage.fit-height img {{
  max-height: calc(100vh - var(--header-h) - 70px);
  width: auto; max-width: none;
}}
.chips {{
  display: flex; flex-direction: column; gap: 8px; margin-top: 8px;
  max-height: 150px; overflow-y: auto; overscroll-behavior: contain;
  padding: 6px 8px; border: 1px solid var(--line); border-radius: 8px;
  background: #fff;
}}
.chips .lab {{
  display: inline-block; min-width: 5.5em; font-size: .8rem; color: var(--muted);
}}
.chip {{
  display: inline-block; margin: 2px 4px 2px 0; padding: 4px 10px; font-size: .82rem;
  border-radius: 999px; border: 1px solid var(--line); background: #fafaf9;
  max-width: 100%; white-space: normal; text-align: left; line-height: 1.3;
}}
.chip.inv:hover {{ border-color: var(--accent); color: var(--accent); }}
.chip.sig:hover {{ border-color: var(--accent2); color: var(--accent2); }}
table {{ width: 100%; border-collapse: collapse; font-size: .88rem; }}
th, td {{ border-bottom: 1px solid var(--line); padding: 8px 6px; vertical-align: top; }}
th {{
  text-align: left; color: var(--muted); font-weight: 500; font-size: .75rem;
  position: sticky; top: 0; background: #fff; z-index: 1;
}}
tr.active {{ background: #ecfdf5; outline: 2px solid #99f6e4; outline-offset: -2px; }}
input[type=text], input[type=number], select {{
  width: 100%; font: inherit; padding: 6px 8px; border: 1px solid var(--line);
  border-radius: 6px; background: #fff;
}}
.muted {{ color: var(--muted); font-size: .85rem; }}
#status.ok {{ color: var(--accent); }}
#status.err {{ color: var(--danger); }}
.banner {{
  background: #fff7ed; border: 1px solid #fdba74; border-radius: 8px;
  padding: 10px 12px; font-size: .85rem; margin-bottom: 12px;
}}
.banner.warn {{ background: #fef2f2; border-color: #fca5a5; }}
.global-wrap {{ flex: 0 0 auto; margin-top: 10px; }}
.global-wrap > p {{ margin: 0 0 5px; }}
#global-chips {{
  max-height: 120px; overflow-y: auto; overscroll-behavior: contain;
  padding: 6px 8px; border: 1px solid var(--line); border-radius: 8px;
  background: #fafaf9;
}}
#global-chips > div + div {{ margin-top: 5px; }}
</style>
</head>
<body>
<header class="top">
  <div>
    <h1>签字页标签工作台</h1>
    <div class="sub">{_esc(contract_name)} · 本机 localhost · 不上传 · 不调用 AI</div>
  </div>
  <div class="actions">
    <button type="button" id="btn-add">加一行（同一页多方）</button>
    <button type="button" id="btn-split">全部按页拆行</button>
    <button type="button" id="btn-save" class="primary">确认标签并继续</button>
  </div>
</header>
<main>
  <div class="left">
    <div id="zoom-pane" aria-hidden="true">
      <div id="zoom-toolbar">
        <span class="title" id="zoom-title">放大预览</span>
        <button type="button" id="zoom-fit-width">适宽</button>
        <button type="button" id="zoom-fit-height">适高</button>
        <button type="button" id="zoom-prev">上一张</button>
        <button type="button" id="zoom-next">下一张</button>
        <button type="button" id="zoom-assign">本页 → 当前行</button>
        <button type="button" class="primary" id="zoom-close">关闭放大（Esc）</button>
      </div>
      <div id="zoom-stage" class="fit-height">
        <img id="zoom-img" alt="放大预览"/>
      </div>
    </div>
    <div id="left-list">
    <div class="banner">
      <strong>两步走：</strong>① 在右侧「标签库」把<strong>签署主体</strong>
      （可为投资方或融资方）整理好——点左侧候选芯片可填入当前标签行；
      ② 到「分配页码」为每一页选一个标签，同页多方用「加一行」。
      缩略图<strong>点击可放大到整个左半屏</strong>，当前行对应的页会高亮。
    </div>
    <div class="banner warn">
      <strong>页码要落到各自的页，分组才真的分开。</strong>
      若多行都留着同一个多页整段，每个分组 PDF 都会含该段全部页，看起来像「没分组」。
      可用缩略图下的「本页 → 当前行」、行内 ◀ ▶、或「按页拆行」「批量加行」。
    </div>
    {''.join(blocks_html)}
    </div>
  </div>
  <div class="panel">
    <div class="tabs">
      <button type="button" class="tab active" data-tab="lib">① 标签库</button>
      <button type="button" class="tab" data-tab="assign">② 分配页码</button>
    </div>
    <p id="status" class="muted">先在「标签库」把签署主体整理好，再到「分配页码」按页选标签。</p>

    <section id="pane-lib" class="tabpane">
      <p class="muted">一条标签 = 一个签署主体（+签字人 / 身份）。点左侧候选填入<strong>当前标签行</strong>。</p>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th></th><th>签署主体</th><th>角色</th><th>签字人</th><th>身份</th><th></th></tr>
          </thead>
          <tbody id="lib-rows"></tbody>
        </table>
      </div>
      <div class="row-actions">
        <button type="button" id="lib-add">新增标签</button>
        <button type="button" id="lib-import">导入候选主体</button>
        <button type="button" id="draft-save">保存标签草稿</button>
        <button type="button" id="lib-next" class="primary">下一步：分配页码</button>
      </div>
    </section>

    <section id="pane-assign" class="tabpane hidden">
      <div class="bulk">
        <span class="lab">批量加行</span>
        <select id="bulk-label"></select>
        <input type="text" id="bulk-pages" placeholder="页码，如 25,27-28"/>
        <button type="button" id="bulk-add">按页加行</button>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr><th>页码</th><th></th><th>标签（签署主体 / 签字人）</th><th>份数</th><th></th></tr>
          </thead>
          <tbody id="rows"></tbody>
        </table>
      </div>
    </section>

    <div class="global-wrap">
      <p class="muted">全局候选：</p>
      <div id="global-chips"></div>
    </div>
  </div>
</main>
<script>
const RANGES = {ranges_json};
const RANGE_OPTIONS = {options_json};
const ALL_PAGES = {pages_json};
const SEED = {seed_json};
const GLOBAL = {global_json};
let active = 0;
const tbody = document.getElementById('rows');
const libBody = document.getElementById('lib-rows');
const statusEl = document.getElementById('status');
let draftSaving = false;

/* ---- thumbnail zoom (fills entire left pane) ---- */
const zoomPane = document.getElementById('zoom-pane');
const zoomImg = document.getElementById('zoom-img');
const zoomTitle = document.getElementById('zoom-title');
const zoomStage = document.getElementById('zoom-stage');
const leftList = document.getElementById('left-list');
let zoomList = [];
let zoomIndex = 0;

function collectThumbs() {{
  return [...document.querySelectorAll('figure.thumb')].map(fig => ({{
    src: fig.dataset.src,
    page: fig.dataset.page,
  }}));
}}
function openZoom(src, page) {{
  zoomList = collectThumbs();
  zoomIndex = Math.max(0, zoomList.findIndex(t => t.src === src));
  if (zoomIndex < 0) zoomIndex = 0;
  showZoomAt(zoomIndex);
  zoomPane.classList.add('open');
  zoomPane.setAttribute('aria-hidden', 'false');
  leftList.style.visibility = 'hidden';
}}
function showZoomAt(i) {{
  if (!zoomList.length) return;
  zoomIndex = (i + zoomList.length) % zoomList.length;
  const t = zoomList[zoomIndex];
  zoomImg.src = t.src;
  zoomTitle.textContent = `第 ${{t.page}} 页（${{zoomIndex+1}}/${{zoomList.length}}）· 滚轮可滚动查看`;
}}
function closeZoom() {{
  zoomPane.classList.remove('open');
  zoomPane.setAttribute('aria-hidden', 'true');
  leftList.style.visibility = '';
  zoomImg.removeAttribute('src');
}}
document.querySelectorAll('figure.thumb').forEach(fig => {{
  fig.addEventListener('click', (e) => {{
    e.preventDefault();
    openZoom(fig.dataset.src, fig.dataset.page);
  }});
}});
document.getElementById('zoom-close').addEventListener('click', closeZoom);
document.getElementById('zoom-prev').addEventListener('click', () => showZoomAt(zoomIndex - 1));
document.getElementById('zoom-next').addEventListener('click', () => showZoomAt(zoomIndex + 1));
document.getElementById('zoom-fit-width').addEventListener('click', () => {{
  zoomStage.classList.remove('fit-height');
}});
document.getElementById('zoom-fit-height').addEventListener('click', () => {{
  zoomStage.classList.add('fit-height');
}});
document.addEventListener('keydown', (e) => {{
  if (!zoomPane.classList.contains('open')) return;
  if (e.key === 'Escape') closeZoom();
  if (e.key === 'ArrowLeft') showZoomAt(zoomIndex - 1);
  if (e.key === 'ArrowRight') showZoomAt(zoomIndex + 1);
}});

function escAttr(s) {{
  return String(s||'').replace(/&/g,'&amp;').replace(/"/g,'&quot;').replace(/</g,'&lt;');
}}

/* ---------- tabs ---------- */
let currentTab = 'lib';
function switchTab(name) {{
  currentTab = name;
  document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.getElementById('pane-lib').classList.toggle('hidden', name !== 'lib');
  document.getElementById('pane-assign').classList.toggle('hidden', name !== 'assign');
}}
document.querySelectorAll('.tab').forEach(b => {{
  b.addEventListener('click', () => switchTab(b.dataset.tab));
}});
document.getElementById('lib-next').addEventListener('click', () => {{
  syncLib();
  switchTab('assign');
  statusEl.textContent = '给每页选一个标签；同页多方用「加一行」。';
  statusEl.className = 'muted';
}});

/* ---------- label library (标签库) ---------- */
let LIB = [];
let libActive = 0;
function labelText(l) {{
  const parts = [l.party, l.signatory].filter(Boolean);
  return parts.join(' / ') || '（空标签）';
}}
function libRowHtml(l, i) {{
  const roles = ['','投资方','融资方','其他'];
  const roleOpts = roles.map(r =>
    `<option value="${{r}}" ${{(l.party_role||'')===r?'selected':''}}>${{r||'（未选）'}}</option>`).join('');
  return `<tr data-li="${{i}}" class="${{i===libActive?'active':''}}">
    <td class="idx">${{i+1}}</td>
    <td><input type="text" data-l="party" value="${{escAttr(l.party||'')}}" placeholder="公司或基金全称"/></td>
    <td style="width:5.5em"><select data-l="party_role">${{roleOpts}}</select></td>
    <td><input type="text" data-l="signatory" value="${{escAttr(l.signatory||'')}}"/></td>
    <td><input type="text" data-l="capacity" value="${{escAttr(l.capacity||'')}}"/></td>
    <td><button type="button" class="danger" data-libdel="${{i}}">删</button></td>
  </tr>`;
}}
function readLib() {{
  return [...libBody.querySelectorAll('tr')].map(tr => {{
    const get = f => {{
      const el = tr.querySelector(`[data-l="${{f}}"]`);
      return el ? el.value.trim() : '';
    }};
    return {{
      party: get('party'),
      party_role: get('party_role'),
      signatory: get('signatory'),
      capacity: get('capacity'),
    }};
  }});
}}
function renderLib(list) {{
  LIB = list;
  libBody.innerHTML = LIB.map(libRowHtml).join('');
  libBody.querySelectorAll('[data-libdel]').forEach(btn => {{
    btn.addEventListener('click', (e) => {{
      e.preventDefault();
      e.stopPropagation();
      deleteLib(Number(btn.getAttribute('data-libdel')));
    }});
  }});
  refreshLabelSelects();
}}
function syncLib() {{
  LIB = readLib();
  refreshLabelSelects();
}}
function setLibActive(i) {{
  libActive = Math.max(0, Math.min(i, libBody.querySelectorAll('tr').length - 1));
  libBody.querySelectorAll('tr').forEach((tr, idx) => {{
    tr.classList.toggle('active', idx === libActive);
  }});
}}
function deleteLib(i) {{
  const lib = readLib();
  lib.splice(i, 1);
  const rows = readRows().map(r => ({{
    range: r.range,
    copies: r.copies,
    lib: r.lib === i ? -1 : (r.lib > i ? r.lib - 1 : r.lib),
  }}));
  libActive = Math.max(0, Math.min(libActive, lib.length - 1));
  renderLib(lib);
  render(rows);
  statusEl.textContent = '已删除标签，引用该标签的行改为「未填」。';
  statusEl.className = 'ok';
}}
libBody.addEventListener('focusin', (e) => {{
  const tr = e.target.closest('tr');
  if (tr) setLibActive(Number(tr.dataset.li));
}});
libBody.addEventListener('mousedown', (e) => {{
  const tr = e.target.closest('tr');
  if (tr && !e.target.closest('button')) setLibActive(Number(tr.dataset.li));
}});
libBody.addEventListener('change', () => syncLib());
document.getElementById('lib-add').addEventListener('click', () => {{
  const lib = readLib();
  lib.push({{party:'', party_role:'', signatory:'', capacity:''}});
  libActive = lib.length - 1;
  renderLib(lib);
  const el = libBody.querySelector(`tr[data-li="${{libActive}}"] [data-l="party"]`);
  if (el) el.focus();
}});
document.getElementById('lib-import').addEventListener('click', () => {{
  const lib = readLib();
  const have = new Set(lib.map(l => l.party).filter(Boolean));
  let added = 0;
  (GLOBAL.investors || []).forEach(v => {{
    if (!have.has(v)) {{
      lib.push({{party:v, party_role:'', signatory:'', capacity:''}});
      have.add(v);
      added += 1;
    }}
  }});
  renderLib(lib);
  statusEl.textContent = added ? `已导入 ${{added}} 个候选主体，请核对后再分配页码。` : '没有新的候选主体可导入。';
  statusEl.className = added ? 'ok' : 'muted';
}});

/* ---------- assignment rows (页码 → 标签) ---------- */
function rangeOptionsHtml(val) {{
  const opts = RANGE_OPTIONS.slice();
  if (val && !opts.includes(val)) opts.unshift(val);
  return opts.map(o =>
    `<option value="${{escAttr(o)}}" ${{o===val?'selected':''}}>${{o.includes('-') ? o + ' 页（整段）' : '第 ' + o + ' 页'}}</option>`
  ).join('') + '<option value="__custom__">自定义…</option>';
}}
function labelOptionsHtml(sel) {{
  return `<option value="-1" ${{sel===-1?'selected':''}}>（未填）</option>` +
    LIB.map((l, i) =>
      `<option value="${{i}}" ${{i===sel?'selected':''}}>${{escAttr(labelText(l))}}</option>`).join('');
}}
function refreshLabelSelects() {{
  tbody.querySelectorAll('[data-f="lib"]').forEach(sel => {{
    const cur = parseInt(sel.value, 10);
    sel.innerHTML = labelOptionsHtml(Number.isFinite(cur) ? cur : -1);
  }});
  const bulk = document.getElementById('bulk-label');
  if (bulk) {{
    const cur = parseInt(bulk.value, 10);
    bulk.innerHTML = labelOptionsHtml(Number.isFinite(cur) ? cur : -1);
  }}
}}
function rowHtml(r, idx) {{
  const sel = Number.isFinite(r.lib) ? r.lib : -1;
  return `<tr data-i="${{idx}}" class="${{idx===active?'active':''}}">
    <td style="width:9em"><select data-f="range">${{rangeOptionsHtml(r.range)}}</select></td>
    <td class="nav" style="width:4.6em">
      <button type="button" class="mini page-prev" title="上一页">◀</button>
      <button type="button" class="mini page-next" title="下一页">▶</button></td>
    <td><select data-f="lib">${{labelOptionsHtml(sel)}}</select></td>
    <td style="width:4.5em"><input type="number" min="1" data-f="copies" value="${{r.copies||1}}"/></td>
    <td><button type="button" class="danger" data-del="${{idx}}">删</button></td>
  </tr>`;
}}
function readRows() {{
  return [...tbody.querySelectorAll('tr')].map(tr => {{
    const val = f => {{
      const el = tr.querySelector(`[data-f="${{f}}"]`);
      return el ? el.value : '';
    }};
    const li = parseInt(val('lib'), 10);
    return {{
      range: String(val('range') || '').trim(),
      lib: Number.isFinite(li) ? li : -1,
      copies: parseInt(val('copies') || '1', 10) || 1,
    }};
  }});
}}
function unitsFromRows() {{
  const rows = readRows();
  const lib = readLib();
  return rows.map(r => {{
    const l = (r.lib >= 0 && r.lib < lib.length)
      ? lib[r.lib]
      : {{party:'', party_role:'', signatory:'', capacity:''}};
    return {{
      range: r.range,
      party: l.party,
      investor: l.party,
      party_role: l.party_role,
      signatory: l.signatory,
      capacity: l.capacity,
      copies: r.copies,
    }};
  }});
}}
function setActive(i, opts) {{
  active = Math.max(0, Math.min(i, tbody.querySelectorAll('tr').length - 1));
  tbody.querySelectorAll('tr').forEach((tr, idx) => {{
    tr.classList.toggle('active', idx === active);
  }});
  const row = tbody.querySelector(`tr[data-i="${{active}}"]`);
  if (!row) return;
  if (opts && opts.scroll) row.scrollIntoView({{ block: 'nearest' }});
  const sel = row.querySelector('[data-f="range"]');
  if (sel) syncLeft(sel.value);
}}
function bindRowHandlers() {{
  // Do NOT re-render on row click — that caused flash & swallowed clicks.
  tbody.querySelectorAll('[data-del]').forEach(btn => {{
    btn.addEventListener('click', (e) => {{
      e.preventDefault();
      e.stopPropagation();
      const rows = readRows();
      rows.splice(Number(btn.getAttribute('data-del')), 1);
      active = Math.max(0, Math.min(active, rows.length - 1));
      render(rows.length ? rows : [{{range: RANGES[0] || '1', lib: -1, copies: 1}}]);
    }});
  }});
  tbody.querySelectorAll('button.page-prev, button.page-next').forEach(btn => {{
    btn.addEventListener('click', (e) => {{
      e.preventDefault();
      e.stopPropagation();
      const tr = btn.closest('tr');
      if (!tr) return;
      setActive(Number(tr.dataset.i));
      stepRowPage(tr, btn.classList.contains('page-next') ? 1 : -1);
    }});
  }});
}}
function render(rows) {{
  tbody.innerHTML = rows.map((r, i) => rowHtml(r, i)).join('');
  bindRowHandlers();
  setActive(active);
}}
function setRowRangeValue(tr, label) {{
  const sel = tr && tr.querySelector('[data-f="range"]');
  if (!sel) return;
  if (![...sel.options].some(o => o.value === label)) {{
    const o = document.createElement('option');
    o.value = label;
    o.textContent = label.includes('-') ? label + ' 页（整段）' : '第 ' + label + ' 页';
    sel.insertBefore(o, sel.firstChild);
  }}
  sel.value = label;
  syncLeft(label);
}}
function stepRowPage(tr, delta) {{
  const sel = tr.querySelector('[data-f="range"]');
  if (!sel) return;
  const r = parseRangeText(sel.value);
  if (!r) return;
  const span = r[1] - r[0];
  const start = Math.max(1, r[0] + delta);
  const label = span > 0 ? `${{start}}-${{start + span}}` : String(start);
  setRowRangeValue(tr, label);
  statusEl.textContent = `第 ${{active+1}} 行页码 → ${{label}}`;
  statusEl.className = 'ok';
}}

/* ---------- left preview follows the current row ---------- */
function syncLeft(rangeLabel) {{
  const r = parseRangeText(rangeLabel);
  if (!r) return;
  const page = r[0];
  document.querySelectorAll('figure.thumb.cur').forEach(f => f.classList.remove('cur'));
  const fig = document.querySelector(`figure.thumb[data-page="${{page}}"]`);
  if (!fig) return;
  fig.classList.add('cur');
  if (zoomPane.classList.contains('open')) {{
    if (!zoomList.length) zoomList = collectThumbs();
    const i = zoomList.findIndex(t => Number(t.page) === page);
    if (i >= 0) showZoomAt(i);
  }} else {{
    fig.scrollIntoView({{ block: 'nearest', inline: 'center' }});
  }}
}}

// Focus / click inside a cell → select that row without destroying DOM
tbody.addEventListener('focusin', (e) => {{
  const tr = e.target.closest('tr');
  if (!tr) return;
  setActive(Number(tr.dataset.i));
}});
tbody.addEventListener('mousedown', (e) => {{
  const tr = e.target.closest('tr');
  if (!tr) return;
  if (e.target.closest('button')) return;
  setActive(Number(tr.dataset.i));
}});
tbody.addEventListener('change', (e) => {{
  const tr = e.target.closest('tr');
  if (!tr) return;
  setActive(Number(tr.dataset.i));
  if (!e.target.matches('[data-f="range"]')) return;
  if (e.target.value === '__custom__') {{
    const txt = prompt('输入页码（如 27 或 27-28）', RANGE_OPTIONS[0] || '');
    const label = (txt || '').trim();
    setRowRangeValue(tr, parseRangeText(label) ? label : (RANGE_OPTIONS[0] || '1'));
    return;
  }}
  syncLeft(e.target.value);
}});
tbody.addEventListener('keydown', (e) => {{
  if (e.key !== 'Enter') return;
  const tr = e.target.closest('tr');
  if (!tr) return;
  e.preventDefault();
  const sel = tr.querySelector('[data-f="range"]');
  if (sel) syncLeft(sel.value);
  const label = tr.querySelector('[data-f="lib"]');
  if (label && e.target.matches('[data-f="range"]')) label.focus();
}});

function parseRangeText(txt) {{
  const m = String(txt || '').trim().replace(/[–—]/g, '-').match(/^(\\d+)(?:\\s*-\\s*(\\d+))?$/);
  if (!m) return null;
  const s = parseInt(m[1], 10);
  const e = m[2] ? parseInt(m[2], 10) : s;
  if (!(s >= 1) || e < s) return null;
  return [s, e];
}}
function rangeWithin(inner, outer) {{
  const a = parseRangeText(inner), b = parseRangeText(outer);
  if (!a || !b) return false;
  return a[0] >= b[0] && a[1] <= b[1];
}}
function fillLibField(li, field, value) {{
  const tr = libBody.querySelector(`tr[data-li="${{li}}"]`);
  if (!tr) return;
  const el = tr.querySelector(`[data-l="${{field}}"]`);
  if (el) el.value = value;
}}
/* Chips edit the *label*: in 标签库 they fill the current label row; in 分配页码
   they fill the label bound to the current row (creating one if needed). */
function applyChip(range, field, value) {{
  if (currentTab === 'lib' || !tbody.querySelectorAll('tr').length) {{
    if (!libBody.querySelectorAll('tr').length) {{
      renderLib([{{party:'', party_role:'', signatory:'', capacity:''}}]);
      libActive = 0;
    }}
    fillLibField(libActive, field, value);
    syncLib();
    statusEl.textContent = `已填入「${{value}}」→ 标签 ${{libActive+1}}`;
    statusEl.className = 'ok';
    return;
  }}
  const rows = readRows();
  if (active < 0 || active >= rows.length) active = 0;
  let li = rows[active].lib;
  if (!(li >= 0 && li < libBody.querySelectorAll('tr').length)) {{
    const lib = readLib();
    lib.push({{party:'', party_role:'', signatory:'', capacity:''}});
    li = lib.length - 1;
    libActive = li;
    renderLib(lib);
    const sel = tbody.querySelector(`tr[data-i="${{active}}"] [data-f="lib"]`);
    if (sel) sel.value = String(li);
  }}
  fillLibField(li, field, value);
  syncLib();
  const tr = tbody.querySelector(`tr[data-i="${{active}}"]`);
  if (tr) {{
    const sel = tr.querySelector('[data-f="range"]');
    if (range && sel && !rangeWithin(sel.value, range)) setRowRangeValue(tr, range);
    setActive(active, {{scroll: true}});
  }}
  statusEl.textContent = `已填入「${{value}}」→ 第 ${{active+1}} 行所用标签`;
  statusEl.className = 'ok';
}}
document.querySelectorAll('.chip').forEach(btn => {{
  btn.addEventListener('click', (e) => {{
    e.preventDefault();
    applyChip(btn.dataset.range, btn.dataset.field, btn.dataset.value);
  }});
}});
document.getElementById('btn-add').addEventListener('click', () => {{
  const rows = readRows();
  const base = rows[active] || {{range: RANGES[0] || '1', lib: -1, copies: 1}};
  rows.splice(active + 1, 0, {{range: base.range, lib: -1, copies: 1}});
  active = active + 1;
  switchTab('assign');
  render(rows);
  statusEl.textContent = `已在 ${{base.range}} 下新增一行（同一页多方），请选标签`;
  statusEl.className = 'ok';
  const sel = tbody.querySelector(`tr[data-i="${{active}}"] [data-f="lib"]`);
  if (sel) sel.focus();
}});
/* ---- per-page assignment & splitting ---- */
function assignPageToActive(page) {{
  switchTab('assign');
  let rows = readRows();
  if (!rows.length) {{
    rows = [{{range: String(page), lib: -1, copies: 1}}];
    active = 0;
    render(rows);
  }}
  if (active < 0 || active >= rows.length) active = 0;
  setRowRangeValue(tbody.querySelector(`tr[data-i="${{active}}"]`), String(page));
  setActive(active, {{scroll: true}});
  statusEl.textContent = `第 ${{active+1}} 行页码已设为第 ${{page}} 页`;
  statusEl.className = 'ok';
}}
document.querySelectorAll('button.set-page').forEach(btn => {{
  btn.addEventListener('click', (e) => {{
    e.preventDefault();
    e.stopPropagation();
    assignPageToActive(Number(btn.dataset.page));
  }});
}});
/* One row per page. Rows covering the same page collapse into one; the label is
   kept only when it is unambiguous, otherwise the page waits for a choice. */
function splitRows(pages) {{
  const rows = readRows();
  const keep = [];
  const split = [];
  rows.forEach(r => {{
    const pr = parseRangeText(r.range);
    const span = [];
    if (pr) for (let p = pr[0]; p <= pr[1]; p++) span.push(p);
    const doSplit = span.length > 1 && (!pages || span.every(p => pages.includes(p)));
    (doSplit ? split : keep).push({{row: r, span}});
  }});
  if (!split.length) {{
    statusEl.textContent = '没有可拆的多页行（都已是单页）。';
    statusEl.className = 'muted';
    return;
  }}
  const kept = new Set();
  keep.forEach(k => k.span.forEach(p => kept.add(p)));
  const byPage = new Map();
  split.forEach(s => s.span.forEach(p => {{
    if (kept.has(p)) return;
    if (!byPage.has(p)) byPage.set(p, []);
    byPage.get(p).push(s.row);
  }}));
  const out = keep.map(k => k.row);
  [...byPage.keys()].sort((a, b) => a - b).forEach(p => {{
    const srcs = byPage.get(p);
    const labels = new Set(srcs.map(r => r.lib));
    out.push({{
      range: String(p),
      lib: labels.size === 1 ? srcs[0].lib : -1,
      copies: srcs[0].copies || 1,
    }});
  }});
  out.sort((a, b) => {{
    const ra = parseRangeText(a.range) || [0, 0];
    const rb = parseRangeText(b.range) || [0, 0];
    return ra[0] - rb[0];
  }});
  active = 0;
  switchTab('assign');
  render(out);
  statusEl.textContent = `已按页拆成 ${{out.length}} 行（每页一行），请给每行选标签`;
  statusEl.className = 'ok';
}}
document.querySelectorAll('button.split-block').forEach(btn => {{
  btn.addEventListener('click', (e) => {{
    e.preventDefault();
    const s = Number(btn.dataset.start), t = Number(btn.dataset.end);
    const pages = [];
    for (let p = s; p <= t; p++) pages.push(p);
    splitRows(pages);
  }});
}});
document.getElementById('btn-split').addEventListener('click', () => splitRows(null));
document.getElementById('zoom-assign').addEventListener('click', () => {{
  const t = zoomList[zoomIndex];
  if (t) assignPageToActive(Number(t.page));
}});

/* ---- bulk: one label × many pages ---- */
function parsePagesText(txt) {{
  const out = [];
  String(txt || '').split(/[,，、;；\\s]+/).filter(Boolean).forEach(seg => {{
    const r = parseRangeText(seg);
    if (r) for (let p = r[0]; p <= r[1]; p++) out.push(p);
  }});
  return [...new Set(out)].sort((a, b) => a - b);
}}
document.getElementById('bulk-add').addEventListener('click', () => {{
  const li = parseInt(document.getElementById('bulk-label').value, 10);
  const input = document.getElementById('bulk-pages');
  const pages = parsePagesText(input.value);
  if (!pages.length) {{
    statusEl.textContent = '请填页码，例如 25,27-28';
    statusEl.className = 'err';
    return;
  }}
  const rows = readRows();
  pages.forEach(p => rows.push({{range: String(p), lib: Number.isFinite(li) ? li : -1, copies: 1}}));
  active = rows.length - 1;
  render(rows);
  input.value = '';
  const name = (li >= 0 && LIB[li]) ? labelText(LIB[li]) : '（未填）';
  statusEl.textContent = `已为「${{name}}」加 ${{pages.length}} 行：第 ${{pages.join('、')}} 页`;
  statusEl.className = 'ok';
}});

document.getElementById('btn-save').addEventListener('click', async () => {{
  const units = unitsFromRows();
  if (!units.length) {{ statusEl.textContent='至少一行'; statusEl.className='err'; return; }}
  const bad = units
    .map((u, i) => (parseRangeText(u.range) ? null : `第 ${{i+1}} 行「${{u.range}}」`))
    .filter(Boolean);
  if (bad.length) {{
    statusEl.textContent = `页码格式无效：${{bad.join('、')}}（应为 27 或 27-28）`;
    statusEl.className = 'err';
    switchTab('assign');
    return;
  }}
  const outside = units.filter(u => {{
    const r = parseRangeText(u.range);
    for (let p = r[0]; p <= r[1]; p++) if (!ALL_PAGES.includes(p)) return true;
    return false;
  }});
  if (outside.length && !confirm(
    `有 ${{outside.length}} 行的页码不在已选签字页范围内（仍会按合同页码取页）。继续？`
  )) return;
  // Same multi-page range shared by different parties →每个包都含整段
  const byRange = {{}};
  units.forEach(u => {{
    const key = u.range;
    (byRange[key] = byRange[key] || []).push(u.party || '');
  }});
  const overlapping = Object.keys(byRange).filter(k => {{
    const r = parseRangeText(k);
    const distinct = new Set(byRange[k].filter(Boolean));
    return r && r[1] > r[0] && distinct.size > 1;
  }});
  if (overlapping.length && !confirm(
    `区间 ${{overlapping.join('、')}} 有多个不同签署主体共用同一多页区间，\\n` +
    '各自的分组 PDF 都会包含该区间的全部页（看起来像没分组）。\\n\\n' +
    '建议先用「按页拆行」或缩略图「本页 → 当前行」。仍要继续？'
  )) return;
  const empty = units.filter(u => !u.party && !u.signatory);
  if (empty.length === units.length) {{
    if (!confirm('全部行为空标签，将进入「未填」桶。仍要继续？')) return;
  }}
  statusEl.textContent = '保存中…';
  try {{
    const res = await fetch('/save', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{units}}),
    }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'save failed');
    statusEl.textContent = '已保存。可关闭本页，回到程序对话框继续。';
    statusEl.className = 'ok';
    document.getElementById('btn-save').disabled = true;
  }} catch (e) {{
    statusEl.textContent = String(e);
    statusEl.className = 'err';
  }}
}});
const g = document.getElementById('global-chips');
function addGlobal(label, arr, field) {{
  if (!arr || !arr.length) return;
  const wrap = document.createElement('div');
  wrap.innerHTML = `<span class="lab">${{label}}</span>`;
  arr.slice(0,20).forEach(v => {{
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'chip'; b.textContent = v;
    b.addEventListener('click', (e) => {{
      e.preventDefault();
      applyChip(null, field, v);
    }});
    wrap.appendChild(b);
  }});
  g.appendChild(wrap);
}}
addGlobal('签署主体', GLOBAL.investors||[], 'party');
addGlobal('签字人', GLOBAL.signatories||[], 'signatory');
addGlobal('身份', GLOBAL.capacities||[], 'capacity');

/* ---------- local server draft (survives page refresh) ---------- */
async function saveDraft() {{
  if (draftSaving) return;
  draftSaving = true;
  const button = document.getElementById('draft-save');
  if (button) button.disabled = true;
  try {{
    const payload = {{
      library: readLib(),
      rows: readRows(),
      active,
      libActive,
      tab: currentTab,
    }};
    const res = await fetch('/draft', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify(payload),
    }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'draft save failed');
    statusEl.textContent = `标签草稿已保存（${{payload.library.length}} 条标签、${{payload.rows.length}} 行）；刷新页面仍会恢复。`;
    statusEl.className = 'ok';
  }} catch (e) {{
    statusEl.textContent = `保存草稿失败：${{String(e)}}`;
    statusEl.className = 'err';
  }} finally {{
    draftSaving = false;
    if (button) button.disabled = false;
  }}
}}
document.getElementById('draft-save').addEventListener('click', saveDraft);

async function loadDraft() {{
  try {{
    const res = await fetch('/draft');
    if (!res.ok) return false;
    const data = await res.json();
    if (!data.found || !Array.isArray(data.library) || !Array.isArray(data.rows)) return false;
    libActive = Math.max(0, Math.min(Number(data.libActive) || 0, data.library.length - 1));
    active = Math.max(0, Math.min(Number(data.active) || 0, data.rows.length - 1));
    renderLib(data.library);
    render(data.rows.length ? data.rows : [{{range: RANGES[0] || '1', lib: -1, copies: 1}}]);
    switchTab(data.tab === 'assign' ? 'assign' : 'lib');
    statusEl.textContent = `已恢复保存的标签草稿（${{data.library.length}} 条标签、${{data.rows.length}} 行）。`;
    statusEl.className = 'ok';
    return true;
  }} catch (_) {{
    return false;
  }}
}}

/* ---------- init: derive the label library from local suggestions ---------- */
(async function init() {{
  const lib = [];
  const seen = new Map();
  const rows = [];
  const seed = SEED.length ? SEED : [{{range: RANGES[0] || '1'}}];
  seed.forEach(u => {{
    const l = {{
      party: u.party || u.investor || '',
      party_role: u.party_role || '',
      signatory: u.signatory || '',
      capacity: u.capacity || '',
    }};
    let li = -1;
    if (l.party || l.signatory || l.capacity) {{
      const k = [l.party, l.party_role, l.signatory, l.capacity].join('\\u241f');
      if (seen.has(k)) {{
        li = seen.get(k);
      }} else {{
        lib.push(l);
        li = lib.length - 1;
        seen.set(k, li);
      }}
    }}
    rows.push({{range: u.range || RANGES[0] || '1', lib: li, copies: u.copies || 1}});
  }});
  renderLib(lib);
  render(rows);
  switchTab('lib');
  if (await loadDraft()) return;
  statusEl.textContent = lib.length
    ? `已从本机扫描归纳出 ${{lib.length}} 条标签，请先核对/补齐，再点「下一步：分配页码」。`
    : '标签库为空：点「新增标签」或「导入候选主体」，也可点左侧候选芯片。';
  statusEl.className = 'muted';
}})();
</script>
</body>
</html>
"""


class _WorkbenchState:
    def __init__(self) -> None:
        self.done = threading.Event()
        self.units: list[dict[str, Any]] | None = None
        self.error: str | None = None
        self.html: str = ""
        self.files_root: Path | None = None


def run_tag_workbench(
    *,
    work_dir: Path,
    contract_name: str,
    ranges: list[tuple[int, int]],
    suggestions: dict[str, Any],
    thumb_paths: dict[int, Path],
    initial_units: list[dict[str, Any]] | None = None,
    open_browser: bool = True,
    timeout_sec: float = 3600.0,
) -> list[SigUnit]:
    """Open local workbench; block until user saves or timeout. Returns SigUnits."""
    work_dir.mkdir(parents=True, exist_ok=True)
    files_dir = work_dir / "files"
    files_dir.mkdir(exist_ok=True)
    draft_path = work_dir / "workbench_draft.json"
    draft_context = {
        "contract_name": contract_name,
        "ranges": [format_range(s, e) for s, e in ranges],
    }

    thumb_rel: dict[str, str] = {}
    for page_no, src in thumb_paths.items():
        dest = files_dir / f"p{page_no}.png"
        if src.resolve() != dest.resolve():
            dest.write_bytes(src.read_bytes())
        thumb_rel[str(page_no)] = dest.name

    state = _WorkbenchState()
    state.files_root = files_dir
    state.html = build_workbench_html(
        contract_name=contract_name,
        ranges=ranges,
        suggestions=suggestions,
        thumb_rel=thumb_rel,
        initial_units=initial_units,
    )
    (work_dir / "workbench.html").write_text(state.html, encoding="utf-8")

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A003
            return

        def _send(self, code: int, body: bytes, content_type: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path in {"/", "/index.html"}:
                self._send(200, state.html.encode("utf-8"), "text/html; charset=utf-8")
                return
            if parsed.path == "/status":
                payload = {
                    "done": state.done.is_set(),
                    "unit_count": len(state.units or []),
                }
                self._send(
                    200,
                    json.dumps(payload).encode("utf-8"),
                    "application/json",
                )
                return
            if parsed.path == "/draft":
                payload: dict[str, Any] = {"found": False}
                try:
                    saved = json.loads(draft_path.read_text(encoding="utf-8"))
                    if saved.get("context") == draft_context:
                        payload = {"found": True, **(saved.get("draft") or {})}
                except (FileNotFoundError, json.JSONDecodeError, OSError):
                    pass
                self._send(
                    200,
                    json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8",
                )
                return
            if parsed.path.startswith("/files/"):
                name = unquote(parsed.path[len("/files/") :])
                path = (files_dir / Path(name).name).resolve()
                if not str(path).startswith(str(files_dir.resolve())) or not path.is_file():
                    self._send(404, b"missing", "text/plain")
                    return
                ctype = "image/png" if path.suffix.lower() == ".png" else "application/octet-stream"
                self._send(200, path.read_bytes(), ctype)
                return
            self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            route = urlparse(self.path).path
            if route not in {"/save", "/draft"}:
                self._send(404, b"not found", "text/plain")
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > 2_000_000:
                self._send(413, b'{"error":"payload too large"}', "application/json")
                return
            raw = self.rfile.read(length)
            try:
                data = json.loads(raw.decode("utf-8"))
                if route == "/draft":
                    library = data.get("library")
                    rows = data.get("rows")
                    if not isinstance(library, list) or not isinstance(rows, list):
                        raise ValueError("draft requires library and rows")
                    if len(library) > 1000 or len(rows) > 10000:
                        raise ValueError("draft has too many labels or rows")
                    draft = {
                        "library": library,
                        "rows": rows,
                        "active": max(0, int(data.get("active") or 0)),
                        "libActive": max(0, int(data.get("libActive") or 0)),
                        "tab": "assign" if data.get("tab") == "assign" else "lib",
                    }
                    draft_path.write_text(
                        json.dumps(
                            {"context": draft_context, "draft": draft},
                            ensure_ascii=False,
                            indent=2,
                        )
                        + "\n",
                        encoding="utf-8",
                    )
                    self._send(
                        200,
                        json.dumps({"ok": True}, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8",
                    )
                    return
                units_raw = data.get("units") or []
                if not isinstance(units_raw, list) or not units_raw:
                    raise ValueError("units required")
                cleaned = []
                for i, item in enumerate(units_raw, start=1):
                    label = str(item.get("range") or "").strip()
                    try:
                        parse_range(label)
                    except Exception as exc:  # noqa: BLE001
                        raise ValueError(f"第 {i} 行区间「{label}」无效：{exc}") from exc
                    cleaned.append(
                        {
                            "range": label,
                            "party": normalize_label(
                                str(item.get("party") or item.get("investor") or "")
                            ),
                            "party_role": normalize_label(
                                str(item.get("party_role") or "")
                            ),
                            "signatory": normalize_label(str(item.get("signatory") or "")),
                            "capacity": normalize_label(str(item.get("capacity") or "")),
                            "copies": max(1, int(item.get("copies") or 1)),
                        }
                    )
                state.units = cleaned
                (work_dir / "tags_from_workbench.json").write_text(
                    json.dumps({"units": cleaned}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                state.done.set()
                self._send(
                    200,
                    json.dumps({"ok": True, "unit_count": len(cleaned)}).encode("utf-8"),
                    "application/json",
                )
            except Exception as exc:  # noqa: BLE001
                state.error = str(exc)
                self._send(
                    400,
                    json.dumps({"error": str(exc)}).encode("utf-8"),
                    "application/json",
                )

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    url = f"http://127.0.0.1:{port}/"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    if open_browser:
        webbrowser.open(url)

    finished = state.done.wait(timeout=timeout_sec)
    server.shutdown()
    if not finished or not state.units:
        raise TimeoutError(
            "标签工作台未保存（超时或已关闭）。请重新打开并点「确认标签并继续」。"
        )

    return [
        SigUnit.from_dict(u)
        for u in state.units
    ]
