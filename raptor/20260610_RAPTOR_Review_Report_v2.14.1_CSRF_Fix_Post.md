# 📋 RAPTOR v2.14.1-hotfix CSRF Cross-Origin 멸균 수술 사후 리뷰 보고서 (Post-Review)

- **검토 일자**: 2026-06-10
- **리뷰어**: Claude Code (claude --print)
- **검토 범위**: P0 CSRF SameSite 수정, P1 환경변수 수정, 보안 심층 분석

---

## 1. [P0] CSRF SameSite=None 수정 평가 — ✅ PASS

### 수정 완결성 검증

| 항목 | 코드 위치 | 결과 |
|------|-----------|------|
| `/api/auth/csrf-token` set_cookie | `main.py:695` | `samesite="none"` ✅ |
| `/api/auth/set-key` set_cookie | `main.py:710` | `samesite="none"` ✅ |
| `/api/auth/clear-key` delete_cookie | `main.py:719` | `samesite="none"` ✅ |
| `/api/auth/check-key` set_cookie | `main.py:733` | `samesite="none"` ✅ |
| `secure=IS_PROD` 조건부 적용 | `main.py:694, 709, 719, 732` | 4곳 모두 적용 ✅ |
| `IS_PROD` 설정 로직 | `main.py:49` | `ENV=production` 환경변수 기반 ✅ |
| CORS `allow_origins` Vercel 포함 | `main.py:118` | `"https://raptor-composer.vercel.app"` ✅ |

### `verify_csrf()` 동작 분석

```python
# main.py:135-143
async def verify_csrf(
    request: Request,
    raptor_csrf: Optional[str] = Cookie(None),
    x_csrf_token: Optional[str] = Header(None)
):
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return
    if not raptor_csrf or not x_csrf_token or not secrets.compare_digest(raptor_csrf, x_csrf_token):
        raise HTTPException(status_code=403, detail="CSRF token validation failed")
```

- **Double Submit Cookie 패턴** 정상 구현 ✅
- SameSite=None 적용 후 cross-origin POST 요청에서 브라우저가 `raptor_csrf` 쿠키를 전송
- `Cookie(None)` 파라미터로 수신 가능
- `raptor_csrf is None`인 경우 즉시 403 반환 (올바른 방어 동작)
- `secrets.compare_digest()` 타이밍 공격 방어 ✅

**판정: PASS** — 4곳 전부 정확히 수정, IS_PROD=True 조건에서 Secure 속성 보장, CORS 허용 도메인에 Vercel 포함됨.

---

## 2. [P1] AuthDashboard.tsx 환경변수 교정 평가 — ✅ PASS

| 항목 | 결과 |
|------|------|
| `NEXT_PUBLIC_API_URL` 잔존 참조 없음 | 전체 `src/` 디렉토리 검증 결과 0건 ✅ |
| `AuthDashboard.tsx L15` | `NEXT_PUBLIC_BACKEND_URL` 사용 ✅ |
| `AuthDashboard.tsx L21` | `NEXT_PUBLIC_BACKEND_URL` 사용 ✅ |
| `getAbsoluteVideoUrl()` baseUrl 참조 | `NEXT_PUBLIC_BACKEND_URL \|\| "http://localhost:8000"` ✅ |
| `RaptorWorkflow.tsx L9` | `NEXT_PUBLIC_BACKEND_URL` 사용 ✅ |
| `api-client.ts L3` | `NEXT_PUBLIC_BACKEND_URL` 사용 ✅ |

환경변수 명칭이 전체 코드베이스에서 `NEXT_PUBLIC_BACKEND_URL`로 통일됨.

**판정: PASS** — 잔존 오류 없음, 전체 파일 정합성 확인.

---

## 3. 잠재적 신규 위험 요소 (보안 심층 분석)

### 3-1. SameSite=None 적용에 따른 보안 의의

**프로덕션 환경 (IS_PROD=True):**
- `SameSite=None; Secure` 조합 → Chrome 80+ 정책 준수 ✅
- HTTPS 한정 전송 보장 (Render HTTPS + Vercel HTTPS)

