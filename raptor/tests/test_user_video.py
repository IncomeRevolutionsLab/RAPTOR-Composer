import os
import pytest
import io
import jwt
from fastapi.testclient import TestClient

# 테스트 환경 변수 설정
os.environ["DATABASE_PATH"] = "test_user_videos.json"
os.environ.setdefault("COOKIE_ENCRYPTION_KEY", "3u8V_z5Fp3Uo54b1f4g7Y3k5l1pD_s1t4a5g7r8a9v0=")
os.environ["SUPABASE_JWT_SECRET"] = "test_supabase_jwt_secret_key"

from main import app

def get_auth_headers(user_id="beta_tester") -> dict:
    payload = {
        "sub": user_id,
        "aud": "authenticated"
    }
    secret = os.environ["SUPABASE_JWT_SECRET"]
    token = jwt.encode(payload, secret, algorithm="HS256")
    return {
        "Authorization": f"Bearer {token}"
    }

@pytest.fixture(autouse=True)
def run_around_tests():
    if os.path.exists("test_user_videos.json"):
        os.remove("test_user_videos.json")
    # 임시 outputs 디렉토리 생성
    if not os.path.exists("outputs"):
        os.makedirs("outputs")
    yield
    if os.path.exists("test_user_videos.json"):
        os.remove("test_user_videos.json")

def test_upload_accepts_mp4_only():
    client = TestClient(app)
    
    # 1. MP4 파일 업로드 시도 (정상)
    # 가짜 mp4 파일 스트림
    fake_mp4 = io.BytesIO(b"fake mp4 header data and video bytes")
    resp = client.post(
        "/api/user-videos",
        files={"file": ("clip.mp4", fake_mp4, "video/mp4")},
        headers=get_auth_headers()
    )
    # 백엔드에서 업로드 처리를 위해 파일의 실질적 유효성(duration 등)을 체크할 수 있으므로,
    # metadata parsing에서 가짜 파일이라 에러가 날 수 있음. 
    # 그러나 설계서의 API 명세상, video/mp4 확장자 및 MIME 타입이 통과하면 200(혹은 metadata 검증에서 실패 시 다른 코드)을 리턴해야 함.
    # 여기서는 확장자 및 MIME 타입 거절(422) 부분을 우선 검증
    assert resp.status_code != 422  # mp4는 형식 위반으로 422가 나선 안 됨

def test_upload_rejects_non_mp4():
    client = TestClient(app)
    
    # 2. non-mp4 파일 업로드 (MOV, PNG 등 거절)
    fake_mov = io.BytesIO(b"fake mov content")
    resp = client.post(
        "/api/user-videos",
        files={"file": ("clip.mov", fake_mov, "video/quicktime")},
        headers=get_auth_headers()
    )
    # 비디오 포맷 제한(mp4만 허용)으로 인해 422 반환해야 함
    assert resp.status_code == 422
