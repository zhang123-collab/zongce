@echo off
chcp 65001 >nul
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo [错误] Docker Desktop 尚未启动，请先启动 Docker Desktop。
  pause
  exit /b 1
)

if not exist "internal-data\zongce.db" (
  echo [错误] 未找到组内数据库 internal-data\zongce.db，请确认压缩包已完整解压。
  pause
  exit /b 1
)

docker compose -f docker-compose.yml -f docker-compose.internal.yml up --build -d
if errorlevel 1 (
  echo [错误] Docker 构建或启动失败。
  pause
  exit /b 1
)

echo 组内完整数据版已启动：http://127.0.0.1:8000
start "" "http://127.0.0.1:8000"
pause
