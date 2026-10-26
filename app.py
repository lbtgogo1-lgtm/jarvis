import asyncio, json, tempfile, os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, Request
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from typing import Literal
from backend import config, database as db, ai_engine as ai, speech_to_text as stt
from backend import research, web_tools
from backend.health import gpu

app = FastAPI(title="J.A.R.V.I.S. Local")
db.init()
active = set()
stt_busy = False


@app.middleware("http")
async def local_only(request: Request, call_next):
    from fastapi.responses import JSONResponse

    if request.headers.get("host", "").split(":")[0] not in (
        "127.0.0.1",
        "localhost",
        "testserver",
    ):
        return JSONResponse({"detail": "Local access only"}, status_code=403)
    origin = request.headers.get("origin")
    if origin and origin not in ("http://127.0.0.1:8000", "http://localhost:8000"):
        return JSONResponse({"detail": "Cross-origin access denied"}, status_code=403)
    return await call_next(request)


class Settings(BaseModel):
    model: str = Field(max_length=120)
    temperature: float = Field(ge=0, le=2)
    stt_model: str = Field(pattern="^(tiny|base|small|medium|large-v3)$")
    quality: str = Field(pattern="^(LOW|MEDIUM|HIGH)$")
    particle_size: float = Field(default=1.0, ge=0.5, le=3)
    personality: str = Field(min_length=1, max_length=12000)
    web_enabled: bool = False
    web_provider: Literal["searxng", "tavily"] = "searxng"
    searxng_url: str = Field(default="http://127.0.0.1:8080", max_length=250)
    web_fetch_pages: bool = False

    @field_validator("searxng_url")
    @classmethod
    def local_search_only(cls, value):
        return web_tools.searxng_url(value)


class Chat(BaseModel):
    text: str = Field(min_length=1, max_length=12000)


class Memory(BaseModel):
    text: str = Field(max_length=6000)


def require(sid):
    if not db.exists(sid):
        raise HTTPException(404, "대화를 찾을 수 없습니다.")


@app.get("/api/ready")
def ready():
    # Opening the HUD must not wait for Ollama, Whisper, or GPU telemetry.
    return {"app": "jarvis", "ready": True}


@app.get("/api/health")
async def health():
    try:
        models = await ai.models()
        error = None
    except Exception:
        models = []
        error = "Ollama 서버에 연결할 수 없습니다. ollama serve를 실행하세요."
    settings = config.load()
    return dict(
        server=True,
        models=models,
        ollama=error is None,
        error=error,
        selected_installed=settings["model"] in models,
        stt=stt.status,
        gpu=await asyncio.to_thread(gpu),
    )


@app.get("/api/settings")
def settings():
    return config.load()


@app.put("/api/settings")
def put_settings(value: Settings):
    config.save(value.model_dump())
    return value


@app.get("/api/web/status")
async def web_status():
    return await web_tools.web_status(config.load())


@app.post("/api/web/check")
async def check_web():
    return await web_tools.web_status(config.load(), force=True)


@app.get("/api/sessions")
def sessions():
    return db.sessions()


@app.post("/api/sessions")
def new():
    return {"id": db.create()}


@app.delete("/api/sessions")
def clear():
    if active:
        raise HTTPException(409, "응답을 먼저 취소하세요.")
    db.delete()
    return {"ok": True}


@app.get("/api/sessions/{sid}")
def history(sid: str):
    require(sid)
    return db.messages(sid)


@app.delete("/api/sessions/{sid}")
def delete(sid: str):
    if sid in active:
        raise HTTPException(409, "응답을 먼저 취소하세요.")
    require(sid)
    db.delete(sid)
    return {"ok": True}


@app.put("/api/sessions/{sid}/memory")
def memory(sid: str, value: Memory):
    require(sid)
    with db.connection() as conn:
        conn.execute("UPDATE sessions SET memory=? WHERE id=?", (value.text, sid))
    return {"ok": True}


