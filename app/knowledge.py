"""Local SQLite knowledge store; no cloud database dependency."""
from pathlib import Path
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException, Depends
from pydantic import BaseModel, Field

router = APIRouter(prefix="/knowledge", tags=["Knowledge Manager"])
DB_FILE = Path(__file__).resolve().parent.parent / "data" / "knowledge.db"
DB_FILE.parent.mkdir(parents=True, exist_ok=True)

def connection():
    c = sqlite3.connect(DB_FILE, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def initialize():
    with connection() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS entries (
            id TEXT PRIMARY KEY, agent_id TEXT NOT NULL, topic TEXT NOT NULL,
            title TEXT NOT NULL, content TEXT NOT NULL, source_url TEXT,
            source_date TEXT, verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_entries_agent_topic ON entries(agent_id,topic);
        CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
            title, content, topic, content='entries', content_rowid='rowid'
        );
        CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
          INSERT INTO entries_fts(rowid,title,content,topic) VALUES(new.rowid,new.title,new.content,new.topic);
        END;
        CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
          INSERT INTO entries_fts(entries_fts,rowid,title,content,topic)
          VALUES('delete',old.rowid,old.title,old.content,old.topic);
        END;
        CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
          INSERT INTO entries_fts(entries_fts,rowid,title,content,topic)
          VALUES('delete',old.rowid,old.title,old.content,old.topic);
          INSERT INTO entries_fts(rowid,title,content,topic) VALUES(new.rowid,new.title,new.content,new.topic);
        END;
        """)
initialize()

def authorize(x_knowledge_key: str | None = Header(default=None)):
    import hmac
    secret = os.environ.get("KNOWLEDGE_API_KEY")
    if not secret or not x_knowledge_key or not hmac.compare_digest(secret, x_knowledge_key):
        raise HTTPException(401, "Knowledge API key required")

class Entry(BaseModel):
    agent_id: str = Field(min_length=1, max_length=100)
    topic: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1)
    source_url: str | None = None
    source_date: str | None = None
    verified: bool = False

@router.post("/entries", status_code=201, dependencies=[Depends(authorize)])
def add_entry(item: Entry):
    identifier = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as c:
        c.execute("""INSERT INTO entries
            (id,agent_id,topic,title,content,source_url,source_date,verified,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (identifier,item.agent_id,item.topic,item.title,item.content,item.source_url,
             item.source_date,int(item.verified),timestamp,timestamp))
    return {"id": identifier, "stored_locally": True}

@router.get("/search", dependencies=[Depends(authorize)])
def search(q: str, agent_id: str | None = None, topic: str | None = None,
           limit: int = 10):
    if not q.strip():
        raise HTTPException(400, "Search query required")
    limit = max(1, min(limit, 50))
    # Literal substring search works for Thai without word segmentation.
    sql = """SELECT id,agent_id,topic,title,content,source_url,source_date,verified,updated_at
             FROM entries WHERE (instr(lower(title),lower(?))>0
             OR instr(lower(content),lower(?))>0 OR instr(lower(topic),lower(?))>0)"""
    params = [q,q,q]
    if agent_id:
        sql += " AND agent_id=?"
        params.append(agent_id)
    if topic:
        sql += " AND topic=?"
        params.append(topic)
    sql += " ORDER BY verified DESC, updated_at DESC LIMIT ?"
    params.append(limit)
    with connection() as c:
        return [dict(row) for row in c.execute(sql, params)]

@router.get("/entries/{entry_id}", dependencies=[Depends(authorize)])
def get_entry(entry_id: str):
    with connection() as c:
        row = c.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Entry not found")
    return dict(row)

@router.put("/entries/{entry_id}", dependencies=[Depends(authorize)])
def update_entry(entry_id: str, item: Entry):
    timestamp = datetime.now(timezone.utc).isoformat()
    with connection() as c:
        cursor = c.execute("""UPDATE entries SET agent_id=?,topic=?,title=?,content=?,
            source_url=?,source_date=?,verified=?,updated_at=? WHERE id=?""",
            (item.agent_id,item.topic,item.title,item.content,item.source_url,
             item.source_date,int(item.verified),timestamp,entry_id))
        if not cursor.rowcount:
            raise HTTPException(404, "Entry not found")
    return {"id":entry_id,"updated":True}
