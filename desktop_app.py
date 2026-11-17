"""Run the FastAPI dashboard inside a native Windows WebView window."""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv


def _runtime_paths() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS), Path(sys.executable).resolve().parent
    source_dir = Path(__file__).resolve().parent
    return source_dir, source_dir


def _free_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((host, 0))
        return int(listener.getsockname()[1])


def _show_error(message: str) -> None:
    try:
        from tkinter import messagebox

        messagebox.showerror("CT-BAYES Desktop", message)
    except Exception:
        print(message, file=sys.stderr)


def main() -> None:
    resource_dir, app_dir = _runtime_paths()
    os.chdir(resource_dir)
    env_file = app_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=False)

    host = "127.0.0.1"
    port = _free_port(host)
    try:
        import uvicorn
        import webview

        from backend.main import app

        server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
        server_thread = threading.Thread(target=server.run, daemon=True)
        server_thread.start()

        url = f"http://{host}:{port}/"
        deadline = time.monotonic() + 120
        while not server.started and server_thread.is_alive() and time.monotonic() < deadline:
            time.sleep(0.2)
        if not server.started:
            raise RuntimeError("The local API did not start. Check MySQL is running and .env is configured.")

        webview.create_window(
            "CT-BAYES | Trial Enrollment Forecasting",
            url,
            min_size=(1024, 720),
            background_color="#070c18",
        )
        webview.start(debug=False)
    except Exception as exc:
        _show_error(str(exc))
    finally:
        if "server" in locals():
            server.should_exit = True
            if "server_thread" in locals():
                server_thread.join(timeout=10)


if __name__ == "__main__":
    main()