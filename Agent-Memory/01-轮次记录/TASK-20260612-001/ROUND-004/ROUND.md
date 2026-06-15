# ROUND-004

## 基本信息

- 所属 TASK：TASK-20260612-001
- ROUND ID：ROUND-004
- 触发来源：用户跨项目产品化任务
- 本轮目标：在 StockSelector 中交付可双击启动、可浏览器验收、利用旧 L.Lawlight 真实数据的“真实历史股票案卷库 V0.1”。
- 起始时间：2026-06-15T00:21:33+08:00
- 起始分支：main
- 起始 HEAD：e3c9faa19704d7ce04ea735a2765fb7e65ff01f2
- 是否 Commit：否
- 是否 Push：否
- 是否修改旧项目：否，仅只读扫描 `D:\AAAAAAAAA项目\L.Lawlight\1`。

## 实际扫描

- `D:\AAAAAAAAA项目\L.Lawlight\1\RadarData`
- `D:\AAAAAAAAA项目\L.Lawlight\1\HumanView`
- 观察旧项目根目录、`local_sources`、`logs`，确认历史运行结果集中在 RadarData/HumanView。

## 真实导入结果

- 扫描目录数：433
- 扫描文件数：2430
- 识别股票数：9
- 识别案卷数：19
- 明确 run_id 运行记录数：13
- 重复文件数：1077
- 无法解析文件数：0
- 文件类型：`.csv`、`.parquet`、`.json`、`.txt`、`.log`、`.md`、`.png`、`.jsonl`、`.html`
- 质量等级分布：A 1，B 18
- 增量复跑：新增 0，更新 0，未变化 2430

## 本轮修改

- 新增 `src/stock_selector/case_library/importer.py`
- 新增 `src/stock_selector/case_library/webapp.py`
- 新增 `scripts/import_legacy_cases.py`
- 新增 `scripts/serve_case_library.py`
- 新增 `scripts/launch_case_library.py`
- 新增 `启动历史案卷库.bat`
- 新增 `docs/legacy_data_schema_map.md`
- 新增 `docs/case_library_usage.md`
- 新增 `tests/test_case_library.py`
- 生成 `data/processed/case_library.sqlite3`
- 生成 `outputs/case_library/import_summary.json`
- 生成 `outputs/case_library/数据考古发现.html`

## 验证记录

- `python scripts\import_legacy_cases.py`：退出码 0，通过；真实扫描 2430 文件，识别 9 股票、19 案卷。
- 第二次 `python scripts\import_legacy_cases.py`：退出码 0，通过；新增 0，更新 0，未变化 2430。
- `python -m unittest tests.test_case_library -v`：退出码 0，通过；12 项案卷库专项测试 OK。
- `python -m unittest discover -s tests -v`：退出码 0，通过；32 项测试 OK。
- HTTP 冒烟：`/`、`/api/stock?code=002558`、`/api/diagnostics` 均返回 200。
- 浏览器冒烟：首页显示 9 股票、19 案卷；搜索 `002558` 显示 10 个案卷；详情页、案卷对比、诊断中心均可打开。

## 当前结论

- 真实历史股票案卷库 V0.1 已达到自动验证可用状态。
- 本轮没有实现正式选股策略，没有生成投资结论。
- 当前验证等级：L2_AGENT_TESTED。
- 用户验证状态：not_run。
- 用户可双击 `启动历史案卷库.bat` 进行真实验收。
