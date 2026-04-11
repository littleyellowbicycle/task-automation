@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================================
echo   Task Automation - Starting with ngrok Tunnel
echo ============================================================
echo.

set SCRIPT_DIR=%~dp0
set LOG_FILE=%TEMP%\ngrok.log
set PID_FILE=%TEMP%\ngrok.pid

REM Refresh PATH
set "PATH=%PATH%;C:\Program Files\ngrok"

REM Check ngrok
echo [1/5] Checking ngrok...
where ngrok >nul 2>&1
if errorlevel 1 (
    echo ERROR: ngrok not found in PATH
    echo Please restart your terminal and try again
    exit /b 1
)
echo    OK: ngrok is installed

REM Check authtoken
echo [2/5] Checking ngrok configuration...
ngrok config check >nul 2>&1
if errorlevel 1 (
    echo ERROR: ngrok authtoken not configured
    echo Run: ngrok config add-authtoken YOUR_TOKEN
    exit /b 1
)
echo    OK: ngrok configured

REM Kill existing ngrok
echo [3/5] Setting up ngrok tunnel...
taskkill /f /im ngrok.exe >nul 2>&1

REM Start ngrok
echo    Starting ngrok on port 8086...
start /B ngrok http 8086 > "%LOG_FILE%" 2>&1

REM Wait for ngrok
timeout /t 4 >nul

REM Get public URL using PowerShell
echo [4/5] Getting public URL...
set PUBLIC_URL=

for /L %%i in (1,1,20) do (
    for /f "usebackq tokens=*" %%p in (`powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://localhost:4040/api/tunnels' -UseBasicParsing; ($r.Content | ConvertFrom-Json).tunnels[0].public_url } catch {}"`) do (
        set PUBLIC_URL=%%p
    )
    if defined PUBLIC_URL goto :got_url
    echo    Waiting... (%%i/20)
    timeout /t 1 >nul
)

:got_url
if not defined PUBLIC_URL (
    echo ERROR: Failed to get ngrok public URL
    echo Check: http://localhost:4040
    exit /b 1
)

echo    OK: Public URL: %PUBLIC_URL%

REM Update .env
set ENV_FILE=%SCRIPT_DIR%.env
if exist "%ENV_FILE%" (
    findstr /v "^PUBLIC_CALLBACK_URL=" "%ENV_FILE%" > "%ENV_FILE%.tmp" 2>nul
    move /y "%ENV_FILE%.tmp" "%ENV_FILE%" >nul 2>nul
)
echo PUBLIC_CALLBACK_URL=%PUBLIC_URL%>> "%ENV_FILE%"
echo    OK: Updated .env

echo.
echo ============================================================
echo   Public URLs for Feishu
echo ============================================================
echo   Callback Base: %PUBLIC_URL%
echo   Approve: %PUBLIC_URL%/decision?task_id=xxx&action=approve
echo   Reject:  %PUBLIC_URL%/decision?task_id=xxx&action=reject
echo ============================================================
echo.

REM Start application
echo [5/5] Starting application...
echo.

cd /d "%SCRIPT_DIR%"
python main.py %*
