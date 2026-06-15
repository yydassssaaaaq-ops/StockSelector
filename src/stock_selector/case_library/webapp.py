from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sqlite3
import threading
import urllib.parse
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .importer import DEFAULT_DB, DEFAULT_LEGACY_ROOT, DEFAULT_OUTPUT_DIR, import_legacy_cases
from .monitor import CaseLibraryMonitor, monitor_state_from_db


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def rows(conn: sqlite3.Connection, sql: str, args: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in conn.execute(sql, args).fetchall()]


def one(conn: sqlite3.Connection, sql: str, args: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    row = conn.execute(sql, args).fetchone()
    return dict(row) if row else None


def loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except Exception:
        return default


def json_response(handler: BaseHTTPRequestHandler, data: Any, status: int = 200) -> None:
    payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def text_response(handler: BaseHTTPRequestHandler, text: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> None:
    payload = text.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def summary(db_path: Path) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        latest = one(conn, "SELECT * FROM import_runs ORDER BY id DESC LIMIT 1")
        lowest = rows(
            conn,
            "SELECT module_name, sum(case when ok=0 then 1 else 0 end) failed_count, count(*) total_count FROM modules GROUP BY module_name HAVING failed_count>0 ORDER BY failed_count DESC, total_count DESC LIMIT 6",
        )
        recent = rows(
            conn,
            "SELECT case_id, stock_code, stock_name, run_time, trade_date, data_quality, file_count FROM cases ORDER BY coalesce(run_time, trade_date) DESC LIMIT 10",
        )
        return {
            "stock_count": conn.execute("SELECT count(*) FROM stocks").fetchone()[0],
            "case_count": conn.execute("SELECT count(*) FROM cases").fetchone()[0],
            "earliest_run": conn.execute("SELECT min(coalesce(run_time, trade_date)) FROM cases").fetchone()[0],
            "latest_run": conn.execute("SELECT max(coalesce(run_time, trade_date)) FROM cases").fetchone()[0],
            "quality_distribution": rows(conn, "SELECT data_quality, count(*) count FROM cases GROUP BY data_quality ORDER BY data_quality"),
            "lowest_success_modules": lowest,
            "unparsed_count": conn.execute("SELECT count(*) FROM files WHERE parse_status='error'").fetchone()[0],
            "recent_import_time": latest["finished_at"] if latest else None,
            "recent_cases": recent,
        }
    finally:
        conn.close()


def search_stocks(db_path: Path, q: str) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        like = f"%{q.strip()}%"
        stocks = rows(
            conn,
            "SELECT * FROM stocks WHERE stock_code LIKE ? OR stock_name LIKE ? ORDER BY case_count DESC, stock_code LIMIT 30",
            (like, like),
        )
        return {"items": stocks}
    finally:
        conn.close()


def stock_detail(db_path: Path, code: str) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        stock = one(conn, "SELECT * FROM stocks WHERE stock_code=?", (code,))
        cases = rows(
            conn,
            """
            SELECT case_id, stock_code, stock_name, trade_date, run_id, run_time, run_session, data_quality,
                   module_success, module_failed, data_sources_json, has_humanview, has_radardata, has_charts,
                   radar_root, humanview_root, file_count, field_coverage
            FROM cases WHERE stock_code=?
            ORDER BY coalesce(run_time, trade_date), case_id
            """,
            (code,),
        )
        for case in cases:
            case["data_sources"] = loads(case.pop("data_sources_json"), [])
        return {"stock": stock, "cases": cases}
    finally:
        conn.close()


def case_detail(db_path: Path, case_id: str) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        case = one(conn, "SELECT * FROM cases WHERE case_id=?", (case_id,))
        if not case:
            return {"error": "case_not_found"}
        for key, default in [
            ("data_sources_json", []),
            ("missing_json", []),
            ("warnings_json", []),
            ("json_summary", []),
            ("csv_preview", []),
            ("text_summary", []),
            ("html_entries", []),
            ("png_entries", []),
        ]:
            case[key.replace("_json", "") if key.endswith("_json") else key] = loads(case.get(key), default)
        files = rows(
            conn,
            "SELECT path, file_type, role, size, mtime, sha256, parse_status, error, duplicate_of FROM files WHERE case_id=? ORDER BY role, path",
            (case_id,),
        )
        modules = rows(
            conn,
            "SELECT module_name, ok, status, rows, cols, source_file, error FROM modules WHERE case_id=? ORDER BY ok, module_name",
            (case_id,),
        )
        return {"case": case, "files": files, "modules": modules}
    finally:
        conn.close()


def compare_cases(db_path: Path, left: str, right: str) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        a = one(conn, "SELECT * FROM cases WHERE case_id=?", (left,))
        b = one(conn, "SELECT * FROM cases WHERE case_id=?", (right,))
        if not a or not b:
            return {"error": "case_not_found"}
        files_a = {row["path"] for row in conn.execute("SELECT path FROM files WHERE case_id=?", (left,)).fetchall()}
        files_b = {row["path"] for row in conn.execute("SELECT path FROM files WHERE case_id=?", (right,)).fetchall()}
        modules_a = {row["module_name"]: bool(row["ok"]) for row in conn.execute("SELECT module_name, ok FROM modules WHERE case_id=?", (left,)).fetchall()}
        modules_b = {row["module_name"]: bool(row["ok"]) for row in conn.execute("SELECT module_name, ok FROM modules WHERE case_id=?", (right,)).fetchall()}
        fields = [
            "run_time", "data_quality", "module_success", "module_failed", "file_count",
            "field_coverage", "has_intraday", "has_fund_flow", "has_humanview", "has_radardata", "has_charts",
        ]
        return {
            "left": {k: a[k] for k in ["case_id", "stock_code", "stock_name", *fields]},
            "right": {k: b[k] for k in ["case_id", "stock_code", "stock_name", *fields]},
            "field_compare": [{"field": f, "left": a[f], "right": b[f], "changed": a[f] != b[f]} for f in fields],
            "sources": {"left": loads(a["data_sources_json"], []), "right": loads(b["data_sources_json"], [])},
            "new_files": sorted(files_b - files_a)[:120],
            "missing_files": sorted(files_a - files_b)[:120],
            "module_changes": [
                {"module": name, "left_ok": modules_a.get(name), "right_ok": modules_b.get(name)}
                for name in sorted(set(modules_a) | set(modules_b))
                if modules_a.get(name) != modules_b.get(name)
            ],
            "structure_changed": a["structure_signature"] != b["structure_signature"],
        }
    finally:
        conn.close()


def diagnostics(db_path: Path) -> dict[str, Any]:
    conn = connect(db_path)
    try:
        bad_files = rows(conn, "SELECT path, case_id, error FROM files WHERE parse_status='error' ORDER BY path LIMIT 100")
        duplicates = rows(conn, "SELECT path, duplicate_of, case_id FROM duplicates ORDER BY id DESC LIMIT 100")
        incomplete = rows(
            conn,
            "SELECT case_id, stock_code, stock_name, missing_json, module_failed, field_coverage FROM cases WHERE missing_json NOT IN ('[]','') OR module_failed>0 ORDER BY field_coverage, module_failed DESC LIMIT 100",
        )
        for row in incomplete:
            row["missing"] = loads(row.pop("missing_json"), [])
        structures = rows(conn, "SELECT structure_signature, count(*) count FROM cases GROUP BY structure_signature ORDER BY count DESC")
        sources = rows(conn, "SELECT data_sources_json FROM cases")
        source_counter: dict[str, int] = {}
        for row in sources:
            for item in loads(row["data_sources_json"], []):
                source_counter[item] = source_counter.get(item, 0) + 1
        module_fail = rows(
            conn,
            "SELECT module_name, sum(case when ok=0 then 1 else 0 end) failed_count, count(*) total_count FROM modules GROUP BY module_name ORDER BY failed_count DESC, total_count DESC LIMIT 40",
        )
        complete = rows(
            conn,
            "SELECT stock_code, max(stock_name) stock_name, count(*) case_count, round(avg(field_coverage),3) avg_coverage FROM cases GROUP BY stock_code ORDER BY avg_coverage DESC, case_count DESC LIMIT 20",
        )
        intraday = rows(
            conn,
            "SELECT stock_code, trade_date, count(*) runs FROM cases GROUP BY stock_code, trade_date HAVING count(*)>1 ORDER BY runs DESC LIMIT 20",
        )
        return {
            "bad_files": bad_files,
            "duplicates": duplicates,
            "incomplete_cases": incomplete,
            "structure_versions": structures,
            "source_changes": sorted(source_counter.items(), key=lambda x: (-x[1], x[0]))[:30],
            "module_failures": module_fail,
            "most_complete_stocks": complete,
            "most_intraday_runs": intraday,
        }
    finally:
        conn.close()


def today_changes(db_path: Path) -> dict[str, Any]:
    day = datetime.now().astimezone().date().isoformat()
    like = f"{day}%"
    conn = connect(db_path)
    try:
        imports = rows(
            conn,
            "SELECT * FROM auto_import_runs WHERE started_at LIKE ? ORDER BY id DESC LIMIT 50",
            (like,),
        )
        events = rows(
            conn,
            "SELECT * FROM monitor_events WHERE event_time LIKE ? ORDER BY id DESC LIMIT 200",
            (like,),
        )
        changes = rows(
            conn,
            "SELECT * FROM case_change_events WHERE created_at LIKE ? ORDER BY id DESC LIMIT 200",
            (like,),
        )
        for item in imports:
            item["summary"] = loads(item.pop("summary_json"), {})
        for item in changes:
            item["before"] = loads(item.pop("before_json"), None)
            item["after"] = loads(item.pop("after_json"), None)
            item["changed_fields"] = loads(item.pop("changed_fields_json"), {})
        new_stocks = sorted({
            item["stock_code"]
            for item in changes
            if item.get("stock_code") and item.get("changed_fields", {}).get("new_stock")
        })
        new_cases = [item for item in changes if item["change_type"] == "new_case"]
        updated_cases = [item for item in changes if item["change_type"] == "updated_case"]
        field_added: dict[str, int] = {}
        field_removed: dict[str, int] = {}
        source_changes: list[dict[str, Any]] = []
        module_changes: list[dict[str, Any]] = []
        quality_changes: list[dict[str, Any]] = []
        for item in changes:
            changed = item.get("changed_fields", {})
            for field in changed.get("field_keys_added", []):
                field_added[field] = field_added.get(field, 0) + 1
            for field in changed.get("field_keys_removed", []):
                field_removed[field] = field_removed.get(field, 0) + 1
            if changed.get("data_sources_added") or changed.get("data_sources_removed"):
                source_changes.append({
                    "case_id": item["case_id"],
                    "stock_code": item["stock_code"],
                    "added": changed.get("data_sources_added", []),
                    "removed": changed.get("data_sources_removed", []),
                })
            if changed.get("module_status_changes") or changed.get("module_success") or changed.get("module_failed"):
                module_changes.append({
                    "case_id": item["case_id"],
                    "stock_code": item["stock_code"],
                    "module_success": changed.get("module_success"),
                    "module_failed": changed.get("module_failed"),
                    "status_changes": changed.get("module_status_changes", []),
                })
            if changed.get("data_quality"):
                quality_changes.append({
                    "case_id": item["case_id"],
                    "stock_code": item["stock_code"],
                    "quality": changed.get("data_quality"),
                })
        unparsed = rows(
            conn,
            "SELECT path, case_id, error, updated_at FROM files WHERE parse_status='error' AND updated_at LIKE ? ORDER BY updated_at DESC LIMIT 100",
            (like,),
        )
        return {
            "date": day,
            "import_runs": imports,
            "monitor_events": events,
            "new_stocks": new_stocks,
            "new_cases": new_cases,
            "updated_cases": updated_cases,
            "field_added": sorted(field_added.items(), key=lambda x: (-x[1], x[0]))[:50],
            "field_removed": sorted(field_removed.items(), key=lambda x: (-x[1], x[0]))[:50],
            "source_changes": source_changes[:100],
            "module_changes": module_changes[:100],
            "quality_changes": quality_changes[:100],
            "unparsed_files": unparsed,
        }
    finally:
        conn.close()


def monitor_status(db_path: Path, monitor: CaseLibraryMonitor | None) -> dict[str, Any]:
    if monitor is not None:
        return monitor.status()
    return monitor_state_from_db(db_path)


def index_html() -> str:
    return r"""<!doctype html>
<meta charset="utf-8">
<title>真实历史股票案卷库 V0.1</title>
<style>
:root{--bg:#f3f6f8;--ink:#17212b;--muted:#657282;--line:#d7dee8;--blue:#145da0;--green:#1d7f58;--red:#b73a3a}
*{box-sizing:border-box} body{margin:0;background:var(--bg);font-family:Segoe UI,'Microsoft YaHei',sans-serif;color:var(--ink);font-size:15px}
header{background:#0f3557;color:white;padding:14px 22px;display:flex;align-items:center;justify-content:space-between}
header h1{font-size:20px;margin:0;font-weight:650} header .addr{font-size:13px;color:#cfe0ef}
nav{display:flex;gap:8px;padding:12px 20px;background:white;border-bottom:1px solid var(--line);position:sticky;top:0;z-index:2}
button,.btn{border:1px solid var(--line);background:white;padding:8px 11px;border-radius:6px;cursor:pointer;color:var(--ink);text-decoration:none}
button.active{background:#e7f0f9;border-color:#9bbadc;color:#0b4f8b} input,select{padding:9px;border:1px solid var(--line);border-radius:6px;font:inherit}
main{padding:18px 22px;max-width:1400px;margin:0 auto}.view{display:none}.view.active{display:block}
.grid{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px}.card{background:white;border:1px solid var(--line);border-radius:8px;padding:14px}
.card h3{margin:0 0 8px;font-size:14px;color:var(--muted);font-weight:550}.num{font-size:26px;font-weight:700;color:#0f3557}
.split{display:grid;grid-template-columns:340px 1fr;gap:14px}.panel{background:white;border:1px solid var(--line);border-radius:8px;padding:14px;margin-bottom:14px}
table{width:100%;border-collapse:collapse;background:white} th,td{border-bottom:1px solid var(--line);padding:8px;vertical-align:top;text-align:left} th{color:#435469;background:#f8fafc;font-weight:650}
.pill{display:inline-block;padding:2px 7px;border-radius:999px;background:#edf2f7;margin:1px;font-size:12px}.ok{color:var(--green)}.bad{color:var(--red)}
pre{white-space:pre-wrap;background:#f7f9fb;border:1px solid var(--line);padding:10px;border-radius:6px;max-height:260px;overflow:auto}
.path{font-family:Consolas,monospace;font-size:12px;word-break:break-all;color:#394b5d}.thumb{max-width:280px;max-height:180px;border:1px solid var(--line);border-radius:6px;background:#fff;margin:4px}
.muted{color:var(--muted)}.toolbar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
</style>
<header><h1>真实历史股票案卷库 V0.1</h1><div class="addr" id="addr"></div></header>
<nav>
  <button data-view="home" class="active">首页</button>
  <button data-view="today">今日变化</button>
  <button data-view="search">股票搜索</button>
  <button data-view="detail">案卷详情</button>
  <button data-view="compare">案卷对比</button>
  <button data-view="diagnostics">诊断中心</button>
  <a class="btn" href="/report" target="_blank">数据考古报告</a>
</nav>
<main>
  <section id="home" class="view active"></section>
  <section id="today" class="view"></section>
  <section id="search" class="view"></section>
  <section id="detail" class="view"></section>
  <section id="compare" class="view"></section>
  <section id="diagnostics" class="view"></section>
</main>
<script>
const $=s=>document.querySelector(s); const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const api=p=>fetch(p).then(r=>r.json()); let currentStock=null, currentCases=[];
document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>show(b.dataset.view));
function show(id){document.querySelectorAll('.view').forEach(v=>v.classList.remove('active'));document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.view===id));$('#'+id).classList.add('active'); if(id==='diagnostics') loadDiag(); if(id==='today') loadToday();}
function table(rows, cols){return `<table><thead><tr>${cols.map(c=>`<th>${esc(c[1])}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${cols.map(c=>`<td>${typeof c[0]==='function'?c[0](r):esc(r[c[0]])}</td>`).join('')}</tr>`).join('')}</tbody></table>`}
function caseLink(id){return `<button onclick="loadCase('${esc(id)}')">查看</button>`}
function fileLink(path,label){return `<a href="/file?path=${encodeURIComponent(path)}" target="_blank">${esc(label||path.split(/[\\\\/]/).pop())}</a>`}
async function loadHome(){let d=await api('/api/summary'); $('#addr').textContent=location.href; $('#home').innerHTML=`
<div class="grid"><div class="card"><h3>已收录股票</h3><div class="num">${d.stock_count}</div></div><div class="card"><h3>已收录案卷</h3><div class="num">${d.case_count}</div></div><div class="card"><h3>运行日期范围</h3><b>${esc(d.earliest_run)}</b><br><span class="muted">至 ${esc(d.latest_run)}</span></div><div class="card"><h3>无法解析文件</h3><div class="num">${d.unparsed_count}</div></div></div>
<div class="two"><div class="panel"><h2>数据质量等级分布</h2>${table(d.quality_distribution,[['data_quality','等级'],['count','数量']])}</div><div class="panel"><h2>成功率最低模块</h2>${table(d.lowest_success_modules,[['module_name','模块'],['failed_count','失败'],['total_count','记录']])}</div></div>
<div class="panel"><h2>最近导入时间</h2><p>${esc(d.recent_import_time)}</p><h2>最近新增/最新案卷</h2>${table(d.recent_cases,[[r=>caseLink(r.case_id),'操作'],['stock_code','代码'],['stock_name','名称'],['run_time','运行时间'],['data_quality','质量'],['file_count','文件']])}</div>`}
function renderSearch(){ $('#search').innerHTML=`<div class="panel"><div class="toolbar"><input id="q" placeholder="输入股票代码或名称，例如 002558 / 巨人网络" style="min-width:360px"><button onclick="doSearch()">搜索</button></div><div id="searchResult"></div></div><div id="stockTimeline"></div>`}
async function doSearch(){let q=$('#q').value.trim(); let d=await api('/api/stocks?q='+encodeURIComponent(q)); $('#searchResult').innerHTML=table(d.items,[[r=>`<button onclick="loadStock('${esc(r.stock_code)}')">打开</button>`,'操作'],['stock_code','代码'],['stock_name','名称'],['case_count','案卷数'],['first_run_time','最早'],['last_run_time','最晚']]);}
async function loadStock(code){currentStock=code;let d=await api('/api/stock?code='+encodeURIComponent(code));currentCases=d.cases;$('#stockTimeline').innerHTML=`<div class="panel"><h2>${esc(code)} ${esc(d.stock?.stock_name||'')}</h2>${table(d.cases,[[r=>caseLink(r.case_id),'案卷'],['run_time','运行时间'],['trade_date','日期'],['data_quality','质量'],['module_success','成功模块'],['module_failed','失败模块'],[r=>r.data_sources.map(x=>`<span class=pill>${esc(x)}</span>`).join(''),'数据源'],[r=>r.has_humanview?'是':'否','HumanView'],[r=>r.has_radardata?'是':'否','RadarData'],[r=>r.has_charts?'是':'否','图表'],['radar_root','原始案卷路径']])}</div>`;renderCompareSelectors();}
async function loadCase(id){show('detail');let d=await api('/api/case?id='+encodeURIComponent(id));let c=d.case;if(!c){$('#detail').innerHTML='<div class=panel>未找到案卷</div>';return;}$('#detail').innerHTML=`<div class="panel"><h2>${esc(c.stock_code)} ${esc(c.stock_name)} / ${esc(c.run_time||c.trade_date)}</h2><p><span class=pill>质量 ${esc(c.data_quality)}</span><span class=pill>成功模块 ${c.module_success}</span><span class=pill>失败模块 ${c.module_failed}</span><span class=pill>字段覆盖率 ${c.field_coverage}</span></p><p class=path>${esc(c.canonical_root||'')}</p></div>
<div class="two"><div class="panel"><h2>成功/失败模块</h2>${table(d.modules,[[r=>r.ok?'<span class=ok>成功</span>':'<span class=bad>失败</span>','状态'],['module_name','模块'],['status','代码'],['rows','行'],['error','错误']])}</div><div class="panel"><h2>缺失与警告</h2><b>缺失内容</b><pre>${esc((c.missing||[]).join('\\n')||'无')}</pre><b>解析警告</b><pre>${esc((c.warnings||[]).join('\\n')||'无')}</pre></div></div>
<div class="panel"><h2>HTML 报告入口 / PNG 图表预览</h2>${(c.html_entries||[]).map(p=>fileLink(p,'打开 HTML 报告')).join(' | ')||'无'}<div>${(c.png_entries||[]).slice(0,12).map(p=>`<a href="/file?path=${encodeURIComponent(p)}" target="_blank"><img class=thumb src="/file?path=${encodeURIComponent(p)}"></a>`).join('')}</div></div>
<div class="panel"><h2>主要 JSON 字段摘要</h2><pre>${esc(JSON.stringify((c.json_summary||[]).slice(0,8),null,2))}</pre></div>
<div class="panel"><h2>CSV 表格预览</h2>${(c.csv_preview||[]).slice(0,6).map(x=>`<h3>${esc(x.path)}</h3><pre>${esc(JSON.stringify(x.rows||x,null,2))}</pre>`).join('')||'无'}</div>
<div class="panel"><h2>Markdown/TXT 摘要</h2>${(c.text_summary||[]).slice(0,8).map(x=>`<h3>${esc(x.path)}</h3><pre>${esc(x.text_preview||'')}</pre>`).join('')||'无'}</div>
<div class="panel"><h2>已识别文件清单</h2>${table(d.files,[[r=>fileLink(r.path),'打开'],['role','角色'],['file_type','类型'],['size','大小'],['parse_status','解析'],['duplicate_of','重复源'],['path','绝对路径']])}</div>`}
function renderCompareSelectors(){let opts=currentCases.map(c=>`<option value="${esc(c.case_id)}">${esc(c.run_time||c.trade_date)} ${esc(c.case_id)}</option>`).join('');$('#compare').innerHTML=`<div class=panel><h2>案卷对比</h2><p class=muted>比较历史案卷内容和完整性，不生成投资结论。</p><div class=toolbar><select id=c1>${opts}</select><select id=c2>${opts}</select><button onclick="doCompare()">对比</button></div><div id=cmp></div></div>`}
async function doCompare(){let a=$('#c1').value,b=$('#c2').value;let d=await api(`/api/compare?left=${encodeURIComponent(a)}&right=${encodeURIComponent(b)}`);$('#cmp').innerHTML=`<div class=two><div><h3>左侧</h3><pre>${esc(JSON.stringify(d.left,null,2))}</pre></div><div><h3>右侧</h3><pre>${esc(JSON.stringify(d.right,null,2))}</pre></div></div><h3>字段比较</h3>${table(d.field_compare,[['field','字段'],['left','左'],['right','右'],[r=>r.changed?'变化':'一致','结果']])}<h3>模块变化</h3>${table(d.module_changes,[['module','模块'],['left_ok','左'],['right_ok','右']])}<div class=two><div><h3>新增文件</h3><pre>${esc((d.new_files||[]).join('\\n'))}</pre></div><div><h3>缺失文件</h3><pre>${esc((d.missing_files||[]).join('\\n'))}</pre></div></div>`}
async function loadDiag(){let d=await api('/api/diagnostics');$('#diagnostics').innerHTML=`<div class=panel><h2>无法解析文件</h2>${table(d.bad_files,[['case_id','案卷'],['error','错误'],['path','路径']])}</div><div class=panel><h2>重复文件</h2>${table(d.duplicates,[['case_id','案卷'],['path','路径'],['duplicate_of','重复源']])}</div><div class=panel><h2>残缺案卷</h2>${table(d.incomplete_cases,[['case_id','案卷'],['stock_code','代码'],['stock_name','名称'],['field_coverage','覆盖率'],['module_failed','失败模块'],[r=>(r.missing||[]).join(', '),'缺失']])}</div><div class=two><div class=panel><h2>结构版本差异</h2>${table(d.structure_versions,[['structure_signature','签名'],['count','数量']])}</div><div class=panel><h2>数据来源变化</h2><pre>${esc(JSON.stringify(d.source_changes,null,2))}</pre></div></div><div class=panel><h2>模块长期失败统计</h2>${table(d.module_failures,[['module_name','模块'],['failed_count','失败'],['total_count','总计']])}</div><div class=two><div class=panel><h2>最完整股票</h2>${table(d.most_complete_stocks,[['stock_code','代码'],['stock_name','名称'],['case_count','案卷'],['avg_coverage','平均覆盖']])}</div><div class=panel><h2>同日多次运行最多</h2>${table(d.most_intraday_runs,[['stock_code','代码'],['trade_date','日期'],['runs','运行次数']])}</div></div>`}
async function toggleMonitor(on){await api('/api/monitor/toggle?enabled='+(on?1:0));await loadToday();}
async function loadToday(){let d=await api('/api/today_changes');let m=await api('/api/monitor/status');let fieldRows=a=>(a||[]).map(x=>({field:x[0],count:x[1]}));$('#today').innerHTML=`
<div class="panel"><h2>监控状态</h2><p><span class=pill>${m.running?'运行中':'未运行'}</span><span class=pill>${m.enabled?'已开启':'已暂停'}</span><span class=pill>防抖 ${esc(m.debounce_seconds)} 秒</span></p><p class=muted>最后心跳：${esc(m.last_heartbeat)}　最后发现：${esc(m.last_event_time)}　最后导入：${esc(m.last_import_time)}</p><p class=path>${esc((m.watched_roots||[]).join ? (m.watched_roots||[]).join('\\n') : m.watched_roots)}</p>${m.last_error?`<pre>${esc(m.last_error)}</pre>`:''}<button onclick="toggleMonitor(${m.enabled?0:1})">${m.enabled?'暂停监控':'开启监控'}</button><button onclick="loadToday()">刷新</button></div>
<div class="grid"><div class="card"><h3>今日新增股票</h3><div class="num">${d.new_stocks.length}</div></div><div class="card"><h3>今日新增案卷</h3><div class="num">${d.new_cases.length}</div></div><div class="card"><h3>今日更新案卷</h3><div class="num">${d.updated_cases.length}</div></div><div class="card"><h3>无法解析文件</h3><div class="num">${d.unparsed_files.length}</div></div></div>
<div class="two"><div class="panel"><h2>自动导入批次</h2>${table(d.import_runs,[['id','批次'],['started_at','开始'],['finished_at','结束'],['changed_count','变更文件'],['duration_ms','耗时ms'],['success','成功']])}</div><div class="panel"><h2>文件监控事件</h2>${table(d.monitor_events,[['event_type','事件'],['status','状态'],['path','路径'],['old_path','原路径']])}</div></div>
<div class="two"><div class="panel"><h2>新增案卷</h2>${table(d.new_cases,[['stock_code','代码'],['stock_name','名称'],['case_id','案卷'],[r=>caseLink(r.case_id),'查看']])}</div><div class="panel"><h2>更新案卷</h2>${table(d.updated_cases,[['stock_code','代码'],['stock_name','名称'],['case_id','案卷'],[r=>`<pre>${esc(JSON.stringify(r.changed_fields,null,2))}</pre>`,'变化']])}</div></div>
<div class="two"><div class="panel"><h2>新增字段</h2>${table(fieldRows(d.field_added),[['field','字段'],['count','次数']])}</div><div class="panel"><h2>消失字段</h2>${table(fieldRows(d.field_removed),[['field','字段'],['count','次数']])}</div></div>
<div class="two"><div class="panel"><h2>数据源变化</h2><pre>${esc(JSON.stringify(d.source_changes,null,2))}</pre></div><div class="panel"><h2>模块成功/失败变化</h2><pre>${esc(JSON.stringify(d.module_changes,null,2))}</pre></div></div>
<div class="two"><div class="panel"><h2>数据质量等级变化</h2><pre>${esc(JSON.stringify(d.quality_changes,null,2))}</pre></div><div class="panel"><h2>无法解析文件</h2>${table(d.unparsed_files,[['case_id','案卷'],['error','错误'],['path','路径']])}</div></div>`}
renderSearch(); loadHome();
</script>"""


class CaseLibraryHandler(BaseHTTPRequestHandler):
    db_path: Path = DEFAULT_DB
    legacy_root: Path = DEFAULT_LEGACY_ROOT
    output_dir: Path = DEFAULT_OUTPUT_DIR
    monitor: CaseLibraryMonitor | None = None

    def log_message(self, format: str, *args: Any) -> None:
        print("[case-library]", format % args)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/":
                return text_response(self, index_html())
            if parsed.path == "/api/summary":
                return json_response(self, summary(self.db_path))
            if parsed.path == "/api/stocks":
                return json_response(self, search_stocks(self.db_path, query.get("q", [""])[0]))
            if parsed.path == "/api/stock":
                return json_response(self, stock_detail(self.db_path, query.get("code", [""])[0]))
            if parsed.path == "/api/case":
                return json_response(self, case_detail(self.db_path, query.get("id", [""])[0]))
            if parsed.path == "/api/compare":
                return json_response(self, compare_cases(self.db_path, query.get("left", [""])[0], query.get("right", [""])[0]))
            if parsed.path == "/api/diagnostics":
                return json_response(self, diagnostics(self.db_path))
            if parsed.path == "/api/today_changes":
                return json_response(self, today_changes(self.db_path))
            if parsed.path == "/api/monitor/status":
                return json_response(self, monitor_status(self.db_path, self.monitor))
            if parsed.path == "/api/monitor/toggle":
                if self.monitor is None:
                    return json_response(self, {"error": "monitor_not_available"}, 409)
                enabled = query.get("enabled", ["1"])[0] not in {"0", "false", "False", "off"}
                self.monitor.set_enabled(enabled)
                return json_response(self, self.monitor.status())
            if parsed.path == "/report":
                report = self.output_dir / "数据考古发现.html"
                return self.serve_file(report)
            if parsed.path == "/file":
                return self.serve_legacy_file(query.get("path", [""])[0])
            return text_response(self, "Not found", 404, "text/plain; charset=utf-8")
        except Exception as exc:
            return json_response(self, {"error": f"{type(exc).__name__}: {exc}"}, 500)

    def serve_legacy_file(self, requested: str) -> None:
        path = Path(urllib.parse.unquote(requested)).resolve()
        allowed = [self.legacy_root.resolve(), PROJECT_ROOT.resolve()]
        if not any(str(path).lower().startswith(str(root).lower()) for root in allowed):
            return text_response(self, "Forbidden", 403, "text/plain; charset=utf-8")
        return self.serve_file(path)

    def serve_file(self, path: Path) -> None:
        if not path.exists() or not path.is_file():
            return text_response(self, "File not found", 404, "text/plain; charset=utf-8")
        content_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def create_server(
    db_path: Path = DEFAULT_DB,
    legacy_root: Path = DEFAULT_LEGACY_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    host: str = "127.0.0.1",
    port: int = 8765,
    monitor: CaseLibraryMonitor | None = None,
) -> ThreadingHTTPServer:
    class Handler(CaseLibraryHandler):
        pass

    Handler.db_path = db_path
    Handler.legacy_root = legacy_root
    Handler.output_dir = output_dir
    Handler.monitor = monitor
    return ThreadingHTTPServer((host, port), Handler)


def serve(
    db_path: Path = DEFAULT_DB,
    legacy_root: Path = DEFAULT_LEGACY_ROOT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = False,
    monitor: CaseLibraryMonitor | None = None,
) -> ThreadingHTTPServer:
    server: ThreadingHTTPServer | None = None
    candidate_ports = [port] if port == 0 else [port, *range(port + 1, port + 20)]
    last_error: OSError | None = None
    for candidate in candidate_ports:
        try:
            server = create_server(db_path, legacy_root, output_dir, host, candidate, monitor=monitor)
            break
        except OSError as exc:
            last_error = exc
            continue
    if server is None:
        raise last_error or OSError("无法启动本地服务")
    url = f"http://{host}:{server.server_address[1]}/"
    print(f"历史案卷库工作台已启动：{url}")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    if monitor is not None:
        monitor.start()
        print("历史案卷库文件监控已启动")
    try:
        server.serve_forever()
    finally:
        if monitor is not None:
            monitor.stop()
        server.server_close()
    return server


def launch(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导入旧项目历史案卷并启动本地工作台。")
    parser.add_argument("--legacy-root", default=os.environ.get("STOCK_SELECTOR_LEGACY_ROOT", str(DEFAULT_LEGACY_ROOT)))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-import", action="store_true")
    parser.add_argument("--no-monitor", action="store_true")
    parser.add_argument("--monitor-interval", type=float, default=1.0)
    parser.add_argument("--monitor-debounce", type=float, default=2.0)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args(argv)
    legacy_root = Path(args.legacy_root)
    db_path = Path(args.db)
    output_dir = Path(args.output_dir)
    if not args.no_import:
        print("正在执行增量索引，请稍候...")
        summary_data = import_legacy_cases(legacy_root, db_path, output_dir)
        print(f"索引完成：股票 {summary_data['stock_count']}，案卷 {summary_data['recognized_cases']}，文件 {summary_data['scanned_files']}")
    monitor = None
    if not args.no_monitor:
        monitor = CaseLibraryMonitor(
            legacy_root=legacy_root,
            db_path=db_path,
            output_dir=output_dir,
            interval_seconds=args.monitor_interval,
            debounce_seconds=args.monitor_debounce,
        )
    serve(db_path, legacy_root, output_dir, args.host, args.port, args.open_browser, monitor=monitor)
    return 0


if __name__ == "__main__":
    raise SystemExit(launch())
