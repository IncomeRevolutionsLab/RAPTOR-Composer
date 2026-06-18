---

# VIBE Post-Review: handleAnalyze CSRF 토큰 자동 재발급 패치
**대상 버전:** `db519b4` (fix(p0): add CSRF token auto-refresh fallback to handleAnalyze)  
**작성일:** 2026-06-18  
**대상 환경:** Safari / Mobile (SameSite=None, Secure=True, cross-origin 쿠키)

---

## 1. 패치 내용 요약

`RaptorWorkflow.tsx:273-284` — `handleAnalyze` 진입 직후, 첫 API 호출(`api.post('/projects')`) 전에 Zustand 스토어에 `csrfToken`이 없을 경우 `/api/auth/csrf-token`을 직접 fetch해 스토어에 저장하는 로직 추가.

```typescript
let activeCsrfToken = store.csrfToken;
if (!activeCsrfToken) {
  try {
    const res = await fetch(`${BACKEND_URL}/api/auth/csrf-token`, { method: 'GET', credentials: 'include' });
    if (res.ok) {
      const data = await res.json();
      if (data.csrf_token) {
        store.setCsrfToken(data.csrf_token);
      }
    }
  } catch (err) {}   // 실패해도 무음 처리
}
```

---

## 2. 패치 유효성 분석

### ✅ 해결되는 시나리오

| 시나리오 | 설명 | 해결 여부 |
|---|---|---|
| 스토어 초기화 후 재진입 | 페이지 전환·HMR·컴포넌트 언마운트 후 Zustand 스토어가 리셋됐으나 서버 쿠키는 유효한 경우 | **해결** |
| 토큰 미발급 상태로 직접 접근 | 사용자가 CSRF 토큰 발급 전에 빠르게 분석 버튼을 클릭한 race condition | **해결** |

### ⚠️ 부분적으로 해결되는 시나리오

| 시나리오 | 설명 | 해결 여부 |
|---|---|---|
| 토큰 만료 (스토어·쿠키 모두 stale) | 재발급 호출로 새 쿠키 + 새 토큰을 동시 갱신 | **대부분 해결** (단, 아래 Safari ITP 조건 참조) |

### ❌ 해결되지 않는 시나리오

| 시나리오 | 설명 | 해결 여부 |
|---|---|---|
| Safari ITP에 의한 쿠키 완전 차단 | 프론트(Vercel)↔백엔드(Koyeb) cross-origin 쿠키를 Safari가 완전히 차단하는 경우, 재발급 시 서버가 `raptor_csrf` 쿠키를 심어도 Safari가 이를 저장·전송하지 않으므로 `verify_csrf`가 여전히 `raptor_csrf=None` 수신 → 403 | **미해결** |
| 자동 재시도 없음 | 403 수신 시 토큰 재발급 후 자동으로 동일 요청을 재시도하는 로직이 없음. 사용자에게 "페이지를 새로고침해달라"는 메시지만 노출 (`api-client.ts:103`) | **미해결** |

---

## 3. 중복 로직 문제

**동일한 fetch-if-missing 로직이 `api-client.ts:44-62`에 이미 존재한다.**

```typescript
// api-client.ts (기존)
let activeCsrfToken = csrfToken;
if (!activeCsrfToken && path !== '/auth/csrf-token') {
  // 동일하게 /api/auth/csrf-token fetch → store.setCsrfToken
}
```

`handleAnalyze`의 패치가 실행되면 스토어에 토큰이 저장되고, 이후 `api.post('/projects')`가 `api-client.ts`에 진입할 때 이미 토큰이 있으므로 `api-client.ts`의 동일 블록은 스킵된다. 중복 실행은 없지만 로직이 두 곳에 분산되어 있다.

> **영향:** 기능적 회귀 없음. 다만 향후 CSRF 로직 수정 시 두 곳을 동기화해야 한다는 유지보수 부채 발생.

---

## 4. 서버 검증 로직 재확인

```python
# main.py:137-145
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

서버는 반드시 **쿠키**(`raptor_csrf`)와 **헤더**(`X-CSRF-Token`) 두 값이 모두 존재하고 일치해야 통과시킨다. 헤더만 정상이어도 쿠키가 없으면 403이다. 따라서 클라이언트 스토어 토큰을 재발급해도, Safari가 쿠키를 차단하면 근본 원인은 해결되지 않는다.

---

## 5. 회귀 위험 평가

| 항목 | 평가 |
|---|---|
| 기존 동작 변경 여부 | 없음 — 토큰이 이미 있으면 패치 블록은 실행되지 않음 |
| 오류 전파 위험 | 없음 — `catch (err) {}`로 실패 시 무음 처리 |
| 쿠키 덮어쓰기 부작용 | 없음 — 유효한 쿠키가 있을 때 재발급을 요청하면 서버가 새 토큰으로 쿠키를 갱신하지만 헤더도 함께 갱신되므로 쌍이 맞음 |

---

## 6. 종합 판정

| 기준 | 결과 |
|---|---|
| **Validity** (목표 버그 해결) | **부분 해결** — Zustand 스토어 리셋·race condition에 의한 403은 해결. Safari ITP 쿠키 차단에 의한 403은 미해결 |
| **Impact** (회귀·부작용) | **없음** — 순수 additive 패치, 기존 경로 변경 없음 |
| **Behavior** (정상 경로) | **정상** — 토큰이 있으면 패치 블록 스킵, 없으면 재발급 후 진행 |
| **Edge Cases** (잔여 위험) | **잔존** — 403 후 자동 재시도 없음, Safari 쿠키 완전 차단 시 여전히 실패 |

---

## 7. 권고 사항

1. **단기 (P1):** `api-client.ts`에서 403 수신 시 토큰 재발급 → 자동 1회 재시도 로직 추가. 현재는 사용자에게 새로고침을 요구하는 UX 단절이 남아 있음.

2. **중기 (P2):** Safari/Mobile cross-origin 쿠키 의존을 제거하는 구조적 해결책 검토. 예: `Authorization` 헤더 기반 double-submit 패턴으로 전환하거나, `raptor_csrf` 쿠키를 `first-party` 도메인(same-origin proxy)에서 발급하도록 변경.

3. **중기 (P3):** `handleAnalyze`의 CSRF fetch 블록을 제거하고 `api-client.ts`의 기존 로직으로 단일화하여 유지보수 부채 해소.
