from pathlib import Path
import sqlite3
import uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FILES_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "task_orchestrator.db"
DATA_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Task Orchestrator API", version="0.1.0")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS agents (
          id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, role TEXT, status TEXT NOT NULL DEFAULT 'available'
        );
        CREATE TABLE IF NOT EXISTS tasks (
          id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
          assigned_agent TEXT, status TEXT NOT NULL DEFAULT 'todo',
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          FOREIGN KEY(assigned_agent) REFERENCES agents(id)
        );
        CREATE TABLE IF NOT EXISTS files (
          id TEXT PRIMARY KEY, task_id TEXT NOT NULL, original_name TEXT NOT NULL,
          stored_path TEXT NOT NULL, created_at TEXT NOT NULL,
          FOREIGN KEY(task_id) REFERENCES tasks(id)
        );
        """)
        for name, role in [
            ("Lauren", "Technical Lead / Developer"),
            ("John Wick", "Software Tester"),
            ("Khun Rabiap", "Documentation"),
            ("Nong Ing", "Project Coordinator"),
        ]:
            conn.execute("INSERT OR IGNORE INTO agents(id,name,role) VALUES(?,?,?)",
                         (name.lower().replace(" ","-"), name, role))

init_db()

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    assigned_agent: str | None = None

class TaskUpdate(BaseModel):
    status: str | None = None
    assigned_agent: str | None = None

@app.get("/health")
def health():
    return {"status": "ok", "database": str(DB_PATH), "files": str(FILES_DIR)}

@app.get("/agents")
def agents():
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM agents ORDER BY name")]

@app.get("/tasks")
def tasks():
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM tasks ORDER BY created_at DESC")]

@app.post("/tasks", status_code=201)
def create_task(item: TaskCreate):
    task_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        if item.assigned_agent and not conn.execute("SELECT 1 FROM agents WHERE id=?", (item.assigned_agent,)).fetchone():
            raise HTTPException(400, "Unknown agent")
        conn.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?)",
                     (task_id,item.title,item.description,item.assigned_agent,"todo",now,now))
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    return dict(row)

@app.patch("/tasks/{task_id}")
def update_task(task_id: str, item: TaskUpdate):
    with db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row: raise HTTPException(404, "Task not found")
        status = item.status if item.status is not None else row["status"]
        agent = item.assigned_agent if item.assigned_agent is not None else row["assigned_agent"]
        if agent and not conn.execute("SELECT 1 FROM agents WHERE id=?", (agent,)).fetchone():
            raise HTTPException(400, "Unknown agent")
        conn.execute("UPDATE tasks SET status=?,assigned_agent=?,updated_at=? WHERE id=?",
                     (status,agent,datetime.now(timezone.utc).isoformat(),task_id))
        return dict(conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone())

@app.post("/tasks/{task_id}/files", status_code=201)
async def upload_file(task_id: str, file: UploadFile = File(...)):
    with db() as conn:
        if not conn.execute("SELECT 1 FROM tasks WHERE id=?", (task_id,)).fetchone():
            raise HTTPException(404, "Task not found")
    file_id = str(uuid.uuid4())
    safe_name = Path(file.filename or "upload.bin").name
    task_dir = FILES_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    target = task_dir / f"{file_id}_{safe_name}"
    target.write_bytes(await file.read())
    now = datetime.now(timezone.utc).isoformat()
    with db() as conn:
        conn.execute("INSERT INTO files VALUES(?,?,?,?,?)",(file_id,task_id,safe_name,str(target),now))
    return {"id":file_id,"task_id":task_id,"name":safe_name,"path":str(target)}

@app.get("/tasks/{task_id}/files")
def task_files(task_id: str):
    with db() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM files WHERE task_id=? ORDER BY created_at",(task_id,))]
