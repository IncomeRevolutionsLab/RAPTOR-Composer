import os
import json
import time
import re
import traceback
import httpx
from typing import List, Optional, Literal
from fastapi import FastAPI, Header, HTTPException, Request, Depends, Cookie, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field, model_validator
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from anthropic import Anthropic
from datetime import datetime, timedelta, date
import uuid
import shutil
import requests
import base64
import io
from PIL import Image

from backend.services.ffmpeg_worker import ffmpeg_worker
from dotenv import load_dotenv
from cryptography.fernet import Fernet
import secrets
# [v2.15.0] import jwt (PyJWT) ?œê±° ??Supabase SDK get_user()ë¡??„í™˜
import asyncio
import zipstream

load_dotenv()

# Fernet Key Fail-Fast Verification
COOKIE_ENCRYPTION_KEY = os.getenv("COOKIE_ENCRYPTION_KEY")
if not COOKIE_ENCRYPTION_KEY:
    raise RuntimeError("COOKIE_ENCRYPTION_KEY must be set in .env")
try:
    fernet = Fernet(COOKIE_ENCRYPTION_KEY.encode())
except Exception as e:
    raise RuntimeError(f"Invalid COOKIE_ENCRYPTION_KEY format: {str(e)}")

# Fail-Fast Verification for Webhook and JWT secrets
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET must be set in .env")

# [v2.15.0] SUPABASE_JWT_SECRET ?˜ì¡´???„ì „ ?œê±° ??ECC(P-256) ?€?‘ìœ¼ë¡?SDK ?„ì„ ?„í™˜

IS_PROD = os.getenv("ENV", "development").lower() in ["production", "prod"]

MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 500 * 1024 * 1024

class KIEHTTPClient(httpx.Client):
    def __init__(self, decrypted_key: str, *args, **kwargs):
        self.decrypted_key = decrypted_key.strip()
        super().__init__(*args, **kwargs)

    def send(self, request, *args, **kwargs):
        if "x-api-key" in request.headers:
            del request.headers["x-api-key"]
        request.headers["Authorization"] = f"Bearer {self.decrypted_key}"
        request.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        return super().send(request, *args, **kwargs)

app = FastAPI()
db_lock = asyncio.Lock()

# Supabase Environment Variable Check
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("\n" + "="*60)
    print("ê²½ê³ : .env ?Œì¼??SUPABASE_URLê³?SUPABASE_KEYë¥??¤ì •?´ì£¼?¸ìš”.")
    print("="*60 + "\n")

# --- System Prompt Caching ---
COMBINED_SYSTEM_PROMPT = ""

def load_raptor_prompts():
    global COMBINED_SYSTEM_PROMPT
    base_dir = os.path.dirname(os.path.abspath(__file__))
    files = [
        "RAPTOR_V2_1_MAIN_v2.2.md",
        "RAPTOR_V2_1_CORE_CONVERSION_PLM.txt",
        "RAPTOR_V2_1_SCRIPT_PLM.txt",
        "RAPTOR_V2_1_SCENE_IMAGE_PLM.txt",
        "RAPTOR_V2_1_TITLE_PLM.txt",
        "RAPTOR_V2_1_UPLOAD_PLM.txt"
    ]
    
    combined_text = ""
    for f in files:
        path = os.path.join(base_dir, f)
        if os.path.exists(path):
            try:
                # ?ˆë„???˜ê²½ ?œê? ê¹¨ì§ ë°?UnicodeDecodeError ?ì²œ ì°¨ë‹¨
                with open(path, "r", encoding="utf-8", errors="replace") as file:
                    content = file.read()
                    combined_text += f"\n\n--- FILE: {f} ---\n"
                    combined_text += content
            except Exception as e:
                print(f"[ERROR] Unexpected error loading {f}: {str(e)}")
        else:
            print(f"[WARNING] Prompt file missing: {path}")
            
    COMBINED_SYSTEM_PROMPT = combined_text
    print(f"[INIT] Combined System Prompt Loaded ({len(COMBINED_SYSTEM_PROMPT)} chars)")

# Load prompts at startup
load_raptor_prompts()

# Ensure outputs directory exists
if not os.path.exists("outputs"):
    os.makedirs("outputs")

app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
origins = ["http://localhost:3000", "http://127.0.0.1:3000", "https://raptor-composer.vercel.app"]
if allowed_origins_env:
    origins.extend([o.strip() for o in allowed_origins_env.split(",") if o.strip()])
