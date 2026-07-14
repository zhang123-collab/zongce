@echo off
chcp 65001 >nul
cd /d "%~dp0"

docker info >nul 2>&1
if errorlevel 1 (
  echo [错误] Docker Desktop 尚未启动，请先启动 Docker Desktop，等待其显示 Engine running 后重试。
  pause
  exit /b 1
)

echo [1/2] 正在构建并启动综测系统...
docker compose up --build -d
if errorlevel 1 (
  echo [错误] Docker 构建或启动失败，请执行 docker compose logs 查看日志。
  pause
  exit /b 1
)

echo [2/2] 启动完成。
echo 系统首页：http://127.0.0.1:8000
echo API文档：http://127.0.0.1:8000/docs
start "" "http://127.0.0.1:8000"
pause
