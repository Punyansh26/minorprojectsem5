@echo off
rem Windows equivalent of start.sh: Demo 2 FastAPI backend (8020) + Next.js web app (3001).
setlocal
cd /d "%~dp0"
for %%I in ("%~dp0..\..\code\demo2") do set "DEMO2_DIR=%%~fI"
set "DEMO2_PYTHON=%USERPROFILE%\anaconda3\envs\minor\python.exe"
rem Separate state from the Streamlit app, which holds the lock on code\demo2\data.
set "DEMO2_DATA_DIR=%DEMO2_DIR%\data\web"
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
set NEXT_TELEMETRY_DISABLED=1

curl -sf http://127.0.0.1:8020/api/health >nul 2>&1
if errorlevel 1 (
  echo Starting Demo 2 API on http://127.0.0.1:8020 ...
  start "Demo2 API" /min /d "%DEMO2_DIR%" "%DEMO2_PYTHON%" -m uvicorn api_server:app --host 127.0.0.1 --port 8020
) else (
  echo Demo 2 API already running on port 8020.
)

echo Starting web app on http://localhost:3001 ...
call npx next dev -H 127.0.0.1 -p 3001
