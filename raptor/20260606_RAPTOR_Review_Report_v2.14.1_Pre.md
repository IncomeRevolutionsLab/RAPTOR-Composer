# RAPTOR 백엔드 인프라 이관 사전 아키텍처 리뷰 (Pre-Review)

**문서 ID:** RAPTOR-INFRA-MIG-2026-001  
**작성일:** 2026-06-06  
**버전:** v1.0  
**상태:** Pre-Review (이관 전)  
**이관 방향:** Koyeb → Render.com  
**관련 리스크:** RISK-010 (Koyeb Billing Lock)

---

## 1. 이관 배경 및 트리거

### 1.1 현황 요약

| 구분 | 현재 상태 |
|------|----------|
| 백엔드 플랫폼 | Koyeb (`raptor-backend.koyeb.app`) |
| 프론트엔드 플랫폼 | Vercel (`raptor-composer.vercel.app`) |
| 데이터베이스 | Supabase 서울 리전 (Pooler 연결) |
| 백엔드 상태 | **서비스 중단 (Suspended)** |
| 중단 원인 | `David Song` Koyeb 계정 결제 프로필 누락 → 플랫폼 Billing Lock 발동 |

### 1.2 RISK-010 개요

Koyeb의 결제 잠금(Billing Lock) 정책은 결제 수단이 등록되지 않은 계정의 서비스를 플랫폼 수준에서 일시 정지(Suspend)한다. 현재 RAPTOR 백엔드는 이 사유로 인해 `https://raptor-backend.koyeb.app` 엔드포인트가 완전히 불응 상태이며, 프론트엔드의 모든 API 통신이 차단되어 있다. Koyeb 계정 결제 복구까지의 소요 시간이 불확정적이므로, 동일 기능을 신속히 대체 가능한 Render.com으로 긴급 이관을 수행한다.

---

## 2. 현행 아키텍처 (As-Is)

```
[사용자 브라우저]
       │
       ▼
[Vercel 프론트엔드]
 raptor-composer.vercel.app
       │
       │ vercel.json rewrites
       │  /api/*       → https://raptor-backend.koyeb.app/api/*
       │  /outputs/*   → https://raptor-backend.koyeb.app/outputs/*
       ▼
[Koyeb 백엔드]  ◄──── ❌ SUSPENDED (Billing Lock)
 raptor-backend.koyeb.app
 FastAPI / uvicorn --workers 1
       │
       ▼
[Supabase 서울 리전]
 DB (Pooler) + Storage (assets 버킷, Private)
```

### 2.1 백엔드 런타임 특성

| 항목 | 값 |
|------|----|
| 프레임워크 | FastAPI (Python) |
| ASGI 서버 | uvicorn |
| 워커 수 | `--workers 1` (asyncio.Lock 기반 TOCTOU 방지) |
| CORS 허용 오리진 | `https://raptor-composer.vercel.app` (코드 레벨 하드코딩 + env 이중 방어, RISK-005 해결) |
| 프론트 연결 방식 | `vercel.json` 프록시 리라이트 |

---

## 3. 목표 아키텍처 (To-Be)

```
[사용자 브라우저]
       │
       ▼
[Vercel 프론트엔드]
 raptor-composer.vercel.app
       │
       │ vercel.json rewrites (수정 필요)
       │  /api/*       → https://[RENDER_SERVICE_URL]/api/*
       │  /outputs/*   → https://[RENDER_SERVICE_URL]/outputs/*
       ▼
[Render.com 백엔드]  ◄──── ✅ 신규 Web Service
 ***.onrender.com
 FastAPI / uvicorn --host 0.0.0.0 --port $PORT --workers 1
       │
       ▼
[Supabase 서울 리전]  (변경 없음)
 DB (Pooler) + Storage (assets 버킷, Private)
```

> **⚠️ 주의:** Render.com은 서비스 생성 후 실제 URL이 확정되므로, `[RENDER_SERVICE_URL]`은 배포 완료 후 실제 주소로 교체해야 한다.

---

## 4. 변경 대상 컴포넌트 분석

### 4.1 변경 필요 항목

