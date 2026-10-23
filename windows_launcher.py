"""Start the local HUD and control only the server owned by this launcher."""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FLAG = ROOT / "data" / "server.stop"
LOCK = ROOT / "data" / "server.lock"
LOG = ROOT / "data" / "startup.log"
PORT = 8000
URL = f"http://127.0.0.1:{PORT}"
# Local readiness must not be routed through system or environment proxies.
LOCAL_HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def server_ready():
    try:
        with LOCAL_HTTP.open(URL + "/api/ready", timeout=1) as response:
            payload = json.loads(response.read(4096))
            return (
                response.status == 200
                and isinstance(payload, dict)
                and payload.get("app") == "jarvis"
                and payload.get("ready") is True
            )
    except (OSError, ValueError):
        return False


def wait_until_ready(process, timeout=45):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Server exited during startup. See data/startup.log.")
        if server_ready():
            return
        time.sleep(0.2)
    raise RuntimeError("Server startup timed out. See data/startup.log.")


def open_browser():
    # Always display a usable address, even if the browser association is broken.
    print(f"JARVIS is running. Open this address in Chrome: {URL}", flush=True)
    try:
        opened = webbrowser.open(URL, new=2)
    except (OSError, webbrowser.Error):
        opened = False
    if not opened:
        print("Automatic browser launch failed. Paste the address above into Chrome.")


def copy_server_output(stream, log):
    for line in stream:
        log.write(line)
        log.flush()
        print(line, end="", flush=True)


def start():
    if not (ROOT / "dist" / "index.html").is_file():
        raise RuntimeError("The interface is not built. Run setup.bat first.")
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(("127.0.0.1", PORT)) == 0:
            raise RuntimeError(
                f"Port {PORT} is already in use. If JARVIS is running, open {URL}. "
                "Otherwise close the application using that port and try again."
            )

    FLAG.parent.mkdir(exist_ok=True)
    try:
        lock = LOCK.open("x", encoding="utf-8")
    except FileExistsError:
        raise RuntimeError(
            "A launcher lock exists. If no JARVIS launcher is running, "
            "remove data/server.lock and try again."
        ) from None

    process = reader = log = None
    try:
        lock.write(str(os.getpid()))
        lock.flush()
        FLAG.unlink(missing_ok=True)
        log = LOG.open("a", encoding="utf-8")
        log.write(f"\nJARVIS startup: {datetime.now().isoformat(timespec='seconds')}\n")
        log.flush()
        print(f"Starting JARVIS. Server log: {LOG}", flush=True)
        child_env = os.environ.copy()
        child_env.update(PYTHONUNBUFFERED="1", PYTHONUTF8="1")
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(PORT),
            ],
            cwd=ROOT,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        reader = threading.Thread(
            target=copy_server_output, args=(process.stdout, log), daemon=True
        )
        reader.start()
        wait_until_ready(process)
        open_browser()
        print(
            "Keep this window open. Press Ctrl+C or run stop.bat to stop.", flush=True
        )
        while process.poll() is None and not FLAG.exists():
            time.sleep(0.3)
        if process.poll() not in (None, 0) and not FLAG.exists():
            raise RuntimeError("Server exited unexpectedly. See data/startup.log.")
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
        if reader:
            reader.join()
        if process and process.stdout:
            process.stdout.close()
        if log:
            log.close()
        lock.close()
        LOCK.unlink(missing_ok=True)
        FLAG.unlink(missing_ok=True)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("start", "stop"):
        print("Usage: windows_launcher.py start|stop")
        return 2
    try:
        if sys.argv[1] == "stop":
            FLAG.parent.mkdir(exist_ok=True)
            FLAG.touch()
            print("Stop requested for this project server only.")
        else:
            start()
        return 0
    except (OSError, RuntimeError) as error:
        print(f"JARVIS could not start: {error}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
