# 真实历史股票案卷库 V0.1 使用说明

## 一键启动

双击项目根目录：

```text
D:\AAAAAAAAA项目\StockSelector\启动历史案卷库.bat
```

启动脚本会自动寻找 Python，优先级为：

1. 项目本地 `.venv`
2. 项目本地 `venv`
3. 环境变量 `STOCK_SELECTOR_PYTHON`
4. `D:\AAAAAAAAA项目\_公共环境\stock_env\Scripts\python.exe`
5. 系统 `python` 或 `py`

启动后会自动执行一次增量导入，随后启动只读文件监控、本地网页服务，并打开浏览器。

默认地址：

```text
http://127.0.0.1:8765/
```

如果启动失败，BAT 窗口会保留错误信息。关闭窗口或按 `Ctrl+C` 时，网页服务和监控线程会一起停止。

## 自动增量监控

默认监控旧项目：

```text
D:\AAAAAAAAA项目\L.Lawlight\1\RadarData
D:\AAAAAAAAA项目\L.Lawlight\1\HumanView
```

监控只读取旧目录，不移动、不重命名、不写入旧文件。系统会检测新增、修改、删除和重命名文件，并在防抖稳定后执行变更路径级增量导入。

网页中的“今日变化”页面显示：

- 当前监控状态和开关
- 今日新增股票
- 今日新增案卷
- 今日更新案卷
- 新增或消失字段
- 数据源变化
- 模块成功/失败变化
- 数据质量等级变化
- 无法解析文件
- 文件监控事件和自动导入批次

监控日志：

```text
D:\AAAAAAAAA项目\StockSelector\logs\case_library_monitor.log
```

## 手动命令

只执行真实旧数据导入：

```powershell
python scripts\import_legacy_cases.py
```

启动工作台并开启监控：

```powershell
python scripts\serve_case_library.py --open-browser
```

启动工作台但暂停监控：

```powershell
python scripts\serve_case_library.py --open-browser --no-monitor
```

## 生成物

- SQLite 索引：`data\processed\case_library.sqlite3`
- 导入摘要：`outputs\case_library\import_summary.json`
- 数据考古报告：`outputs\case_library\数据考古发现.html`
- 模拟监控验收摘要：`outputs\case_library\monitor_simulation_summary.json`
- 真实格式调查：`docs\legacy_data_schema_map.md`

## 验收样本

建议搜索：

```text
002558
```

当前真实导入中，`002558 / 巨人网络` 有 10 个历史案卷，其中 `2026-06-03` 有 5 次同日运行，可用于验证时间线、案卷详情和案卷对比。

## 注意事项

- 本工具只读取旧项目 `D:\AAAAAAAAA项目\L.Lawlight\1`。
- 本工具不生成选股结论，不预测涨跌。
- “案卷对比”比较的是历史案卷内容、文件、字段覆盖率和数据完整性。
- 缺失字段不会被默认值伪装，详情页会显示缺失内容和解析警告。
