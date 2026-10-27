@echo off
rem Windows equivalent of run.sh: start the Demo 2 Streamlit app from the "minor" conda env.
rem Usage: double-click, or run "run.cmd" (extra arguments go to streamlit, e.g. --server.port 8502).
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
"%USERPROFILE%\anaconda3\envs\minor\python.exe" -m streamlit run app.py --server.address 127.0.0.1 %*
