# Claude Review Report — v2.19.10 P1-P3 Hotfix (Post-Review)

**Date:** 2026-06-17  
**Commit:** `84d3ca8` — `refactor(p1-p3): extract uploadFile helper, improve error UX and fix indentation`  
**Target File:** `src/components/RaptorWorkflow.tsx` (L40–65, L1469–1640)

---

## 변경 적용 확인

| 항목 | 결과 |
|---|---|
| `uploadFile` 헬퍼 추출 (L44–60) | ✅ |
| 4개 핸들러에서 `uploadFile` 호출 | ✅ |
| JWT 토큰 없을 시 throw 처리 | ✅ |
| 들여쓰기 정규화 | ✅ |

---

## 발견된 결함

### 🔴 P1-HIGH — Silent Failure: 이미지 업로드 후 `data.url` 미반환 시 무응답
**위치:** L1493–1500, L1567–1576

```typescript
if (data && data.url) {
  updateSceneScript(i, 'image_url', data.url);
}
// else 분기 없음 → data.url 누락 시 스피너만 사라지고 씬은 그대로
```
서버가 `{ success: true }` 형태로 응답하거나 `url` 필드가 누락될 경우 업로드 성공인데 씬이 갱신되지 않는 버그. `else` 분기에 alert 추가 필요.

---

### 🔴 P1-HIGH — HTTP 상태 코드 미포함: 인증 만료 vs 서버 오류 구분 불가
**위치:** L58

```typescript
if (!res.ok) throw new Error("업로드 실패 (서버 에러)");
```
`401`(토큰 만료), `413`(파일 크기 초과), `429`(Rate Limit), `500`을 모두 동일 메시지로 처리. 401 시 사용자에게 재로그인 안내가 필요함에도 "서버 에러"만 표시됨.

**수정:**
```typescript
if (!res.ok) {
  let msg = `업로드 실패 (HTTP ${res.status})`;
  if (res.status === 401) msg = "인증이 만료되었습니다. 재로그인 후 다시 시도하세요.";
  if (res.status === 413) msg = "파일 크기가 너무 큽니다.";
  if (res.status === 429) msg = "요청이 너무 많습니다. 잠시 후 다시 시도하세요.";
  throw new Error(msg);
}
```

---

### 🔴 P1-HIGH — 클라이언트 파일 크기 검증 누락 (4개 핸들러 모두)
**위치:** L1484, L1517, L1559, L1594

서버에는 P1 패치(`a97f180`)에서 OOM 방어가 구현되어 있으나, 클라이언트 측 사전 검사 없음. 대용량 파일을 전부 전송한 후에야 서버 거부가 발생해 불필요한 대기·비용 발생.

---

### 🟡 P2-MEDIUM — `supabase.auth.getSession()` error 객체 미처리
**위치:** L46

```typescript
const { data: sessionData } = await supabase.auth.getSession();
```
`error` 필드를 destructure하지 않아 스토리지 접근 불가 등 세션 조회 실패 시에도 "로그인이 필요합니다"라는 부정확한 메시지 표시.

---

### 🟡 P2-MEDIUM — `isUploading` Dead State
**위치:** L90

선언은 되어 있지만 4개 핸들러 모두 `setLoading`(Zustand)을 사용하며 `setIsUploading`을 호출하지 않음. 미사용 상태 제거 또는 의도한 용도로 활성화 필요.

---

### 🟡 P2-MEDIUM — `res.json()` 파싱 실패 시 혼란스러운 오류 메시지
**위치:** L59

서버가 `200 OK`를 반환하지만 응답이 유효한 JSON이 아닌 경우, `SyntaxError: Unexpected token '<'...` 같은 내부 오류 메시지가 사용자에게 그대로 노출됨.

---

### 🟢 P3-LOW — `data.id` 서버 응답값 URL 직접 보간
**위치:** L1529, L1607

```typescript
`${BACKEND_URL}/outputs/${data.id}.mp4`
```
서버 응답의 `id`를 별도 검증 없이 URL에 직접 보간. 브라우저 `<video src>` 속성으로 사용되므로 위험도는 낮으나 입력 신뢰 원칙에 위배.

---

### 🟢 P3-LOW — `console.error(err)` 프로덕션 노출
**위치:** L1501, L1537, L1578, L1616

에러 객체 전체를 콘솔에 출력하면 요청 URL·헤더 정보가 DevTools에 노출될 수 있음.

---

## 보안 검토 요약

| 항목 | 상태 |
|---|---|
| JWT 토큰 전송 (`Authorization: Bearer`) | ✅ |
| 토큰 미존재 시 요청 차단 | ✅ |
| 파일 타입 클라이언트 검증 | ✅ 4개 핸들러 모두 |
| **파일 크기 클라이언트 검증** | ❌ **누락** |
| **HTTP 상태별 인증 오류 구분** | ❌ **미흡** |
| XSS 위험 | N/A (React 자동 이스케이프) |
| 경로 순회 위험 | ⚠️ 낮음 |

---

## 액션 아이템 우선순위

| 우선순위 | 항목 | 위치 |
|---|---|---|
| 🔴 P1 | 이미지 업로드 silent failure `else` 분기 추가 | L1494, L1567 |
| 🔴 P1 | HTTP 상태 코드별 오류 메시지 세분화 | L58 |
| 🔴 P1 | 클라이언트 파일 크기 사전 검증 (4개 핸들러) | L1484, L1517, L1559, L1594 |
| 🟡 P2 | `getSession()` error 객체 처리 | L46 |
| 🟡 P2 | `isUploading` dead state 제거 | L90 |
| 🟡 P2 | `res.json()` 파싱 예외 래핑 | L59 |
| 🟢 P3 | `data.id` URL 보간 검증 | L1529, L1607 |
| 🟢 P3 | 프로덕션 `console.error` 정제 | L1501, 1537, 1578, 1616 |
