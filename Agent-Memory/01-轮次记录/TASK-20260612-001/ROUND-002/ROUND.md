# ROUND-002

## 基本信息

- 所属 TASK：TASK-20260612-001
- ROUND ID：ROUND-002
- 触发来源：用户真实验证反馈
- 本轮目标：修复 Windows BAT 辅助入口问题，不修改选股业务代码。
- 起始时间：2026-06-12T20:52:52+08:00
- 结束时间：2026-06-12T21:01:19+08:00
- 用户重新验证时间：2026-06-12T21:09:44+08:00
- 起始分支：main
- 起始 HEAD：a38c8ad71ce4e95dd910cad6b86d9b9392981bb4
- 是否 Commit：否
- 是否 Push：否
- 是否创建或切换分支：否

## 用户真实反馈

- `python scripts\project_status.py` 可以正常显示项目状态。
- `python scripts\validate_memory.py` 结果为 PASS，FAIL 0，WARNING 0。
- `python -m unittest discover -s tests -v` 共 11 项测试，全部通过。
- 双击 `scripts\project_status.bat` 执行失败。
- 实际问题包括：BAT 错误寻找 `scripts\scripts\project_status.py`；仓库路径包含中文时命令解析异常；CMD 中文乱码；BAT 没有可靠地从任意启动位置切换到仓库根目录。

## 本轮修改

- 修复 `scripts/project_status.bat`。
- 修复 `scripts/validate_memory.bat`。
- 修复 `scripts/build_gpt_context.bat`。
- 为 `user_verification` 增加并使用 `partial_failed` 状态。
- 更新 `scripts/project_status.py`，使用户验证状态输出带明确说明。
- 更新 `scripts/validate_memory.py`，校验 `not_run`、`passed`、`failed`、`partial_failed`。
- 更新 `tests/test_memory_tools.py`，增加 BAT 辅助入口内容检查。
- 更新当前状态文档和开放问题记录。

## BAT 修复规则

- 使用 `%~dp0` 获取 BAT 自身所在目录。
- 使用 `cd /d "%~dp0.."` 切换到仓库根目录。
- 使用 `set "SCRIPT=%~dp0对应脚本.py"` 直接指向同目录 Python 文件，不再拼接 `scripts\*.py`。
- 使用引号保护 Python 文件路径。
- 当前进程设置 `chcp 65001 >nul` 和 `set "PYTHONUTF8=1"`。
- 先检测并尝试 `python`，不可用时再尝试 `py`。
- 两者都不可用时输出中文错误并返回退出码 1。
- 正常双击结束后 `pause` 保留窗口。
- `STOCKSELECTOR_NO_PAUSE=1` 时跳过 `pause`，用于自动测试。

## 开放问题

- 当前无开放问题。
- 原 Windows BAT 辅助入口问题已由用户重新验证通过。

## 用户重新验证结果

- `scripts\project_status.bat`：用户亲自双击验证通过；正常运行；能正确显示项目状态；中文显示正常；不再出现 `scripts\scripts` 路径错误；窗口能够保留。
- `scripts\validate_memory.bat`：用户亲自双击验证通过；正常运行；结果为 FAIL 0 项，WARNING 0 项。
- `scripts\build_gpt_context.bat`：用户亲自双击验证通过；正常运行；成功生成 `GPT_CONTEXT.md`；窗口能够保留。
- 结论：三个 BAT 均由用户真实双击验证通过，原问题已经解决。

## 测试记录

- `set STOCKSELECTOR_NO_PAUSE=1 && call scripts\project_status.bat`：退出码 0，通过；非交互模式未执行 pause，正确显示 partial_failed 状态。
- `set STOCKSELECTOR_NO_PAUSE=1 && call scripts\validate_memory.bat`：退出码 0，通过；Agent-Memory 校验 PASS，FAIL 0，WARNING 0。
- `set STOCKSELECTOR_NO_PAUSE=1 && call scripts\build_gpt_context.bat`：退出码 0，通过；已生成 GPT_CONTEXT.md。
- `python scripts\project_status.py`：退出码 0，通过；正确显示 partial_failed 用户验证状态。
- `python scripts\validate_memory.py`：退出码 0，通过；Agent-Memory 校验 PASS，FAIL 0，WARNING 0。
- `python -m unittest discover -s tests -v`：退出码 0，通过；13 项测试全部 OK，包含 BAT 辅助入口内容检查。

## 用户复验后收口复测

- 执行时间：2026-06-12T21:14:21+08:00
- `python scripts\build_gpt_context.py`：退出码 0，通过。
- `python scripts\build_index.py`：退出码 0，通过。
- `python scripts\validate_memory.py`：退出码 0，通过；FAIL 0 项，WARNING 0 项。
- `python scripts\project_status.py`：退出码 0，通过；显示 `waiting_github_sync`、`L4_USER_VERIFIED`、`passed`、开放问题数量 0。
- `python -m unittest discover -s tests -v`：退出码 0，通过；13 项测试全部 OK。

## HEAD 状态记录自引用修复

- 发现问题：`MEMORY_STATUS.json` 被 Git 跟踪，如果其中 `head_commit` 被定义为“当前真实 HEAD”，那么提交该文件后 Git 会生成新 commit，文件内旧 HEAD 立即过期，再次修正又会产生新 HEAD，形成无法收敛的自引用循环。
- 修复方式：新增 `observed_head_commit`，语义为“最近一次生成状态文件时观察到的 HEAD”。兼容字段 `head_commit` 暂时保留，但语义同样调整为观察值，不再声明它永远等于当前真实 HEAD。
- 当前真实 HEAD 来源：每次运行时由 Git 动态读取，`scripts/project_status.py` 会同时显示当前真实 HEAD 与状态文件观察到的 HEAD。
- 校验策略：`scripts/validate_memory.py` 不再要求状态文件观察值严格等于当前 HEAD；观察值不是 Git 可识别 commit 时才 FAIL；若观察值与当前 HEAD 不同，但它是当前 HEAD 的祖先，或仓库存在未提交修改，则只提示 WARNING/INFO，不得 FAIL。
- 测试补充：新增测试覆盖提交后 HEAD 变化不直接失败、项目状态双 HEAD 显示、合法历史观察值识别、非法观察值失败。
- 本次仍未 Commit，仍未 Push，未创建或切换分支。
- 当前状态继续保持 `L4_USER_VERIFIED`、`passed`、`waiting_github_sync`、`not_pushed`，且不得进入 `L5_CLOSED`。

## HEAD 自引用修复后复测

- 执行时间：2026-06-13T12:57:00+08:00
- `python scripts\build_gpt_context.py`：退出码 0，通过。
- `python scripts\build_index.py`：退出码 0，通过。
- `python scripts\validate_memory.py`：退出码 0，通过；FAIL 0 项，WARNING 0 项。
- `python scripts\project_status.py`：退出码 0，通过；同时显示当前真实 HEAD 与状态文件观察到的 HEAD。
- `python -m unittest discover -s tests -v`：退出码 0，通过；18 项测试全部 OK。
- 结果：提交后 HEAD 变化不再导致记忆系统直接 FAIL；非法观察值仍会 FAIL。

## 当前结论

- 不修改选股业务代码。
- 自动测试全部通过。
- 用户重新验证通过。
- 当前验证等级提升为 L4_USER_VERIFIED。
- 用户验证状态为 passed。
- 执行状态为 waiting_github_sync。
- GitHub 同步保持 not_pushed。
- 当前尚未 Commit。
- 当前尚未 Push。
- 当前不得进入 L5_CLOSED。
