@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose down
if errorlevel 1 (
  echo [错误] 停止失败，请确认 Docker Desktop 已启动。
) else (
  echo 系统已停止，数据库和上传材料仍保留在 zongce_data 数据卷中。
)
pause
