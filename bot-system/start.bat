@echo off
title TLE LINE Discord Bot Starter
cd /d "%~dp0"

echo ======================================
echo   TLE LINE + Discord Bot Starter
echo ======================================
echo.

if not exist main.py (
    echo ไม่พบไฟล์ main.py
    pause
    exit
)

if not exist .env (
    echo ไม่พบไฟล์ .env
    pause
    exit
)

if not exist ngrok.exe (
    echo ไม่พบไฟล์ ngrok.exe
    pause
    exit
)

echo กำลังเปิด Python Bot...
start "TLE Python Bot" cmd /k "cd /d %~dp0 && python main.py"

timeout /t 3 >nul

echo กำลังเปิด ngrok...
start "TLE Ngrok" cmd /k "cd /d %~dp0 && ngrok http 5000"

echo.
echo เปิดระบบเรียบร้อยแล้ว
echo.
echo ขั้นตอนต่อไป:
echo 1. ดูหน้าต่าง ngrok
echo 2. Copy URL ที่ขึ้นต้นด้วย https://
echo 3. นำไปใส่ LINE Webhook เป็น https://URL/webhook
echo.
pause