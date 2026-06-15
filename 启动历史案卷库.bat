@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

set "PYTHON_EXE="
if exist "%~dp0.venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if not defined PYTHON_EXE if defined STOCK_SELECTOR_PYTHON if exist "%STOCK_SELECTOR_PYTHON%" set "PYTHON_EXE=%STOCK_SELECTOR_PYTHON%"
if not defined PYTHON_EXE if exist "D:\AAAAAAAAA项目\_公共环境\stock_env\Scripts\python.exe" set "PYTHON_EXE=D:\AAAAAAAAA项目\_公共环境\stock_env\Scripts\python.exe"

if not defined PYTHON_EXE (
  where python >nul 2>nul
  if not errorlevel 1 for /f "delims=" %%P in ('where python') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)

if not defined PYTHON_EXE (
  where py >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=py"
)

if not defined PYTHON_EXE (
  echo 错误：未找到可用 Python。
  echo 请安装 Python，或设置 STOCK_SELECTOR_PYTHON 指向 python.exe。
  pause
  exit /b 1
)

echo 使用 Python：%PYTHON_EXE%
echo 正在执行增量导入、启动只读文件监控，并打开本地历史案卷库工作台...
echo 本地地址：http://127.0.0.1:8765/
echo 若浏览器没有自动打开，请手动复制上面的地址。
echo 关闭此窗口或按 Ctrl+C 时，会停止网页服务和监控线程。

if "%PYTHON_EXE%"=="py" (
  py "%~dp0scripts\launch_case_library.py"
) else (
  "%PYTHON_EXE%" "%~dp0scripts\launch_case_library.py"
)
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" (
  echo.
  echo 启动失败，退出码：%CODE%
  echo 请检查上方错误信息。
  pause
)
exit /b %CODE%
