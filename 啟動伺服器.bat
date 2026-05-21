@echo off
chcp 65001 >nul
title 台股布林訊號系統

set PYTHON=C:\Users\user\AppData\Local\Programs\Python\Python312\python.exe
set PROJECT=C:\Users\user\.gemini\antigravity\scratch\stock-signal-system

echo 正在啟動台股布林訊號系統...

:: 結束舊的 Python 伺服器（避免 port 衝突）
for /f "tokens=5" %%a in ('netstat -aon 2^>nul ^| findstr ":8000 "') do (
    taskkill /pid %%a /f >nul 2>&1
)
timeout /t 1 /nobreak >nul

:: 啟動後端（背景執行，不顯示視窗）
start "" /B cmd /c "cd /d %PROJECT% && "%PYTHON%" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 > "%PROJECT%\server.log" 2>&1"

:: 等待伺服器就緒
echo 等待伺服器啟動...
:WAIT_LOOP
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":8000 " >nul 2>&1
if errorlevel 1 goto WAIT_LOOP

:: 開啟瀏覽器（必須用 http://，不能用 file://）
echo 開啟看盤介面...
start "" "http://localhost:8000/app/"

exit
