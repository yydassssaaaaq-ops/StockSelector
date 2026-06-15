# OPEN_ISSUES

当前开放问题：

- GitHub 同步未完全完成：核心重构 commit `2d664de4ccf8b5882e101c173a23c0e60f3eaf73` 已推送成功，但后续本地记忆同步 commit `507ad11860f2192fe3f309fb62be65ca66f3b95e` 推送连续两次失败，错误为 HTTPS `Recv failure: Connection was reset`；需网络恢复后重试普通 push，不得 force push。
- 用户尚未真实查看 ROUND-008 报告，因此不得标记 L4_USER_VERIFIED 或 L5_CLOSED。

非阻塞观察：

- 默认股票池已不再使用当天候选 CSV 或今天成交额过滤过去，但仍是当前仍上市代码池过渡方案，历史退市股票和历史成分变化尚未纳入，仍存在幸存者偏差。
- 东财 `push2his` 对沪深 300 基准在本轮真实验收中仍出现连接断开，已真实回退 Yahoo Finance `000300.SS` 并记录失败；东财历史源保留为可选源。
- 腾讯历史源成交额由成交手数乘价格派生，换手率、主力资金和估值字段仍缺失；ROUND-008 历史策略不再使用这些实时字段伪装成同一模型。
- 日线级涨跌停/停牌处理只是近似，不能替代逐笔盘口或真实撮合数据。
- ROUND-007 的 18.78% 回测结果已保留为固定当前候选 CSV 下的历史工程样例，不能作为策略有效性证据。
- ROUND-008 核心重构 commit `2d664de4ccf8b5882e101c173a23c0e60f3eaf73` 已推送到 `origin/main`；未使用 force push。
