@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker compose -f docker-compose.yml -f docker-compose.internal.yml down
pause
