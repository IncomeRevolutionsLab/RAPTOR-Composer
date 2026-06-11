import os
import json
import time
import re
import traceback
import httpx
from typing import List, Optional, Literal
from fastapi import FastAPI, Header, HTTPException, Request, Depends, Cookie, UploadFile, File, BackgroundTasks
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
# [v2.15.0] import jwt (PyJWT) 제거 — Supabase SDK get_user()로 전환
import asyncio

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

# [v2.15.0] SUPABASE_JWT_SECRET 의존성 완전 제거 — ECC(P-256) 대응으로 SDK 위임 전환

IS_PROD = os.getenv("ENV", "development").lower() in ["production", "prod"]

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
    print("경고: .env 파일에 SUPABASE_URL과 SUPABASE_KEY를 설정해주세요.")
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
                # 윈도우 환경 한글 깨짐 및 UnicodeDecodeError 원천 차단
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
        raise HTTPException(status_code=401, detail="API Key가 설정되지 않았습니다. Global Settings에서 KIE API Key를 입력해 주세요.")
    return x_byok_kie.strip()

def get_jwt_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    [v2.15.0] ECC(P-256) 대응 — PyJWT 수동 검증 철거, Supabase SDK 위임 방식으로 전환
    - supabase.auth.get_user(token): SDK 레벨에서 JWKS 자동 처리 (HS256/ES256 모두 지원)
    - sync def 유지: FastAPI가 스레드풀에서 실행 → 이벤트 루프 차단 없음
    - Claude Code Pre-Review 권고 반영: 예외 메시지 은닉 + 올바른 예외 전파
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 헤더가 누락되었거나 형식이 올바르지 않습니다.")
    token = authorization.split(" ", 1)[1]
    try:
        response = supabase.auth.get_user(token)
        user = response.user
        if not user or not user.id:
            raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
        return user.id
    except HTTPException:
        raise
    except Exception as e:
        # [SECURITY] 내부 에러 메시지 클라이언트 노출 방지 — 서버 로그에만 상세 기록
        print(f"[AUTH ERROR] get_user failed: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

def map_image_model(model_name: Optional[str]) -> str:
    if not model_name:
        return "gpt-image-2"
    normalized = model_name.lower().strip()
    if "openai" in normalized or normalized == "gpt-image-2":
        return "gpt-image-2"
    elif "grok" in normalized:
        return "grok-imagine/text-to-image"
    elif "banana" in normalized:
        return "nano-banana-2"
    return model_name



# --- Database Configuration ---
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mock-project.supabase.co")
# S-004: 백엔드 내부 DB 연동은 RLS 우회 및 데이터 직접 제어가 필요하므로 SUPABASE_SERVICE_ROLE_KEY 사용
# 만약 환경변수 SUPABASE_SERVICE_ROLE_KEY가 정의되어 있지 않으면 기존 SUPABASE_KEY를 폴백으로 사용
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_KEY", "mock-service-role-key-123456789"))
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

def sanitize_uuid(user_id_str: str) -> str:
    uuid_pattern = re.compile(r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$')
    if uuid_pattern.match(user_id_str):
        return user_id_str
    raise HTTPException(status_code=400, detail="Invalid user ID format (UUID expected).")

async def upload_image_to_supabase(image_url: str, scene_id: int) -> tuple[str, str]:
    """
    [A-005] 이미지 다운로드 및 Supabase 스토리지 업로드 로직의 단일화
    [S-006] Supabase Storage assets 버킷을 Private으로 전환하고, 30분 만료(TTL) 서명된 URL 발급
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
        # 30분(1800초) 유효한 Signed URL 발급
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
    target_language: str = "한국어"
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
    model: Optional[str] = "gpt-image-2"

class VideoGenRequest(BaseModel):
    product_name: str
    scenes: List[dict]
    engine: str = "grok"
    rendering_mode: str = "full"
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"

class RenderRequest(BaseModel):
    product_name: str
    scenes: List[dict]
    voice_type: str = "여성-발랄한"
    status: str

class RenderStreamRequest(BaseModel):
    product_name: str
    scenes: List[dict]
    voice_type: str = "여성-발랄한"
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    quality: str = "export"
    subtitle_position: str = "하"
    render_duration: str = "자막 맞춤 길이 (Dynamic Sync)"
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

async def enforce_user_fifo_limit(user_id: str, limit: int):
    """
    [P-006] FIFO 한도 정리 로직을 공통 함수로 단일화
    """
    sanitized_user = sanitize_uuid(user_id)
    res_projects = supabase.table("projects").select("project_id, created_at").eq("user_id", sanitized_user).execute()
    user_projects = res_projects.data or []
    
    if len(user_projects) > limit:
        user_projects.sort(key=lambda x: x.get("created_at", ""))
        excess_count = len(user_projects) - limit
        to_delete = user_projects[:excess_count]
        to_delete_ids = [p.get("project_id") for p in to_delete]
        
        # CASCADE delete: Supabase will delete tasks automatically
        res_tasks = supabase.table("tasks").select("task_id").in_("project_id", to_delete_ids).execute()
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
                
        supabase.table("projects").delete().in_("project_id", to_delete_ids).execute()
        print(f"[CASCADE FIFO] Cleaned up oldest projects: {to_delete_ids} to enforce limit {limit}")

async def check_and_enforce_user_limits(user_id: str = "beta_tester"):
    sanitized_user = sanitize_uuid(user_id)
    current_month = datetime.now().strftime("%Y-%m")
    
    res_projects = supabase.table("projects").select("*").eq("user_id", sanitized_user).execute()
    user_projects = res_projects.data or []
    
    # 1. Monthly Limit Check (10 projects per month)
    monthly_count = len([p for p in user_projects if p.get("created_at", "").startswith(current_month)])
    if monthly_count >= 10:
        raise Exception("베타 테스트 월간 프로젝트 생성 한도(10개)를 초과했습니다. 다음 달에 다시 이용해 주세요.")
        
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
            "description": title or "최종 렌더링 완료",
            "status": "success",
            "result_url": output_url,
            "error": None,
            "created_at": datetime.now().isoformat()
        }
        supabase.table("tasks").insert(new_task).execute()

@app.get("/api/user-videos")
async def get_user_videos(user_id: str, jwt_user_id: str = Depends(get_jwt_user_id)):
    if user_id != jwt_user_id:
        raise HTTPException(status_code=403, detail="타인의 비디오 목록을 조회할 권한이 없습니다.")
        
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

# 프로젝트 소유권 검증 헬퍼 (IDOR 방어)
def verify_project_owner(project_id: str, user_id: str):
    sanitized_user = sanitize_uuid(user_id)
    res = supabase.table("projects").select("user_id").eq("project_id", project_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="프로젝트를 찾을 수 없습니다.")
    if res.data[0].get("user_id") != sanitized_user:
        raise HTTPException(status_code=403, detail="프로젝트에 접근할 권한이 없습니다.")

# 태스크 소유권 검증 헬퍼 (IDOR 방어)
def verify_task_owner(task_id: str, user_id: str):
    res = supabase.table("tasks").select("project_id").eq("task_id", task_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다.")
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
        raise HTTPException(status_code=404, detail="태스크를 찾을 수 없습니다.")
    return task

@app.get("/api/dashboard/projects")
async def get_dashboard_projects(user_id: str, jwt_user_id: str = Depends(get_jwt_user_id)):
    if user_id != jwt_user_id:
        raise HTTPException(status_code=403, detail="타인의 프로젝트 목록을 조회할 권한이 없습니다.")
        
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


# --- Endpoints ---

class AuthRequest(BaseModel):
    email: str
    password: str

@app.post("/api/auth/signup")
async def auth_signup(req: AuthRequest):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase 설정이 구성되지 않았습니다.")
    
    # S-001: 일반 signup API (/auth/v1/signup) 사용으로 전환. anon key 사용 가능.
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
                error_msg = resp_data.get("msg") or resp_data.get("error_description") or resp_data.get("error", {}).get("message") or "회원가입 실패"
                raise HTTPException(status_code=resp.status_code, detail=error_msg)
            return {"user": resp_data}
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"인증 서버 통신 실패: {str(e)}")

@app.post("/api/auth/signin")
async def auth_signin(req: AuthRequest):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise HTTPException(status_code=500, detail="Supabase 설정이 구성되지 않았습니다.")
    
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
                error_msg = resp_data.get("error_description") or resp_data.get("msg") or "로그인 실패"
                raise HTTPException(status_code=resp.status_code, detail=error_msg)
            return resp_data
        except httpx.RequestError as e:
            raise HTTPException(status_code=500, detail=f"인증 서버 통신 실패: {str(e)}")

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
    # 동적으로 가장 최신의 implementation_plan.md가 위치한 brain 폴더 경로를 감지합니다.
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
            
    # Risk_Tracker.md는 workspace root에 존재하는 것을 읽습니다.
    tracker_path = "Risk_Tracker.md"
    
    if not os.path.exists(plan_path):
        raise HTTPException(status_code=404, detail="실행 계획서(implementation_plan.md)를 찾을 수 없습니다.")
    
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

    prompt = f"""아래는 RAPTOR V2.5 랩터 워크플로우 전면 분리 및 UX 대개편 수술 계획서(implementation_plan.md)와 기존의 누적 리스크 추적 문서(Risk_Tracker.md)입니다.
현재 실제 소스 코드 상태와 두 문서를 교차 검증하여 한국어로 꼼꼼하게 아키텍처 사전 리뷰(Pre-Review) 보고서를 작성해줘.

리뷰 보고서는 반드시 다음 3가지 카테고리로만 엄격하게 분류하여 작성해야 해:
1. [Resolved]: 이전 지적 사항(Risk_Tracker.md의 리스크 목록) 중 이번 계획서(implementation_plan.md)를 통해 완벽히 해결되는 항목과 그 설명
2. [Pending]: 이전 지적 사항 중 이번 계획서에서도 아직 완전한 해결책이 제시되지 않고 위험 요소로 남은 항목과 그 이유
3. [New]: 이번 코드 개편 계획이나 현재 상태에서 새롭게 식별된 잠재적 취약점 또는 개선점

[누적 리스크 추적서 (Risk_Tracker.md)]
{tracker_content}

[실행 계획서 (implementation_plan.md)]
{plan_content}
"""
    try:
        response = client.messages.create(
            model=DEFAULT_CLAUDE_MODEL,
            max_tokens=4096,
            messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        )
        review_result = response.content[0].text
        
        today_str = date.today().strftime("%Y%m%d")
        report_filename = f"{today_str}_RAPTOR_Review_Report_v2.9.18_Pre.md"
        report_path = os.path.join(target_brain_dir, report_filename)
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(review_result)
            
        # 하위 호환성을 위해 legacy review_report.md도 최신 내용으로 백업 갱신
        legacy_report_path = os.path.join(target_brain_dir, "review_report.md")
        with open(legacy_report_path, "w", encoding="utf-8") as f:
            f.write(review_result)
            
        return {"status": "success", "message": "사전 리뷰 보고서가 정상적으로 갱신되었습니다.", "filename": report_filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KIE Claude 호출 실패: {str(e)}")




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
            raise HTTPException(status_code=403, detail="SSRF 방어: 허용되지 않은 도메인의 이미지 프록시는 금지됩니다.")

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
    raise HTTPException(status_code=503, detail="스크래핑 기능은 현재 점검 중입니다.")

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
    p_name = request.product_name or request.name or "상품"
    
    # --- Dynamic HIL Pattern Instruction ---
    hil_instruction = ""
    if request.selected_pattern:
        hil_instruction = f"\n[CRITICAL HIL RULE]: 사용자가 [{request.selected_pattern}] 패턴을 강제 지정했다. AI 자체 판단을 무시하고 스크립트 작성 시 무조건 이 패턴을 최우선으로 적용하라."

    # --- Dynamic Manual Additions (HIL) ---
    manual_instruction = ""
    if request.manual_additions:
        pains = request.manual_additions.get("pain_points", [])
        strens = request.manual_additions.get("strengths", [])
        if pains or strens:
            manual_instruction = "\n[USER INPUT HIL DATA]: 사용자가 직접 분석한 수동 피드백 정보가 존재합니다. 이 내용을 시나리오와 기획에 적극 반영하여 스크립트를 생성하십시오."
            if pains:
                manual_instruction += f"\n- 사용자 지정 불편함(Pain Points): {', '.join(pains)}"
            if strens:
                manual_instruction += f"\n- 사용자 지정 장점(Strengths): {', '.join(strens)}"

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
Marketing Purpose (숏폼 목적): {request.purpose or "쇼핑 전환"}
Target Audience (타깃층): {request.target_audience or "전체"}
Video Tone (영상 톤): {request.tone or "리뷰형"}
{manual_instruction}

Please analyze the product and recommend the top 2 patterns from the following 7 short-form patterns:
1. 문제 해결형
2. 전후 비교형
3. 숨은 기능 발견형
4. 시간 절약형
5. 생활 개선형
6. 공감형
7. 실사용 후기형

Output MUST be a valid JSON matching this schema exactly, and nothing else:
{{
  "product_analysis": {{
    "pain_point": "분석된 사용자 고통 (타깃층과 목적을 반영)",
    "core_benefit": "핵심 장점",
    "purchase_trigger": "선택된 구매 트리거",
    "product_ref": ["특징1", "특징2", "특징3"]
  }},
  "recommended_patterns": [
    {{
      "pattern_name": "추천 패턴 1 (위 7가지 중 하나)",
      "reason": "추천 이유 한 줄 (타깃층과 마케팅 목적에 근거)",
      "sample_dialogue": "짧은 대사 샘플 (후킹용 1문장)"
    }},
    {{
      "pattern_name": "추천 패턴 2 (위 7가지 중 하나)",
      "reason": "추천 이유 한 줄 (타깃층과 마케팅 목적에 근거)",
      "sample_dialogue": "짧은 대사 샘플 (후킹용 1문장)"
    }}
  ]
}}
"""
    else:
        # Generation Mode: Build actual scenes based on selected pattern
        user_prompt = f"""
[CRITICAL HIL RULE]: 사용자가 [{request.selected_pattern}] 패턴을 강제 지정했다. AI 자체 판단을 무시하고 스크립트 작성 시 무조건 이 패턴을 최우선으로 적용하라.
{manual_instruction}

Create a professional 9:16 short-form commercial plan based on the following:
Product Name: {p_name}
User Description: {request.description}
Target Language: {request.target_language}
Video Length: {request.duration} seconds
Marketing Purpose (숏폼 목적): {request.purpose or "쇼핑 전환"}
Target Audience (타깃층): {request.target_audience or "전체"}
Video Tone (영상 톤): {request.tone or "리뷰형"}

[DYNAMIC HOOK & SCRIPT VARIETY RULE]
반드시 무미건조한 기본 패턴을 탈피하라! 상품의 성격과 지정된 패턴에 맞추어 완전히 다른 극적인 Hook(도입부)과 파격적인 스토리텔링을 구성해라.
절대 뻔한 "안녕하세요", "소개합니다" 식의 멘트를 쓰지 말고, 시청자가 첫 1초 만에 몰입할 수 있는 공격적이고 창의적인 훅을 작성하라.

Output MUST be a valid JSON matching this schema exactly, and nothing else:
{{
  "strategy": {{
    "selected_pattern": "{request.selected_pattern}",
    "hook": "스크립트의 첫 후킹 문장",
    "wow": "후킹 직후의 놀람 문장",
    "cta": "행동 유도 문장"
  }},
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": 2,
      "role": "문제 상황 장면",
      "dialogue": "영상에 들어갈 실제 대사",
      "visual_description": "장면의 시각적 설명",
      "image_prompt": "DALL-E 3용 고품질 영문 프롬프트"
    }}
    // 더 많은 Scene 객체들...
  ],
  "upload_package": {{
    "titles": ["제목1", "제목2", "제목3", "제목4", "제목5"],
    "description": "설명문",
    "hashtags": ["#태그1", "#태그2"],
    "keywords": ["키워드1", "키워드2"],
    "thumbnail_texts": ["썸네일문구1", "썸네일문구2", "썸네일문구3"]
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
                        messages=[{"role": "user", "content": content}]
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

                    return json.loads(clean_json)
                    
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
                    # 1. createTask 호출
                    create_res = await client.post(
                        "https://api.kie.ai/api/v1/jobs/createTask",
                        headers={
                            "Authorization": f"Bearer {decrypted_key}",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        },
                        json={
                            "model": map_image_model(request.model),
                            "input": {
                                "prompt": full_prompt,
                                "n": 1,
                                "size": img_size,
                                "quality": "medium"
                            }
                        },
                        timeout=60.0
                    )
                    
                    if create_res.status_code != 200:
                        raise Exception(f"Failed to create image task ({create_res.status_code}): {create_res.text}")
                    
                    resp_data = create_res.json()
                    data_dict = resp_data.get('data') or {}
                    task_id = resp_data.get('taskId') or data_dict.get('taskId') or resp_data.get('id') or data_dict.get('id')
                    
                    if not task_id:
                        raise Exception(f"Failed to get taskId from create image task. Response: {create_res.text}")
                    
                    # 2. recordInfo 폴링
                    polling_timeout = 180
                    start_poll_time = time.time()
                    image_url = None
                    
                    while True:
                        await asyncio.sleep(3)
                        elapsed = time.time() - start_poll_time
                        if elapsed >= polling_timeout:
                            raise Exception("이미지 생성 서버 응답 지연(3분 초과)입니다.")
                        
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
                            raise Exception("이미지 생성에 실패했습니다 (KIE 서버 렌더링 오류).")
                            
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
                            raise Exception("이미지 생성에 실패했습니다 (KIE 서버 작업 실패).")
                    
                    if image_url:
                        return {"data": [{"url": image_url}]}
                    else:
                        raise Exception("이미지 URL을 찾을 수 없습니다.")
                        
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
        raise HTTPException(status_code=500, detail="서버 설정 오류: .env 파일에 SUPABASE_URL과 SUPABASE_KEY를 설정해주세요.")

    results = []
    uploaded_files = [] # 업로드된 임시 이미지 파일명 추적용 (P-002)
    
    try:
        async with httpx.AsyncClient() as client:
            for index, scene in enumerate(request.scenes):
                # 1. 크레딧 방어: 기존 비디오가 유효하면 KIE API 스킵
                existing_video_url = scene.get('video_url')
                if existing_video_url and existing_video_url.startswith("http"):
                    print(f"[SKIP] Scene {index+1} already has a valid video URL: {existing_video_url}")
                    results.append(scene)
                    continue

                # 2. 하이브리드 모드 시 특정 씬 스킵 (프론트엔드 제어)
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
                    
                # engine 분기 적용
                is_veo = (request.engine in ["veo", "veo_lite", "veo_fast"])
                
                if is_veo:
                    url = "https://api.kie.ai/api/v1/veo/generate"
                    
                    # Veo 모델 및 generationType 분기 처리
                    model_name = "veo3_fast" if request.engine == "veo_fast" else "veo3_lite"
                    gen_type = "REFERENCE_2_VIDEO" if request.engine == "veo_fast" else "FIRST_AND_LAST_FRAMES_2_VIDEO"
                    
                    payload = {
                        "prompt": scene.get('image_prompt', 'Animate this image'),
                        "imageUrls": [public_url],
                        "model": model_name,
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
                            "image_urls": [public_url],
                            "prompt": scene.get('image_prompt', 'Animate this image'),
                            "duration": str(scene_duration),
                            "resolution": "720p",
                            "aspect_ratio": request.aspect_ratio,
                            "mode": "normal"
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
                        raise Exception("서버 응답 지연(절대 시간 30분 초과)입니다.")
                    elif elapsed >= polling_timeout and last_status not in ['WAITING', 'IN_PROGRESS', 'PENDING', 'PROCESSING', 'QUEUE']:
                        raise Exception("서버 응답 지연(시간 초과)입니다. 실패한 씬부터 이어서 렌더링 버튼을 눌러주세요.")
                    
                    poll_res = await client.get(
                        f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
                        headers={"Authorization": f"Bearer {decrypted_key}"},
                        timeout=30.0
                    )

                    if poll_res.status_code >= 500:
                        raise Exception("비디오 생성에 실패했습니다 (KIE 서버 렌더링 오류). 다시 시도해 주세요.")

                    if poll_res.status_code != 200:
                        break
                        
                    poll_data = poll_res.json()
                    poll_data_dict = poll_data.get('data') or {}
                    poll_code = poll_data.get('code')
                    if poll_code and (poll_code >= 500 or poll_code == -1):
                        raise Exception("비디오 생성에 실패했습니다 (KIE 서버 렌더링 오류). 다시 시도해 주세요.")

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
                        fail_msg = poll_data_dict.get('failMsg') or poll_data.get('failMsg') or poll_data_dict.get('reason') or poll_data.get('reason') or "KIE AI 비디오 생성 엔진 실패"
                        raise HTTPException(status_code=500, detail=f"비디오 생성 실패: {fail_msg}")
                    elif state == 'waiting':
                        print(f"[KIE Polling] Task {task_id} is waiting for completion...")

                if not video_url:
                    raise HTTPException(status_code=500, detail="API Error (500): Task failed or no video URL found.")

                results.append({**scene, "video_url": video_url})
    finally:
        # P-002: 업로드된 임시 이미지 일괄 삭제
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
                    messages=[{"role": "user", "content": [{"type": "text", "text": refine_prompt_text}]}]
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
                    dalle_res = await http_client.post(
                        "https://api.kie.ai/api/v1/jobs/createTask",
                        headers={
                            "Authorization": f"Bearer {decrypted_key}",
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        },
                        json={
                            "model": map_image_model(request.model),
                            "input": {
                                "prompt": full_prompt,
                                "n": 1,
                                "size": img_size,
                                "quality": "medium"
                            }
                        },
                        timeout=60.0
                    )
                    
                    if dalle_res.status_code != 200:
                        raise Exception(f"Failed to create image task ({dalle_res.status_code}): {dalle_res.text}")
                    
                    resp_data = dalle_res.json()
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
                            raise Exception("이미지 생성 서버 응답 지연(3분 초과)입니다.")
                            
                        poll_res = await http_client.get(
                            f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
                            headers={
                                "Authorization": f"Bearer {decrypted_key}",
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                            },
                            timeout=30.0
                        )
                        
                        if poll_res.status_code >= 500:
                            raise Exception("이미지 생성에 실패했습니다 (KIE 서버 렌더링 오류).")
                            
                        if poll_res.status_code != 200:
                            raise Exception(f"Failed to poll image status ({poll_res.status_code})")
                            
                        poll_data = poll_res.json()
                        poll_code = poll_data.get('code')
                        poll_dict = poll_data.get('data') or {}
                        
                        if poll_code and (poll_code >= 500 or poll_code == -1):
                            raise Exception("이미지 생성에 실패했습니다 (KIE 서버 렌더링 오류).")
                            
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
                            raise Exception("이미지 생성에 실패했습니다 (KIE 서버 작업 실패).")
                            
                    if new_image_url:
                        return {
                            "image_url": new_image_url,
                            "image_prompt": new_prompt
                        }
                    else:
                        raise Exception("이미지 URL을 찾을 수 없습니다.")
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
        "description": request.plan.title or "비디오 생성 대기 중",
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
        raise HTTPException(status_code=500, detail="서버 설정 오류: WEBHOOK_SECRET 환경 변수가 설정되지 않았습니다.")
        
    signature = request.headers.get("X-KIE-Signature")
    if not signature:
        raise HTTPException(status_code=401, detail="X-KIE-Signature 헤더가 누락되었습니다.")
        
    # A-003: "sha256=" 프리픽스 예외 처리
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
        raise HTTPException(status_code=401, detail="웹훅 서명이 유효하지 않습니다.")
        
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

    # A-002: 대기 중인 SSE 스트림에게 완료 알림 trigger
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

@app.post("/api/user-videos")
async def upload_user_video(file: UploadFile = File(...), jwt_user_id: str = Depends(get_jwt_user_id)):
    if file.content_type != "video/mp4" or not file.filename.endswith(".mp4"):
        raise HTTPException(status_code=422, detail="Only MP4 video files are allowed.")
        
    video_id = f"uv_{uuid.uuid4().hex[:8]}"
    file_path = f"outputs/{video_id}.mp4"
    sanitized_user = sanitize_uuid(jwt_user_id)
    
    # Save file locally for test runner and worker access
    file_content = await file.read()
    with open(file_path, "wb") as buffer:
        buffer.write(file_content)
        
    # Upload to Supabase Storage (assets bucket)
    try:
        supabase.storage.from_("assets").upload(
            path=f"{video_id}.mp4",
            file=file_content,
            file_options={"content-type": "video/mp4"}
        )
    except Exception as e:
        print(f"[Supabase Storage Upload Warning] {e}")
        
    duration_seconds = 5.0
    asset_data = {
        "id": video_id,
        "filename": file.filename,
        "duration_seconds": duration_seconds,
        "uploaded_at": datetime.utcnow().isoformat(),
        "user_id": sanitized_user
    }
    
    res = supabase.table("user_video_assets").insert(asset_data).execute()
    if not res.data:
        raise HTTPException(status_code=500, detail="Failed to insert video asset metadata in database")
        
    return {
        "id": video_id,
        "filename": file.filename,
        "duration_seconds": duration_seconds,
        "uploaded_at": asset_data["uploaded_at"]
    }



@app.post("/api/render-stream-test")
async def render_stream_test(
    request: RenderStreamRequest,
    raw_request: Request,
):
    import asyncio
    decrypted_key = COOKIE_ENCRYPTION_KEY
    jwt_user_id = request.user_id
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    N = len(request.scenes)

    async def generate_stream():
        yield f"data: {json.dumps({'message': 'KIE AI 비디오 생성 엔진(Grok-imagine) 초기화 중...'})}\n\n"

        async def process_scene_inner(scene, index):
            if await raw_request.is_disconnected():
                print(f"[DISCONNECT-TEST] Scene {index+1} aborted. Client disconnected.")
                raise asyncio.CancelledError()

            # RISK-B 방어 가드: 데이터베이스에서 해당 프로젝트의 해당 씬에 대해 가장 최신 성공(success) 비디오를 긁어오기 (P-001)
            if request.project_id:
                try:
                    response = supabase.table("tasks").select("*")\
                        .eq("project_id", request.project_id)\
                        .eq("status", "success")\
                        .eq("task_type", "video_generation")\
                        .like("description", f"%장면 {index+1}%")\
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

            # 신규 태스크 생성
            scene_task_id = f"task_{request.project_id or 'test'}_{index+1}_{int(time.time())}"
            if request.project_id:
                await create_task_in_db(request.project_id, scene_task_id, "video_generation", f"장면 {index+1} 비디오 생성 시도")

            is_success = False
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

                print(f"[MOCK SUCCESS] Scene {index+1} simulated success")
                scene_copy = dict(scene)
                scene_copy['video_url'] = "http://localhost:8000/outputs/mock_success.mp4"
                if request.project_id:
                    await update_task_in_db(scene_task_id, "success", result_url="http://localhost:8000/outputs/mock_success.mp4")
                is_success = True
                return {**scene_copy, "_index": index, "status": "success"}
            except asyncio.CancelledError as ce:
                print(f"[DISCONNECT-TEST] Scene {index+1} task {scene_task_id} cancelled due to disconnect.")
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

        tasks = [asyncio.create_task(process_scene_inner(scene, i)) for i, scene in enumerate(request.scenes)]
        yield f"data: {json.dumps({'message': f'총 {N}개의 장면 동영상 생성 동시 요청 완료'})}\n\n"

        results = [None] * N
        completed_count = 0
        for completed_task in asyncio.as_completed(tasks):
            if await raw_request.is_disconnected():
                print("[DISCONNECT-TEST] Client disconnected during scene tasks completion loop. Cancelling tasks.")
                for t in tasks:
                    if not t.done():
                        t.cancel()
                raise asyncio.CancelledError()

            try:
                res = await completed_task
                results[res["_index"]] = res
                completed_count += 1
                idx = res["_index"]
                yield f"data: {json.dumps({'message': f'장면 {idx + 1} 완료', 'scene_update': res})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

        if await raw_request.is_disconnected():
            print("[DISCONNECT-TEST] Client disconnected before final rendering output yield.")
            return

        ordered_scenes = [{k: v for k, v in scene.items() if k != "_index"} for scene in results if scene is not None]
        yield f"data: {json.dumps({'message': '최종 렌더링 완료!', 'output_url': '/outputs/mock_final.mp4'})}\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


@app.post("/api/render-stream")
async def render_stream(
    request: RenderStreamRequest,
    raw_request: Request,
    background_tasks: BackgroundTasks,
    jwt_user_id: str = Depends(get_jwt_user_id),
    decrypted_key: str = Depends(get_decrypted_key),
    verify: None = Depends(verify_csrf)
):
    import asyncio

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        raise HTTPException(status_code=500, detail="서버 설정 오류: .env 파일에 SUPABASE_URL과 SUPABASE_KEY를 설정해주세요.")

    N = len(request.scenes)

    async def generate_stream():
        try:
            # Beta test user limits check (Max 10 per month, Max 5 storage FIFO)
            await check_and_enforce_user_limits(jwt_user_id)
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return
            
        # 1. KIE AI Grok-imagine 호출 (병렬)
        yield f"data: {json.dumps({'message': 'KIE AI 비디오 생성 엔진(Grok-imagine) 초기화 중...'})}\n\n"

        async def process_scene_inner(scene, index):
            # RISK-B 방어 가드: 데이터베이스에서 해당 프로젝트의 해당 씬에 대해 가장 최신 성공(success) 비디오를 긁어오기 (P-001)
            if request.project_id:
                try:
                    response = supabase.table("tasks").select("*")\
                        .eq("project_id", request.project_id)\
                        .eq("status", "success")\
                        .eq("task_type", "video_generation")\
                        .like("description", f"%장면 {index+1}%")\
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

            # 1. 크레딧 방어: 기존 비디오가 유효하면 KIE API 스킵
            existing_video_url = scene.get('video_url')
            if existing_video_url and existing_video_url.startswith("http"):
                print(f"[SKIP] Scene {index+1} already has a valid video URL: {existing_video_url}")
                return {**scene, "_index": index}
            
            # 방어 로직: taskId가 있고 이미 완료되었거나 처리 중이면 중복 호출 방지
            existing_task_id = scene.get('taskId')
            if existing_task_id and scene.get('status') in ['success', 'waiting', 'ready', 'active']:
                print(f"[SKIP] Scene {index+1} already has a running/completed task: {existing_task_id}")
                if scene.get('status') == 'success' and existing_video_url:
                    return {**scene, "_index": index}

            # 신규 태스크 생성 및 등록 (pending)
            scene_task_id = f"task_{request.project_id or 'render'}_{index+1}_{int(time.time())}"
            if request.project_id:
                await create_task_in_db(request.project_id, scene_task_id, "video_generation", f"장면 {index+1} 비디오 생성 시도")

            is_success = False
            uploaded_files_scene = [] # 씬별 임시 이미지 에셋 추적 (P-002)
            try:
                # 2. 스틸컷 전용 모드 시 비디오 렌더링 스킵 (프론트엔드 제어)
                is_hybrid_skip = scene.get('use_image_only', False)
                if is_hybrid_skip:
                    print(f"[HYBRID SKIP] Scene {index+1} text-heavy scene skipped for video generation (Hybrid Mode)")
                    scene_copy = dict(scene)
                    scene_copy['video_url'] = None
                    if request.project_id:
                        await update_task_in_db(scene_task_id, "success", result_url=None)
                    is_success = True
                    return {**scene_copy, "_index": index}

                # 테스트용 Mock 503 에러 유도
                if scene.get("prompt") == "TRIGGER_MOCK_ERROR":
                    print(f"[MOCK ERROR] Simulating 503 error for scene {index+1}")
                    raise Exception("Mock Video Generation Failure (503 Service Unavailable)")

                async with httpx.AsyncClient() as client:
                    image_url = scene.get('image_url')
                    if not image_url:
                        return {**scene, "_index": index}

                    # 1. Download and Upload to Supabase Storage (A-005, S-006)
                    public_url, file_name = await upload_image_to_supabase(image_url, id(scene))
                    uploaded_files_scene.append(file_name)

                    # 2. Create Task & Get Callback URL (A-001)
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

                    # engine 분기 적용
                    is_veo = (request.engine in ["veo", "veo_lite", "veo_fast"])
                    
                    if is_veo:
                        url = "https://api.kie.ai/api/v1/veo/generate"
                        model_name = "veo3_fast" if request.engine == "veo_fast" else "veo3_lite"
                        gen_type = "REFERENCE_2_VIDEO" if request.engine == "veo_fast" else "FIRST_AND_LAST_FRAMES_2_VIDEO"
                        
                        payload = {
                            "prompt": scene.get('image_prompt', 'Animate this image'),
                            "imageUrls": [public_url],
                            "model": model_name,
                            "aspect_ratio": request.aspect_ratio,
                            "generationType": gen_type,
                            "enableFallback": False,
                            "enableTranslation": True
                        }
                        if callback_url:
                            payload["webhook_url"] = callback_url
                    else:
                        url = "https://api.kie.ai/api/v1/jobs/createTask"
                        model_name = "grok-imagine/image-to-video"
                        payload = {
                            "model": model_name,
                            "input": {
                                "image_urls": [public_url],
                                "prompt": scene.get('image_prompt', 'Animate this image'),
                                "duration": str(scene_duration),
                                "resolution": "720p",
                                "aspect_ratio": request.aspect_ratio,
                                "mode": "normal"
                            }
                        }
                        if callback_url:
                            payload["input"]["webhook_url"] = callback_url

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

                    # 3. KIE AI 비동기 완료 대기 브릿지 (A-002)
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
                            
                            # 5초 간격으로 이벤트 wait
                            try:
                                await asyncio.wait_for(event.wait(), timeout=5.0)
                                event.clear()
                            except asyncio.TimeoutError:
                                pass
                                
                            poll_attempts += 1
                            elapsed = time.time() - start_poll_time
                            if elapsed >= 1800:
                                raise Exception("서버 응답 지연(절대 시간 30분 초과)입니다.")
                            elif elapsed >= polling_timeout and last_status not in ['WAITING', 'IN_PROGRESS', 'PENDING', 'PROCESSING', 'QUEUE']:
                                raise Exception("서버 응답 지연(시간 초과)입니다. 실패한 씬부터 이어서 렌더링 버튼을 눌러주세요.")
                            
                            # A-002 DB 상태 먼저 체크
                            res_task = supabase.table("tasks").select("status, result_url, error").eq("task_id", task_id).execute()
                            if res_task.data:
                                task_data = res_task.data[0]
                                state = task_data.get("status", "waiting").lower()
                                last_status = state.upper()
                                
                                if state == 'success' or state == 'completed':
                                    vid_url = task_data.get("result_url")
                                    break
                                elif state == 'fail' or state == 'failed':
                                    raise Exception(f"비디오 생성 실패: {task_data.get('error') or 'KIE AI 비디오 생성 엔진 실패'}")
                            
                            # 폴백으로 recordInfo API 노킹
                            poll_res = await client.get(f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}", headers={"Authorization": f"Bearer {decrypted_key}"}, timeout=30.0)
                            
                            if poll_res.status_code >= 500:
                                raise Exception("비디오 생성에 실패했습니다 (KIE 서버 렌더링 오류). 다시 시도해 주세요.")
                                
                            if poll_res.status_code == 200:
                                poll_data = poll_res.json()
                                poll_code = poll_data.get('code')
                                poll_dict = poll_data.get('data') or {}
                                
                                if poll_code and (poll_code >= 500 or poll_code == -1):
                                    raise Exception("비디오 생성에 실패했습니다 (KIE 서버 렌더링 오류). 다시 시도해 주세요.")
                                    
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
                                    fail_msg = poll_dict.get('failMsg') or poll_data.get('failMsg') or poll_dict.get('reason') or poll_data.get('reason') or "KIE AI 비디오 생성 엔진 실패"
                                    print(f"[KIE AI VIDEO ERROR] Task {task_id} failed. Status: {status}, failMsg: {fail_msg}")
                                    raise Exception(f"비디오 생성 실패: {fail_msg}")
                                elif status == 'waiting':
                                    print(f"[KIE Polling] Task {task_id} is waiting for completion...")
                            else:
                                print(f"[KIE] Scene {index+1} Polling Error Status: {poll_res.status_code}, Body: {poll_res.text}")
                                if poll_attempts > 180:
                                    break
                    finally:
                        TASK_EVENTS.pop(task_id, None)

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
                # P-002: KIE AI 비디오 생성 요청 완료 후(성공/실패 상관없이) 임시 이미지 삭제
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
        yield f"data: {json.dumps({'message': f'총 {N}개의 장면 동영상 생성 동시 요청 완료'})}\n\n"

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
                msg = res.get("_fallback_msg") or f"장면 {idx + 1} 동영상 완료 ({completed_count}/{N}), 나머지 대기 중..."
                yield f"data: {json.dumps({'message': msg, 'scene_update': res})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                return

        ordered_scenes = [{k: v for k, v in scene.items() if k != "_index"} for scene in results]

        yield f"data: {json.dumps({'message': f'{N}개의 동영상 음성과 자막을 합쳐 FFmpeg 최종 렌더링 중...'})}\n\n"

        try:
            task_id = f"task_{int(time.time())}"
            if request.project_id:
                await create_task_in_db(request.project_id, task_id, "final_render", "최종 동영상 MP4 렌더링 시도")
            
            gen = ffmpeg_worker.render_video(
                task_id=task_id,
                scenes=ordered_scenes,
                voice_type=request.voice_type,
                aspect_ratio=request.aspect_ratio,
                subtitle_position=request.subtitle_position,
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
                        yield f"data: {json.dumps({'message': '최종 렌더링 완료!', 'output_url': item['output_url']})}\n\n"
            finally:
                await gen.aclose()
        except Exception as e:
            if request.project_id:
                await update_task_in_db(task_id, "failed", error=str(e))
            yield f"data: {json.dumps({'error': f'FFmpeg Error: {str(e)}'})}\n\n"
            
    return StreamingResponse(generate_stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

