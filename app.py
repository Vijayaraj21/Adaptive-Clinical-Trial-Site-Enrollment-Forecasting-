"""Convenience launcher for the local FastAPI dashboard."""

import os
import socket
import sys
from pathlib import Path


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    venv_python = project_dir / "venv" / "Scripts" / "python.exe"
    if venv_python.exists() and Path(sys.executable).resolve() != venv_python.resolve():
        os.execv(str(venv_python), [str(venv_python), str(Path(__file__).resolve())])

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        port_in_use = probe.connect_ex((host, port)) == 0
    if port_in_use:
        print(f"Port {port} is already in use. The dashboard may already be running at http://{host}:{port}/.")
        print(f"To start another instance, set $env:PORT = {port + 1} and run this command again.")
        return

    import uvicorn

    uvicorn.run("backend.main:app", host=host, port=port)


if __name__ == "__main__":
    main()
