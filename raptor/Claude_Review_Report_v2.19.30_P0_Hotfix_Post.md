---

# VIBE Post-Review: P0 Hotfix (handleAnalyze Rollback, API Retry & KIE Error Guard)
**대상 버전:** `df70799` (fix(p0): revert handleAnalyze header override...)  
**작성일:** 2026-06-18  
**대상 환경:** Safari / Mobile (SameSite=None, Secure=True, cross-origin 쿠키)

---

## 1. 패치 내용 요약 및 분석

### 1-A. RaptorWorkflow.tsx — handleAnalyze 롤백 (lines 265-295)
**제거 이유:** `handleAnalyze`에서 `store.setCsrfToken()`을 호출해 토큰을 스토어에 저장했으나, 이 스코프에서는 `api-client.ts`가 요청에 첨부하는 `X-BYOK-KIE` 헤더 등 다른 인증 헤더 조립 로직과 독립적으로 실행된다. 롤백 전에는 stale 토큰이 스토어에 이미 없을 경우 race condition 없이 정상 동작했지만, 이 블록이 토큰을 새로 발급받아 스토어에 넣는 과정에서 `api-client.ts` 내부의 `Authorization: Bearer` 주입 흐름(supabase 세션 fetch)과 타이밍이 충돌해 KIE 백엔드가 `401 Unauthorized`를 응답하는 부작용이 확인됨.

### 1-B. api-client.ts — 403 자동 재시도 중앙 집중화 (lines 89–109)
모든 `api.request()` 호출이 이 단일 경로를 통과하므로, 403이 발생하는 모든 엔드포인트(`/projects`, `/generate-plan`, `/generate-images` 등)에 재시도 로직이 자동 적용된다. `/auth/csrf-token` 경로는 guard로 제외해 무한 재귀를 방지한다.
이전 `db519b4` Pre-Review 권고사항 **§7 단기 (P1): api-client.ts에서 403 수신 시 자동 1회 재시도 로직 추가** 가 본 커밋에서 이행됨.

### 1-C. main.py — KIE API 에러 NoneType 방어막 (lines 1142–1143)
KIE Claude 호출 응답이 `{"error": "some_message"}` 형태의 JSON일 때, 기존 코드는 이를 성공 응답으로 처리해 상위 파이프라인에서 `NoneType` 또는 예상치 못한 키 접근 오류를 유발했다. 이 guard는 에러 페이로드를 즉시 `RuntimeError`로 변환해 `except` 블록의 재시도 또는 상위 예외 전파 경로로 보낸다.

---

## 2. 패치 유효성 분석

### ✅ 완전 해결된 시나리오
| 시나리오 | 설명 | 해결 여부 |
|---|---|---|
| handleAnalyze CSRF 헤더 주입 → KIE 401 | `db519b4` 패치가 유발한 regression. 토큰 재발급 타이밍과 Authorization 헤더 조립 간 race condition으로 KIE 인증 실패 | **완전 해결 (롤백)** |
| 403 후 사용자에게 새로고침 요구하는 UX 단절 | `db519b4` Pre-Review §7 P1 잔여 문제. api-client 단위에서 자동 재시도 없어 사용자 개입 필요 | **완전 해결** |
| KIE 에러 JSON이 성공으로 오해석되어 NoneType 발생 | `generate_plan` 내 `call_claude_with_fallback` 반환 직후 상위 코드가 result 키에 접근 시 AttributeError/KeyError 발생 | **완전 해결** |
| 중복 CSRF fetch 로직 분산 (db519b4 유지보수 부채) | `handleAnalyze`와 `api-client.ts` 두 곳에 동일 fetch-if-missing 블록 존재 | **완전 해결 (단일화)** |

### ⚠️ 부분/미해결 시나리오
| 시나리오 | 설명 | 해결 여부 |
|---|---|---|
| Safari ITP 구조적 차단 | cross-origin `raptor_csrf` 쿠키를 Safari가 완전 차단 시, 재발급 자체는 성공해도 쿠키가 재전송되지 않아 `verify_csrf`가 여전히 403 반환 | **부분 해결** (재시도는 1회 작동하나 근본적으로 쿠키가 저장되지 않음) |

---

## 3. 종합 판정

| VIBE 기준 | 결과 |
|---|---|
| **Validity** (목표 버그 해결) | **해결** — db519b4가 유발한 KIE 401 regression 롤백 완료, api-client 403 자동 재시도 중앙 집중화, KIE NoneType 방어막 3개 목표 모두 이행 |
| **Impact** (회귀·부작용) | **없음** — 롤백 후 api-client의 기존 CSRF fetch 로직이 기능 공백 없이 인계받음 |
| **Behavior** (정상 경로) | **정상** — CSRF 토큰 있을 때는 재시도 블록 미실행, KIE 정상 JSON은 guard 통과 |
| **Edge Cases** (잔여 위험) | **잔존 (P2)** — Safari ITP 쿠키 완전 차단 시 재시도 1회 후 여전히 403 최종 실패. 구조적 해결은 same-origin 프록시 또는 Authorization 헤더 기반 CSRF 교체 필요 |

---

## 4. 잔여 권고 사항

1. **(P2 — 중기)** Safari/Mobile cross-origin 쿠키 의존 제거. `Vercel(frontend) ↔ Koyeb(backend)` 구조에서 `raptor_csrf` 쿠키 대신 `Authorization` 헤더 기반 double-submit CSRF 패턴으로 전환하거나, Vercel rewrites를 통한 same-origin 프록시 도입 검토.
2. **(P3 — 저우선)** `api-client.ts:44-62`의 pre-flight CSRF fetch 블록과 `lines 89–109`의 사후 재시도 블록이 논리적으로 중복된다. 두 블록을 단일 `ensureCsrfToken()` 유틸로 추출하면 향후 CSRF 정책 변경 시 수정 포인트를 단일화할 수 있다.