@app.post("/api/sessions/{sid}/chat")
async def chat(sid: str, value: Chat, request: Request):
    require(sid)
    if not value.text.strip():
        raise HTTPException(400, "빈 메시지입니다.")
    if sid in active:
        raise HTTPException(409, "이미 응답 중입니다.")
    settings = config.load()
    try:
        models = await ai.models()
    except Exception:
        raise HTTPException(
            503, "Ollama 서버에 연결할 수 없습니다. ollama serve를 실행하세요."
        )
    if settings["model"] not in models:
        raise HTTPException(
            400, "선택한 모델이 없습니다. Ollama에서 직접 설치 후 다시 선택하세요."
        )
    if sid in active:
        raise HTTPException(409, "이미 응답 중입니다.")
    active.add(sid)
    db.add(sid, "user", value.text)

    async def events():
        answer = ""
        sources = []
        try:
            context = db.context(sid)
            prepared = None
            if research.intent(value.text):
                if settings.get("web_enabled"):
                    yield json.dumps(
                        {"state": "SEARCHING", "web": "SEARCHING WEB"}
                    ) + "\n"
                prepared = await research.prepare(settings, context, value.text)
                if await request.is_disconnected():
                    return
                sources = prepared["sources"]
                yield json.dumps(
                    {
                        "sources": sources,
                        "warnings": prepared["warnings"],
                        "web": "WEB CONNECTED" if prepared["connected"] else "OFFLINE",
                    },
                    ensure_ascii=False,
                ) + "\n"
                context = prepared["messages"]
                yield json.dumps({"state": "THINKING"}) + "\n"
            if prepared and prepared["answer"] is not None:
                answer = prepared["answer"]
                yield json.dumps({"token": answer}, ensure_ascii=False) + "\n"
                db.add(sid, "assistant", answer, sources)
                yield json.dumps({"done": True}) + "\n"
                return
            async for token in ai.stream(settings, context):
                if await request.is_disconnected():
                    break
                answer += token
                yield json.dumps({"token": token}, ensure_ascii=False) + "\n"
            else:
                if answer:
                    db.add(sid, "assistant", answer, sources)
                yield json.dumps({"done": True}) + "\n"
        except asyncio.CancelledError:
            raise
        except Exception:
            yield json.dumps(
                {
                    "error": "AI 연결이 끊겼습니다. Ollama 상태를 확인하고 다시 시도하세요."
                },
                ensure_ascii=False,
            ) + "\n"
        finally:
            active.discard(sid)

    return StreamingResponse(events(), media_type="application/x-ndjson")


@app.post("/api/stt")
async def speech(file: UploadFile):
    global stt_busy
    if stt_busy:
        raise HTTPException(409, "음성 처리 중입니다.")
    stt_busy = True
    path = None
    try:
        content = await file.read(12 * 1024 * 1024 + 1)
        if len(content) > 12 * 1024 * 1024:
            raise HTTPException(413, "녹음 파일은 12MB 이하로 제한됩니다.")
        if not content:
            raise HTTPException(400, "빈 음성입니다.")
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".webm", dir=config.DATA
        ) as f:
            path = f.name
            f.write(content)
        try:
            text = await asyncio.to_thread(
                stt.transcribe, path, config.load()["stt_model"]
            )
        except Exception:
            raise HTTPException(503, stt.status["error"])
        if not text:
            raise HTTPException(422, "음성이 감지되지 않았습니다. 다시 녹음하세요.")
        return {"text": text, "device": stt.status["device"]}
    finally:
        stt_busy = False
        if path:
            os.unlink(path)


if (config.ROOT / "dist").exists():
    app.mount(
        "/assets", StaticFiles(directory=config.ROOT / "dist/assets"), name="assets"
    )

    @app.get("/")
    def index():
        return FileResponse(config.ROOT / "dist/index.html")
