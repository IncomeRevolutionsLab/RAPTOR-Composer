# 📋 RAPTOR v2.14.2-hotfix E2E Auth/BYOK/401 수술 사후 리뷰 보고서 (Post-Review)

- **검토 일자**: 2026-06-10
- **리뷰어**: Claude Code (claude --print)
- **커밋**: 7951c64
- **검토 범위**: P0 BYOK Store 동기화, P0 비밀번호 재설정 분리, P1 Placeholder 교정

---

## 1. [P0] BYOKSettingsForm KIE Store 동기화 수정 평가 — ✅ PASS

### 코드 확인 결과

| 항목 | 위치 | 결과 |
|------|------|------|
| `setKieKey: setStoreKieKey` destructure | `BYOKSettingsForm.tsx:9` | ✅ |
| 키 저장 시 `setStoreKieKey(kieKey.trim())` 호출 | `BYOKSettingsForm.tsx:74` | ✅ |
| 키 클리어 시 `setStoreKieKey('')` 호출 | `BYOKSettingsForm.tsx:55` | ✅ |
| `api-client.ts` X-BYOK-KIE 헤더 전송 | `api-client.ts:19-21` | ✅ |
| `main.py` 헤더 없으면 401 반환 | `main.py:145-148` | ✅ |

**401 재현 불가** — 수정으로 흐름이 완전히 해결됨.

---

## 2. [P0] 비밀번호 재설정 401 분리 평가 — ✅ PASS

- `AuthDashboard.tsx:100` — `supabase.auth.resetPasswordForEmail()` 호출 시 Supabase SDK 직접 호출, **api-client.ts 미경유**
- KIE Key 의존성 **완전 분리** 확인. `isKeyConfigured` 체크 없음
- `supabaseClient.ts:4` — `NEXT_PUBLIC_SUPABASE_ANON_KEY` 환경변수로 올바른 anon JWT 사용 ✅

---

## 3. [P1] Placeholder 교정 평가 — ✅ PASS

| 파일 | 수정 전 | 수정 후 |
|------|---------|---------|
| `BYOKSettingsForm.tsx:178` | `"kie-..."` | `"API Key 입력..."` ✅ |
| `AuthDashboard.tsx:587` | `"kie-..."` / `"kie-***..."` | `"API Key 입력..."` / `"***... (이미 설정됨)"` ✅ |

---

## 4. 잠재적 신규 위험 요소

### 4-1. TDD 채점 — ⚠️ FAIL (`api-client.test.ts` 업데이트 필요)

`src/lib/api-client.test.ts`의 Test 1이 **구(舊) 멀티키 아키텍처 기반**으로 작성되어 현재 코드와 불일치:

```typescript
// 테스트 (구 방식 — 오작동)
window.localStorage.setItem('raptor_grok_key', 'test-xai-key');
expect(headers['X-BYOK-Grok'])   // 존재하지 않는 헤더명

// 실제 코드 (현재)
if (store.kieKey) headers['X-BYOK-KIE'] = store.kieKey;  // Zustand store 기반
```

테스트가 `localStorage + X-BYOK-Grok` 검증인데, 실제 구현은 `Zustand store.kieKey + X-BYOK-KIE`.
→ **테스트 코드 업데이트 필요 (P1 잔여 작업)**

### 4-2. 아키텍처 설계 메모 (참고)

**`/api/auth/set-key` 백엔드는 `kie_key`를 서버에 저장하지 않음** — CSRF 토큰만 발급.
KIE Key는 클라이언트(Zustand + localStorage)에만 존재하며, 요청마다 헤더로 전달.
→ **올바른 BYOK 설계** — 서버에 민감 키 미보관 ✅

### 4-3. 잔존 리스크

| 위험도 | 항목 | 설명 |
|--------|------|------|
| 🟠 MEDIUM | `kieKey` localStorage 평문 저장 | XSS 공격 시 탈취 가능. BYOK 아키텍처 본질적 트레이드오프로 인지 후 수용 필요 |
| 🟡 LOW | `AuthDashboard.handleSaveKey`가 `/auth/set-key` 미호출 | CSRF 토큰 미갱신. 단, `api-client.ts:25-41`의 자동 prefetch fallback으로 보완됨 |
| 🟡 LOW | 쿠키-localStorage kieKey 불일치 시나리오 | 다른 탭에서 키 변경 시 두 저장소 불일치 가능. 현재 치명적 장애 아님 |

---

## 5. TDD 채점표

| # | 테스트 항목 | 판정 |
|---|------------|------|
| T1 | BYOKSettingsForm 키 저장 → store.kieKey 설정 | ✅ PASS (코드 검증) |
| T2 | api-client.ts X-BYOK-KIE 헤더 전송 | ✅ PASS (코드 검증) |
| T3 | 백엔드 get_decrypted_key 헤더 수신 | ✅ PASS (코드 검증) |
| T4 | supabase.auth.resetPasswordForEmail() KIE 분리 | ✅ PASS |
| T5 | Placeholder 'kie-...' 문구 제거 | ✅ PASS |
| T6 | api-client.test.ts 자동화 테스트 | ⚠️ FAIL (구 아키텍처 기반 — 업데이트 필요) |

---

## 6. 최종 결론 및 잔여 권고사항

### 최종 판정

| 구분 | 상태 |
|------|------|
| P0 BYOKSettingsForm Store 동기화 | **PASS ✅** |
| P0 비밀번호 재설정 401 분리 | **PASS ✅** |
| P1 Placeholder 교정 | **PASS ✅** |
| TDD 자동화 테스트 | **⚠️ FAIL (업데이트 필요)** |

### 🏁 전체 판정: **조건부 PASS** ✅

P0/P1 핵심 수정 모두 코드상 정확히 구현됨. 단, **테스트 코드 1건 업데이트 필요**.

### 잔여 권고사항 (우선순위순)

| 순위 | 항목 | 파일 | 내용 |
|------|------|------|------|
| 🟠 **P1** | `api-client.test.ts` 업데이트 | `src/lib/api-client.test.ts` | X-BYOK-Grok → X-BYOK-KIE, localStorage → Zustand store mock으로 교체 |
| 🟡 P2 | `AuthDashboard.handleSaveKey`에 CSRF 토큰 갱신 추가 | `AuthDashboard.tsx` | `/auth/set-key` 호출하여 CSRF 토큰 동기화 |
| 🟡 P3 | kieKey localStorage 암호화 검토 | `useWorkflowStore.ts` | XSS 완화를 위한 저장 시 암호화 고려 |