origins = list(set(origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CSRF & Cookie Helpers
def generate_csrf_token() -> str:
    return secrets.token_hex(32)

async def verify_csrf(
    request: Request,
    raptor_csrf: Optional[str] = Cookie(None),
    x_csrf_token: Optional[str] = Header(None)
):
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return
    if not raptor_csrf or not x_csrf_token or not secrets.compare_digest(raptor_csrf, x_csrf_token):
        raise HTTPException(status_code=403, detail="CSRF token validation failed")

def get_decrypted_key(x_byok_kie: Optional[str] = Header(None)) -> str:
    if not x_byok_kie or not x_byok_kie.strip():
        raise HTTPException(status_code=401, detail="API Keyê°€ ?¤ì •?˜ì? ?Šì•˜?µë‹ˆ?? Global Settings?ì„œ KIE API Keyë¥??…ë ¥??ì£¼ì„¸??")
    return x_byok_kie.strip()

def get_jwt_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    [v2.15.0] ECC(P-256) ?€????PyJWT ?˜ë™ ê²€ì¦?ì² ê±°, Supabase SDK ?„ì„ ë°©ì‹?¼ë¡œ ?„í™˜
    - supabase.auth.get_user(token): SDK ?ˆë²¨?ì„œ JWKS ?ë™ ì²˜ë¦¬ (HS256/ES256 ëª¨ë‘ ì§€??
    - sync def ? ì?: FastAPIê°€ ?¤ë ˆ?œí??ì„œ ?¤í–‰ ???´ë²¤??ë£¨í”„ ì°¨ë‹¨ ?†ìŒ
    - Claude Code Pre-Review ê¶Œê³  ë°˜ì˜: ?ˆì™¸ ë©”ì‹œì§€ ?€??+ ?¬ë°”ë¥??ˆì™¸ ?„íŒŒ
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="?¸ì¦ ?¤ë”ê°€ ?„ë½?˜ì—ˆê±°ë‚˜ ?•ì‹???¬ë°”ë¥´ì? ?ŠìŠµ?ˆë‹¤.")
    token = authorization.split(" ", 1)[1]
    try:
        response = supabase.auth.get_user(token)
        user = response.user
        if not user or not user.id:
            raise HTTPException(status_code=401, detail="? íš¨?˜ì? ?Šì? ? í°?…ë‹ˆ??")
        return user.id
    except HTTPException:
        raise
    except Exception as e:
        # [SECURITY] ?´ë? ?ëŸ¬ ë©”ì‹œì§€ ?´ë¼?´ì–¸???¸ì¶œ ë°©ì? ???œë²„ ë¡œê·¸?ë§Œ ?ì„¸ ê¸°ë¡
        print(f"[AUTH ERROR] get_user failed: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=401, detail="? íš¨?˜ì? ?Šì? ? í°?…ë‹ˆ??")

def map_image_model(model_name: Optional[str]) -> str:
    if not model_name:
        return "gpt-image-2-text-to-image"
    normalized = model_name.lower().strip()
    if "openai" in normalized or "gpt-image-2" in normalized or "gpt image 2" in normalized or "dall-e" in normalized or "dalle" in normalized:
        return "gpt-image-2-text-to-image"
    elif "grok" in normalized:
        return "grok-imagine/text-to-image"
    elif "banana" in normalized:
        return "nano-banana-2"
    return model_name



# --- Database Configuration ---
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mock-project.supabase.co")
# S-004: ë°±ì—”???´ë? DB ?°ë™?€ RLS ?°íšŒ ë°??°ì´??ì§ì ‘ ?œì–´ê°€ ?„ìš”?˜ë?ë¡?SUPABASE_SERVICE_ROLE_KEY ?¬ìš©
# ë§Œì•½ ?˜ê²½ë³€??SUPABASE_SERVICE_ROLE_KEYê°€ ?•ì˜?˜ì–´ ?ˆì? ?Šìœ¼ë©?ê¸°ì¡´ SUPABASE_KEYë¥??´ë°±?¼ë¡œ ?¬ìš©
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_KEY", "mock-service-role-key-123456789"))
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def sanitize_uuid(user_id_str: str) -> str:
    uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    if uuid_pattern.match(user_id_str):
        return user_id_str
    raise HTTPException(status_code=400, detail="Invalid user ID format (UUID expected).")

async def upload_image_to_supabase(image_url: str, scene_id: int) -> tuple[str, str]:
    """
    [A-005] ?´ë?ì§€ ?¤ìš´ë¡œë“œ ë°?Supabase ?¤í† ë¦¬ì? ?…ë¡œ??ë¡œì§???¨ì¼??
    [S-006] Supabase Storage assets ë²„í‚·??Private?¼ë¡œ ?„í™˜?˜ê³ , 30ë¶?ë§Œë£Œ(TTL) ?œëª…??URL ë°œê¸‰
    """
    import base64
    import time
    if image_url.startswith("data:image"):
        header, encoded = image_url.split(",", 1)
        img_bytes = base64.b64decode(encoded)
    else:
        async with httpx.AsyncClient() as client:
            img_res = await client.get(image_url, timeout=30.0)
            img_res.raise_for_status()
            img_bytes = img_res.content
            
    file_name = f"raptor_{int(time.time())}_{scene_id}.png"
    
    loop = asyncio.get_event_loop()
    def _upload_and_sign():
        # upload
        supabase.storage.from_("assets").upload(
            path=file_name,
            file=img_bytes,
            file_options={"content-type": "image/png"}
        )
        # 30ë¶?1800ì´? ? íš¨??Signed URL ë°œê¸‰
        signed_res = supabase.storage.from_("assets").create_signed_url(file_name, 1800)
        signed_url = None
        if isinstance(signed_res, dict):
            signed_url = signed_res.get("signedURL") or signed_res.get("signedUrl")
        elif isinstance(signed_res, str):
            signed_url = signed_res
        
        if not signed_url:
            raise RuntimeError(f"Failed to generate signed URL for {file_name}: {signed_res}")
        return signed_url

    signed_url = await loop.run_in_executor(None, _upload_and_sign)
    return signed_url, file_name

class ProjectModel(BaseModel):
    project_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    created_at: datetime
    user_id: str = Field(min_length=1)
    plan_snapshot: Optional[dict] = None

class TaskModel(BaseModel):
    task_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    task_type: Literal['text_generation', 'image_generation', 'video_generation', 'final_render']
    description: str = Field(min_length=1)
    status: Literal['pending', 'processing', 'success', 'failed']
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime


# --- New Pydantic Models for Webhook Revamp ---
class Scene(BaseModel):
    scene_index: int
    duration_seconds: Literal[3, 5, 7]
    prompt: str = Field(min_length=10)
    subtitle: str = Field(max_length=200)
    user_video_id: Optional[str] = None

class PlanOutput(BaseModel):
    product_name: str
    selected_pattern: str
    scenes: List[Scene] = Field(min_length=3, max_length=8)
    title: str = Field(max_length=100)
    hashtags: List[str] = Field(max_length=10)
    total_duration: int

    @model_validator(mode="after")
    def validate_total_duration(self) -> "PlanOutput":
        expected = sum(s.duration_seconds for s in self.scenes)
        if self.total_duration != expected:
            raise ValueError(f"total_duration {self.total_duration} != {expected}")
        return self

class RenderTaskRequest(BaseModel):
    plan: PlanOutput
    voice_type: Literal["male", "female", "none"]
    aspect_ratio: Literal["9:16", "1:1", "16:9"]
    callback_url: str

class RenderTaskStatus(BaseModel):
    task_id: str
    status: Literal["pending", "processing", "completed", "failed"]
    result_url: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

class KieWebhookPayload(BaseModel):
    task_id: str
    status: Literal["completed", "failed"]
    result_url: Optional[str] = None
    error: Optional[str] = None

class UserVideoAsset(BaseModel):
    id: str
    filename: str
    duration_seconds: float
    uploaded_at: datetime

# --- Models ---

class ScrapeRequest(BaseModel):
    url: str

class PlanRequest(BaseModel):
    name: Optional[str] = None
    product_name: Optional[str] = None
    description: str
    images: List[str] = []
    duration: int = 15
    target_language: str = "?œêµ­??
    mode: str = "auto"
    model: Optional[str] = None
    selected_pattern: Optional[str] = None # Added HIL Pattern Support
    purpose: Optional[str] = None
    target_audience: Optional[str] = None
    tone: Optional[str] = None
    manual_additions: Optional[dict] = None

class ImageGenRequest(BaseModel):
    product_name: str
    scenes: List[dict]
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    model: Optional[str] = "gpt-image-2-text-to-image"

class RefinePromptRequest(BaseModel):
    product_name: str
    current_scene: dict
    user_feedback: str
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    model: Optional[str] = "gpt-image-2-text-to-image"

class VideoGenRequest(BaseModel):

    product_name: str
    scenes: List[dict]
    engine: str = "grok"
    rendering_mode: str = "full"
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"

class RenderRequest(BaseModel):
    product_name: str
    scenes: List[dict]
    voice_type: str = "?¬ì„±-ë°œë„??
    status: str

class RenderStreamRequest(BaseModel):
    product_name: str
    scenes: List[dict]
    voice_type: str = "?¬ì„±-ë°œë„??
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    quality: str = "export"
    subtitle_position: str = "??
    subtitle_font: str = "BlackHanSans"
    render_duration: str = "?ë§‰ ë§ì¶¤ ê¸¸ì´ (Dynamic Sync)"
    watermark_enabled: bool = False
    watermark_logo: Optional[str] = None
    watermark_position: str = "top-right"
    user_id: str
    upload_package: Optional[dict] = None
    engine: str = "grok"
    rendering_mode: str = "full"
    project_id: Optional[str] = None


# --- Configuration ---
DEFAULT_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
CLAUDE_FALLBACK_OPUS = "claude-opus-4-7"
CLAUDE_FALLBACK_HAIKU = "claude-haiku-4-5"

import shutil

class ProjectCreateRequest(BaseModel):
    product_name: str
    user_id: str

class TaskCreateRequest(BaseModel):
    task_id: str
    task_type: Literal['text_generation', 'image_generation', 'video_generation', 'final_render']
    description: str

class TaskUpdateRequest(BaseModel):
    status: Literal['pending', 'processing', 'success', 'failed']
    result_url: Optional[str] = None
    error: Optional[str] = None

async def create_project_in_db(product_name: str, user_id: str) -> dict:
    project_id = str(uuid.uuid4())
    sanitized_user = sanitize_uuid(user_id)
    new_project = {
        "project_id": project_id,
        "product_name": product_name,
        "created_at": datetime.now().isoformat(),
        "user_id": sanitized_user,
        "plan_snapshot": {}
    }
    
    res = supabase.table("projects").insert(new_project).execute()
    if not res.data:
        raise Exception("Failed to insert project into Supabase database")
    return res.data[0]

async def create_task_in_db(project_id: str, task_id: str, task_type: str, description: str) -> dict:
    new_task = {
        "task_id": task_id,
        "project_id": project_id,
        "task_type": task_type,
        "description": description,
        "status": "pending",
        "result_url": None,
        "error": None,
        "created_at": datetime.now().isoformat()
    }
    
    res = supabase.table("tasks").insert(new_task).execute()
    if not res.data:
        raise Exception("Failed to insert task into Supabase database")
    return res.data[0]

async def update_task_in_db(task_id: str, status: str, result_url: str = None, error: str = None) -> dict:
    update_data = {"status": status}
    if result_url is not None:
        update_data["result_url"] = result_url
    if error is not None:
        update_data["error"] = error
        
    res = supabase.table("tasks").update(update_data).eq("task_id", task_id).execute()
    if not res.data:
        return {}
    return res.data[0]

def _supabase_retry(operation, max_retries: int = 2, delay: float = 0.5):
    """Retry a Supabase call on transient network/API failure."""
    last_exc: Exception = None
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                print(f"[Supabase Retry] Attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
    raise last_exc

async def enforce_user_fifo_limit(user_id: str, limit: int):
    """
    [P-006] FIFO ?œë„ ?•ë¦¬ ë¡œì§??ê³µí†µ ?¨ìˆ˜ë¡??¨ì¼??
    """
    sanitized_user = sanitize_uuid(user_id)
    res_projects = _supabase_retry(lambda: supabase.table("projects").select("project_id, created_at").eq("user_id", sanitized_user).execute())
    user_projects = res_projects.data or []
    
    if len(user_projects) > limit:
        user_projects.sort(key=lambda x: x.get("created_at", ""))
        excess_count = len(user_projects) - limit
        to_delete = user_projects[:excess_count]
        to_delete_ids = [p.get("project_id") for p in to_delete]
        
        # CASCADE delete: Supabase will delete tasks automatically
        res_tasks = _supabase_retry(lambda: supabase.table("tasks").select("task_id").in_("project_id", to_delete_ids).execute())
        tasks_to_delete = res_tasks.data or []
        for t in tasks_to_delete:
            t_id = t.get("task_id")
            # Delete physical storage (.mp4)
            mp4_path = f"outputs/raptor_{t_id}.mp4"
            if os.path.exists(mp4_path):
                try: os.remove(mp4_path)
                except: pass
            # Delete temp image assets
            temp_dir = f"outputs/temp_{t_id}"
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
                
        try:
            _supabase_retry(lambda: supabase.table("projects").delete().in_("project_id", to_delete_ids).execute())
            print(f"[CASCADE FIFO] Cleaned up oldest projects: {to_delete_ids} to enforce limit {limit}")
        except Exception as e:
            print(f"[CASCADE FIFO] Warning: FIFO enforcement failed (non-critical, skipped): {str(e)}")

async def check_and_enforce_user_limits(user_id: str = "beta_tester"):
    sanitized_user = sanitize_uuid(user_id)
    current_month = datetime.now().strftime("%Y-%m")
    
    res_projects = supabase.table("projects").select("*").eq("user_id", sanitized_user).execute()
    user_projects = res_projects.data or []
    
    # 1. Monthly Limit Check (10 projects per month)
    monthly_count = len([p for p in user_projects if p.get("created_at", "").startswith(current_month)])
    if monthly_count >= 10:
        raise Exception("ë² í? ?ŒìŠ¤???”ê°„ ?„ë¡œ?íŠ¸ ?ì„± ?œë„(10ê°?ë¥?ì´ˆê³¼?ˆìŠµ?ˆë‹¤. ?¤ìŒ ?¬ì— ?¤ì‹œ ?´ìš©??ì£¼ì„¸??")
        
    # 2. Project FIFO Storage Limit (Max 10 projects)
    await enforce_user_fifo_limit(sanitized_user, 9)

async def record_user_asset(user_id: str, task_id: str, output_url: str, product_name: str = "", title: str = "", thumbnail_url: str = "", upload_package: dict = None):
    project_id = f"proj_{task_id}"
    sanitized_user = sanitize_uuid(user_id)
    
    res_proj = supabase.table("projects").select("project_id").eq("project_id", project_id).execute()
    if not res_proj.data:
        new_project = {
            "project_id": project_id,
            "product_name": product_name or f"Project {task_id}",
            "created_at": datetime.now().isoformat(),
            "user_id": sanitized_user,
            "plan_snapshot": upload_package or {}
        }
        supabase.table("projects").insert(new_project).execute()
        
    res_task = supabase.table("tasks").select("task_id").eq("task_id", task_id).execute()
    if not res_task.data:
        new_task = {
            "task_id": task_id,
            "project_id": project_id,
            "task_type": "final_render",
            "description": title or "ìµœì¢… ?Œë”ë§??„ë£Œ",
            "status": "success",
            "result_url": output_url,
            "error": None,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("tasks").insert(new_task).execute()

@app.get("/api/user-videos")
async def get_user_videos(user_id: str, jwt_user_id: str = Depends(get_jwt_user_id)):
    if user_id != jwt_user_id:
        raise HTTPException(status_code=403, detail="?€?¸ì˜ ë¹„ë””??ëª©ë¡??ì¡°íšŒ??ê¶Œí•œ???†ìŠµ?ˆë‹¤.")
        
    sanitized_user = sanitize_uuid(user_id)
    res_proj = supabase.table("projects").select("*").eq("user_id", sanitized_user).execute()
    user_projects = res_proj.data or []
    proj_map = {p.get("project_id"): p for p in user_projects}
    proj_ids = list(proj_map.keys())
    
    if not proj_ids:
        return {"videos": []}
        
    res_tasks = supabase.table("tasks").select("*").in_("project_id", proj_ids).eq("task_type", "final_render").eq("status", "success").execute()
    tasks = res_tasks.data or []
    
    videos = []
    for task in tasks:
        p_id = task.get("project_id")
        proj = proj_map[p_id]
        videos.append({
            "user_id": user_id,
            "task_id": task.get("task_id"),
            "output_url": task.get("result_url"),
            "product_name": proj.get("product_name"),
            "title": task.get("description"),
            "thumbnail_url": "/real_velociraptor.png",
            "upload_package": proj.get("plan_snapshot") or {},
            "created_at": task.get("created_at")
        })
        
    videos.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"videos": videos[:5]}

TASK_EVENTS = {}

# ?„ë¡œ?íŠ¸ ?Œìœ ê¶?ê²€ì¦??¬í¼ (IDOR ë°©ì–´)
def verify_project_owner(project_id: str, user_id: str):
    sanitized_user = sanitize_uuid(user_id)
    res = supabase.table("projects").select("user_id").eq("project_id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="?„ë¡œ?íŠ¸ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.")
    if res.data[0].get("user_id") != sanitized_user:
        raise HTTPException(status_code=403, detail="?„ë¡œ?íŠ¸???‘ê·¼??ê¶Œí•œ???†ìŠµ?ˆë‹¤.")

# ?œìŠ¤???Œìœ ê¶?ê²€ì¦??¬í¼ (IDOR ë°©ì–´)
def verify_task_owner(task_id: str, user_id: str):
    res = supabase.table("tasks").select("project_id").eq("task_id", task_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="?œìŠ¤?¬ë? ì°¾ì„ ???†ìŠµ?ˆë‹¤.")
    proj_id = res.data[0].get("project_id")
    verify_project_owner(proj_id, user_id)

@app.post("/api/projects", status_code=201)
async def create_project(req: ProjectCreateRequest, jwt_user_id: str = Depends(get_jwt_user_id)):
    req.user_id = jwt_user_id
    sanitized_user = sanitize_uuid(req.user_id)
    async with db_lock:
        await check_and_enforce_user_limits(sanitized_user)
        return await create_project_in_db(req.product_name, sanitized_user)

@app.post("/api/projects/{project_id}/tasks", status_code=201)
async def create_task_endpoint(
    project_id: str,
    req: TaskCreateRequest,
    jwt_user_id: str = Depends(get_jwt_user_id)
):
    verify_project_owner(project_id, jwt_user_id)
    return await create_task_in_db(project_id, req.task_id, req.task_type, req.description)

@app.patch("/api/tasks/{task_id}")
async def update_task_endpoint(
    task_id: str,
    req: TaskUpdateRequest,
    jwt_user_id: str = Depends(get_jwt_user_id)
):
    verify_task_owner(task_id, jwt_user_id)
    task = await update_task_in_db(task_id, req.status, req.result_url, req.error)
    if not task:
        raise HTTPException(status_code=404, detail="?œìŠ¤?¬ë? ì°¾ì„ ???†ìŠµ?ˆë‹¤.")
    return task

@app.get("/api/dashboard/projects")
async def get_dashboard_projects(user_id: str, jwt_user_id: str = Depends(get_jwt_user_id)):
    if user_id != jwt_user_id:
        raise HTTPException(status_code=403, detail="?€?¸ì˜ ?„ë¡œ?íŠ¸ ëª©ë¡??ì¡°íšŒ??ê¶Œí•œ???†ìŠµ?ˆë‹¤.")
        
    sanitized_user = sanitize_uuid(user_id)
    res_proj = supabase.table("projects").select("*").eq("user_id", sanitized_user).execute()
    user_projects = res_proj.data or []
    proj_map = {p.get("project_id"): p for p in user_projects}
    proj_ids = list(proj_map.keys())
    
    if not proj_ids:
        return {"rows": []}
        
    res_tasks = supabase.table("tasks").select("*").in_("project_id", proj_ids).execute()
    tasks = res_tasks.data or []
    
    rows = []
    for task in tasks:
        p_id = task.get("project_id")
        if p_id in proj_map:
            proj = proj_map[p_id]
            rows.append({
                "product_name": proj.get("product_name"),
                "project_id": p_id,
                "task_id": task.get("task_id"),
                "description": task.get("description"),
                "status": task.get("status"),
                "result_url": task.get("result_url"),
                "created_at": task.get("created_at")
            })
            
    rows.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return {"rows": rows}

@app.get("/api/status/render")
async def get_render_status():
    """
    ?„ì¬ DB?ì„œ ?Œë”ë§?final_render) ì¤‘ì¸(pending ?ëŠ” processing) ?œìŠ¤??ê°œìˆ˜ë¥?ë°˜í™˜?©ë‹ˆ??
    """
    res = supabase.table("tasks").select("task_id", count="exact").eq("task_type", "final_render").in_("status", ["pending", "processing"]).execute()
    count = res.count if hasattr(res, "count") and res.count is not None else len(res.data)
    return {"active_renders": count}

@app.get("/api/projects/{project_id}/download-assets")
async def download_assets(project_id: str, token: str = Query(..., description="JWT access token from frontend for window.open bypass")):
    """
    ì£¼ì–´ì§??„ë¡œ?íŠ¸??ëª¨ë“  ?ë³¸ ?ì…‹(?´ë?ì§€/ë¹„ë””???ë§‰ ?????¤íŠ¸ë¦¬ë° ZIP?¼ë¡œ ë¬¶ì–´ ë°˜í™˜?©ë‹ˆ??
    (?œë²„ ë©”ëª¨ë¦?ì´ˆê³¼ ë°©ì–´ - OOM ë°©ì? ë°?ë³´ì•ˆ ê°€??
    """
    try:
        response = supabase.auth.get_user(token)
        jwt_user_id = response.user.id
        if not jwt_user_id:
            raise ValueError("No user id")
    except Exception as e:
        raise HTTPException(status_code=401, detail="? íš¨?˜ì? ?Šì? ? í°?…ë‹ˆ??")

    # 1. ?„ë¡œ?íŠ¸ ?¤ëƒ…??ë°??Œìœ ??ì¡°íšŒ
    res_proj = supabase.table("projects").select("plan_snapshot, user_id").eq("project_id", project_id).execute()
    if not res_proj.data:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # 2. ?Œìœ ê¶?ê²€ì¦?(IDOR ë°©ì–´)
    project_owner_id = res_proj.data[0].get("user_id")
    if project_owner_id != jwt_user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You do not have permission to access this project's assets.")
        
    plan_snapshot = res_proj.data[0].get("plan_snapshot") or {}
    scenes = plan_snapshot.get("scenes", [])
    
    # ?œë„ˆ?ˆì´?°ë? ?œìš©??ë¹„ë™ê¸??¤ìš´ë¡œë“œ ë°??¤íŠ¸ë¦¬ë°
    def iter_zip():
        z = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)
        
        # ???°ì´???•ë¦¬ ë°??„ì¹´?´ë¹™ (?¨ìˆœ ?ìŠ¤???¬í•¨)
        script_text = ""
        for i, scene in enumerate(scenes):
            scene_num = i + 1
            script_text += f"--- Scene {scene_num} ---\n"
            script_text += f"Duration: {scene.get('duration_seconds', 0)}s\n"
            script_text += f"Prompt: {scene.get('prompt', '')}\n"
            script_text += f"Subtitle: {scene.get('subtitle', '')}\n\n"
            
            # ?¬ê¸°???¸ë? URL ?¤íŠ¸ë¦¬ë° ?¤ìš´ë¡œë“œ ë¡œì§?€ ?œê°„/ë³µì¡???œì•½??httpx???™ê¸° ?œë„ˆ?ˆì´???˜í•‘???„ìš”?œë°,
            # zipstream?€ ?™ê¸° ?œë„ˆ?ˆì´?°ë? ?”êµ¬?©ë‹ˆ?? 
            # ?°ë¼??URL ëª©ë¡???ìŠ¤?¸ì— ?¬í•¨?œí‚¤??ë°©ì‹?¼ë¡œ ?¬í”Œ??MVP ?ì…‹ ë²ˆë“¤??êµ¬ì„±?©ë‹ˆ??
            image_url = scene.get('image_url')
            video_url = scene.get('video_url')
            user_video_id = scene.get('user_video_id')
            if image_url: script_text += f"Image URL: {image_url}\n"
            if video_url: script_text += f"Video URL: {video_url}\n"
            if user_video_id: script_text += f"User Video ID: {user_video_id}\n"
            script_text += "\n"
            
        z.write_iter("script_and_assets_links.txt", iter([script_text.encode("utf-8")]))
        
        for chunk in z:
            yield chunk

    response = StreamingResponse(iter_zip(), media_type="application/zip")
    response.headers["Content-Disposition"] = f"attachment; filename=raptor_assets_{project_id}.zip"
    return response

# --- Endpoints ---

class AuthRequest(BaseModel):
    email: str
    password: str

@app.post("/api/auth/signup")
async def auth_signup(req: AuthRequest):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase ?¤ì •??êµ¬ì„±?˜ì? ?Šì•˜?µë‹ˆ??")
    
    # S-001: ?¼ë°˜ signup API (/auth/v1/signup) ?¬ìš©?¼ë¡œ ?„í™˜. anon key ?¬ìš© ê°€??
    url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/signup"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "email": req.email,
        "password": req.password
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=data, timeout=10.0)
            resp_data = resp.json()
            if resp.status_code != 200 and resp.status_code != 201:
                error_msg = resp_data.get("msg") or resp_data.get("error_description") or resp_data.get("error", {}).get("message") or "?Œì›ê°€???¤íŒ¨"
                raise HTTPException(status_code=resp.status_code, detail=error_msg)
            return {"user": resp_data}
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"?¸ì¦ ?œë²„ ?µì‹  ?¤íŒ¨: {str(e)}")

@app.post("/api/auth/signin")
async def auth_signin(req: AuthRequest):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase ?¤ì •??êµ¬ì„±?˜ì? ?Šì•˜?µë‹ˆ??")
    
    url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password"
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "email": req.email,
        "password": req.password
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=data, timeout=10.0)
            resp_data = resp.json()
            if resp.status_code != 200:
                error_msg = resp_data.get("error_description") or resp_data.get("msg") or "ë¡œê·¸???¤íŒ¨"
                raise HTTPException(status_code=resp.status_code, detail=error_msg)
            return resp_data
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"?¸ì¦ ?œë²„ ?µì‹  ?¤íŒ¨: {str(e)}")

