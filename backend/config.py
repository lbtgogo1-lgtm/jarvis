import json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("JARVIS_DATA", ROOT / "data")).resolve()
DATA.mkdir(parents=True, exist_ok=True)
DEFAULT = dict(
    model="qwen3:8b",
    temperature=0.6,
    stt_model="small",
    quality="MEDIUM",
    particle_size=1.0,
    personality=(ROOT / "config/jarvis_personality.txt").read_text(encoding="utf-8"),
)


def load():
    return DEFAULT | (
        json.loads((DATA / "settings.json").read_text(encoding="utf-8"))
        if (DATA / "settings.json").exists()
        else {}
    )


def save(value):
    temp = DATA / "settings.tmp"
    temp.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temp.replace(DATA / "settings.json")
