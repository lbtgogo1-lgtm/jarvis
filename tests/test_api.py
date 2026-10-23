import os, tempfile, importlib

os.environ["JARVIS_DATA"] = tempfile.mkdtemp(prefix="jarvis-tests-")
from fastapi.testclient import TestClient
import app as module
from backend import database as db

client = TestClient(module.app)


def create():
    return client.post("/api/sessions").json()["id"]


def test_history_survives_reinitialization():
    sid = create()
    db.add(sid, "user", "한국어 기록")
    db.add(sid, "assistant", "안녕하세요")
    db.init()
    assert client.get("/api/sessions/" + sid).json() == [
        {"role": "user", "content": "한국어 기록"},
        {"role": "assistant", "content": "안녕하세요"},
    ]
    assert client.delete("/api/sessions/" + sid).status_code == 200
    assert client.get("/api/sessions/" + sid).status_code == 404


def test_model_missing_no_fake_reply(monkeypatch):
    async def models():
        return []

    monkeypatch.setattr(module.ai, "models", models)
    sid = create()
    r = client.post(f"/api/sessions/{sid}/chat", json={"text": "안녕"})
    assert r.status_code == 400
    assert db.messages(sid) == []


def test_stream_and_context(monkeypatch):
    async def models():
        return ["qwen3:8b"]

    captured = []

    async def stream(settings, messages):
        captured.extend(messages)
        yield "안녕"
        yield "하세요"

    monkeypatch.setattr(module.ai, "models", models)
    monkeypatch.setattr(module.ai, "stream", stream)
    sid = create()
    assert (
        client.post(f"/api/sessions/{sid}/chat", json={"text": "첫 질문"}).status_code
        == 200
    )
    assert db.messages(sid)[-1]["content"] == "안녕하세요"
    r = client.post(f"/api/sessions/{sid}/chat", json={"text": "이어서"})
    assert "done" in r.text
    assert any(m["content"] == "첫 질문" for m in captured)
    assert sid not in module.active


def test_settings_validation_and_persistence():
    settings = client.get("/api/settings").json()
    settings["temperature"] = 0.4
    assert client.put("/api/settings", json=settings).status_code == 200
    assert importlib.reload(module.config).load()["temperature"] == 0.4
    settings["stt_model"] = "../../bad"
    assert client.put("/api/settings", json=settings).status_code == 422


def test_origin_and_host_rejected():
    assert (
        client.post(
            "/api/sessions", headers={"origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.get("/api/health", headers={"host": "evil.example"}).status_code == 403
    )


def test_bounded_memory():
    sid = create()
    client.put(f"/api/sessions/{sid}/memory", json={"text": "영상 기획 중"})
    for i in range(40):
        db.add(sid, "user", str(i) * 1000)
    context = db.context(sid)
    assert len(context) <= 25
    assert sum(len(m["content"]) for m in context[1:]) <= 24000
    assert "영상 기획 중" in context[0]["content"]


def test_empty_audio_and_busy():
    assert (
        client.post(
            "/api/stt", files={"file": ("a.webm", b"", "audio/webm")}
        ).status_code
        == 400
    )
    assert module.stt_busy is False
    module.stt_busy = True
    try:
        assert (
            client.post(
                "/api/stt", files={"file": ("a.webm", b"abc", "audio/webm")}
            ).status_code
            == 409
        )
    finally:
        module.stt_busy = False


def test_stt_integration_and_cleanup(monkeypatch):
    seen = []

    def transcribe(path, name):
        assert os.path.exists(path)
        seen.append(path)
        return "영상 아이디어"

    monkeypatch.setattr(module.stt, "transcribe", transcribe)
    r = client.post(
        "/api/stt", files={"file": ("a.webm", b"audio fixture", "audio/webm")}
    )
    assert r.json()["text"] == "영상 아이디어"
    assert not os.path.exists(seen[0])


def test_ollama_down(monkeypatch):
    async def models():
        raise OSError("offline")

    monkeypatch.setattr(module.ai, "models", models)
    sid = create()
    assert (
        client.post(f"/api/sessions/{sid}/chat", json={"text": "안녕"}).status_code
        == 503
    )
    health = client.get("/api/health").json()
    assert health["server"] and not health["ollama"]


def test_stream_error_not_saved(monkeypatch):
    async def models():
        return ["qwen3:8b"]

    async def stream(*args):
        yield "미완료"
        raise OSError("interrupted")

    monkeypatch.setattr(module.ai, "models", models)
    monkeypatch.setattr(module.ai, "stream", stream)
    sid = create()
    r = client.post(f"/api/sessions/{sid}/chat", json={"text": "질문"})
    assert "error" in r.text
    assert len(db.messages(sid)) == 1
    assert sid not in module.active
