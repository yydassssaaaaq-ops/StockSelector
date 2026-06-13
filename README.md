# StockSelector

StockSelector 是一个面向 A 股智能选股系统的工程仓库。当前阶段只建立 Agent 项目闭环基础设施和中性工程目录壳，尚没有真实选股、回测、交易或报告生成能力。

## 常用命令

```powershell
python scripts/project_status.py
python scripts/build_gpt_context.py
python scripts/build_index.py
python scripts/validate_memory.py
python -m unittest discover -s tests -v
```

当前业务事实如数据源、复权方案、股票池、指标、模型、交易周期和输出规则均为待确认。
