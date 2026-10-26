import json, sqlite3, uuid
from .config import DATA


def connection():
    db = sqlite3.connect(DATA / "jarvis.sqlite", timeout=15)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def init():
    with connection() as db:
        db.executescript(
            'CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY, title TEXT, created TEXT DEFAULT CURRENT_TIMESTAMP, memory TEXT DEFAULT ""); CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, session TEXT REFERENCES sessions(id) ON DELETE CASCADE, role TEXT, content TEXT);'
        )
        columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
        if "sources" not in columns:
            db.execute(
                "ALTER TABLE messages ADD COLUMN sources TEXT NOT NULL DEFAULT '[]'"
            )


def sessions():
    with connection() as db:
        return [
            dict(r)
            for r in db.execute(
                "SELECT * FROM sessions ORDER BY created DESC, rowid DESC"
            )
        ]


def create():
    sid = str(uuid.uuid4())
    with connection() as db:
        db.execute("INSERT INTO sessions(id,title) VALUES(?,?)", (sid, "새 대화"))
    return sid


def exists(sid):
    with connection() as db:
        return (
            db.execute("SELECT 1 FROM sessions WHERE id=?", (sid,)).fetchone()
            is not None
        )


def messages(sid):
    with connection() as db:
        result = []
        for row in db.execute(
            "SELECT role,content,sources FROM messages WHERE session=? ORDER BY id",
            (sid,),
        ):
            item = {"role": row["role"], "content": row["content"]}
            sources = json.loads(row["sources"])
            if sources:
                item["sources"] = sources
            result.append(item)
        return result


def add(sid, role, text, sources=None):
    with connection() as db:
        db.execute(
            "INSERT INTO messages(session,role,content,sources) VALUES(?,?,?,?)",
            (sid, role, text, json.dumps(sources or [], ensure_ascii=False)),
        )
        if role == "user":
            db.execute(
                "UPDATE sessions SET title=? WHERE id=? AND title=?",
                (text[:40], sid, "새 대화"),
            )


def delete(sid=None):
    with connection() as db:
        if sid:
            db.execute("DELETE FROM sessions WHERE id=?", (sid,))
        else:
            db.execute("DELETE FROM sessions")


def context(sid):
    # Bounded recent context plus explicit user-editable summary memory.
    with connection() as db:
        memory = db.execute(
            "SELECT memory FROM sessions WHERE id=?", (sid,)
        ).fetchone()["memory"]
    recent = []
    size = 0
    for m in reversed(messages(sid)[-24:]):
        if size + len(m["content"]) > 24000:
            break
        recent.insert(0, {"role": m["role"], "content": m["content"]})
        size += len(m["content"])
    return (
        [{"role": "system", "content": "이전 대화 요약: " + memory}] if memory else []
    ) + recent
