# 开发工作流

本地内循环：阅读 Agent-Memory，修改相关文件，运行生成、验证、状态和 unittest 命令，使用 `finish_round.py` 记录结果。

GitHub 外循环需用户确认。Codex 不自动 `git add`、Commit、Push、Pull、Merge、Rebase，也不自动创建或切换分支。

验证等级：`L0_PLANNED`、`L1_CHANGED`、`L2_AGENT_TESTED`、`L4_USER_VERIFIED`、`L5_CLOSED`。用户未验证时不得标记 L4 或 L5。
