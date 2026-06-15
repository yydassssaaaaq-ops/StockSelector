from __future__ import annotations

import csv
import html
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stock_selector.data.eastmoney import AShareQuote
from stock_selector.screening.momentum_liquidity import ScreenResult


@dataclass(frozen=True)
class ScreenOutputPaths:
    run_dir: Path
    raw_csv: Path
    candidates_csv: Path
    summary_json: Path
    report_html: Path
    latest_html: Path

    def as_dict(self) -> dict[str, str]:
        return {key: str(value) for key, value in self.__dict__.items()}


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key)) for key in fieldnames})


def format_cny(value: float | None) -> str:
    if value is None:
        return ""
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    if abs_value >= 100_000_000:
        return f"{sign}{abs_value / 100_000_000:.2f} 亿"
    if abs_value >= 10_000:
        return f"{sign}{abs_value / 10_000:.2f} 万"
    return f"{value:.2f}"


def quote_url(exchange: str, code: str) -> str:
    prefix = {"SH": "sh", "SZ": "sz", "BJ": "bj"}.get(exchange, "")
    return f"https://quote.eastmoney.com/{prefix}{code}.html" if prefix else "https://quote.eastmoney.com/"


def candidate_row(item: dict[str, Any]) -> str:
    code = html.escape(str(item["code"]))
    name = html.escape(str(item["name"]))
    url = html.escape(quote_url(str(item["exchange"]), str(item["code"])))
    return (
        "<tr>"
        f"<td>{item['rank']}</td>"
        f"<td><a href=\"{url}\" target=\"_blank\">{code}</a></td>"
        f"<td>{name}</td>"
        f"<td>{html.escape(str(item['board']))}</td>"
        f"<td>{item['score']:.3f}</td>"
        f"<td>{item.get('latest_price') or ''}</td>"
        f"<td>{item.get('pct_change') or ''}%</td>"
        f"<td>{format_cny(item.get('amount'))}</td>"
        f"<td>{item.get('turnover_rate') or ''}%</td>"
        f"<td>{format_cny(item.get('main_net_inflow'))}</td>"
        f"<td>{item.get('main_net_inflow_pct') or ''}%</td>"
        f"<td>{item.get('pe_ttm') or ''}</td>"
        f"<td>{item.get('pb') or ''}</td>"
        f"<td>{item.get('amplitude') or ''}%</td>"
        f"<td>{html.escape(str(item.get('quote_time') or ''))}</td>"
        "</tr>"
    )


def rejection_rows(rejections: dict[str, int]) -> str:
    if not rejections:
        return "<tr><td>none</td><td>0</td></tr>"
    return "".join(
        f"<tr><td>{html.escape(reason)}</td><td>{count}</td></tr>"
        for reason, count in sorted(rejections.items(), key=lambda item: (-item[1], item[0]))
    )


def render_html(result: ScreenResult, metadata: dict[str, Any], paths: ScreenOutputPaths) -> str:
    data = result.as_dict()
    candidates = data["candidates"]
    config_json = html.escape(json.dumps(data["config"], ensure_ascii=False, indent=2))
    metadata_json = html.escape(json.dumps(metadata, ensure_ascii=False, indent=2))
    rows = "\n".join(candidate_row(item) for item in candidates)
    return f"""<!doctype html>
<meta charset="utf-8">
<title>A股真实行情选股快照</title>
<style>
body{{font-family:Segoe UI,'Microsoft YaHei',sans-serif;margin:28px;color:#1f2a33;background:#f6f8fb;line-height:1.55}}
h1{{margin:0 0 6px;color:#12385f}} h2{{margin-top:24px;color:#12385f}}
.muted{{color:#667789}} .warn{{background:#fff7e6;border:1px solid #f0cf8a;padding:10px 12px;border-radius:6px}}
.grid{{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:12px;margin:18px 0}}
.card{{background:white;border:1px solid #d9e1ea;border-radius:8px;padding:12px}} .num{{font-size:25px;font-weight:700;color:#0d5f85}}
table{{width:100%;border-collapse:collapse;background:white;font-size:13px}} th,td{{border:1px solid #d9e1ea;padding:7px;text-align:left;vertical-align:top}} th{{background:#eaf1f7}}
a{{color:#0b5cad;text-decoration:none}} pre{{white-space:pre-wrap;background:#fff;border:1px solid #d9e1ea;border-radius:6px;padding:10px;max-height:360px;overflow:auto}}
</style>
<h1>A股真实行情选股快照</h1>
<div class="muted">生成时间：{html.escape(str(metadata.get("fetched_at")))}；数据源：{html.escape(str(metadata.get("source_name")))}</div>
<p class="warn">本报告是工程验证用的规则筛选结果，只说明数据链路和排序逻辑已跑通，不构成投资建议、收益承诺或交易指令。</p>
<div class="grid">
  <div class="card"><b>行情记录</b><div class="num">{data["total_quotes"]}</div></div>
  <div class="card"><b>过滤后股票</b><div class="num">{data["accepted_before_top_n"]}</div></div>
  <div class="card"><b>展示候选</b><div class="num">{len(candidates)}</div></div>
  <div class="card"><b>原始接口总数</b><div class="num">{metadata.get("reported_total")}</div></div>
</div>
<h2>候选股票 Top {len(candidates)}</h2>
<table>
<thead><tr><th>排名</th><th>代码</th><th>名称</th><th>板块</th><th>分数</th><th>现价</th><th>涨跌幅</th><th>成交额</th><th>换手率</th><th>主力净流入</th><th>主力净占比</th><th>PE(TTM)</th><th>PB</th><th>振幅</th><th>行情时间</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<h2>过滤原因计数</h2>
<table><thead><tr><th>原因</th><th>次数</th></tr></thead><tbody>{rejection_rows(data["rejection_counts"])}</tbody></table>
<h2>运行文件</h2>
<ul>
  <li>候选 CSV：{html.escape(str(paths.candidates_csv))}</li>
  <li>原始行情 CSV：{html.escape(str(paths.raw_csv))}</li>
  <li>摘要 JSON：{html.escape(str(paths.summary_json))}</li>
</ul>
<h2>筛选配置</h2>
<pre>{config_json}</pre>
<h2>数据源元信息</h2>
<pre>{metadata_json}</pre>
"""


def write_screen_outputs(
    *,
    run_id: str,
    quotes: list[AShareQuote],
    result: ScreenResult,
    metadata: dict[str, Any],
    output_root: Path,
    raw_root: Path,
) -> ScreenOutputPaths:
    run_dir = output_root / run_id
    raw_csv = raw_root / f"{run_id}_quotes.csv"
    candidates_csv = run_dir / "candidates.csv"
    summary_json = run_dir / "summary.json"
    report_html = run_dir / "report.html"
    latest_html = output_root / "latest.html"

    raw_rows = [quote.as_dict() for quote in quotes]
    candidate_rows = [item.as_dict() for item in result.candidates]
    write_csv(raw_csv, raw_rows)
    write_csv(candidates_csv, candidate_rows)

    paths = ScreenOutputPaths(
        run_dir=run_dir,
        raw_csv=raw_csv,
        candidates_csv=candidates_csv,
        summary_json=summary_json,
        report_html=report_html,
        latest_html=latest_html,
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "run_id": run_id,
        "metadata": metadata,
        "result": result.as_dict(),
        "paths": paths.as_dict(),
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_html.write_text(render_html(result, metadata, paths), encoding="utf-8")
    latest_html.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(report_html, latest_html)
    return paths
