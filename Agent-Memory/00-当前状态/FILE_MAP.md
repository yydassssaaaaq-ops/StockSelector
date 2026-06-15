# FILE_MAP

- `src/stock_selector/`：中性业务模块壳。
- `scripts/`：闭环自动化脚本。
- `tests/`：unittest 测试。
- `Agent-Memory/`：项目记忆、状态和轮次记录。
- `docs/`：架构、工作流、设计问题。
- `config/`：非敏感配置说明与样例入口。
- `data/raw`、`data/interim`、`data/processed`：未来数据分层目录，当前仅保留 `.gitkeep`。
- `logs/`：本地日志目录，当前仅保留 README。
- `outputs/`：未来输出目录，当前仅保留 README。
- `src/stock_selector/case_library/`：真实历史股票案卷库 V0.1 的导入器与本地网页工作台。
- `scripts/import_legacy_cases.py`：只读导入旧 L.Lawlight 历史案卷并生成 SQLite/报告。
- `scripts/serve_case_library.py`：启动本地网页工作台。
- `scripts/launch_case_library.py` 与 `启动历史案卷库.bat`：一键导入并启动工作台。
- `data/processed/case_library.sqlite3`：真实案卷索引数据库。
- `outputs/case_library/`：导入摘要与数据考古报告。
- 当前结构疑点：业务路线待确认，尚未选择数据源、指标、模型、回测或报告方案。
- GPT 建议优先检查区域：`src/stock_selector/case_library/`、`tests/test_case_library.py`、`outputs/case_library/import_summary.json`、`Agent-Memory/01-轮次记录/TASK-20260612-001/ROUND-004/`。