class KeyConfigRequest(BaseModel):
    kie_key: str

@app.get("/api/auth/csrf-token")
async def get_csrf_token():
    csrf_token = generate_csrf_token()
    from fastapi.responses import JSONResponse
    res = JSONResponse(content={"csrf_token": csrf_token})
    res.set_cookie(
        key="raptor_csrf",
        value=csrf_token,
        httponly=False,
        secure=IS_PROD,
        samesite="none",
        max_age=2592000
    )
    return res

@app.post("/api/auth/set-key")
async def set_key(request: KeyConfigRequest):
    csrf_token = generate_csrf_token()
    from fastapi.responses import JSONResponse
    res = JSONResponse(content={"message": "API Key configured successfully", "csrf_token": csrf_token})
    res.set_cookie(
        key="raptor_csrf",
        value=csrf_token,
        httponly=False,
        secure=IS_PROD,
        samesite="none",
        max_age=2592000
    )
    return res

@app.post("/api/auth/clear-key")
async def clear_key():
    from fastapi.responses import JSONResponse
    res = JSONResponse(content={"message": "API Key cleared successfully"})
    res.delete_cookie(key="raptor_csrf", secure=IS_PROD, samesite="none")
    return res

@app.get("/api/auth/check-key")
async def check_key(x_byok_kie: Optional[str] = Header(None)):
    configured = bool(x_byok_kie and x_byok_kie.strip())
    csrf_token = generate_csrf_token()
    from fastapi.responses import JSONResponse
    res = JSONResponse(content={"configured": configured, "csrf_token": csrf_token})
    res.set_cookie(
        key="raptor_csrf",
        value=csrf_token,
        httponly=False,
        secure=IS_PROD,
        samesite="none",
        max_age=2592000
    )
    return res


