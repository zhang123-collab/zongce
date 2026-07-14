@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [失败] 尚未安装依赖，请先双击“安装依赖.bat”。
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\check_environment.py
if errorlevel 1 (
  echo.
  echo 启动已取消，请处理上面的环境问题。
  pause
  exit /b 1
)
echo.
echo [启动] 浏览器访问：http://127.0.0.1:8000
echo [接口文档] http://127.0.0.1:8000/docs
echo 按 Ctrl+C 可停止服务。
".venv\Scripts\python.exe" app.py
pause
