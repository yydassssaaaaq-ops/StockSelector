# legacy_data_schema_map

本文件记录 StockSelector 对旧项目 `D:\AAAAAAAAA项目\L.Lawlight\1` 的真实只读调查结果。内容来自实际目录和文件扫描，不是理想化设计。

## 扫描范围

- `D:\AAAAAAAAA项目\L.Lawlight\1\RadarData`
- `D:\AAAAAAAAA项目\L.Lawlight\1\HumanView`
- 同时查看旧项目根目录、`local_sources` 和 `logs`。本次可导入的历史运行结果集中在 `RadarData` 与 `HumanView`；根目录脚本和说明文件不纳入案卷库。

## 总体规模

- `RadarData` + `HumanView` 实际扫描目录数：433
- 实际扫描文件数：2430
- 文件类型分布：
  - `.csv`：681
  - `.parquet`：564
  - `.json`：463
  - `.txt`：247
  - `.log`：236
  - `.md`：107
  - `.png`：63
  - `.jsonl`：41
  - `.html`：28

## 股票代码与股票名称

- `RadarData` 一级目录是 6 位股票代码，例如 `RadarData\002558`。
- `HumanView` 一级目录格式为 `股票代码_股票名称_日期`，例如 `HumanView\002558_巨人网络_2026-06-03`。
- `stock_timeline.json` 中有 `stock_code`、`stock_name`。
- `case_packet.json`、`agent_case_packet.json` 和 `data_quality_report.json` 中常见中文字段 `股票代码`、`股票名称`。
- 旧格式或残缺文件中名称可能缺失；导入时保存为 `null` 或后续由同案卷其他文件补齐。

## 运行日期、时间和案卷 ID

- 新格式运行目录：`RadarData\<code>\<YYYY-MM-DD>\runs\<run_id>`。
- `run_id` 真实格式：`YYYYMMDD_HHMMSS_session`，例如 `20260603_204337_post_close`。
- 同样的 run 目录在 `HumanView\<code>_<name>_<date>\runs\<run_id>` 中存在人类报告快照。
- `stock_runs_index.jsonl`、日期级 `runs_index.jsonl`、`run_manifest.json`、`latest_run.json` 和 `stock_timeline.json` 都可提供 `run_id`、`run_time`、`run_session`、`data_cutoff_time`。
- 旧格式日期目录没有明确 run_id，例如 `RadarData\002258\2026-06-02\packet\case_packet.json`；导入器以 `code:date:legacy` 建立兼容案卷，不伪造 run_id。

## 机器数据与人类报告

机器数据主要位于 `RadarData`：

- `packet\case_packet.json`
- `packet\agent_case_packet.json`
- `quality\data_quality_report.json`
- `quality\module_status.csv`
- `raw\*.csv` / `raw\*.parquet`
- `features\*.csv` / `features\*.parquet`
- `charts\*.csv` / `charts\*.parquet` / `charts\*.png`
- `observe\*.json`
- `predict\*.json`
- `logs\*_error.log`

人类报告主要位于 `HumanView`：

- `00_打开我.html`
- `00_人类摘要.md`
- `01_数据质量说明.txt`
- `02_核心观察点.txt`
- `03_次日观察任务.txt`
- `03_昨日观察验证.txt`
- `04_盘中预测输入.txt`
- `05_预测验证记录.txt`
- `06_信号含义与组合状态.txt`
- `tables\*.csv`
- `charts\*.png`
- `human_view_manifest.json`
- `machine_links\机器案卷路径.txt`
- `predict_links\机器预测文件路径.txt`

## 稳定可提取字段

- 股票：`stock_code` / `股票代码`，`stock_name` / `股票名称`
- 运行：`run_id`、`run_time`、`run_session`、`data_cutoff_time`
- 质量：`data_quality_grade` / `数据可信等级`
- 模块：`模块状态` 列表、`模块成功数`、`模块失败数`、`模块空结果数`
- 数据来源：`有效日K来源`、`备用源接管`、模块路径和模块名称中的来源标识
- 文件清单：`文件清单`、`file_manifest`、manifest 中的路径字段
- HumanView：`humanview_root`、`humanview_html_path`、`open_html`

## 同股票、同一天、多次运行

- `002558` 在 `2026-06-03` 存在 5 次运行：
  - `20260603_204337_post_close`
  - `20260603_204338_post_close`
  - `20260603_204806_post_close`
  - `20260603_205440_post_close`
  - `20260603_222204_post_close`
- 新格式中 `runs\<run_id>` 是历史快照真源；日期目录下的 `packet/observe/predict/quality/features/charts` 是 latest view，可能被后续运行覆盖。
- 导入器以 `stock_code + run_id` 区分新格式案卷，以 `stock_code + date + legacy` 区分旧格式案卷。

## 数据质量、模块状态和来源

- `data_quality_report.json` 中稳定存在 `数据可信等级`，本次真实导入发现等级分布为 `A: 1`、`B: 18`。
- `模块状态` 列表包含：
  - `name`
  - `ok`
  - `rows`
  - `cols`
  - `path`
  - `error`
  - `status`
  - `critical`
  - `usable_for_agent`
  - `reason`
  - `started_at`
  - `finished_at`
- 真实统计中常见失败模块包括 `概念板块-东财`、`个股信息-东财`、`日K-东财-前复权`、`行业板块-东财`、`日K-东财-不复权`。
- 常见数据源或接管记录包括 `tencent_qfq_backup`、`akshare_stock_zh_a_minute`、`tick_derived_fund_flow_proxy`。

## 重复、残缺和历史格式变化

- 重复文件大量存在，主要来自：
  - `case_packet.json` 与 `agent_case_packet.json` 内容相同或近似。
  - 日期级 latest view 与 `runs\<run_id>` 快照重复。
  - HumanView 日期级报告与 run 快照重复。
- 历史格式变化：
  - 旧格式：日期目录直接存放 `packet/quality/raw/features/charts/predict/observe`。
  - 新格式：日期目录下有 `runs\<run_id>`，并配套 `runs_index.jsonl`、`stock_runs_index.jsonl`、`stock_timeline.json`。
  - HumanView 同样从日期级目录演进为 `runs\<run_id>` 快照。
- 残缺案卷识别规则：
  - 缺少 `RadarData`
  - 缺少 `HumanView`
  - 缺少 HTML 报告
  - 缺少 PNG 图表
  - 存在模块失败
  - 存在无法解析文件

## 兼容策略

- 旧目录严格只读，所有索引和报告写入 StockSelector。
- 缺失字段保存为 `null`、`unknown` 或 `missing_json` 中的显式条目。
- 损坏 JSON 或异常文件进入 `import_errors` 与 `files.parse_status='error'`，不阻断整个导入。
- 相同 SHA-256 文件写入 `duplicates`，不删除、不移动旧文件。
- 第二次导入对 size/mtime 未变化的文件计为 `unchanged_file_count`，只处理新增或变化内容。