| 컴포넌트 | 파일 | 변경 내용 | 우선순위 |
|---------|------|-----------|---------|
| Vercel 프록시 설정 | `vercel.json` | `destination` URL을 Koyeb → Render 주소로 교체 | **P0 (필수)** |
| Vercel 환경변수 | Vercel 대시보드 | `NEXT_PUBLIC_BACKEND_URL` 갱신 | **P0 (필수)** |
| Render 서비스 | Render 대시보드 | Web Service 신규 생성 및 환경변수 7종 주입 | **P0 (필수)** |

### 4.2 변경 불필요 항목 (근거 포함)

| 컴포넌트 | 변경 불필요 근거 |
|---------|----------------|
| `main.py` (백엔드 소스) | CORS 오리진은 이미 실서버 도메인 기준으로 설정 완료 (RISK-005 Resolved) |
| Supabase DB / Storage | 연결 정보는 환경변수로 주입되며, 플랫폼 변경과 무관 |
| 프론트엔드 소스 코드 | `NEXT_PUBLIC_BACKEND_URL` env 통해 동적 참조 중 (RISK-007 Resolved) |

---

## 5. Render.com 플랫폼 기술 검토

### 5.1 포트 바인딩 차이점 (Critical)

| 항목 | Koyeb | Render.com |
|------|-------|------------|
| 포트 할당 방식 | 플랫폼 기본 포트 자동 노출 | `$PORT` 환경변수로 동적 할당 (기본값: 10000) |
| 바인딩 요구사항 | 별도 지정 없이 동작 가능 | **반드시 `--port $PORT`로 수신해야 함** |

**Start Command (implementation_plan.md 기준):**
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1
```
`$PORT` 동적 바인딩이 올바르게 명시되어 있다. ✅

### 5.2 단일 워커 강제 유지 (Critical)

`main.py`의 `db_lock = asyncio.Lock()`은 동일 프로세스 내에서만 유효한 인메모리 뮤텍스다. `--workers 2` 이상으로 멀티 프로세스를 기동할 경우, 각 워커가 별도 Lock 인스턴스를 보유하여 **TOCTOU 경쟁 조건**이 발생한다. Render 이관 후에도 `--workers 1` 옵션은 반드시 유지해야 한다.

### 5.3 무료 플랜 콜드 스타트 위험

| 플랜 | 인스턴스 Spin-down | 콜드 스타트 지연 | 비용 |
|------|-------------------|----------------|------|
| Free | 비활성 약 15분 후 자동 중지 | 약 50초 (첫 요청) | $0 |
| **Starter** | **없음 (Always-on)** | **없음** | **$7/mo** |

**→ 프로덕션 환경이므로 Starter 플랜 이상 강력 권고.**

### 5.4 필수 환경변수 7종

| # | 환경변수 키 | 설명 | 보안 등급 |
|---|-------------|------|---------|
| 1 | `SUPABASE_URL` | Supabase 프로젝트 URL | 일반 |
| 2 | `SUPABASE_KEY` | Service Role Key | **Secret** |
| 3 | `SUPABASE_DB_PASSWORD` | DB 비밀번호 | **Secret** |
| 4 | `DATABASE_URL` | Pooler 연결 문자열 | **Secret** |
| 5 | `JWT_SECRET` | JWT 서명 검증 키 | **Secret** |
| 6 | `ALLOWED_ORIGINS` | `https://raptor-composer.vercel.app` | 일반 |
| 7 | `OPENAI_API_KEY` | OpenAI API 키 | **Secret** |

> Secret 표시 항목은 Render 대시보드에서 "Secret" 타입으로 입력하여 빌드/런타임 로그 노출을 방지할 것.

---

## 6. 연결 전환 경로 분석 (vercel.json)

### 6.1 현행 설정

```json
{
  "version": 2,
  "rewrites": [
    { "source": "/api/:path*",     "destination": "https://raptor-backend.koyeb.app/api/:path*" },
    { "source": "/outputs/:path*", "destination": "https://raptor-backend.koyeb.app/outputs/:path*" }
  ]
}
```

### 6.2 변경 후 설정

```json
{
  "version": 2,
  "rewrites": [
    { "source": "/api/:path*",     "destination": "https://[RENDER_SERVICE_URL]/api/:path*" },
    { "source": "/outputs/:path*", "destination": "https://[RENDER_SERVICE_URL]/outputs/:path*" }
  ]
}
```

