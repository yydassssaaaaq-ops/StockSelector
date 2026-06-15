# ENVIRONMENT

- 操作系统：Windows-10-10.0.26200-SP0
- Python 实际版本：3.11.9
- Git 实际版本：PowerShell PATH 中不可用；本轮使用 GitHub Desktop 自带 `git version 2.53.0.windows.3` 完成状态读取和后续 Git 操作。
- 仓库路径：D:\AAAAAAAAA项目\StockSelector
- 当前分支：main
- 本轮起始 HEAD：a062e3f1c9abc83ccd82356b0df03dc564d13515
- 当前真实 HEAD 获取方式：运行时由 Git 动态读取；状态文件内 `observed_head_commit` 表示生成状态文件时观察到的 HEAD，允许在提交后成为当前 HEAD 的祖先。
- 包管理方式：pyproject.toml；本轮未新增第三方依赖。
- 真实行情源：默认新浪市场中心 `hs_a`；可选东财 push2 A 股行情快照。
- 真实样例输出目录：`outputs/a_share_screen/`；原始行情快照目录：`data/raw/a_share_quotes/`；两者按 `.gitignore` 作为本地生成结果保留。
- 环境变量名称：`STOCK_SELECTOR_DATA_SOURCE`、`STOCK_SELECTOR_API_KEY`、`STOCK_SELECTOR_OUTPUT_DIR`
- 敏感信息说明：不得读取、记录、复制、显示或提交真实密钥、Token、Cookie、密码、私钥或证书内容。
- 最后确认时间：2026-06-15T16:56:34+08:00
