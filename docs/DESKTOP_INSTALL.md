# Windows Desktop Build

## Build

Run `build_desktop.bat` from the project folder. It installs the desktop-only build tools and creates the portable app in `dist/CTBayesDesktop/`.

To create a setup executable, open `installer.iss` with Inno Setup and compile it. The installer writes `CTBayesDesktopSetup.exe` to `installer_output/` and creates Start Menu and desktop shortcuts.

## Configure MySQL

The desktop app expects the MySQL service to be running. Beside `CTBayesDesktop.exe`, copy `.env.example` to `.env` and set `MYSQL_PASSWORD` to the MySQL account password. Do not distribute `.env` or put credentials in the installer. The app creates or uses the database configured in `config.yaml`.

## Run

Launch `CTBayesDesktop.exe`. It starts the local API and opens the dashboard in a native WebView window. Closing the window shuts down the API. Microsoft Edge WebView2 Runtime is required; it is present on most current Windows installations.
