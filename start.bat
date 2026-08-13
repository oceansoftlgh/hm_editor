@echo off
chcp 65001 >nul
title 惠每电子病历编辑器 HmEditor

cd /d %~dp0

set PORT=3071
set NODE_ENV=production

echo ========================================
echo  惠每电子病历编辑器 HmEditor
echo  启动中...
echo ========================================
echo.
echo 端口: %PORT%
echo 模式: %NODE_ENV%
echo 目录: %CD%
echo.

node index.js

echo.
echo 服务已停止。
pause
