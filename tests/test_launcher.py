import io
import socket
import sys

import pytest

import windows_launcher as launcher


@pytest.fixture
def isolated_launcher(monkeypatch, tmp_path):
    for name, file in [
        ("FLAG", "server.stop"),
        ("LOCK", "server.lock"),
        ("LOG", "startup.log"),
    ]:
        monkeypatch.setattr(launcher, name, tmp_path / file)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    monkeypatch.setattr(launcher, "PORT", port)
    monkeypatch.setattr(launcher, "URL", f"http://127.0.0.1:{port}")
    monkeypatch.setenv("JARVIS_DATA", str(tmp_path / "app-data"))


def test_real_server_start_readiness_and_stop(monkeypatch, isolated_launcher):
    opened = []

    def inspect_hud():
        with launcher.LOCAL_HTTP.open(launcher.URL, timeout=3) as response:
            assert response.status == 200
            assert b"J.A.R.V.I.S." in response.read()
        opened.append(True)
        launcher.FLAG.touch()

    monkeypatch.setattr(launcher, "open_browser", inspect_hud)
    launcher.start()
    assert opened == [True]
    assert not launcher.LOCK.exists()
    assert not launcher.FLAG.exists()
    assert not launcher.server_ready()
    assert "Application startup complete" in launcher.LOG.read_text()


def test_child_failure_keeps_log_and_releases_lock(monkeypatch, isolated_launcher):
    original_popen = launcher.subprocess.Popen

    def failing_child(command, **kwargs):
        return original_popen(
            [
                sys.executable,
                "-c",
                "print('simulated import failure'); raise SystemExit(7)",
            ],
            **kwargs,
        )

    monkeypatch.setattr(launcher.subprocess, "Popen", failing_child)
    with pytest.raises(RuntimeError, match="exited during startup"):
        launcher.start()
    assert "simulated import failure" in launcher.LOG.read_text()
    assert not launcher.LOCK.exists()


@pytest.mark.parametrize("raises", [False, True])
def test_browser_failure_keeps_manual_address(monkeypatch, capsys, raises):
    def unavailable(*args, **kwargs):
        if raises:
            raise OSError("No registered browser")
        return False

    monkeypatch.setattr(launcher.webbrowser, "open", unavailable)
    launcher.open_browser()
    output = capsys.readouterr().out
    assert launcher.URL in output
    assert "Paste the address" in output


def test_another_service_is_not_ready(monkeypatch):
    class Response(io.BytesIO):
        status = 200

    monkeypatch.setattr(
        launcher.LOCAL_HTTP,
        "open",
        lambda *args, **kwargs: Response(b'{"app":"another-app","ready":true}'),
    )
    assert launcher.server_ready() is False


def test_missing_build_gives_setup_guidance(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="Run setup.bat"):
        launcher.start()


def test_port_in_use_does_not_stop_existing_process(monkeypatch, isolated_launcher):
    with socket.socket() as server:
        server.bind(("127.0.0.1", launcher.PORT))
        server.listen(1)
        with pytest.raises(RuntimeError, match="already in use"):
            launcher.start()
        assert server.getsockname()[1] == launcher.PORT
        assert not launcher.LOCK.exists()
