# 실행 계획서 v2.15.0 — JWT ECC(P-256) 대응 수술
> **작성 일시**: 2026-06-12  
> **버전**: v2.15.0  
> **상태**: Step 1 완료 — Step 2 외부 리뷰 진행 중  
> **타겟 파일**: `main.py`, `requirements.txt`

---

## 배경 및 문제 정의

Supabase 프로젝트가 JWT 서명 알고리즘을 **HS256 → ECC(P-256)** 으로 업그레이드함.  
기존 백엔드의 `get_jwt_user_id()` 함수가 PyJWT를 이용해 `HS256`으로 하드코딩된 수동 검증을 수행하고 있어, ECC 서명된 토큰을 `InvalidTokenError`로 거부 → **모든 인증 엔드포인트 401 에러 붕괴**.

---

## 수술 대상 코드 (현재 상태)

### [타겟 1] `main.py` L26
```python
import jwt  # PyJWT — 철거 대상
```

### [타겟 2] `main.py` L45-47 — SUPABASE_JWT_SECRET Fail-Fast
```python
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
if not SUPABASE_JWT_SECRET:
    raise RuntimeError("SUPABASE_JWT_SECRET must be set in .env")
```

### [타겟 3] `main.py` L150-166 — get_jwt_user_id() 핵심 함수
```python
def get_jwt_user_id(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증 헤더가 누락되었거나 형식이 올바르지 않습니다.")
    token = authorization.split(" ", 1)[1]
    supabase_jwt_secret = os.getenv("SUPABASE_JWT_SECRET")
    if not supabase_jwt_secret:
        raise HTTPException(status_code=500, detail="서버 설정 오류: SUPABASE_JWT_SECRET 환경 변수가 설정되지 않았습니다.")
    try:
        payload = jwt.decode(token, supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
        # ❌ HS256 하드코딩 — ECC(P-256) 서명 토큰 검증 불가 → InvalidTokenError
        sub = payload.get('sub')
        if not sub:
            raise HTTPException(status_code=401, detail="JWT 토큰 내 sub 클레임이 누락되었습니다.")
        return sub
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="JWT 토큰 유효 기간이 만료되었습니다.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 JWT 토큰 서명입니다.")
```

### [타겟 4] `requirements.txt` L24
```
pyjwt>=2.7.0
```

---

## 아키텍처 변경 설계

```
[현재 — 붕괴 중]
Bearer Token
  → jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
  → ❌ ECC(P-256) 서명 토큰: InvalidTokenError → 401

[신규 — SDK 위임]
Bearer Token
  → supabase.auth.get_user(token)
  → ✅ SDK 내부에서 JWKS 자동 조회 및 ECC/HS256 모두 처리
  → user.id 반환
```

---

## 제안 수정안

### 수정 1: `main.py` — `import jwt` 제거 (L26)
```diff
- import jwt
```

### 수정 2: `main.py` — SUPABASE_JWT_SECRET Fail-Fast 제거 (L45-47)
```diff
- SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
- if not SUPABASE_JWT_SECRET:
-     raise RuntimeError("SUPABASE_JWT_SECRET must be set in .env")
```

### 수정 3: `main.py` — `get_jwt_user_id()` 함수 전면 교체 (L150-166)
```diff
- def get_jwt_user_id(authorization: Optional[str] = Header(None)) -> str:
-     ...PyJWT 기반 수동 검증 전체...

+ def get_jwt_user_id(authorization: Optional[str] = Header(None)) -> str:
+     if not authorization or not authorization.startswith("Bearer "):
+         raise HTTPException(status_code=401, detail="인증 헤더가 누락되었거나 형식이 올바르지 않습니다.")
+     token = authorization.split(" ", 1)[1]
+     try:
+         # [ECC 대응] Supabase SDK get_user()는 JWKS 자동 처리 — HS256/P-256 모두 지원
+         response = supabase.auth.get_user(token)
+         user = response.user
+         if not user or not user.id:
+             raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
+         return user.id
+     except HTTPException:
+         raise
+     except Exception as e:
+         raise HTTPException(status_code=401, detail=f"토큰 검증 실패: {str(e)}")
```

### 수정 4: `requirements.txt` — `pyjwt` 제거 (L24)
```diff
- pyjwt>=2.7.0
```

---

## 리스크 분석

| 리스크 | 내용 | 대응 |
|--------|------|------|
| service_role 클라이언트로 get_user() 호출 | L189의 supabase 변수는 SERVICE_ROLE_KEY로 생성됨. get_user()는 user context가 아닌 admin context에서 호출 | Supabase 공식 문서상 service_role 클라이언트도 get_user(token) 정상 지원 확인 필요 |
| 네트워크 레이턴시 | jwt.decode(로컬) → supabase.auth.get_user(네트워크 API 호출)로 변경 | 인증 요청당 ~50-200ms 추가. 허용 가능한 트레이드오프 |
| 동기 함수 블로킹 | get_jwt_user_id()는 동기 def 함수. supabase.auth.get_user()도 동기 호출이나 FastAPI의 async 이벤트 루프 블로킹 가능성 | asyncio.to_thread() 래핑 또는 async def로 변환 검토 필요 |

---

## 검증 계획

1. 수정 후 로컬 서버 기동 확인 (`SUPABASE_JWT_SECRET` 없이 정상 시작 여부)
2. ECC 서명 토큰으로 `/api/dashboard/projects` 호출 → 200 응답 확인
3. 만료된 토큰으로 호출 → 401 응답 확인
4. 헤더 없이 호출 → 401 응답 확인
