@echo off
setlocal
cd /d "%~dp0"

if not exist ".\venv\Scripts\python.exe" (
  echo Creating Python 3.11 environment...
  py -3.11 -m venv venv
  if errorlevel 1 exit /b %errorlevel%
)

echo Installing desktop build dependencies...
.\venv\Scripts\python.exe -m pip install -r requirements-desktop.txt
if errorlevel 1 exit /b %errorlevel%

echo Building CT-BAYES Desktop...
.\venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --windowed --name CTBayesDesktop ^
  --collect-all webview ^
  --collect-all pymc ^
  --collect-all arviz ^
  --collect-all pytensor ^
  --add-data "config.yaml;." ^
  --add-data "data;data" ^
  --add-data "frontend;frontend" ^
  --add-data "models_cache;models_cache" ^
  --add-data "reports;reports" ^
  desktop_app.py
if errorlevel 1 exit /b %errorlevel%

copy /y .env.example "dist\CTBayesDesktop\.env.example" >nul
echo.
echo Desktop application created at: dist\CTBayesDesktop\CTBayesDesktop.exe
echo Copy .env.example to .env beside the EXE and set MYSQL_PASSWORD before launching.
echo Run installer.iss with Inno Setup to create a setup EXE.
endlocal
