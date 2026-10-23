"""Control only the server process owned by this launcher; never terminate Ollama."""

import sys, subprocess, time, urllib.request, webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLAG = ROOT / "data" / "server.stop"
LOCK = ROOT / "data" / "server.lock"
if __name__ == "__main__":
    FLAG.parent.mkdir(exist_ok=True)
    if sys.argv[1] == "stop":
        FLAG.touch()
        print("Stop requested for this project server only.")
    else:
        import socket

        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", 8000)) == 0:
                sys.exit("Port 8000 is occupied. Existing process was not changed.")
        try:
            handle = LOCK.open("x")
        except FileExistsError:
            sys.exit(
                "Launcher lock exists. If no launcher is running, remove data/server.lock manually."
            )
        FLAG.unlink(missing_ok=True)
        process = None
        try:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                ],
                cwd=ROOT,
            )
            for _ in range(100):
                if process.poll() is not None:
                    sys.exit("Server failed. Check output above.")
                try:
                    with urllib.request.urlopen(
                        "http://127.0.0.1:8000/api/health", timeout=1
                    ) as r:
                        if r.status == 200:
                            break
                except OSError:
                    time.sleep(0.2)
            else:
                sys.exit("Server startup timed out.")
            webbrowser.open("http://127.0.0.1:8000")
            print("Keep this window open. Press Ctrl+C or run stop.bat to stop.")
            while process.poll() is None and not FLAG.exists():
                time.sleep(0.3)
        except KeyboardInterrupt:
            pass
        finally:
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            handle.close()
            LOCK.unlink(missing_ok=True)
            FLAG.unlink(missing_ok=True)