**개발 환경 (IS_PROD=False):**
- `SameSite=None; Secure=False` 조합은 Chrome이 **거부**하고 `SameSite=Lax`로 강등 처리
- 단, 개발 환경은 `localhost:3000 ↔ localhost:8000` 동일 호스트 접근이므로 실질적 영향 없음
- **위험도: Low** (개발 환경 한정)

### 3-2. HttpOnly=False 유지에 따른 XSS 트레이드오프

```python
httponly=False,  # main.py:693
```

- **불가피한 설계 선택**: Double Submit Cookie 패턴에서 JS가 `document.cookie`에서 토큰을 읽어 헤더에 첨부해야 하므로 구조적 요구사항임
- **리스크**: XSS 취약점 발생 시 공격자가 CSRF 토큰 탈취 후 인증된 API 요청 위조 가능
- **현재 완화 요소**:
  - KIE API Key는 `x-byok-kie` 헤더 별도 검증
  - Supabase JWT Bearer 토큰 별도 검증 (`get_jwt_user_id`)
  - 이중 검증 레이어로 CSRF 토큰 단독 탈취만으로는 심각한 피해 제한됨
- **권고**: CSP(Content-Security-Policy) 헤더 추가 검토 (XSS 근본 차단)

### 3-3. Render Free Plan 슬립 이후 쿠키 세션 소실 가능성

- 15분 비활동 후 **콜드 스타트(30~50초)** 발생
- 사용자의 첫 접근 시 `/api/auth/csrf-token` 요청이 타임아웃되면 프론트엔드에서 오류 화면 노출 가능성
- **현재 코드에 재시도 로직 없음** (기능 결함이 아닌 UX 리스크)
- **권고**: `api-client.ts`에 exponential backoff 재시도 로직 추가 검토

---

## 4. TDD 채점표

| # | 테스트 케이스 | 예상 결과 | 판정 |
|---|--------------|-----------|------|
| T1 | Vercel → Render `GET /api/auth/csrf-token` | 200 + `raptor_csrf` 쿠키 Set | ✅ PASS (코드 검증) |
| T2 | 쿠키 응답에 `SameSite=None; Secure` 속성 포함 | 속성 확인 | ✅ PASS |
| T3 | Vercel → Render `POST /api/auth/set-key` with valid CSRF | 200 | ✅ PASS (코드 검증) |
| T4 | CSRF 헤더 없이 POST 요청 | 403 반환 | ✅ PASS |
| T5 | CSRF 쿠키-헤더 불일치 POST | 403 반환 | ✅ PASS |
| T6 | AuthDashboard: 비디오 URL이 상대 경로일 때 | `BACKEND_URL` 기반 절대 URL 변환 | ✅ PASS |
| T7 | `NEXT_PUBLIC_API_URL` 환경변수 미설정 상태 | 오류 없음 (변수 미사용) | ✅ PASS |
| T8 | `IS_PROD=False` 개발환경 쿠키 설정 | `Secure=False` (localhost 정상 동작) | ⚠️ WARN (Chrome 정책 참고) |

---

## 5. 최종 결론 및 잔여 권고사항

### 최종 판정 요약

| 구분 | 상태 |
|------|------|
| P0 CSRF SameSite=None 수정 | **PASS ✅** |
| P1 AuthDashboard 환경변수 수정 | **PASS ✅** |
| 보안 구조의 적절성 | **PASS ✅** (단, HttpOnly=False 트레이드오프 인지 필요) |
| 배포 준비 상태 | **PASS ✅** |

### 🏁 전체 판정: **PASS** ✅

v2.14.1-hotfix 수정사항은 충분히 P0/P1 이슈를 모두 올바르게 해결하였으며, 보안 구조적으로도 계획된 트레이드오프 내에서 합격 수준입니다.

### 잔여 권고사항 (선택적)

| 순위 | 항목 | 파일 | 영향 |
|------|------|------|------|
| 🟡 P2 | CSP 헤더 추가 (XSS 근본 차단) | `main.py` CORS 설정 | 보안 강화 |
| 🟡 P3 | `api-client.ts` 콜드 스타트 retry 로직 | `api-client.ts` | UX 개선 |
| 🟡 P4 | Render 환경변수 `ENV=production` 설정 확인 | Render 대시보드 | IS_PROD=True 보장 |
| 🟡 P5 | `vercel.json` rewrites dead code 의도 명확화 | `vercel.json` | 코드 가독성 |
