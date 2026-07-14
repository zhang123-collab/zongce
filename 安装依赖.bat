@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [安装] 正在创建Python虚拟环境...
  py -3 -m venv .venv
  if errorlevel 1 goto :failed
)
echo [安装] 正在安装项目依赖...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :failed
echo.
echo [完成] 基础依赖安装成功。
echo 如需扫描版PDF和图片OCR，请再执行：
echo .venv\Scripts\python.exe -m pip install -r requirements-ai.txt
pause
exit /b 0
:failed
echo.
echo [失败] 依赖安装未完成，请检查Python和网络环境。
pause
exit /b 1