@app.post("/api/auth/review-plan")
async def review_plan(decrypted_key: str = Depends(get_decrypted_key)):
    # ?™ì ?¼ë¡œ ê°€??ìµœì‹ ??implementation_plan.mdê°€ ?„ì¹˜??brain ?´ë” ê²½ë¡œë¥?ê°ì??©ë‹ˆ??
    user_home = os.path.expanduser("~")
    brain_base_dir = os.getenv("BRAIN_DIR", os.path.join(user_home, ".gemini", "antigravity-ide", "brain"))
    plan_path = "implementation_plan.md"  # Fallback
    target_brain_dir = os.getcwd()  # Fallback
    
    if os.path.exists(brain_base_dir):
        candidates = []
        for root, dirs, files in os.walk(brain_base_dir):
            if "implementation_plan.md" in files:
                full_path = os.path.join(root, "implementation_plan.md")
                candidates.append((full_path, os.path.getmtime(full_path), root))
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            plan_path = candidates[0][0]
            target_brain_dir = candidates[0][2]
            
    # Risk_Tracker.md??workspace root??ì¡´ì¬?˜ëŠ” ê²ƒì„ ?½ìŠµ?ˆë‹¤.
    tracker_path = "Risk_Tracker.md"
    
    if not os.path.exists(plan_path):
        raise HTTPException(status_code=404, detail="?¤í–‰ ê³„íš??implementation_plan.md)ë¥?ì°¾ì„ ???†ìŠµ?ˆë‹¤.")
    
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_content = f.read()
        
    tracker_content = ""
    if os.path.exists(tracker_path):
        with open(tracker_path, "r", encoding="utf-8") as f:
            tracker_content = f.read()

    decrypted_key_clean = decrypted_key.strip()
    client = Anthropic(
        base_url="https://api.kie.ai/claude",
        api_key=decrypted_key_clean,
        http_client=KIEHTTPClient(decrypted_key_clean)
    )

    prompt = f"""?„ë˜??RAPTOR V2.5 ?©í„° ?Œí¬?Œë¡œ???„ë©´ ë¶„ë¦¬ ë°?UX ?€ê°œí¸ ?˜ìˆ  ê³„íš??implementation_plan.md)?€ ê¸°ì¡´???„ì  ë¦¬ìŠ¤??ì¶”ì  ë¬¸ì„œ(Risk_Tracker.md)?…ë‹ˆ??
?„ì¬ ?¤ì œ ?ŒìŠ¤ ì½”ë“œ ?íƒœ?€ ??ë¬¸ì„œë¥?êµì°¨ ê²€ì¦í•˜???œêµ­?´ë¡œ ê¼¼ê¼¼?˜ê²Œ ?„í‚¤?ì²˜ ?¬ì „ ë¦¬ë·°(Pre-Review) ë³´ê³ ?œë? ?‘ì„±?´ì¤˜.

ë¦¬ë·° ë³´ê³ ?œëŠ” ë°˜ë“œ???¤ìŒ 3ê°€ì§€ ì¹´í…Œê³ ë¦¬ë¡œë§Œ ?„ê²©?˜ê²Œ ë¶„ë¥˜?˜ì—¬ ?‘ì„±?´ì•¼ ??
1. [Resolved]: ?´ì „ ì§€???¬í•­(Risk_Tracker.md??ë¦¬ìŠ¤??ëª©ë¡) ì¤??´ë²ˆ ê³„íš??implementation_plan.md)ë¥??µí•´ ?„ë²½???´ê²°?˜ëŠ” ??ª©ê³?ê·??¤ëª…
2. [Pending]: ?´ì „ ì§€???¬í•­ ì¤??´ë²ˆ ê³„íš?œì—?œë„ ?„ì§ ?„ì „???´ê²°ì±…ì´ ?œì‹œ?˜ì? ?Šê³  ?„í—˜ ?”ì†Œë¡??¨ì? ??ª©ê³?ê·??´ìœ 
3. [New]: ?´ë²ˆ ì½”ë“œ ê°œí¸ ê³„íš?´ë‚˜ ?„ì¬ ?íƒœ?ì„œ ?ˆë¡­ê²??ë³„??? ì¬??ì·¨ì•½???ëŠ” ê°œì„ ??

[?„ì  ë¦¬ìŠ¤??ì¶”ì ??(Risk_Tracker.md)]
{tracker_content}

[?¤í–‰ ê³„íš??(implementation_plan.md)]
{plan_content}
"""
    try:
        response = client.messages.create(
            model=DEFAULT_CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            extra_body={"thinkingFlag": True}
        )
        review_result = response.content[0].text
        
        today_str = date.today().strftime("%Y%m%d")
        report_filename = f"{today_str}_RAPTOR_Review_Report_v2.9.18_Pre.md"
        report_path = os.path.join(target_brain_dir, report_filename)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(review_result)
            
        # ?˜ìœ„ ?¸í™˜?±ì„ ?„í•´ legacy review_report.md??ìµœì‹  ?´ìš©?¼ë¡œ ë°±ì—… ê°±ì‹ 
        legacy_report_path = os.path.join(target_brain_dir, "review_report.md")
        with open(legacy_report_path, "w", encoding="utf-8") as f:
            f.write(review_result)
            
        return {"status": "success", "message": "?¬ì „ ë¦¬ë·° ë³´ê³ ?œê? ?•ìƒ?ìœ¼ë¡?ê°±ì‹ ?˜ì—ˆ?µë‹ˆ??", "filename": report_filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KIE Claude ?¸ì¶œ ?¤íŒ¨: {str(e)}")




ALLOWED_PROXY_DOMAINS = [
    "api.openai.com",
    "oaidalleapiprodscus.blob.core.windows.net",
    "api.kie.ai",
    "ulasrprjenbflylxjtcx.supabase.co"
]

@app.get("/api/proxy-image")
async def proxy_image(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="Missing url parameter")
    try:
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname
        if not hostname:
            raise HTTPException(status_code=400, detail="Invalid URL format")
        
        is_allowed = False
        for domain in ALLOWED_PROXY_DOMAINS:
            if hostname == domain or hostname.endswith("." + domain):
                is_allowed = True
                break
        
        if not is_allowed:
            raise HTTPException(status_code=403, detail="SSRF ë°©ì–´: ?ˆìš©?˜ì? ?Šì? ?„ë©”?¸ì˜ ?´ë?ì§€ ?„ë¡?œëŠ” ê¸ˆì??©ë‹ˆ??")

        async with httpx.AsyncClient() as client:
            res = await client.get(url, timeout=30.0)
            res.raise_for_status()
            content_type = res.headers.get("content-type", "image/png")
            return StreamingResponse(io.BytesIO(res.content), media_type=content_type)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Proxy image failed: {str(e)}")

@app.post("/api/scrape")
async def scrape_product(request: ScrapeRequest, verify: None = Depends(verify_csrf)):
    raise HTTPException(status_code=503, detail="?¤í¬?˜í•‘ ê¸°ëŠ¥?€ ?„ì¬ ?ê? ì¤‘ì…?ˆë‹¤.")

@app.post("/api/generate-plan")
async def generate_plan(request: PlanRequest, decrypted_key: str = Depends(get_decrypted_key), verify: None = Depends(verify_csrf)):
    """
    Step 1: Claude - Planning & Scripting (V2.2 Unified Prompting)
    """
    decrypted_key_clean = decrypted_key.strip()
    client = Anthropic(
        base_url="https://api.kie.ai/claude",
        api_key=decrypted_key_clean,
        http_client=KIEHTTPClient(decrypted_key_clean)
    )
    p_name = request.product_name or request.name or "?í’ˆ"
    
    # --- Dynamic HIL Pattern Instruction ---
    hil_instruction = ""
    if request.selected_pattern:
        hil_instruction = f"\n[CRITICAL HIL RULE]: ?¬ìš©?ê? [{request.selected_pattern}] ?¨í„´??ê°•ì œ ì§€?•í–ˆ?? AI ?ì²´ ?ë‹¨??ë¬´ì‹œ?˜ê³  ?¤í¬ë¦½íŠ¸ ?‘ì„± ??ë¬´ì¡°ê±????¨í„´??ìµœìš°? ìœ¼ë¡??ìš©?˜ë¼."

    # --- Dynamic Manual Additions (HIL) ---
    manual_instruction = ""
    if request.manual_additions:
        pains = request.manual_additions.get("pain_points", [])
        strens = request.manual_additions.get("strengths", [])
        if pains or strens:
            manual_instruction = "\n[USER INPUT HIL DATA]: ?¬ìš©?ê? ì§ì ‘ ë¶„ì„???˜ë™ ?¼ë“œë°??•ë³´ê°€ ì¡´ì¬?©ë‹ˆ?? ???´ìš©???œë‚˜ë¦¬ì˜¤?€ ê¸°íš???ê·¹ ë°˜ì˜?˜ì—¬ ?¤í¬ë¦½íŠ¸ë¥??ì„±?˜ì‹­?œì˜¤."
            if pains:
                manual_instruction += f"\n- ?¬ìš©??ì§€??ë¶ˆí¸??Pain Points): {', '.join(pains)}"
            if strens:
                manual_instruction += f"\n- ?¬ìš©??ì§€???¥ì (Strengths): {', '.join(strens)}"

    content = []
    if request.images:
        img_data = request.images[0]
        media_type = "image/jpeg"
        if "image/png" in img_data: media_type = "image/png"
        elif "image/webp" in img_data: media_type = "image/webp"
        
        base64_data = img_data.split(',')[-1].strip()
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": base64_data
            }
        })

    if not request.selected_pattern:
        # Recommendation Mode: Only return analysis and recommended patterns
        user_prompt = f"""
Create a professional product analysis and pattern recommendation based on the following:
Product Name: {p_name}
User Description: {request.description}
Target Language: {request.target_language}
Marketing Purpose (?í¼ ëª©ì ): {request.purpose or "?¼í•‘ ?„í™˜"}
Target Audience (?€ê¹ƒì¸µ): {request.target_audience or "?„ì²´"}
Video Tone (?ìƒ ??: {request.tone or "ë¦¬ë·°??}
{manual_instruction}

Please analyze the product and recommend the top 2 patterns from the following 7 short-form patterns:
1. ë¬¸ì œ ?´ê²°??
2. ?„í›„ ë¹„êµ??
3. ?¨ì? ê¸°ëŠ¥ ë°œê²¬??
4. ?œê°„ ?ˆì•½??
5. ?í™œ ê°œì„ ??
6. ê³µê°??
7. ?¤ì‚¬???„ê¸°??

Output MUST be a valid JSON matching this schema exactly, and nothing else:
{{
  "product_analysis": {{
    "pain_point": "ë¶„ì„???¬ìš©??ê³ í†µ (?€ê¹ƒì¸µê³?ëª©ì ??ë°˜ì˜)",
    "core_benefit": "?µì‹¬ ?¥ì ",
    "purchase_trigger": "? íƒ??êµ¬ë§¤ ?¸ë¦¬ê±?,
    "product_ref": ["?¹ì§•1", "?¹ì§•2", "?¹ì§•3"]
  }},
  "recommended_patterns": [
    {{
      "pattern_name": "ì¶”ì²œ ?¨í„´ 1 (??7ê°€ì§€ ì¤??˜ë‚˜)",
      "reason": "ì¶”ì²œ ?´ìœ  ??ì¤?(?€ê¹ƒì¸µê³?ë§ˆì???ëª©ì ??ê·¼ê±°)",
      "sample_dialogue": "ì§§ì? ?€???˜í”Œ (?„í‚¹??1ë¬¸ì¥)"
    }},
    {{
      "pattern_name": "ì¶”ì²œ ?¨í„´ 2 (??7ê°€ì§€ ì¤??˜ë‚˜)",
      "reason": "ì¶”ì²œ ?´ìœ  ??ì¤?(?€ê¹ƒì¸µê³?ë§ˆì???ëª©ì ??ê·¼ê±°)",
      "sample_dialogue": "ì§§ì? ?€???˜í”Œ (?„í‚¹??1ë¬¸ì¥)"
    }}
  ]
}}
"""
    else:
        # Generation Mode: Build actual scenes based on selected pattern
        user_prompt = f"""
[CRITICAL HIL RULE]: ?¬ìš©?ê? [{request.selected_pattern}] ?¨í„´??ê°•ì œ ì§€?•í–ˆ?? AI ?ì²´ ?ë‹¨??ë¬´ì‹œ?˜ê³  ?¤í¬ë¦½íŠ¸ ?‘ì„± ??ë¬´ì¡°ê±????¨í„´??ìµœìš°? ìœ¼ë¡??ìš©?˜ë¼.
{manual_instruction}

Create a professional 9:16 short-form commercial plan based on the following:
Product Name: {p_name}
User Description: {request.description}
Target Language: {request.target_language}
Video Length: {request.duration} seconds
Marketing Purpose (?í¼ ëª©ì ): {request.purpose or "?¼í•‘ ?„í™˜"}
Target Audience (?€ê¹ƒì¸µ): {request.target_audience or "?„ì²´"}
Video Tone (?ìƒ ??: {request.tone or "ë¦¬ë·°??}

[DYNAMIC HOOK & SCRIPT VARIETY RULE]
ë°˜ë“œ??ë¬´ë?ê±´ì¡°??ê¸°ë³¸ ?¨í„´???ˆí”¼?˜ë¼! ?í’ˆ???±ê²©ê³?ì§€?•ëœ ?¨í„´??ë§ì¶”???„ì „???¤ë¥¸ ê·¹ì ??Hook(?„ì…ë¶€)ê³??Œê²©?ì¸ ?¤í† ë¦¬í…”ë§ì„ êµ¬ì„±?´ë¼.
?ˆë? ë»”í•œ "?ˆë…•?˜ì„¸??, "?Œê°œ?©ë‹ˆ?? ?ì˜ ë©˜íŠ¸ë¥??°ì? ë§ê³ , ?œì²­?ê? ì²?1ì´?ë§Œì— ëª°ì…?????ˆëŠ” ê³µê²©?ì´ê³?ì°½ì˜?ì¸ ?…ì„ ?‘ì„±?˜ë¼.

Output MUST be a valid JSON matching this schema exactly, and nothing else:
{{
  "strategy": {{
    "selected_pattern": "{request.selected_pattern}",
    "hook": "?¤í¬ë¦½íŠ¸??ì²??„í‚¹ ë¬¸ì¥",
    "wow": "?„í‚¹ ì§í›„???€??ë¬¸ì¥",
    "cta": "?‰ë™ ? ë„ ë¬¸ì¥"
  }},
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": 2,
      "role": "ë¬¸ì œ ?í™© ?¥ë©´",
      "dialogue": "?ìƒ???¤ì–´ê°??¤ì œ ?€??,
      "visual_description": "?¥ë©´???œê°???¤ëª…",
      "image_prompt": "DALL-E 3??ê³ í’ˆì§??ë¬¸ ?„ë¡¬?„íŠ¸"
    }}
    // ??ë§ì? Scene ê°ì²´??..
  ],
  "upload_package": {{
    "titles": ["?œëª©1", "?œëª©2", "?œëª©3", "?œëª©4", "?œëª©5"],
    "description": "?¤ëª…ë¬?,
    "hashtags": ["#?œê·¸1", "#?œê·¸2"],
    "keywords": ["?¤ì›Œ??", "?¤ì›Œ??"],
    "thumbnail_texts": ["?¸ë„¤?¼ë¬¸êµ?", "?¸ë„¤?¼ë¬¸êµ?", "?¸ë„¤?¼ë¬¸êµ?"]
  }}
}}
"""
    content.append({"type": "text", "text": user_prompt})

    # Resolve primary model
    primary_model = request.model or DEFAULT_CLAUDE_MODEL
    
    # 3-Tier Execution Pipeline
    models_to_try = [primary_model]
    if not request.model: 
        models_to_try.extend([CLAUDE_FALLBACK_OPUS, CLAUDE_FALLBACK_HAIKU])

    last_error = None
    import asyncio
    
    for model_name in models_to_try:
        try:
            max_retries = 3
            base_delay = 3
            for attempt in range(max_retries + 1):
                try:
                    print(f"[CLAUDE] Attempting model: {model_name} with V2.2 Unified Prompt (Attempt {attempt+1})")
                    response = client.messages.create(
                        model=model_name,
                        system=COMBINED_SYSTEM_PROMPT, # Injecting combined PLM/Guidelines
                        max_tokens=8192,
                        messages=[{"role": "user", "content": content}],
                        extra_body={"thinkingFlag": True}
                    )
                    
                    raw_text = response.content[0].text
                    
                    # --- Robust JSON Sanitize Logic ---
                    clean_json = raw_text.strip()
                    clean_json = re.sub(r"```[a-zA-Z]*\n", "", clean_json)
                    clean_json = clean_json.replace("```", "").strip()
                    
                    try:
                        first_idx = min([i for i in [clean_json.find("{"), clean_json.find("[")] if i != -1], default=-1)
                        if first_idx != -1:
                            last_idx = clean_json.rfind("}") if clean_json[first_idx] == "{" else clean_json.rfind("]")
                            if last_idx != -1:
                                clean_json = clean_json[first_idx:last_idx+1]
                    except Exception as e:
                        print(f"[JSON SANITIZE ERROR] {e}")

                    data = json.loads(clean_json)
                    if isinstance(data, dict) and "error" in data:
                        raise RuntimeError(f"KIE API Error: {data['error']}")
                    return data
                    
                except Exception as e:
                    status_code = getattr(e, 'status_code', None)
                    if status_code is None:
                        err_str = str(e)
                        if '529' in err_str: status_code = 529
                        elif '500' in err_str: status_code = 500
                        elif '502' in err_str: status_code = 502
                        elif '503' in err_str: status_code = 503
                    
                    if status_code in [529, 500, 502, 503] and attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        print(f"[CLAUDE AUTO-RETRY] Model {model_name} got {status_code} error. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        raise e
            
        except Exception as e:
            print(f"[CLAUDE ERROR] {model_name} failed: {str(e)}")
            last_error = e
            continue

    print(traceback.format_exc())
    raise HTTPException(
        status_code=500, 
        detail=f"Claude API Pipeline Failed. Error: {str(last_error)}"
    )

@app.post("/api/generate-images")
async def generate_images(request: ImageGenRequest, decrypted_key: str = Depends(get_decrypted_key), verify: None = Depends(verify_csrf)):
    """
    Step 2: KIE Image Generation via createTask (Asynchronous Polling)
    """
    import asyncio

    # Determine size and description by aspect ratio
    img_size = "1024x1536"
    aspect_desc = "9:16 vertical aspect ratio"
    if request.aspect_ratio == "1:1":
        img_size = "1024x1024"
        aspect_desc = "1:1 square aspect ratio"
    elif request.aspect_ratio == "16:9":
        img_size = "1536x1024"
        aspect_desc = "16:9 horizontal aspect ratio"

    async with httpx.AsyncClient() as client:
        # Since frontend calls per scene for lazy-loading, we process and return the first valid response
        for scene in request.scenes:
            prompt = scene.get('image_prompt', '')
            if not prompt: continue
            
            full_prompt = f"{prompt}. {aspect_desc}, high-quality commercial photography style, Korean setting/models. NO text, NO letters, NO logos, NO watermarks, NO brand names. Clean visual only. NO red circles, NO shapes covering logos, NO censorship marks. Backgrounds and surfaces must be completely natural and clean. ABSOLUTELY NO national flags (specifically NO Japanese, North Korean, or Chinese flags). All humans in the image MUST be 100% fictitious, generic, and non-existent models. DO NOT generate anyone resembling real celebrities, public figures, or copyrighted characters."
            
            max_retries = 3
            base_delay = 3
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    # 1. createTask ?¸ì¶œ
                    model_val = map_image_model(request.model)
                    
                    # ë² ì´???˜ì´ë¡œë“œ êµ¬ì„± (KIE ê¸°ìˆ ì§€?í? ê³µì‹ ?¤í™ ?„ì „ ?¼ì¹˜??
                    input_payload = {
                        "prompt": full_prompt,
                        "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
                    }
                    
                    # [P0] KIE 422 ?ëŸ¬ ?ì²œ ?´ê²°: GPT-Image-2 ë°?Grok ëª¨ë¸???´ìƒ???„ìˆ˜ ê·œê²© ?€??
                    # request.aspect_ratioê°€ "auto"ê°€ ?„ë‹ˆê±°ë‚˜ GPT-Image-2, Grok, Nano Banana ëª¨ë¸??ê²½ìš° ê°•ì œ ì£¼ì…
                    if input_payload["aspect_ratio"] != "auto" or model_val in ["gpt-image-2-text-to-image", "grok-imagine/text-to-image", "nano-banana-2"]:
                        input_payload["resolution"] = "1K"
                    
                    if model_val == "nano-banana-2":
                        input_payload.update({
                            "image_input": [],
                            "output_format": "png"
                        })
                    
                    # [P0] ?”ë²„ê·?ë¡œê¹… ê°•í™”: createTask ?¸ì¶œ ì§ì „ Payload ì¶œë ¥
                    print(f"KIE Payload: {input_payload}")
                    
                    create_res = await client.post(
                        "https://api.kie.ai/api/v1/jobs/createTask",
                        headers={
                            "Authorization": f"Bearer {decrypted_key}",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        },
                        json={
                            "model": model_val,
                            "callBackUrl": os.getenv("KIE_WEBHOOK_CALLBACK_URL", "https://raptor-composer.onrender.com/api/webhook/kie"),
                            "input": input_payload
                        },
                        timeout=60.0
                    )
                    
                    # [P0] KIE 422 ?ëŸ¬ ?˜í•‘ ?ˆì™¸ ì²˜ë¦¬ ë³´ê°•
                    if create_res.status_code == 422:
                        raise Exception("API ?Œë¼ë¯¸í„° ê·œê²© ?¤ë¥˜(?´ìƒ???ëŠ” ì¢…íš¡ë¹?ë¯¸ì???")
                    
                    if create_res.status_code != 200:
                        raise Exception(f"Failed to create image task ({create_res.status_code}): {create_res.text}")
                    
                    resp_data = create_res.json()
                    if resp_data.get('code') == 422:
                        raise Exception("API ?Œë¼ë¯¸í„° ê·œê²© ?¤ë¥˜(?´ìƒ???ëŠ” ì¢…íš¡ë¹?ë¯¸ì???")
                        
                    data_dict = resp_data.get('data') or {}
                    task_id = resp_data.get('taskId') or data_dict.get('taskId') or resp_data.get('id') or data_dict.get('id')
                    
                    if not task_id:
                        raise Exception(f"Failed to get taskId from create image task. Response: {create_res.text}")
                    
                    # 2. recordInfo ?´ë§
                    polling_timeout = 180
                    start_poll_time = time.time()
                    image_url = None
                    
                    while True:
                        await asyncio.sleep(3)
                        elapsed = time.time() - start_poll_time
                        if elapsed >= polling_timeout:
                            raise Exception("?´ë?ì§€ ?ì„± ?œë²„ ?‘ë‹µ ì§€??3ë¶?ì´ˆê³¼)?…ë‹ˆ??")
                        
                        poll_res = await client.get(
                            f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
                            headers={
                                "Authorization": f"Bearer {decrypted_key}",
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            },
                            timeout=30.0
                        )
                        
                        if poll_res.status_code != 200:
                            raise Exception(f"Failed to poll image status ({poll_res.status_code})")
                            
                        poll_data = poll_res.json()
                        poll_code = poll_data.get('code')
                        poll_dict = poll_data.get('data') or {}
                        
                        if poll_code and (poll_code >= 500 or poll_code == -1):
                            raise Exception("?´ë?ì§€ ?ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?Œë”ë§??¤ë¥˜).")
                            
                        status_raw = poll_dict.get('state') or poll_dict.get('status') or poll_data.get('state') or poll_data.get('status')
                        status = str(status_raw).lower() if status_raw else "waiting"
                        
                        if status == 'success':
                            result_json = poll_dict.get('resultJson')
                            try:
                                if isinstance(result_json, str):
                                    parsed = json.loads(result_json)
                                elif isinstance(result_json, dict):
                                    parsed = result_json
                                else:
                                    parsed = {}
                                
                                urls = parsed.get('resultUrls') or parsed.get('urls') or []
                                if urls and len(urls) > 0:
                                    image_url = urls[0]
                            except Exception as pe:
                                print(f"[KIE Polling] JSON Parse fail: {pe}")
                            
                            if not image_url:
                                image_url = poll_dict.get('image_url') or poll_dict.get('file_url') or poll_dict.get('url') or poll_data.get('image_url')
                            break
                        elif status == 'fail':
                            raise Exception("?´ë?ì§€ ?ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?‘ì—… ?¤íŒ¨).")
                    
                    if image_url:
                        return {"data": [{"url": image_url}]}
                    else:
                        raise Exception("?´ë?ì§€ URL??ì°¾ì„ ???†ìŠµ?ˆë‹¤.")
                        
                except Exception as e:
                    last_exception = e
                    print(f"[IMAGE GEN RETRY WARN] Attempt {attempt + 1}/{max_retries + 1} Failed: {str(e)}")
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        print(traceback.format_exc())
                        raise HTTPException(status_code=500, detail=f"Internal Server Error (Auto-Retry Failed): {str(last_exception)}")
                        
    return {"data": []} # Fallback for empty scenes

@app.post("/api/generate-videos")
async def generate_videos(
    request: VideoGenRequest, 
    decrypted_key: str = Depends(get_decrypted_key),
    verify: None = Depends(verify_csrf)
):
    """
    Step 3: Grok-imagine - Image-to-Video Rendering via KIE AI
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="?œë²„ ?¤ì • ?¤ë¥˜: .env ?Œì¼??SUPABASE_URLê³?SUPABASE_KEYë¥??¤ì •?´ì£¼?¸ìš”.")

    results = []
    uploaded_files = [] # ?…ë¡œ?œëœ ?„ì‹œ ?´ë?ì§€ ?Œì¼ëª?ì¶”ì ??(P-002)
    
    try:
        async with httpx.AsyncClient() as client:
            for index, scene in enumerate(request.scenes):
                # 1. ?¬ë ˆ??ë°©ì–´: ê¸°ì¡´ ë¹„ë””?¤ê? ? íš¨?˜ë©´ KIE API ?¤í‚µ
                existing_video_url = scene.get('video_url')
                if existing_video_url and existing_video_url.startswith("http"):
                    print(f"[SKIP] Scene {index+1} already has a valid video URL: {existing_video_url}")
                    results.append(scene)
                    continue

                # 2. ?˜ì´ë¸Œë¦¬??ëª¨ë“œ ???¹ì • ???¤í‚µ (?„ë¡ ?¸ì—”???œì–´)
                is_hybrid_skip = scene.get('use_image_only', False)
                if is_hybrid_skip:
                    print(f"[HYBRID SKIP] Scene {index+1} text-heavy scene skipped for video generation (Hybrid Mode)")
                    scene_copy = dict(scene)
                    scene_copy['video_url'] = None
                    results.append(scene_copy)
                    continue

                image_url = scene.get('image_url')
                if not image_url: 
                    results.append(scene)
                    continue
                
                # 1. Download image and upload to Supabase Storage (A-005, S-006)
                try:
                    public_url, file_name = await upload_image_to_supabase(image_url, id(scene))
                    uploaded_files.append(file_name)
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to process image: {str(e)}")

                # 2. Start video generation task via KIE AI
                # Parse duration from scene, map to KIE AI supported ranges ("6", "10", "15")
                try:
                    raw_duration = int(float(scene.get('duration_seconds', 4)))
                except (ValueError, TypeError):
                    raw_duration = 4
                    
                if raw_duration <= 6:
                    scene_duration = "6"
                elif raw_duration <= 10:
                    scene_duration = "10"
                else:
                    scene_duration = "15"
                    
                # engine ë¶„ê¸° ?ìš©
                is_veo = (request.engine in ["veo", "veo_lite", "veo_fast"])
                
                if is_veo:
                    url = "https://api.kie.ai/api/v1/veo/generate"
                    
                    # Veo ëª¨ë¸ ë°?generationType ë¶„ê¸° ì²˜ë¦¬
                    model_name = "veo3_fast" if request.engine == "veo_fast" else "veo3_lite"
                    gen_type = "REFERENCE_2_VIDEO" if request.engine == "veo_fast" else "FIRST_AND_LAST_FRAMES_2_VIDEO"
                    
                    payload = {
                        "prompt": scene.get('image_prompt', 'Animate this image'),
                        "imageUrls": [public_url],
                        "model": model_name,
                        "watermark": "",
                        "aspect_ratio": request.aspect_ratio,
                        "generationType": gen_type,
                        "enableFallback": False,
                        "enableTranslation": True
                    }
                else:
                    url = "https://api.kie.ai/api/v1/jobs/createTask"
                    model_name = "grok-imagine/image-to-video"
                    payload = {
                        "model": model_name,
                        "input": {
                            "task_id": f"task_grok_{id(scene)}_{int(time.time())}",
                            "image_urls": [public_url],
                            "prompt": scene.get('image_prompt', 'Animate this image'),
                            "mode": "normal",
                            "duration": str(scene_duration),
                            "resolution": "480p",
                            "aspect_ratio": request.aspect_ratio
                        }
                    }
                
                # Log the payload to stdout instead of appending to file (P-003)
                print(f"\n--- NEW REQUEST ({request.engine}) ---\nSENDING PAYLOAD to {url}: {json.dumps(payload, indent=2)}\n")

                import asyncio

                task_id = None
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {decrypted_key}"},
                    json=payload,
                    timeout=90.0
                )
                
                if response.status_code == 200:
                    resp_data = response.json()
                    data_dict = resp_data.get('data') or {}
                    task_id = resp_data.get('taskId') or data_dict.get('taskId') or resp_data.get('id') or data_dict.get('id')
                
                if not task_id:
                    raise HTTPException(status_code=500, detail=f"Failed to create task. Response: {response.text}")

                # Polling loop (Grok 720s, Veo 900s)
                polling_timeout = 720 if request.engine == "grok" else 900
                start_poll_time = time.time()
                video_url = None
                last_status = "WAITING"
                
                while True:
                    await asyncio.sleep(5)
                    elapsed = time.time() - start_poll_time
                    if elapsed >= 1800:
                        raise Exception("?œë²„ ?‘ë‹µ ì§€???ˆë? ?œê°„ 30ë¶?ì´ˆê³¼)?…ë‹ˆ??")
                    elif elapsed >= polling_timeout and last_status not in ['WAITING', 'IN_PROGRESS', 'PENDING', 'PROCESSING', 'QUEUE']:
                        raise Exception("?œë²„ ?‘ë‹µ ì§€???œê°„ ì´ˆê³¼)?…ë‹ˆ?? ?¤íŒ¨???¬ë????´ì–´???Œë”ë§?ë²„íŠ¼???ŒëŸ¬ì£¼ì„¸??")
                    
                    poll_res = await client.get(
                        f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
                        headers={"Authorization": f"Bearer {decrypted_key}"},
                        timeout=30.0
                    )

                    if poll_res.status_code >= 500:
                        raise Exception("ë¹„ë””???ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?Œë”ë§??¤ë¥˜). ?¤ì‹œ ?œë„??ì£¼ì„¸??")

                    if poll_res.status_code != 200:
                        break
                        
                    poll_data = poll_res.json()
                    poll_data_dict = poll_data.get('data') or {}
                    poll_code = poll_data.get('code')
                    if poll_code and (poll_code >= 500 or poll_code == -1):
                        raise Exception("ë¹„ë””???ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?Œë”ë§??¤ë¥˜). ?¤ì‹œ ?œë„??ì£¼ì„¸??")

                    state_raw = poll_data_dict.get('state')
                    if not state_raw:
                        state_raw = poll_data.get('state')
                    
                    state = str(state_raw).lower() if state_raw else "waiting"
                    last_status = state.upper()
                    
                    if state == 'success':
                        try:
                            result_json = poll_data_dict.get('resultJson')
                            if isinstance(result_json, str):
                                parsed = json.loads(result_json)
                            elif isinstance(result_json, dict):
                                parsed = result_json
                            else:
                                parsed = {}
                                
                            urls = parsed.get('resultUrls')
                            if urls and isinstance(urls, list) and len(urls) > 0:
                                video_url = urls[0]
                            else:
                                fallback_urls = parsed.get('urls') or []
                                video_url = poll_data_dict.get('video_url') or poll_data.get('video_url') or (fallback_urls[0] if fallback_urls else None)
                        except Exception as e:
                            print(f"[KIE Polling Error] Raw Response: {poll_data}")
                            print(f"[KIE] Failed to parse resultJson in generate_videos: {e}")
                        
                        break
                    elif state == 'fail':
                        fail_msg = poll_data_dict.get('failMsg') or poll_data.get('failMsg') or poll_data_dict.get('reason') or poll_data.get('reason') or "KIE AI ë¹„ë””???ì„± ?”ì§„ ?¤íŒ¨"
                        raise HTTPException(status_code=500, detail=f"ë¹„ë””???ì„± ?¤íŒ¨: {fail_msg}")
                    elif state == 'waiting':
                        print(f"[KIE Polling] Task {task_id} is waiting for completion...")

                if not video_url:
                    raise HTTPException(status_code=500, detail="API Error (500): Task failed or no video URL found.")

                results.append({**scene, "video_url": video_url})
    finally:
        # P-002: ?…ë¡œ?œëœ ?„ì‹œ ?´ë?ì§€ ?¼ê´„ ?? œ
        if uploaded_files:
            loop = asyncio.get_event_loop()
            def _cleanup():
                try:
                    supabase.storage.from_("assets").remove(uploaded_files)
                    print(f"[CLEANUP] Successfully removed temporary assets: {uploaded_files}")
                except Exception as e:
                    print(f"[CLEANUP ERROR] Failed to remove temporary assets {uploaded_files}: {e}")
            await loop.run_in_executor(None, _cleanup)

    return {"script": results}

@app.post("/api/refine-prompt")
async def refine_prompt(
    request: RefinePromptRequest, 
    decrypted_key: str = Depends(get_decrypted_key),
    verify: None = Depends(verify_csrf)
):
    """
    Raptor UX Optimization: Refine image prompt based on Korean feedback and regenerate image.
    """
    decrypted_key_clean = decrypted_key.strip()
    client = Anthropic(
        base_url="https://api.kie.ai/claude",
        api_key=decrypted_key_clean,
        http_client=KIEHTTPClient(decrypted_key_clean)
    )
    
    refine_prompt_text = f"""[CONTEXT: Image Generation Prompt Refinement]
Original Product: {request.product_name}
Current Scene Dialogue (KO): {request.current_scene.get('dialogue', request.current_scene.get('caption_ko'))}
Current Scene Visual (KO): {request.current_scene.get('visual_description', request.current_scene.get('visual_ko'))}
Current Prompt (EN): {request.current_scene.get('image_prompt')}
User Request (KO): {request.user_feedback}

CRITICAL RULES:
1. Improve the English image_prompt based on the User Request, the Dialogue, and the Visual Description.
2. Maintain the product consistency.
3. Output ONLY valid JSON.

JSON Structure:
{{
    "refined_image_prompt": "New enhanced English prompt"
}}"""

    try:
        import asyncio
        max_retries = 3
        base_delay = 3
        raw_text = ""
        
        for attempt in range(max_retries + 1):
            try:
                response = client.messages.create(
                    model=DEFAULT_CLAUDE_MODEL,
                    max_tokens=1024,
                    messages=[{"role": "user", "content": [{"type": "text", "text": refine_prompt_text}]}],
                    extra_body={"thinkingFlag": True}
                )
                raw_text = response.content[0].text
                break
            except Exception as e:
                status_code = getattr(e, 'status_code', None)
                if status_code is None:
                    err_str = str(e)
                    if '529' in err_str: status_code = 529
                    elif '500' in err_str: status_code = 500
                    elif '502' in err_str: status_code = 502
                    elif '503' in err_str: status_code = 503
                
                if status_code in [529, 500, 502, 503] and attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    print(f"[CLAUDE AUTO-RETRY] refine_prompt got {status_code} error. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                else:
                    raise e
        clean_json = raw_text.strip()
        clean_json = re.sub(r"```[a-zA-Z]*\n", "", clean_json)
        clean_json = clean_json.replace("```", "").strip()
        
        try:
            first_idx = min([i for i in [clean_json.find("{"), clean_json.find("[")] if i != -1], default=-1)
            if first_idx != -1:
                last_idx = clean_json.rfind("}") if clean_json[first_idx] == "{" else clean_json.rfind("]")
                if last_idx != -1:
                    clean_json = clean_json[first_idx:last_idx+1]
        except Exception as e:
            print(f"[JSON SANITIZE ERROR] {e}")
        
        refined_data = json.loads(clean_json)
        new_prompt = refined_data.get("refined_image_prompt")
        
        # Determine size and description by aspect ratio
        img_size = "1024x1536"
        aspect_desc = "9:16 vertical aspect ratio"
        if request.aspect_ratio == "1:1":
            img_size = "1024x1024"
            aspect_desc = "1:1 square aspect ratio"
        elif request.aspect_ratio == "16:9":
            img_size = "1536x1024"
            aspect_desc = "16:9 horizontal aspect ratio"

        full_prompt = f"{new_prompt}. {aspect_desc}, high-quality commercial photography style, Korean setting/models. NO text, NO letters, NO logos, NO watermarks, NO brand names. Clean visual only. NO red circles, NO shapes covering logos, NO censorship marks. Backgrounds and surfaces must be completely natural and clean. ABSOLUTELY NO national flags (specifically NO Japanese, North Korean, or Chinese flags). All humans in the image MUST be 100% fictitious, generic, and non-existent models. DO NOT generate anyone resembling real celebrities, public figures, or copyrighted characters."
        
        import asyncio
        async with httpx.AsyncClient() as http_client:
            max_retries = 3
            base_delay = 3
            last_err = None
            
            for attempt in range(max_retries + 1):
                try:
                    model_val = map_image_model(request.model)
                    # ë² ì´???˜ì´ë¡œë“œ êµ¬ì„± (KIE ê¸°ìˆ ì§€?í? ê³µì‹ ?¤í™ ?„ì „ ?¼ì¹˜??
                    input_payload = {
                        "prompt": full_prompt,
                        "aspect_ratio": request.aspect_ratio if hasattr(request, 'aspect_ratio') and request.aspect_ratio else "auto"
                    }
                    
                    # [P0] KIE 422 ?ëŸ¬ ?ì²œ ?´ê²°: GPT-Image-2 ë°?Grok ëª¨ë¸???´ìƒ???„ìˆ˜ ê·œê²© ?€??
                    # request.aspect_ratioê°€ "auto"ê°€ ?„ë‹ˆê±°ë‚˜ GPT-Image-2, Grok, Nano Banana ëª¨ë¸??ê²½ìš° ê°•ì œ ì£¼ì…
                    if input_payload["aspect_ratio"] != "auto" or model_val in ["gpt-image-2-text-to-image", "grok-imagine/text-to-image", "nano-banana-2"]:
                        input_payload["resolution"] = "1K"
                    
                    if model_val == "nano-banana-2":
                        input_payload.update({
                            "image_input": [],
                            "output_format": "png"
                        })
                    
                    # [P0] ?”ë²„ê·?ë¡œê¹… ê°•í™”: createTask ?¸ì¶œ ì§ì „ Payload ì¶œë ¥
                    print(f"KIE Payload: {input_payload}")
                    
                    dalle_res = await http_client.post(
                        "https://api.kie.ai/api/v1/jobs/createTask",
                        headers={
                            "Authorization": f"Bearer {decrypted_key}",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        },
                        json={
                            "model": model_val,
                            "callBackUrl": os.getenv("KIE_WEBHOOK_CALLBACK_URL", "https://raptor-composer.onrender.com/api/webhook/kie"),
                            "input": input_payload
                        },
                        timeout=60.0
                    )
                    
                    # [P0] KIE 422 ?ëŸ¬ ?˜í•‘ ?ˆì™¸ ì²˜ë¦¬ ë³´ê°•
                    if dalle_res.status_code == 422:
                        raise Exception("API ?Œë¼ë¯¸í„° ê·œê²© ?¤ë¥˜(?´ìƒ???ëŠ” ì¢…íš¡ë¹?ë¯¸ì???")
                    
                    if dalle_res.status_code != 200:
                        raise Exception(f"Failed to create image task ({dalle_res.status_code}): {dalle_res.text}")
                    
                    resp_data = dalle_res.json()
                    if resp_data.get('code') == 422:
                        raise Exception("API ?Œë¼ë¯¸í„° ê·œê²© ?¤ë¥˜(?´ìƒ???ëŠ” ì¢…íš¡ë¹?ë¯¸ì???")
                        
                    data_dict = resp_data.get('data') or {}
                    task_id = resp_data.get('taskId') or data_dict.get('taskId') or resp_data.get('id') or data_dict.get('id')
                    
                    if not task_id:
                        raise Exception(f"Failed to get taskId from create image task. Response: {dalle_res.text}")
                    
                    polling_timeout = 180
                    start_poll_time = time.time()
                    new_image_url = None
                    
                    while True:
                        await asyncio.sleep(3)
                        elapsed = time.time() - start_poll_time
                        if elapsed >= polling_timeout:
                            raise Exception("?´ë?ì§€ ?ì„± ?œë²„ ?‘ë‹µ ì§€??3ë¶?ì´ˆê³¼)?…ë‹ˆ??")
                            
                        poll_res = await http_client.get(
                            f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
                            headers={
                                "Authorization": f"Bearer {decrypted_key}",
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            },
                            timeout=30.0
                        )
                        
                        if poll_res.status_code >= 500:
                            raise Exception("?´ë?ì§€ ?ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?Œë”ë§??¤ë¥˜).")
                            
                        if poll_res.status_code != 200:
                            raise Exception(f"Failed to poll image status ({poll_res.status_code})")
                            
                        poll_data = poll_res.json()
                        poll_code = poll_data.get('code')
                        poll_dict = poll_data.get('data') or {}
                        
                        if poll_code and (poll_code >= 500 or poll_code == -1):
                            raise Exception("?´ë?ì§€ ?ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?Œë”ë§??¤ë¥˜).")
                            
                        status_raw = poll_dict.get('state') or poll_dict.get('status') or poll_data.get('state') or poll_data.get('status')
                        status = str(status_raw).lower() if status_raw else "waiting"
                        
                        if status == 'success':
                            result_json = poll_dict.get('resultJson')
                            try:
                                if isinstance(result_json, str):
                                    parsed = json.loads(result_json)
                                elif isinstance(result_json, dict):
                                    parsed = result_json
                                else:
                                    parsed = {}
                                
                                urls = parsed.get('resultUrls') or parsed.get('urls') or []
                                if urls and len(urls) > 0:
                                    new_image_url = urls[0]
                            except Exception as pe:
                                print(f"[KIE Polling] JSON Parse fail: {pe}")
                            
                            if not new_image_url:
                                new_image_url = poll_dict.get('image_url') or poll_dict.get('file_url') or poll_dict.get('url') or poll_data.get('image_url')
                            break
                        elif status == 'fail':
                            raise Exception("?´ë?ì§€ ?ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?‘ì—… ?¤íŒ¨).")
                            
                    if new_image_url:
                        return {
                            "image_url": new_image_url,
                            "image_prompt": new_prompt
                        }
                    else:
                        raise Exception("?´ë?ì§€ URL??ì°¾ì„ ???†ìŠµ?ˆë‹¤.")
                except HTTPException as he:
                    raise he
                except Exception as e:
                    last_err = e
                    print(f"[REFINE PROMPT RETRY WARN] Attempt {attempt + 1}/{max_retries + 1} Failed: {str(e)}")
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        raise HTTPException(status_code=500, detail=f"Internal Server Error (Refine Prompt Auto-Retry Failed): {str(last_err)}")
                
    except Exception as e:
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/render-task")
async def render_task(
    request: RenderTaskRequest,
    jwt_user_id: str = Depends(get_jwt_user_id),
    verify: None = Depends(verify_csrf)
):
    task_id = f"task_{uuid.uuid4().hex[:8]}"
    created_at = datetime.utcnow().isoformat()
    project_id = f"proj_{task_id}"
    sanitized_user = sanitize_uuid(jwt_user_id)
    
    # Insert project into Supabase (Include callback_url inside plan_snapshot)
    new_project = {
        "project_id": project_id,
        "product_name": request.plan.product_name,
        "created_at": created_at,
        "user_id": sanitized_user,
        "plan_snapshot": {**request.plan.dict(), "callback_url": request.callback_url}
    }
    supabase.table("projects").insert(new_project).execute()
    
    # Insert task into Supabase
    new_task = {
        "task_id": task_id,
        "project_id": project_id,
        "task_type": "final_render",
        "description": request.plan.title or "ë¹„ë””???ì„± ?€ê¸?ì¤?,
        "status": "pending",
        "result_url": None,
        "error": None,
        "created_at": created_at
    }
    supabase.table("tasks").insert(new_task).execute()
        
    return JSONResponse(status_code=202, content={"task_id": task_id, "status": "pending"})

@app.post("/api/webhook/kie")
async def webhook_kie(request: Request):
    webhook_secret = os.getenv("WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="?œë²„ ?¤ì • ?¤ë¥˜: WEBHOOK_SECRET ?˜ê²½ ë³€?˜ê? ?¤ì •?˜ì? ?Šì•˜?µë‹ˆ??")
        
    signature = request.headers.get("X-KIE-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="X-KIE-Signature ?¤ë”ê°€ ?„ë½?˜ì—ˆ?µë‹ˆ??")
        
    # A-003: "sha256=" ?„ë¦¬?½ìŠ¤ ?ˆì™¸ ì²˜ë¦¬
    if signature.startswith("sha256="):
        signature = signature[7:]
        
    raw_body = await request.body()
    
    import hmac
    import hashlib
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="?¹í›… ?œëª…??? íš¨?˜ì? ?ŠìŠµ?ˆë‹¤.")
        
    try:
        payload = KieWebhookPayload.model_validate_json(raw_body)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Request body format invalid: {str(e)}")

    # Update Task Status in Supabase
    res_task = supabase.table("tasks").select("*").eq("task_id", payload.task_id).execute()
    if not res_task.data:
        raise HTTPException(status_code=404, detail="Task not found")
        
    task_rec = res_task.data[0]
    update_data = {"status": payload.status}
    if payload.status == "completed":
        update_data["result_url"] = payload.result_url
    elif payload.status == "failed":
        update_data["error"] = payload.error or "KIE generation failed"
        
    supabase.table("tasks").update(update_data).eq("task_id", payload.task_id).execute()

    # A-002: ?€ê¸?ì¤‘ì¸ SSE ?¤íŠ¸ë¦¼ì—ê²??„ë£Œ ?Œë¦¼ trigger
    if payload.task_id in TASK_EVENTS:
        TASK_EVENTS[payload.task_id].set()
    
    # FIFO 50 cleanup based on projects limit
    proj_id = task_rec.get("project_id")
    u_id = None
    if proj_id:
        res_proj = supabase.table("projects").select("user_id").eq("project_id", proj_id).execute()
        if res_proj.data:
            u_id = res_proj.data[0].get("user_id")
    if not u_id:
        u_id = task_rec.get("user_id") or "beta_tester"
    await enforce_user_fifo_limit(u_id, 50)
            
    return {"received": True}

@app.get("/api/archive")
async def get_archive(jwt_user_id: str = Depends(get_jwt_user_id)):
    sanitized_user = sanitize_uuid(jwt_user_id)
    res = supabase.table("projects").select("*, tasks(*)").eq("user_id", sanitized_user).execute()
    db_projects = res.data or []
    
    items = []
    now = datetime.utcnow()
    
    for proj in db_projects:
        plan = proj.get("plan_snapshot") or {}
        proj_tasks = proj.get("tasks") or []
        final_render_tasks = [t for t in proj_tasks if t.get("task_type") == "final_render"]
        
        for task in final_render_tasks:
            created_at_str = task.get("created_at")
            expires_at = None
            if created_at_str:
                try:
                    cleaned_created = created_at_str.replace("Z", "+00:00")
                    created_dt = datetime.fromisoformat(cleaned_created)
                    if created_dt.tzinfo is not None:
                        created_dt = created_dt.replace(tzinfo=None)
                    expires_dt = created_dt + timedelta(days=14)
                    if expires_dt < now:
                        continue
                    expires_at = expires_dt.isoformat()
                except Exception as ex:
                    print(f"[Archive Expiry Calc Error] {ex}")
            
            items.append({
                "user_id": jwt_user_id,
                "task_id": task.get("task_id"),
                "status": task.get("status"),
                "product_name": proj.get("product_name"),
                "created_at": task.get("created_at"),
                "title": task.get("description") or proj.get("product_name"),
                "plan_snapshot": plan,
                "result_url": task.get("result_url"),
                "expires_at": expires_at
            })
            
    items.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    items = items[:50]
    return {"items": items, "total": len(items)}

@app.post("/api/user-images")
async def upload_user_image(
    request: Request,
    file: UploadFile = File(...), 
    jwt_user_id: str = Depends(get_jwt_user_id)
):
    content_length = request.headers.get("content-length")
    try:
        if content_length and int(content_length) > MAX_IMAGE_SIZE:
            raise HTTPException(status_code=413, detail="File size exceeds 10MB limit.")
    except ValueError:
        pass

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=422, detail="Only image files are allowed.")
        
    filename = file.filename or 'upload.png'
    ext = filename.split('.')[-1].lower() if '.' in filename else 'png'
    
    if ext not in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
        raise HTTPException(status_code=422, detail=f"Unsupported image format: {ext}")
        
    image_id = f"ui_{uuid.uuid4().hex[:8]}"
    sanitized_user = sanitize_uuid(jwt_user_id)
    file_name = f"{sanitized_user}/{image_id}.{ext}"
    
    file_content = await file.read()
    if len(file_content) > MAX_IMAGE_SIZE:
        raise HTTPException(status_code=413, detail="File size exceeds 10MB limit.")
        
    try:
        supabase.storage.from_("assets").upload(
            path=file_name,
            file=file_content,
            file_options={"content-type": file.content_type}
        )
    except Exception as e:
        print(f"[Supabase Storage Upload Warning] {e}")
        raise HTTPException(status_code=500, detail="Failed to upload image to storage")
        
    signed_res = supabase.storage.from_("assets").create_signed_url(file_name, 3600)
    signed_url = None
    if isinstance(signed_res, dict):
        signed_url = signed_res.get("signedURL") or signed_res.get("signedUrl")
    elif isinstance(signed_res, str):
        signed_url = signed_res
        
    if not signed_url:
        raise HTTPException(status_code=500, detail="Failed to generate signed URL.")
    
    return {
        "url": signed_url,
        "id": image_id,
        "filename": file_name
    }

@app.post("/api/user-videos")
async def upload_user_video(
    request: Request,
    file: UploadFile = File(...), 
    jwt_user_id: str = Depends(get_jwt_user_id)
):
    content_length = request.headers.get("content-length")
    try:
        if content_length and int(content_length) > MAX_VIDEO_SIZE:
            raise HTTPException(status_code=413, detail="Video file size exceeds 500MB limit.")
    except ValueError:
        pass

    if not file.content_type.startswith("video/"):
        raise HTTPException(status_code=422, detail="Only video files are allowed.")
        
    filename = file.filename or 'upload.mp4'
    ext = filename.split('.')[-1].lower() if '.' in filename else 'mp4'
    if ext not in ['mp4', 'mov', 'webm']:
        raise HTTPException(status_code=422, detail=f"Unsupported video format: {ext}")
        
    video_id = f"uv_{uuid.uuid4().hex[:8]}"
    file_path = f"outputs/{video_id}.mp4"
    sanitized_user = sanitize_uuid(jwt_user_id)
    
    file_content = await file.read()
    if len(file_content) > MAX_VIDEO_SIZE:
        raise HTTPException(status_code=413, detail="Video file size exceeds 500MB limit.")

    try:
        os.makedirs("outputs", exist_ok=True)
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
            
        # Upload to Supabase Storage (assets bucket)
        try:
            supabase.storage.from_("assets").upload(
                path=f"{sanitized_user}/{video_id}.mp4",
                file=file_content,
                file_options={"content-type": "video/mp4"}
            )
        except Exception as e:
            print(f"[Supabase Storage Upload Error] {e}")
            raise HTTPException(status_code=500, detail="Video storage upload failed.")
            
        duration_seconds = 5.0
        asset_data = {
            "id": video_id,
            "filename": filename,
            "duration_seconds": duration_seconds,
            "uploaded_at": datetime.utcnow().isoformat(),
            "user_id": sanitized_user
        }
        
        res = supabase.table("user_video_assets").insert(asset_data).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="Failed to insert video asset metadata in database")
            
        return {
            "id": video_id,
            "filename": filename,
            "duration_seconds": duration_seconds,
            "uploaded_at": asset_data["uploaded_at"]
        }
    finally:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"[Cleanup Error] Failed to remove {file_path}: {e}")



@app.post("/api/generate-video-clips")
async def generate_video_clips_stream(
    request: RenderStreamRequest,
    raw_request: Request,
    background_tasks: BackgroundTasks,
    jwt_user_id: str = Depends(get_jwt_user_id),
    decrypted_key: str = Depends(get_decrypted_key),
    verify: None = Depends(verify_csrf)
):
    import asyncio
    import time
    import json

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="?œë²„ ?¤ì • ?¤ë¥˜: .env ?Œì¼??SUPABASE_URLê³?SUPABASE_KEYë¥??¤ì •?´ì£¼?¸ìš”.")

    N = len(request.scenes)

    async def generate_stream():
        try:
            await check_and_enforce_user_limits(jwt_user_id)
        except Exception as e:
            
            if "veo" in str(e).lower():
                yield f"data: {json.dumps({'status': 'error', 'message': 'Veo3.1 ë¹„ë””???ì„± ?¤íŒ¨. ?´íŒ ì°¸ì¡°.'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return
            
        yield f"data: {json.dumps({'message': 'KIE AI ë¹„ë””???ì„± ?”ì§„(Grok-imagine) ì´ˆê¸°??ì¤?..'})}\n\n"

        async def process_scene_inner(scene, index):
            if request.project_id:
                try:
                    response = supabase.table("tasks").select("*")\
                        .eq("project_id", request.project_id)\
                        .eq("status", "success")\
                        .eq("task_type", "video_generation")\
                        .like("description", f"%?¥ë©´ {index+1}%")\
                        .order("created_at", desc=True)\
                        .limit(1)\
                        .execute()
                    if response.data:
                        db_video_url = response.data[0].get("result_url")
                        if db_video_url:
                            print(f"[RISK-B GUARD] Found latest successful video from DB for Scene {index+1}: {db_video_url}")
                            scene_copy = dict(scene)
                            scene_copy['video_url'] = db_video_url
                            scene_copy['status'] = 'success'
                            return {**scene_copy, "_index": index}
                except Exception as db_err:
                    print(f"[RISK-B GUARD ERROR] Failed to query database: {db_err}")

            existing_video_url = scene.get('video_url')
            if existing_video_url and existing_video_url.startswith("http"):
                print(f"[SKIP] Scene {index+1} already has a valid video URL: {existing_video_url}")
                return {**scene, "_index": index}
            
            existing_task_id = scene.get('taskId')
            if existing_task_id and scene.get('status') in ['success', 'waiting', 'ready', 'active']:
                print(f"[SKIP] Scene {index+1} already has a running/completed task: {existing_task_id}")
                if scene.get('status') == 'success' and existing_video_url:
                    return {**scene, "_index": index}

            scene_task_id = f"task_{request.project_id or 'render'}_{index+1}_{int(time.time())}"
            if request.project_id:
                await create_task_in_db(request.project_id, scene_task_id, "video_generation", f"?¥ë©´ {index+1} ë¹„ë””???ì„± ?œë„")

            is_success = False
            uploaded_files_scene = [] 
            try:
                is_hybrid_skip = scene.get('use_image_only', False)
                if is_hybrid_skip:
                    print(f"[HYBRID SKIP] Scene {index+1} text-heavy scene skipped for video generation (Hybrid Mode)")
                    scene_copy = dict(scene)
                    scene_copy['video_url'] = None
                    if request.project_id:
                        await update_task_in_db(scene_task_id, "success", result_url=None)
                    is_success = True
                    return {**scene_copy, "_index": index}

                if scene.get("prompt") == "TRIGGER_MOCK_ERROR":
                    print(f"[MOCK ERROR] Simulating 503 error for scene {index+1}")
                    raise Exception("Mock Video Generation Failure (503 Service Unavailable)")

                # Use manual client management to explicitly call aclose() and prevent Errno 11
                client = httpx.AsyncClient()
                try:
                    image_url = scene.get('image_url')
                    if not image_url:
                        return {**scene, "_index": index}

                    public_url, file_name = await upload_image_to_supabase(image_url, id(scene))
                    uploaded_files_scene.append(file_name)

                    callback_url = None
                    if request.project_id:
                        try:
                            res_proj = supabase.table("projects").select("plan_snapshot").eq("project_id", request.project_id).execute()
                            if res_proj.data and res_proj.data[0].get("plan_snapshot"):
                                callback_url = res_proj.data[0]["plan_snapshot"].get("callback_url")
                        except Exception as pe:
                            print(f"[CALLBACK FETCH WARN] Failed to fetch callback_url: {pe}")

                    try:
                        raw_duration = int(float(scene.get('duration_seconds', 4)))
                    except (ValueError, TypeError):
                        raw_duration = 4
                    scene_duration = "6" if raw_duration <= 6 else "10" if raw_duration <= 10 else "15"

                    is_veo = (request.engine in ["veo", "veo_lite", "veo_fast"])
                    
                    if is_veo:
                        url = "https://api.kie.ai/api/v1/veo/generate"
                        model_name = "veo3_fast" if request.engine == "veo_fast" else "veo3_lite"
                        gen_type = "REFERENCE_2_VIDEO" if request.engine == "veo_fast" else "FIRST_AND_LAST_FRAMES_2_VIDEO"
                        
                        payload = {
                            "prompt": scene.get('image_prompt', 'Animate this image'),
                            "imageUrls": [public_url],
                            "model": model_name,
                            "watermark": "",
                            "aspect_ratio": request.aspect_ratio,
                            "generationType": gen_type,
                            "enableFallback": False,
                            "enableTranslation": True
                        }
                        if callback_url:
                            payload["callBackUrl"] = callback_url
                    else:
                        url = "https://api.kie.ai/api/v1/jobs/createTask"
                        model_name = "grok-imagine/image-to-video"
                        payload = {
                            "model": model_name,
                            "input": {
                                "task_id": f"task_grok_{id(scene)}_{int(time.time())}",
                                "image_urls": [public_url],
                                "prompt": scene.get('image_prompt', 'Animate this image'),
                                "mode": "normal",
                                "duration": str(scene_duration),
                                "resolution": "480p",
                                "aspect_ratio": request.aspect_ratio
                            }
                        }
                        if callback_url:
                            payload["callBackUrl"] = callback_url

                    vid_url = None
                    task_id = None
                    credits_consumed = 0
                    print(f"[KIE] Scene {index+1} Create Task")
                    res = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {decrypted_key}"},
                        json=payload,
                        timeout=90.0
                    )
                    print(f"[KIE] Scene {index+1} Create Task Status: {res.status_code}, Body: {res.text}")
                    if res.status_code == 200:
                        data = res.json()
                        task_id = data.get('taskId') or (data.get('data') or {}).get('taskId') or data.get('id') or (data.get('data') or {}).get('id')
                    
                    if not task_id:
                        raise Exception(f"Failed to get task_id from KIE AI for scene {index+1}. Response: {res.text if 'res' in locals() else 'None'}")

                    print(f"[KIE] Scene {index+1} Task ID: {task_id}")

                    poll_attempts = 0
                    start_poll_time = time.time()
                    polling_timeout = 720 if request.engine == "grok" else 900
                    last_status = "WAITING"
                    
                    event = TASK_EVENTS.setdefault(task_id, asyncio.Event())
                    
                    try:
                        while True:
                            if await raw_request.is_disconnected():
                                print(f"[DISCONNECT] Scene {index+1} task {task_id} polling loop aborted. Client disconnected.")
                                raise asyncio.CancelledError()
                            
                            try:
                                await asyncio.wait_for(event.wait(), timeout=5.0)
                                event.clear()
                            except asyncio.TimeoutError:
                                pass
                                
                            poll_attempts += 1
                            elapsed = time.time() - start_poll_time
                            if elapsed >= 1800:
                                raise Exception("?œë²„ ?‘ë‹µ ì§€???ˆë? ?œê°„ 30ë¶?ì´ˆê³¼)?…ë‹ˆ??")
                            elif elapsed >= polling_timeout and last_status not in ['WAITING', 'IN_PROGRESS', 'PENDING', 'PROCESSING', 'QUEUE']:
                                raise Exception("?œë²„ ?‘ë‹µ ì§€???œê°„ ì´ˆê³¼)?…ë‹ˆ?? ?¤íŒ¨???¬ë????´ì–´???Œë”ë§?ë²„íŠ¼???ŒëŸ¬ì£¼ì„¸??")
                            
                            res_task = supabase.table("tasks").select("status, result_url, error").eq("task_id", task_id).execute()
                            if res_task.data:
                                task_data = res_task.data[0]
                                state = task_data.get("status", "waiting").lower()
                                last_status = state.upper()
                                
                                if state == 'success' or state == 'completed':
                                    vid_url = task_data.get("result_url")
                                    break
                                elif state == 'fail' or state == 'failed':
                                    raise Exception(f"ë¹„ë””???ì„± ?¤íŒ¨: {task_data.get('error') or 'KIE AI ë¹„ë””???ì„± ?”ì§„ ?¤íŒ¨'}")
                            
                            poll_res = await client.get(f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}", headers={"Authorization": f"Bearer {decrypted_key}"}, timeout=30.0)
                            
                            if poll_res.status_code >= 500:
                                raise Exception("ë¹„ë””???ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?Œë”ë§??¤ë¥˜). ?¤ì‹œ ?œë„??ì£¼ì„¸??")
                                
                            if poll_res.status_code == 200:
                                poll_data = poll_res.json()
                                poll_code = poll_data.get('code')
                                poll_dict = poll_data.get('data') or {}
                                
                                if poll_code and (poll_code >= 500 or poll_code == -1):
                                    raise Exception("ë¹„ë””???ì„±???¤íŒ¨?ˆìŠµ?ˆë‹¤ (KIE ?œë²„ ?Œë”ë§??¤ë¥˜). ?¤ì‹œ ?œë„??ì£¼ì„¸??")
                                    
                                if poll_code is not None and poll_code != 200:
                                    print(f"[KIE] Scene {index+1} Task {task_id} API returned error code {poll_code}: {poll_res.text}")
                                    break
                                    
                                status_raw = poll_dict.get('state') or poll_dict.get('status') or poll_data.get('state') or poll_data.get('status')
                                status = str(status_raw).lower() if status_raw else "waiting"
                                last_status = status.upper()
                                
                                print(f"[KIE] Scene {index+1} Task {task_id} Polling... Status: {last_status}")
                                
                                if status == 'success':
                                    result_json = poll_dict.get('resultJson') or poll_data.get('resultJson')
                                    if result_json:
                                        try:
                                            if isinstance(result_json, str):
                                                parsed = json.loads(result_json)
                                            elif isinstance(result_json, dict):
                                                parsed = result_json
                                            else:
                                                parsed = {}
                                            urls = parsed.get('resultUrls') or parsed.get('urls') or []
                                            if urls and len(urls) > 0:
                                                vid_url = urls[0]
                                        except Exception as e:
                                            print(f"[KIE Polling Error] Raw Response: {poll_data}")
                                            print(f"[KIE] Failed to parse resultJson: {e}")
                                    
                                    if not vid_url:
                                        vid_url = poll_dict.get('video_url') or poll_dict.get('file_url') or poll_dict.get('url') or poll_data.get('video_url')
                                    
                                    credits_consumed = poll_dict.get('creditsConsumed') or poll_dict.get('credits_consumed') or poll_data.get('creditsConsumed') or poll_data.get('credits_consumed') or 0
                                    try:
                                        credits_consumed = int(credits_consumed)
                                    except:
                                        credits_consumed = 0
                                    break
                                elif status == 'fail':
                                    fail_msg = poll_dict.get('failMsg') or poll_data.get('failMsg') or poll_dict.get('reason') or poll_data.get('reason') or "KIE AI ë¹„ë””???ì„± ?”ì§„ ?¤íŒ¨"
                                    print(f"[KIE AI VIDEO ERROR] Task {task_id} failed. Status: {status}, failMsg: {fail_msg}")
                                    raise Exception(f"ë¹„ë””???ì„± ?¤íŒ¨: {fail_msg}")
                                elif status == 'waiting':
                                    print(f"[KIE Polling] Task {task_id} is waiting for completion...")
                            else:
                                print(f"[KIE] Scene {index+1} Polling Error Status: {poll_res.status_code}, Body: {poll_res.text}")
                                if poll_attempts > 180:
                                    break
                    finally:
                        TASK_EVENTS.pop(task_id, None)
                finally:
                    # Explicitly close the connection to prevent Errno 11 resource leak
                    await client.aclose()

                if vid_url:
                    if request.project_id:
                        await update_task_in_db(scene_task_id, "success", result_url=vid_url)
                    is_success = True
                    return {**scene, "video_url": vid_url, "_index": index, "status": "success", "taskId": task_id, "credits_consumed": credits_consumed}
                else:
                    raise Exception(f"Task {task_id} failed or no video URL found.")
            except asyncio.CancelledError as ce:
                print(f"[DISCONNECT] Scene {index+1} task {scene_task_id} cancelled due to disconnect.")
                if request.project_id:
                    await update_task_in_db(scene_task_id, "failed", error="Client connection disconnected.")
                raise ce
            except Exception as e:
                if request.project_id:
                    await update_task_in_db(scene_task_id, "failed", error=str(e))
                raise e
            finally:
                if not is_success and request.project_id:
                    try:
                        await update_task_in_db(scene_task_id, "failed", error="Render stream terminated unexpectedly.")
                    except:
                        pass
                if uploaded_files_scene:
                    loop = asyncio.get_event_loop()
                    def _cleanup():
                        try:
                            supabase.storage.from_("assets").remove(uploaded_files_scene)
                            print(f"[CLEANUP] Successfully removed temporary assets from stream: {uploaded_files_scene}")
                        except Exception as e:
                            print(f"[CLEANUP ERROR] Failed to remove temporary assets {uploaded_files_scene}: {e}")
                    await loop.run_in_executor(None, _cleanup)

        async def process_scene(scene, index):
            return await process_scene_inner(scene, index)

        tasks = [asyncio.create_task(process_scene(scene, i)) for i, scene in enumerate(request.scenes)]
        yield f"data: {json.dumps({'message': f'ì´?{N}ê°œì˜ ?¥ë©´ ?™ì˜???ì„± ?™ì‹œ ?”ì²­ ?„ë£Œ'})}\n\n"

        results = [None] * N
        completed_count = 0
        for completed_task in asyncio.as_completed(tasks):
            if await raw_request.is_disconnected():
                print("[DISCONNECT] Client disconnected during scene tasks completion loop. Cancelling remaining tasks.")
                for t in tasks:
                    if not t.done():
                        t.cancel()
                raise asyncio.CancelledError()

            try:
                res = await completed_task
                results[res["_index"]] = res
                completed_count += 1
                idx = res["_index"]
                msg = res.get("_fallback_msg") or f"?¥ë©´ {idx + 1} ?™ì˜???„ë£Œ ({completed_count}/{N}), ?˜ë¨¸ì§€ ?€ê¸?ì¤?.."
                yield f"data: {json.dumps({'message': msg, 'scene_update': res})}\n\n"
            except Exception as e:
                if "veo" in str(e).lower():
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Veo3.1 ë¹„ë””???ì„± ?¤íŒ¨. ?´íŒ ì°¸ì¡°.'})}\n\n"
                else:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

        ordered_scenes = [{k: v for k, v in scene.items() if k != "_index"} for scene in results]
        yield f"data: {json.dumps({'message': 'ë¹„ë””???´ë¦½ ?ì„± ?„ë£Œ', 'clips_ready': True, 'scenes': ordered_scenes})}\n\n"
            
    return StreamingResponse(generate_stream(), media_type="text/event-stream")


@app.post("/api/render-final")
async def render_final_stream(
    request: RenderStreamRequest,
    raw_request: Request,
    background_tasks: BackgroundTasks,
    jwt_user_id: str = Depends(get_jwt_user_id),
    decrypted_key: str = Depends(get_decrypted_key),
    verify: None = Depends(verify_csrf)
):
    import asyncio
    import time
    import json

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="?œë²„ ?¤ì • ?¤ë¥˜: .env ?Œì¼??SUPABASE_URLê³?SUPABASE_KEYë¥??¤ì •?´ì£¼?¸ìš”.")

    N = len(request.scenes)

    async def generate_stream():
        try:
            await check_and_enforce_user_limits(jwt_user_id)
        except Exception as e:
            
            if "veo" in str(e).lower():
                yield f"data: {json.dumps({'status': 'error', 'message': 'Veo3.1 ë¹„ë””???ì„± ?¤íŒ¨. ?´íŒ ì°¸ì¡°.'})}\n\n"
            else:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

            return
            
        yield f"data: {json.dumps({'message': f'{N}ê°œì˜ ?™ì˜???Œì„±ê³??ë§‰???©ì³ FFmpeg ìµœì¢… ?Œë”ë§?ì¤?..'})}\n\n"

        task_id = None
        try:
            task_id = f"task_{int(time.time())}"
            if request.project_id:
                await create_task_in_db(request.project_id, task_id, "final_render", "ìµœì¢… ?™ì˜??MP4 ?Œë”ë§??œë„")
            
            gen = ffmpeg_worker.render_video(
                task_id=task_id,
                scenes=request.scenes,
                voice_type=request.voice_type,
                aspect_ratio=request.aspect_ratio,
                subtitle_position=request.subtitle_position,
                subtitle_font=request.subtitle_font,
                render_duration=request.render_duration,
                openai_key=decrypted_key,
                watermark_enabled=request.watermark_enabled,
                watermark_logo=request.watermark_logo,
                watermark_position=request.watermark_position,
                rendering_mode=request.rendering_mode
            )
            try:
                async for item in gen:
                    if await raw_request.is_disconnected():
                        print("[DISCONNECT] Client disconnected during FFmpeg video rendering loop.")
                        raise asyncio.CancelledError()

                    if isinstance(item, str):
                        yield f"data: {json.dumps({'message': item})}\n\n"
                    elif isinstance(item, dict) and "output_url" in item:
                        user_id = jwt_user_id
                        product_name = request.product_name
                        upload_package = request.upload_package or {}
                        title = upload_package.get("titles", [product_name])[0] if upload_package.get("titles") else product_name
                        thumbnail_url = ""
                        if request.scenes and len(request.scenes) > 0:
                            thumbnail_url = request.scenes[0].get("image_url", "")
                        await record_user_asset(user_id, task_id, item['output_url'], product_name, title, thumbnail_url, upload_package)
                        if request.project_id:
                            await update_task_in_db(task_id, "success", result_url=item['output_url'])
                        yield f"data: {json.dumps({'message': 'ìµœì¢… ?Œë”ë§??„ë£Œ!', 'output_url': item['output_url']})}\n\n"
            finally:
                await gen.aclose()
        except Exception as e:
            if request.project_id and task_id:
                await update_task_in_db(task_id, "failed", error=str(e))
            yield f"data: {json.dumps({'error': f'FFmpeg Error: {str(e)}'})}\n\n"
            
    return StreamingResponse(generate_stream(), media_type="text/event-stream")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

