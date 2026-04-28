from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
import threading
import uuid
import os
from typing import Optional, List
import shutil
app = FastAPI(title="Fyh_project Report API")

# simple in-memory registry of running threads
_threads = {}


class StartRequest(BaseModel):
    task_description: str
    context_data: Optional[str] = ""


@app.post("/report/start")
def start_report(req: StartRequest):
    thread_id = str(uuid.uuid4())
    try:
        from main import build_autonomous_graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot import graph builder: {e}")
    graph = build_autonomous_graph()
    thread_config = {"configurable": {"thread_id": thread_id}}
    initial_state = {
        "task_description": req.task_description,
        "context_data": req.context_data or "",
        "artifact_paths": [],
        "dynamic_tables": [],
        "execution_errors": [],
    }

    def runner():
        try:
            for _ in graph.stream(initial_state, config=thread_config):
                pass
        except Exception:
            pass

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    _threads[thread_id] = t
    return {"thread_id": thread_id}


@app.post("/knowledge/upload")
def upload_knowledge(files: List[UploadFile] = File(...)):
    """Accept multiple files and save them into `assets/knowledge_base/`."""
    kb_dir = os.path.join("assets", "knowledge_base")
    os.makedirs(kb_dir, exist_ok=True)
    saved = []
    for up in files:
        try:
            filename = os.path.basename(up.filename)
            dest = os.path.join(kb_dir, filename)
            # avoid overwrite by adding suffix if necessary
            if os.path.exists(dest):
                base, ext = os.path.splitext(filename)
                i = 1
                while os.path.exists(os.path.join(kb_dir, f"{base}_{i}{ext}")):
                    i += 1
                dest = os.path.join(kb_dir, f"{base}_{i}{ext}")
            with open(dest, "wb") as f:
                shutil.copyfileobj(up.file, f)
            saved.append(os.path.basename(dest))
        except Exception as e:
            return {"error": str(e)}
    return {"saved": saved}


@app.get("/knowledge/list")
def knowledge_list():
    kb_dir = os.path.join("assets", "knowledge_base")
    if not os.path.isdir(kb_dir):
        return {"files": []}
    files = sorted(os.listdir(kb_dir))
    return {"files": files}


@app.get("/report/status/{thread_id}")
def report_status(thread_id: str):
    try:
        from main import build_autonomous_graph
    except Exception as e:
        return {"status": "unavailable", "error": str(e), "state": None}
    graph = build_autonomous_graph()
    thread_config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = graph.get_state(thread_config)
    if not state_snapshot or state_snapshot.values is None:
        return {"status": "unknown", "state": None}
    current_node = state_snapshot.current_node
    if current_node is None:
        status = "completed"
    elif current_node in graph.interrupt_before:
        status = "paused_for_hitl"
    else:
        status = "running"
    return {"status": status, "current_node": current_node, "state": state_snapshot.values}


class FeedbackRequest(BaseModel):
    feedback: Optional[str] = None


@app.post("/report/feedback/{thread_id}")
def report_feedback(thread_id: str, req: FeedbackRequest):
    try:
        from main import build_autonomous_graph
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cannot import graph builder: {e}")
    graph = build_autonomous_graph()
    thread_config = {"configurable": {"thread_id": thread_id}}
    state, current_node = graph._load_checkpoint(thread_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Thread not found")

    # Add feedback into checkpoint
    if req.feedback:
        state["human_feedback"] = req.feedback

    # Save updated checkpoint at same node
    try:
        graph.checkpointer.save(thread_id, state, current_node)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # resume graph in background
    def runner():
        try:
            for _ in graph.stream(None, config=thread_config):
                pass
        except Exception:
            pass

    t = threading.Thread(target=runner, daemon=True)
    t.start()
    _threads[thread_id] = t
    return {"resumed": True}


@app.get("/report/download/{thread_id}")
def report_download(thread_id: str):
    out = os.path.join("artifacts", "Final_Academic_Report.docx")
    if not os.path.exists(out):
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(out, media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document', filename=f"Final_Academic_Report_{thread_id}.docx")