---

## 7. 위험 요소 사전 분석

| ID | 리스크 | 발생 가능성 | 영향도 | 대응 방안 |
|----|--------|------------|--------|----------|
| R-1 | Render URL 확정 전 `vercel.json` 재수정 필요 | 높음 | 보통 | 배포 완료 후 URL 확인 후 적용 |
| R-2 | 환경변수 오입력으로 DB 연결 실패 | 보통 | 높음 | `/api/auth/csrf-token` 헬스체크로 즉시 검증 |
| R-3 | `$PORT` 미적용으로 바인딩 실패 (502) | 낮음 | 높음 | Start Command 명시적 확인 |
| R-4 | CORS 차단 (`ALLOWED_ORIGINS` 미설정) | 낮음 | 높음 | 환경변수 입력값 검수 |
| R-5 | 무료 플랜 콜드 스타트 UX 저하 | 높음 (무료 선택 시) | 보통 | Starter 플랜 이상 선택으로 원천 차단 |
| R-6 | Vercel 프록시 캐시로 URL 전환 지연 | 보통 | 낮음 | Vercel 강제 Redeploy 트리거 |

### 롤백 계획

Koyeb Billing Lock이 해소될 경우 원복 경로는 단순하다: `vercel.json` destination을 Koyeb 주소로 재변경 후 Vercel 재배포. 단, Koyeb 계정 복구 시점이 불확정적이므로 **Render를 장기 주력 인프라로 운영**하는 것을 기본 시나리오로 채택한다.

---

## 8. 이관 작업 체크리스트 (Pre-Verified)

### Phase 1: Render 서비스 생성
- [ ] Render.com New Web Service 생성 및 레포지터리 연결
- [ ] **Build Command:** `pip install -r requirements.txt`
- [ ] **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1`
- [ ] 플랜: Starter ($7/mo) 이상 선택
- [ ] 환경변수 7종 전체 주입

### Phase 2: 배포 후 검증
- [ ] `GET https://[RENDER_URL]/api/auth/csrf-token` → `200 OK` 확인
- [ ] `Origin: https://raptor-composer.vercel.app` 헤더 포함 요청 → `Access-Control-Allow-Origin` 응답 확인
- [ ] 실제 Render 서비스 도메인 확인 및 기록

### Phase 3: Vercel 연결 전환
- [ ] `vercel.json` destination 2곳 Render URL로 교체
- [ ] Vercel 대시보드 `NEXT_PUBLIC_BACKEND_URL` 갱신
- [ ] Vercel 강제 Redeploy 실행

### Phase 4: E2E 최종 검증
- [ ] 프로덕션 URL에서 회원가입 흐름 정상 동작 확인
- [ ] 로그인 후 프로젝트 목록 조회 정상 동작 확인
- [ ] 브라우저 Network 탭 API 오류 없음 확인

---

## 9. 결론 및 권고사항

**이관 즉시 실행을 권고한다.** Koyeb Billing Lock은 코드 수정으로 해소 불가한 외부 플랫폼 사유이며, Render.com은 RAPTOR 백엔드의 `$PORT` 동적 바인딩 및 단일 워커 요구사항을 완전히 충족한다. 백엔드 소스 코드 변경 없이 Render Web Service 생성 + 환경변수 주입 + `vercel.json` URL 교체만으로 이관이 완료된다.

**플랜 선택:**

| 선택 | 결과 |
|------|------|
| Free | 15분 비활성 → 50초 콜드 스타트 → 사용자 이탈 위험 |
| **Starter ($7/mo)** | **Always-on → 즉시 응답 → 프로덕션 품질 보장** |

**이관 완료 후 추가 검토 사항:**
1. Render 헬스체크 Path(`/api/auth/csrf-token`) 대시보드 등록으로 자동 모니터링 활성화
2. 트래픽 증가 대비 `asyncio.Lock` → Redis 분산 락 전환 중장기 로드맵 수립
3. Koyeb 서비스 공식 폐기 및 단일 플랫폼 확정

---

*본 문서는 Koyeb → Render.com 이관 수행 전 아키텍처 검토 목적으로 작성되었습니다. 이관 완료 후 Post-Review 문서가 별도 발행됩니다.*
