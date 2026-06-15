# 开发工作流

本地内循环：阅读 Agent-Memory，修改相关文件，运行真实样例、生成、验证、状态和 unittest 命令，并记录 ROUND 结果。

GitHub 外循环：任务完成、测试通过且工作区内容确认无明显异常后，Codex 可在当前分支执行 `git add`、Commit 和 Push 到当前远程分支；不创建或切换分支，不使用 force push，不删除或覆盖已有历史。Push 被拒绝或测试失败时必须如实记录并保留现场。

验证等级：`L0_PLANNED`、`L1_CHANGED`、`L2_AGENT_TESTED`、`L4_USER_VERIFIED`、`L5_CLOSED`。用户未验证时不得标记 L4 或 L5。
