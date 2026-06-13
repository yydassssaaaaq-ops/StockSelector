@echo off
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0.."
set "SCRIPT=%~dp0project_status.py"

where python >nul 2>nul
if not errorlevel 1 goto run_python

where py >nul 2>nul
if not errorlevel 1 goto run_py

echo 错误：未找到 python 或 py，请先安装 Python 或将 Python 加入 PATH。
set "CODE=1"
goto done

:run_python
python "%SCRIPT%"
set "CODE=%ERRORLEVEL%"
goto done

:run_py
py "%SCRIPT%"
set "CODE=%ERRORLEVEL%"
goto done

:done
set "NO_PAUSE=%STOCKSELECTOR_NO_PAUSE: =%"
if not "%NO_PAUSE%"=="1" pause
exit /b %CODE%
