# 📋 RAPTOR v2.14.1 Vercel 프록시 정합성 핫픽스 사후 리뷰 보고서

- **리뷰 버전**: v2.14.1-hotfix
- **리뷰 일시**: 2026-06-10
- **리뷰어**: Claude Code (claude --print)
- **패치 목적**: 로그인/회원가입 시 `<!DOCTYPE html> is not valid JSON` 에러 해결

---

## ✅ 수정 검증 (Hotfix 적용 확인)

| 항목 | 파일 | 상태 |
|------|------|------|
| `BACKEND_URL` 상수 정의 | `RaptorWorkflow.tsx` L9 | ✅ 확인됨 |
| video `src` localhost 제거 | `RaptorWorkflow.tsx` L1346 | ✅ `${BACKEND_URL}/outputs/...` |
| 비디오 업로드 fetch (1번째) | `RaptorWorkflow.tsx` L1424 | ✅ `${BACKEND_URL}/api/user-videos` |
| 업로드 후 video_url 설정 (1번째) | `RaptorWorkflow.tsx` L1431 | ✅ `${BACKEND_URL}/outputs/...` |
| 비디오 업로드 fetch (2번째) | `RaptorWorkflow.tsx` L1491 | ✅ `${BACKEND_URL}/api/user-videos` |
| 업로드 후 video_url 설정 (2번째) | `RaptorWorkflow.tsx` L1498 | ✅ `${BACKEND_URL}/outputs/...` |
| `NEXT_PUBLIC_BACKEND_URL` 수정 | `.env.production.local` | ✅ `https://raptor-composer.onrender.com` |
| Vercel 대시보드 환경변수 업데이트 | Vercel CLI | ✅ rm 후 재등록 완료 |
| `vercel.json` Render URL rewrites | `vercel.json` | ✅ 원래 정상 (수정 없음) |
| 강제 재배포 | Vercel Production | ✅ READY (dpl_BFp2NEBvpnrYJB2wRwa77W8ufWXN) |

---

## 1. 핵심 버그 수정 평가

### 원인: `NEXT_PUBLIC_BACKEND_URL = ""` (빈 문자열 Truthy 버그)

**PASS** — 근본 원인을 정확히 진단하고 수정함.

```
빈 문자열("")은 JavaScript에서 truthy이므로:
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
  → BACKEND_URL = "" (localhost 폴백 미작동)
  → fetch("" + "/api/auth/signin") = fetch("/api/auth/signin")
  → Vercel 자신에게 요청 → Next.js 404 HTML 반환
  → JSON.parse() 실패 → "<!DOCTYPE html> is not valid JSON"
```

수정 후: `NEXT_PUBLIC_BACKEND_URL = "https://raptor-composer.onrender.com"`으로 명시 → 정상 동작.

---

## 2. 하드코딩 URL 제거 완결성 평가

**PASS (단, 1건 잔존)** — `RaptorWorkflow.tsx` 5곳 모두 제거됨.

### ⚠️ 잔존 이슈: `AuthDashboard.tsx` L15

```typescript
// 현재 (버그)
const baseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// 문제: NEXT_PUBLIC_API_URL은 Vercel 환경변수에 존재하지 않음
// 결과: DB에 상대 경로(/outputs/abc.mp4)로 저장된 영상 → localhost fallback → 재생 실패
```

**수정 필요:**
```typescript
// 수정 후
const baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";
```

---

## 3. CORS/credentials 아키텍처 위험도 평가

### 🚨 Critical: CSRF 쿠키 Cross-Origin 전송 불가 → P0

**FAIL** — 현재 아키텍처에서 핵심 API 403 에러 발생 가능성 높음.

**원인 분석:**
```
Frontend: raptor-composer.vercel.app   (Origin A)
Backend:  raptor-composer.onrender.com (Origin B) → cross-origin

main.py 쿠키 설정:
  response.set_cookie("raptor_csrf", ..., samesite="lax", secure=IS_PROD)

SameSite=Lax + cross-origin 규칙:
  - CSRF 토큰 GET → Render가 Set-Cookie 전송 → 브라우저 저장
  - 이후 POST 요청 시 → 브라우저가 SameSite=Lax 정책으로 쿠키 미전송
  - verify_csrf() → raptor_csrf = None → 403 에러
  
영향 엔드포인트 (전체 핵심 라우트):
  /api/generate-plan, /api/generate-images, /api/render-stream,
  /api/create-project, /api/auth/signin, /api/auth/signup 등
```

**수정 방법:**

`main.py` 내 `set_cookie` 호출 3곳 모두 수정:

```python
# Before (L695, L711, L731 — 3곳)
samesite="lax"

# After
samesite="none"   # cross-origin 쿠키 허용 (소문자)
# secure=IS_PROD 반드시 유지 (samesite=none은 Secure 필수)
```

> **참고**: Vercel Hobby Plan 함수 timeout 10초 제한으로 인해 Vercel 프록시 경유 방식은
> 30분 이상 소요되는 렌더링 작업에 부적합. 직접 Render 호출 방식이 올바른 선택이나,
> 이로 인해 cross-origin CORS 설정이 필수적으로 요구됨.

---

## 4. 보안 관점 평가

**PASS (조건부)**

- `NEXT_PUBLIC_` 변수는 클라이언트에 노출되나, Render URL 자체는 공개 정보이므로 보안 위험 없음.
- `vercel.json`의 `/api/*` 리라이트 규칙: 현재 직접 호출 방식 사용으로 **Dead Code 상태**.
  - Vercel 자체 API Routes가 없으므로 충돌 위험 없음.
  - 단, 혼란 방지를 위해 의도를 README 또는 주석으로 명시 권장.

---

## 5. 잠재적 회귀(Regression) 위험 요소

| 위험 | 설명 | 위험도 |
|------|------|--------|
| CSRF 쿠키 미전송 | SameSite=Lax + cross-origin → P0 즉시 수정 필요 | 🔴 Critical |
| `NEXT_PUBLIC_API_URL` 미설정 | AuthDashboard.tsx L15 → 영상 재생 폴백 실패 | 🟠 High |
| `vercel.json` Dead Code | 향후 개발자 혼란 유발 가능 | 🟡 Low |
| `.env.production.local` 빈 Supabase 값 | 로컬 프로덕션 빌드 시 Supabase 미작동 | 🟡 Low |

---

## 6. 최종 결론 및 추가 권고사항

### 결론

이번 핫픽스는 **`<!DOCTYPE html> is not valid JSON` 에러의 직접 원인(빈 문자열 환경변수 버그 + localhost 하드코딩)**을 정확히 수정했으나, 수정 방향(직접 Render 호출)으로 인해 **CSRF 쿠키 SameSite 정책 충돌이라는 새로운 P0 이슈**가 잠재되어 있음.

### 즉시 권고 사항 (우선순위순)

| 순위 | 항목 | 파일 | 변경 내용 |
|------|------|------|----------|
| **P0** | CSRF 쿠키 SameSite 수정 | `main.py` L695, L711, L731 | `samesite="lax"` → `samesite="none"` |
| **P1** | 환경변수명 통일 | `AuthDashboard.tsx` L15 | `NEXT_PUBLIC_API_URL` → `NEXT_PUBLIC_BACKEND_URL` |
| **P2** | vercel.json 의도 명확화 | `vercel.json` | 주석 또는 README 추가 |
| **P3** | 로컬 빌드 환경 복원 | `.env.production.local` | Supabase 값 복원 |
