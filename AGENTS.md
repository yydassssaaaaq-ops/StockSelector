# AGENTS.md

## 开始任务前

1. 阅读 `Agent-Memory/INDEX.md`。
2. 阅读 `Agent-Memory/03-GPT导出/GPT_CONTEXT.md`、`Agent-Memory/00-当前状态/CURRENT_TASK.md`、`Agent-Memory/00-当前状态/CURRENT_STATE.md`。
3. 阅读 `Agent-Memory/MEMORY_STATUS.json`。
4. 获取当前工作目录、真实 Git 分支和起始 commit。
5. 检查是否存在旧的未提交修改。
6. 不得把旧轮次修改混入本轮而不说明。

## 执行任务时

1. 可以检查和修改与当前任务有关的仓库文件。
2. 不得把推测写成已确认事实。
3. 测试失败必须如实记录。
4. 用户真实运行结果优先于自动测试。
5. 不读取、不记录、不提交真实密钥。
6. 任务完成、测试通过且工作区内容确认无明显异常后，允许在当前分支执行 `git add`、Commit 和 Push。
7. 不使用 force push，不删除或覆盖已有历史；Git 操作失败必须如实记录并保留现场。
8. 不擅自创建或切换分支。
9. `MEMORY_STATUS.json` 是机器状态唯一权威来源。
10. 不为填满模板而编造内容。

## 结束任务前

1. 新建或更新本轮 `ROUND.md`。
2. 更新每轮必更新文件。
3. 仅在事实变化时更新 `FILE_MAP.md`、`ENVIRONMENT.md`、`USAGE.md`、`PROJECT.md`。
4. 更新 `MEMORY_STATUS.json`。
5. 重新生成 `GPT_CONTEXT.md`。
6. 重新生成 `INDEX.md`。
7. 运行 `validate_memory.py`。
8. 明确当前验证等级。
9. 未经用户真实验证，不得标记 L4 或 L5。
10. 若测试通过且工作区内容确认无明显异常，可在当前分支正常 Commit 并 Push 到当前远程分支；不得 force push。
