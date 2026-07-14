@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [失败] 尚未安装依赖，请先双击“安装依赖.bat”。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\backup_data.py
pause
