@echo off
title Clinical Trial Enrollment Forecasting Dashboard
echo =======================================================================
echo   ADAPTIVE CLINICAL TRIAL ENROLLMENT FORECASTING PLATFORM
echo   Hierarchical Bayesian Inference & Hospital Patient Flow Analytics
echo =======================================================================
echo.
cd /d "%~dp0"
echo [1/2] Launching browser to http://127.0.0.1:8000/ ...
start "" http://127.0.0.1:8000/
echo [2/2] Starting FastAPI backend service...
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
