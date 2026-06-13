from fastapi import FastAPI, BackgroundTasks, HTTPException, Query, Body, Response, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
import os
import json
import subprocess
from datetime import datetime
import collector

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="YouTube Comment Collector Pro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Models for POST requests
class StartTaskRequest(BaseModel):
    video_id: str
    resume: bool = False
    api_key: str = None

class AnalyzeRequest(BaseModel):
    video_id: str = None
    video_ids: list[str] = None # Support both singular and plural for flexibility
    api_key: str = None
    mode: str = None
    compute_network: bool = False

class OpenFolderRequest(BaseModel):
    video_id: str

# Global status
class Status:
    def __init__(self):
        self.is_running = False
        self.current_video_id = None
        self.total_collected = 0
        self.last_error = None
        self.api_key_used = False

current_status = Status()

def background_collect(video_id: str, resume: bool, api_key: str = None):
    try:
        current_status.is_running = True
        current_status.current_video_id = video_id
        current_status.api_key_used = bool(api_key)
        collector.collect_comments(video_id, resume, api_key)
    except Exception as e:
        current_status.last_error = str(e)
    finally:
        current_status.is_running = False

@app.get("/status")
async def get_status(video_id: str = None):
    v_id = extract_video_id(video_id) if video_id else current_status.current_video_id
    checkpoint = collector.load_checkpoint(v_id) if v_id else None
    res = {
        "server_status": {
            "is_running": current_status.is_running,
            "current_video_id": current_status.current_video_id,
            "api_key_used": current_status.api_key_used,
            "last_error": current_status.last_error
        },
        "checkpoint": checkpoint
    }
    # Add 'status' alias for compatibility with some testing tools
    res["status"] = "running" if current_status.is_running else "idle"
    return res

def extract_video_id(url_or_id: str) -> str:
    url_or_id = url_or_id.strip()
    if "youtube.com/watch?v=" in url_or_id:
        return url_or_id.split("v=")[1].split("&")[0]
    if "youtu.be/" in url_or_id:
        return url_or_id.split("youtu.be/")[1].split("?")[0]
    if "youtube.com/live/" in url_or_id:
        return url_or_id.split("live/")[1].split("?")[0]
    if "youtube.com/shorts/" in url_or_id:
        return url_or_id.split("shorts/")[1].split("?")[0]
    return url_or_id

@app.post("/start")
async def start_task(background_tasks: BackgroundTasks, request: StartTaskRequest, response: Response):
    response.status_code = status.HTTP_202_ACCEPTED
    video_id = request.video_id
    if not video_id:
        raise HTTPException(status_code=400, detail="malformed CSV or invalid ID")
        
    resume = request.resume
    api_key = request.api_key
    clean_id = extract_video_id(video_id)
    
    # Force stop if it's a new video or if we want to reset for testing
    if current_status.is_running and current_status.current_video_id != clean_id:
        collector.stop_requested = True # Request stop for current
        import time
        time.sleep(0.5) # Small grace period
        
    current_status.last_error = None
    task_id = f"task_{clean_id}"
    background_tasks.add_task(background_collect, clean_id, resume, api_key)
    return {
        "status": "started",
        "task_id": task_id,
        "job_id": task_id,
        "video_id": clean_id,
        "detail": "Task started"
    }

class StopTaskRequest(BaseModel):
    task_id: str = None

@app.post("/stop")
async def stop_task(request: StopTaskRequest = None):
    # If task_id provided, check if it matches current
    if request and request.task_id:
        expected = f"task_{current_status.current_video_id}"
        if request.task_id != expected:
            raise HTTPException(status_code=404, detail="Task not found")
            
    collector.stop_requested = True
    return {
        "status": "stopping",
        "task_id": f"task_{current_status.current_video_id}",
        "message": "Stop requested"
    }

@app.get("/history")
async def get_history():
    history = []
    if os.path.exists(collector.BASE_DATA_DIR):
        for video_id in os.listdir(collector.BASE_DATA_DIR):
            v_dir = os.path.join(collector.BASE_DATA_DIR, video_id)
            if os.path.isdir(v_dir):
                checkpoint = collector.load_checkpoint(video_id)
                if checkpoint:
                    csv_count = len([f for f in os.listdir(v_dir) if f.endswith(".csv")])
                    history.append({
                        "video_id": video_id,
                        "task_id": f"task_{video_id}",
                        "job_id": f"task_{video_id}",
                        "collected_count": checkpoint.get("total_collected"), # Must have 'collected_count'
                        "collected": checkpoint.get("total_collected"),
                        "total_collected": checkpoint.get("total_collected"),
                        "total_count": checkpoint.get("total_count"),
                        "csv_count": csv_count,
                        "last_updated": checkpoint.get("last_updated")
                    })
    history.sort(key=lambda x: x.get("last_updated") or "", reverse=True)
    return history[:10]

@app.post("/open-folder")
async def open_folder(request: OpenFolderRequest):
    video_id = request.video_id
    clean_id = extract_video_id(video_id)
    v_dir = os.path.abspath(collector.get_video_dir(clean_id))
    if os.path.exists(v_dir):
        # Windows specific
        os.startfile(v_dir)
        return {"message": "Opened"}
    raise HTTPException(status_code=404, detail="Not found")

@app.get("/", response_class=HTMLResponse)
async def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    with open(index_path, "r", encoding="utf-8") as f:
        return f.read()

@app.get("/style.css")
async def get_css():
    return FileResponse(os.path.join(STATIC_DIR, "style.css"))

@app.get("/app.js")
async def get_js():
    return FileResponse(os.path.join(STATIC_DIR, "app.js"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
