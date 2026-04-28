from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
import threading
import uuid
import os
from typing import Optional

from main import build_autonomous_graph

app = FastAPI(title="Fyh_project Report API")

# simple in-memory registry of running threads
_threads = {}


class StartRequest(BaseModel):
    task_description: str
    context_data: Optional[str] = ""


@app.post("/report/start")
def start_report(req: StartRequest):
    thread_id = str(uuid.uuid4())
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


@app.get("/report/status/{thread_id}")
def report_status(thread_id: str):
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
