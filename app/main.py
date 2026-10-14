from pathlib import Path
import sqlite3, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field

BASE_DIR=Path(__file__).resolve().parent.parent
DATA_DIR=BASE_DIR/"data"; FILES_DIR=DATA_DIR/"files"; DB_PATH=DATA_DIR/"task_orchestrator.db"
DATA_DIR.mkdir(exist_ok=True); FILES_DIR.mkdir(parents=True,exist_ok=True)
app=FastAPI(title="Task Orchestrator API",version="0.2.0")

def now(): return datetime.now(timezone.utc).isoformat()
def db():
    c=sqlite3.connect(DB_PATH,timeout=30,check_same_thread=False); c.row_factory=sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL"); c.execute("PRAGMA foreign_keys=ON"); return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS agents(id TEXT PRIMARY KEY,name TEXT NOT NULL UNIQUE,role TEXT,status TEXT NOT NULL DEFAULT 'available');
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT,assigned_agent TEXT,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,result TEXT,error TEXT,retry_count INTEGER NOT NULL DEFAULT 0,max_retries INTEGER NOT NULL DEFAULT 2,cancel_requested INTEGER NOT NULL DEFAULT 0,FOREIGN KEY(assigned_agent) REFERENCES agents(id));
        CREATE TABLE IF NOT EXISTS task_dependencies(task_id TEXT NOT NULL,depends_on_task_id TEXT NOT NULL,PRIMARY KEY(task_id,depends_on_task_id),FOREIGN KEY(task_id) REFERENCES tasks(id),FOREIGN KEY(depends_on_task_id) REFERENCES tasks(id));
        CREATE TABLE IF NOT EXISTS task_logs(id TEXT PRIMARY KEY,task_id TEXT NOT NULL,level TEXT NOT NULL,message TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(task_id) REFERENCES tasks(id));
        CREATE TABLE IF NOT EXISTS files(id TEXT PRIMARY KEY,task_id TEXT NOT NULL,original_name TEXT NOT NULL,stored_path TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(task_id) REFERENCES tasks(id));
        """)
        cols={r["name"] for r in c.execute("PRAGMA table_info(tasks)")}
        for name,sql in {"result":"ALTER TABLE tasks ADD COLUMN result TEXT","error":"ALTER TABLE tasks ADD COLUMN error TEXT","retry_count":"ALTER TABLE tasks ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0","max_retries":"ALTER TABLE tasks ADD COLUMN max_retries INTEGER NOT NULL DEFAULT 2","cancel_requested":"ALTER TABLE tasks ADD COLUMN cancel_requested INTEGER NOT NULL DEFAULT 0"}.items():
            if name not in cols: c.execute(sql)
        for name,role in [("Lauren","Technical Lead / Developer"),("John Wick","Software Tester"),("Khun Rabiap","Documentation"),("Nong Ing","Project Coordinator")]:
            c.execute("INSERT OR IGNORE INTO agents(id,name,role) VALUES(?,?,?)",(name.lower().replace(" ","-"),name,role))
init_db()

class TaskCreate(BaseModel):
    title:str; description:str|None=None; assigned_agent:str|None=None
    depends_on:list[str]=Field(default_factory=list); max_retries:int=2
class TaskUpdate(BaseModel):
    status:str|None=None; assigned_agent:str|None=None; result:str|None=None; error:str|None=None
class WorkflowCreate(BaseModel):
    tasks:list[TaskCreate]

def add_log(c,task_id,message,level="info"):
    c.execute("INSERT INTO task_logs VALUES(?,?,?,?,?)",(str(uuid.uuid4()),task_id,level,message,now()))
def ready(c,task_id):
    deps=c.execute("SELECT depends_on_task_id FROM task_dependencies WHERE task_id=?",(task_id,)).fetchall()
    return all((r:=c.execute("SELECT status FROM tasks WHERE id=?",(d[0],)).fetchone()) and r["status"]=="completed" for d in deps)

@app.get("/health")
def health(): return {"status":"ok","version":"0.2.0","database":str(DB_PATH)}
@app.get("/agents")
def agents():
    with db() as c:return [dict(r) for r in c.execute("SELECT * FROM agents ORDER BY name")]
@app.get("/tasks")
def tasks():
    with db() as c:return [dict(r) for r in c.execute("SELECT * FROM tasks ORDER BY created_at DESC")]
@app.get("/tasks/{task_id}")
def task(task_id:str):
    with db() as c:
        r=c.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
        if not r: raise HTTPException(404,"Task not found")
        out=dict(r); out["dependencies"]=[x[0] for x in c.execute("SELECT depends_on_task_id FROM task_dependencies WHERE task_id=?",(task_id,))]
        return out

@app.post("/tasks",status_code=201)
def create_task(item:TaskCreate):
    tid=str(uuid.uuid4()); ts=now()
    with db() as c:
        if item.assigned_agent and not c.execute("SELECT 1 FROM agents WHERE id=?",(item.assigned_agent,)).fetchone(): raise HTTPException(400,"Unknown agent")
        for dep in item.depends_on:
            if not c.execute("SELECT 1 FROM tasks WHERE id=?",(dep,)).fetchone(): raise HTTPException(400,f"Unknown dependency: {dep}")
        c.execute("INSERT INTO tasks(id,title,description,assigned_agent,status,created_at,updated_at,max_retries) VALUES(?,?,?,?,?,?,?,?)",(tid,item.title,item.description,item.assigned_agent,"pending",ts,ts,item.max_retries))
        for dep in item.depends_on:c.execute("INSERT INTO task_dependencies VALUES(?,?)",(tid,dep))
        add_log(c,tid,"Task queued")
        return dict(c.execute("SELECT * FROM tasks WHERE id=?",(tid,)).fetchone())

@app.post("/workflows",status_code=201)
def create_workflow(wf:WorkflowCreate):
    ids=[]; alias={}
    with db() as c:
        for i,item in enumerate(wf.tasks):
            tid=str(uuid.uuid4()); ids.append(tid); alias[str(i)]=tid; ts=now()
            c.execute("INSERT INTO tasks(id,title,description,assigned_agent,status,created_at,updated_at,max_retries) VALUES(?,?,?,?,?,?,?,?)",(tid,item.title,item.description,item.assigned_agent,"pending",ts,ts,item.max_retries)); add_log(c,tid,"Workflow task queued")
        for i,item in enumerate(wf.tasks):
            for dep in item.depends_on:
                target=alias.get(dep,dep)
                if target not in ids and not c.execute("SELECT 1 FROM tasks WHERE id=?",(target,)).fetchone(): raise HTTPException(400,f"Unknown dependency: {dep}")
                c.execute("INSERT INTO task_dependencies VALUES(?,?)",(ids[i],target))
    return {"task_ids":ids}

@app.post("/worker/claim")
def claim(agent_id:str):
    with db() as c:
        rows=c.execute("SELECT * FROM tasks WHERE status='pending' AND cancel_requested=0 AND (assigned_agent IS NULL OR assigned_agent=?) ORDER BY created_at",(agent_id,)).fetchall()
        for r in rows:
            if ready(c,r["id"]):
                c.execute("UPDATE tasks SET status='running',assigned_agent=?,updated_at=? WHERE id=? AND status='pending'",(agent_id,now(),r["id"]))
                if c.total_changes: add_log(c,r["id"],f"Claimed by {agent_id}"); return dict(c.execute("SELECT * FROM tasks WHERE id=?",(r["id"],)).fetchone())
    return {"task":None}

@app.post("/tasks/{task_id}/complete")
def complete(task_id:str,result:str|None=None):
    with db() as c:
        if not c.execute("SELECT 1 FROM tasks WHERE id=?",(task_id,)).fetchone(): raise HTTPException(404,"Task not found")
        c.execute("UPDATE tasks SET status='completed',result=?,error=NULL,updated_at=? WHERE id=?",(result,now(),task_id)); add_log(c,task_id,"Task completed")
    return {"id":task_id,"status":"completed"}

@app.post("/tasks/{task_id}/fail")
def fail(task_id:str,error:str):
    with db() as c:
        r=c.execute("SELECT * FROM tasks WHERE id=?",(task_id,)).fetchone()
        if not r: raise HTTPException(404,"Task not found")
        retry=r["retry_count"]+1; status="pending" if retry<=r["max_retries"] else "failed"
        c.execute("UPDATE tasks SET status=?,error=?,retry_count=?,updated_at=? WHERE id=?",(status,error,retry,now(),task_id)); add_log(c,task_id,f"Task failed; next status={status}","error")
    return {"id":task_id,"status":status,"retry_count":retry}

@app.post("/tasks/{task_id}/cancel")
def cancel(task_id:str):
    with db() as c:
        if not c.execute("SELECT 1 FROM tasks WHERE id=?",(task_id,)).fetchone(): raise HTTPException(404,"Task not found")
        c.execute("UPDATE tasks SET cancel_requested=1,status=CASE WHEN status='pending' THEN 'cancelled' ELSE status END,updated_at=? WHERE id=?",(now(),task_id)); add_log(c,task_id,"Cancellation requested","warning")
    return {"id":task_id,"cancel_requested":True}

@app.get("/tasks/{task_id}/logs")
def logs(task_id:str):
    with db() as c:return [dict(r) for r in c.execute("SELECT * FROM task_logs WHERE task_id=? ORDER BY created_at",(task_id,))]

@app.post("/tasks/{task_id}/files",status_code=201)
async def upload_file(task_id:str,file:UploadFile=File(...)):
    with db() as c:
        if not c.execute("SELECT 1 FROM tasks WHERE id=?",(task_id,)).fetchone(): raise HTTPException(404,"Task not found")
    fid=str(uuid.uuid4()); name=Path(file.filename or "upload.bin").name; d=FILES_DIR/task_id; d.mkdir(parents=True,exist_ok=True); target=d/f"{fid}_{name}"; target.write_bytes(await file.read())
    with db() as c:c.execute("INSERT INTO files VALUES(?,?,?,?,?)",(fid,task_id,name,str(target),now()))
    return {"id":fid,"task_id":task_id,"name":name,"path":str(target)}
@app.get("/tasks/{task_id}/files")
def task_files(task_id:str):
    with db() as c:return [dict(r) for r in c.execute("SELECT * FROM files WHERE task_id=? ORDER BY created_at",(task_id,))]
