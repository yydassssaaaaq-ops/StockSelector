from __future__ import annotations

import csv
import html
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from stock_selector.backtest.engine import BacktestResult


@dataclass(frozen=True)
class BacktestOutputPaths:
    run_dir: Path
    report_html: Path
    summary_json: Path
    periods_csv: Path
    holdings_csv: Path
    failures_csv: Path
    universe_csv: Path
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


def pct(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value * 100:.2f}%"


def number(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        return str(value)
    return f"{value:.4f}"


def flatten_periods(result: BacktestResult) -> list[dict[str, Any]]:
    rows = []
    for period in result.periods:
        rows.append(
            {
                "signal_date": period.signal_date,
                "entry_date": period.entry_date,
                "exit_date": period.exit_date,
                "selected_count": period.selected_count,
                "held_count": period.held_count,
                "gross_return": period.gross_return,
                "cost_impact": period.cost_impact,
                "net_return": period.net_return,
                "benchmark_return": period.benchmark_return,
                "universe_equal_weight_return": period.universe_equal_weight_return,
                "single_factor_baseline_return": period.single_factor_baseline_return,
                "turnover": period.turnover,
                "trade_count": period.trade_count,
                "cash_weight": period.cash_weight,
                "missing_signal_bars": period.missing_signal_bars,
                "blocked_entries": period.blocked_entries,
                "blocked_exits": period.blocked_exits,
                "factor_audit": period.factor_audit,
            }
        )
    return rows


def flatten_holdings(result: BacktestResult) -> list[dict[str, Any]]:
    rows = []
    for period in result.periods:
        for holding in period.holdings:
            row = holding.as_dict()
            row["period_signal_date"] = period.signal_date
            row["period_net_return"] = period.net_return
            row["period_benchmark_return"] = period.benchmark_return
            rows.append(row)
    return rows


def drawdown_values(returns: list[float]) -> list[float]:
    equity = 1.0
    peak = 1.0
    values = []
    for value in returns:
        equity *= 1.0 + value
        peak = max(peak, equity)
        values.append(equity / peak - 1.0)
    return values


def svg_line(values: list[float], *, stroke: str, height: int = 170, width: int = 760) -> str:
    if not values:
        return "<div class=\"muted\">无有效数据</div>"
    low = min(values)
    high = max(values)
    if high == low:
        high += 0.01
        low -= 0.01
    points = []
    for index, value in enumerate(values):
        x = index / max(1, len(values) - 1) * width
        y = height - (value - low) / (high - low) * height
        points.append(f"{x:.1f},{y:.1f}")
    zero_y = height - (0.0 - low) / (high - low) * height if low <= 0 <= high else height
    return (
        f"<svg viewBox=\"0 0 {width} {height}\" role=\"img\">"
        f"<line x1=\"0\" y1=\"{zero_y:.1f}\" x2=\"{width}\" y2=\"{zero_y:.1f}\" stroke=\"#cfd7df\"/>"
        f"<polyline fill=\"none\" stroke=\"{stroke}\" stroke-width=\"2\" points=\"{' '.join(points)}\"/>"
        "</svg>"
    )


def metrics_table(title: str, metrics: dict[str, Any]) -> str:
    labels = {
        "cumulative_return": "累计收益",
        "annualized_return": "年化收益",
        "max_drawdown": "最大回撤",
        "annualized_volatility": "年化波动率",
        "sharpe_ratio": "夏普比率",
        "win_rate": "胜率",
        "average_period_return": "平均单期收益",
        "best_period_return": "最好单期收益",
        "worst_period_return": "最差单期收益",
        "turnover_rate": "换手率",
        "trade_count": "交易次数",
        "effective_periods": "有效回测期数",
        "excess_cumulative_return": "相对基准超额收益",
    }
    rows = []
    for key, label in labels.items():
        value = metrics.get(key)
        if key.endswith("return") or key in {"max_drawdown", "annualized_volatility", "win_rate", "turnover_rate"}:
            display = pct(value)
        else:
            display = number(value)
        rows.append(f"<tr><td>{html.escape(label)}</td><td>{html.escape(display)}</td></tr>")
    return f"<h3>{html.escape(title)}</h3><table><tbody>{''.join(rows)}</tbody></table>"


def period_rows(result: BacktestResult) -> str:
    rows = []
    for period in result.periods:
        rows.append(
            "<tr>"
            f"<td>{html.escape(period.signal_date)}</td>"
            f"<td>{html.escape(period.entry_date)}</td>"
            f"<td>{html.escape(period.exit_date)}</td>"
            f"<td>{period.selected_count}</td>"
            f"<td>{period.held_count}</td>"
            f"<td>{pct(period.net_return)}</td>"
            f"<td>{pct(period.benchmark_return)}</td>"
            f"<td>{pct(period.universe_equal_weight_return)}</td>"
            f"<td>{pct(period.single_factor_baseline_return)}</td>"
            f"<td>{pct(period.cost_impact)}</td>"
            f"<td>{pct(period.turnover)}</td>"
            f"<td>{pct(period.cash_weight)}</td>"
            f"<td>{period.trade_count}</td>"
            f"<td>{html.escape(','.join(period.blocked_entries))}</td>"
            f"<td>{html.escape(','.join(period.blocked_exits))}</td>"
            "</tr>"
        )
    return "".join(rows)


def holding_rows(result: BacktestResult, limit: int = 300) -> str:
    rows = []
    for period in result.periods:
        for holding in period.holdings:
            rows.append(
                "<tr>"
                f"<td>{html.escape(period.signal_date)}</td>"
                f"<td>{holding.rank}</td>"
                f"<td>{html.escape(holding.code)}</td>"
                f"<td>{html.escape(holding.name)}</td>"
                f"<td>{holding.score:.3f}</td>"
                f"<td>{pct(holding.weight)}</td>"
                f"<td>{pct(holding.gross_return)}</td>"
                f"<td>{html.escape(json.dumps(holding.score_parts, ensure_ascii=False))}</td>"
                f"<td>{pct(holding.data_completeness)}</td>"
                f"<td>{html.escape(';'.join(holding.execution_notes))}</td>"
                "</tr>"
            )
            if len(rows) >= limit:
                rows.append("<tr><td colspan=\"10\">更多持仓请查看 holdings.csv</td></tr>")
                return "".join(rows)
    return "".join(rows)


def failure_rows(result: BacktestResult) -> str:
    if not result.data_failures:
        return "<tr><td colspan=\"4\">无单票历史数据失败</td></tr>"
    return "".join(
        "<tr>"
        f"<td>{html.escape(item.code)}</td>"
        f"<td>{html.escape(item.name)}</td>"
        f"<td>{html.escape(item.source)}</td>"
        f"<td>{html.escape(item.error)}</td>"
        "</tr>"
        for item in result.data_failures
    )


def render_html(result: BacktestResult, paths: BacktestOutputPaths) -> str:
    data = result.as_dict()
    strategy_returns = [period.net_return or 0.0 for period in result.periods]
    benchmark_returns = [period.benchmark_return or 0.0 for period in result.periods]
    strategy_curve = [item["strategy_cumulative_return"] or 0.0 for item in result.equity_curve]
    benchmark_curve = [item["benchmark_cumulative_return"] or 0.0 for item in result.equity_curve]
    equal_curve = [item["universe_equal_weight_cumulative_return"] or 0.0 for item in result.equity_curve]
    single_curve = [item["single_factor_trend_20d_cumulative_return"] or 0.0 for item in result.equity_curve]
    drawdowns = drawdown_values(strategy_returns)
    benchmark_drawdowns = drawdown_values(benchmark_returns)
    best_period = max(result.periods, key=lambda item: item.net_return or -999.0, default=None)
    worst_period = min(result.periods, key=lambda item: item.net_return or 999.0, default=None)
    return f"""<!doctype html>
<meta charset="utf-8">
<title>A股可信历史验证回测</title>
<style>
body{{font-family:Segoe UI,'Microsoft YaHei',sans-serif;margin:28px;color:#202933;background:#f7f8fa;line-height:1.55}}
h1{{margin:0 0 6px;color:#12385f}} h2{{margin-top:26px;color:#12385f}} h3{{margin-bottom:8px;color:#2b455f}}
.muted{{color:#657381}} .warn{{background:#fff7e6;border:1px solid #e8c878;padding:10px 12px;border-radius:6px}}
.summary{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px;margin:16px 0}}
.summary div{{background:white;border:1px solid #dce4ec;border-radius:8px;padding:12px}}
.num{{font-size:24px;font-weight:700;color:#0d5f85}}
table{{width:100%;border-collapse:collapse;background:white;font-size:13px;margin:8px 0 14px}} th,td{{border:1px solid #d9e1ea;padding:7px;text-align:left;vertical-align:top}} th{{background:#eaf1f7}}
pre{{white-space:pre-wrap;background:#fff;border:1px solid #d9e1ea;border-radius:6px;padding:10px;max-height:360px;overflow:auto}}
svg{{width:100%;height:180px;background:white;border:1px solid #d9e1ea;border-radius:6px}}
</style>
<h1>A股可信历史验证回测</h1>
<div class="muted">区间：{html.escape(result.config.start_date)} 至 {html.escape(result.config.end_date)}；策略：{html.escape(result.config.strategy.strategy_id)}；基准：{html.escape(result.config.benchmark_name)}；成交：信号日后下一交易日开盘。</div>
<p class="warn">本报告基于真实公开历史行情生成，不构成投资建议。若结果较差，仍按原始结果保留。</p>

<h2>回测概览</h2>
<div class="summary">
  <div><b>股票池数量</b><div class="num">{result.config.universe_size}</div></div>
  <div><b>历史数据成功</b><div class="num">{result.data_audit.get("loaded_series")}</div></div>
  <div><b>有效期数</b><div class="num">{result.strategy_metrics.effective_periods}</div></div>
  <div><b>相对基准</b><div class="num">{pct(result.strategy_metrics.excess_cumulative_return)}</div></div>
</div>
{metrics_table("策略指标", data["strategy_metrics"])}
{metrics_table("基准指标", data["benchmark_metrics"])}
{"".join(metrics_table('基线：' + html.escape(name), metrics.as_dict()) for name, metrics in result.baseline_metrics.items())}

<h2>策略收益与比较基线</h2>
<p class="muted">蓝线为策略累计收益，灰线为沪深 300，绿色为股票池等权，橙色为 20 日趋势单因子。</p>
{svg_line(strategy_curve, stroke="#0d6b99")}
{svg_line(benchmark_curve, stroke="#6b7280")}
{svg_line(equal_curve, stroke="#237a57")}
{svg_line(single_curve, stroke="#bd6b00")}

<h2>最大回撤</h2>
<p class="muted">蓝线为策略回撤，灰线为基准回撤。</p>
{svg_line(drawdowns, stroke="#0d6b99")}
{svg_line(benchmark_drawdowns, stroke="#6b7280")}

<h2>每期选股结果与收益</h2>
<table><thead><tr><th>信号日</th><th>买入日</th><th>卖出日</th><th>入选</th><th>持仓</th><th>策略收益</th><th>基准收益</th><th>等权基线</th><th>单因子基线</th><th>成本滑点</th><th>换手</th><th>现金</th><th>交易数</th><th>买入阻断</th><th>卖出阻断</th></tr></thead><tbody>{period_rows(result)}</tbody></table>

<h2>每期持仓与收益</h2>
<table><thead><tr><th>信号日</th><th>排名</th><th>代码</th><th>名称</th><th>分数</th><th>权重</th><th>持仓收益</th><th>因子贡献</th><th>完整性</th><th>执行说明</th></tr></thead><tbody>{holding_rows(result)}</tbody></table>

<h2>交易成本与滑点影响</h2>
<p>交易成本参数：{pct(result.config.transaction_cost_rate)}；滑点参数：{pct(result.config.slippage_rate)}；平均换手：{pct(result.strategy_metrics.turnover_rate)}；总交易次数：{result.strategy_metrics.trade_count}。</p>

<h2>最好和最差时期</h2>
<table><thead><tr><th>类型</th><th>信号日</th><th>退出日</th><th>策略收益</th><th>基准收益</th></tr></thead><tbody>
<tr><td>最好</td><td>{html.escape(best_period.signal_date if best_period else "")}</td><td>{html.escape(best_period.exit_date if best_period else "")}</td><td>{pct(best_period.net_return if best_period else None)}</td><td>{pct(best_period.benchmark_return if best_period else None)}</td></tr>
<tr><td>最差</td><td>{html.escape(worst_period.signal_date if worst_period else "")}</td><td>{html.escape(worst_period.exit_date if worst_period else "")}</td><td>{pct(worst_period.net_return if worst_period else None)}</td><td>{pct(worst_period.benchmark_return if worst_period else None)}</td></tr>
</tbody></table>

<h2>数据缺失情况</h2>
<table><thead><tr><th>代码</th><th>名称</th><th>数据源</th><th>失败原因</th></tr></thead><tbody>{failure_rows(result)}</tbody></table>

<h2>数据源使用情况</h2>
<pre>{html.escape(json.dumps(result.data_audit, ensure_ascii=False, indent=2))}</pre>

<h2>策略身份与因子定义</h2>
<pre>{html.escape(json.dumps(result.config.strategy.as_dict(), ensure_ascii=False, indent=2))}</pre>

<h2>回测参数</h2>
<pre>{html.escape(json.dumps(result.config.as_dict(), ensure_ascii=False, indent=2))}</pre>

<h2>风险与偏差说明</h2>
<ul>{"".join(f"<li>{html.escape(item)}</li>" for item in result.warnings)}</ul>

<h2>当前规则是否具有初步历史价值</h2>
<p>{html.escape(result.conclusion)}</p>

<h2>输出文件</h2>
<ul>
  <li>summary JSON：{html.escape(str(paths.summary_json))}</li>
  <li>periods CSV：{html.escape(str(paths.periods_csv))}</li>
  <li>holdings CSV：{html.escape(str(paths.holdings_csv))}</li>
  <li>failures CSV：{html.escape(str(paths.failures_csv))}</li>
  <li>universe CSV：{html.escape(str(paths.universe_csv))}</li>
</ul>
"""


def write_backtest_outputs(
    *,
    run_id: str,
    result: BacktestResult,
    output_dir: Path,
    universe_rows: list[dict[str, Any]] | None = None,
) -> BacktestOutputPaths:
    run_dir = output_dir / run_id
    report_html = run_dir / "report.html"
    summary_json = run_dir / "summary.json"
    periods_csv = run_dir / "periods.csv"
    holdings_csv = run_dir / "holdings.csv"
    failures_csv = run_dir / "failures.csv"
    universe_csv = run_dir / "universe.csv"
    latest_html = output_dir / "latest.html"
    run_dir.mkdir(parents=True, exist_ok=True)

    write_csv(periods_csv, flatten_periods(result))
    write_csv(holdings_csv, flatten_holdings(result))
    write_csv(failures_csv, [item.as_dict() for item in result.data_failures])
    write_csv(universe_csv, universe_rows or [])
    paths = BacktestOutputPaths(
        run_dir=run_dir,
        report_html=report_html,
        summary_json=summary_json,
        periods_csv=periods_csv,
        holdings_csv=holdings_csv,
        failures_csv=failures_csv,
        universe_csv=universe_csv,
        latest_html=latest_html,
    )
    summary = result.as_dict()
    summary["paths"] = paths.as_dict()
    summary["run_id"] = run_id
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_html.write_text(render_html(result, paths), encoding="utf-8")
    latest_html.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(report_html, latest_html)
    return paths
