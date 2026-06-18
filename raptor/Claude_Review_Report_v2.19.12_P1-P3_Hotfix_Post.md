## Post-Review Report — [P1-P3] 에러 파싱 리팩토링 (3060dfe)

**대상 파일:** `src/components/RaptorWorkflow.tsx`
**기준 커밋:** `3060dfe` (P1-P3 리팩토링) / `fcbefb8` (P0 선행 패치)
**프레임워크:** VIBE (Vulnerability · Integrity · Behavior · Efficiency)

---

### V — Vulnerability (보안)

**판정: PASS**

- `extractErrorMessage`는 에러 객체를 문자열로 변환 후 React 상태(`setErrorMessage`)에 저장하며, 렌더링 시 `innerHTML`이 아닌 텍스트 노드로 출력됩니다. XSS 위험 없음.
- `uploadFile`의 JWT Bearer 헤더 처리는 변경사항 없이 유지. 인증 흐름 무결.
- 에러 메시지에 내부 서버 정보(스택 트레이스 등)가 포함될 가능성은 `e.message` 기반 추출이므로 기존과 동일 수준.

---

### I — Integrity (안정성)

**판정: PASS (주의사항 1건)**

**✅ 수정된 사항 (긍정 평가)**
- `useCallback` 의존성 배열에 `setRenderStatus` 추가 (Line 176): 이전에 누락된 의존성이 올바르게 보정됨. Zustand 액션은 참조가 안정적이므로 실제 무한 루프 위험은 없으나, ESLint exhaustive-deps 경고 제거 및 의도 명확화에 기여.
- 클립 생성 `catch` 블록에서 `setLoading(false)` 제거 후 `finally`로 일원화: 중복 상태 설정 제거, `finally` 보장 실행으로 안정성 향상.

**⚠️ 잔존 주의사항 (P2 수준)**

```typescript
// Line 412–415
let displayError = extractErrorMessage(error);
if (displayError.includes('401') || displayError.includes('403') || ...) {
  displayError = displayError;  // ← 완전한 no-op 자기 대입
}
```

이 `if` 블록은 아무 동작도 하지 않는 데드 코드입니다. 원래 에러 마스킹 해제를 위한 분기였으나 P1-P3에서 `displayError = \`${error.message}\`` → `displayError = displayError`로 리팩토링하며 의도가 소실됐습니다. 현재 로직에 실질적 영향은 없지만, 유지보수 시 혼란을 유발합니다.

**권장 조치:** 블록 전체 제거.

```typescript
// 수정 전
let displayError = extractErrorMessage(error);
if (displayError.includes('401') || ...) {
  displayError = displayError;
}

// 수정 후
const displayError = extractErrorMessage(error);
```

---

### B — Behavior (동작 정확성)

**판정: PASS (잔존 엣지케이스 1건)**

**✅ 핵심 버그 수정 완료**
- P0에서 `errorMsg`(이미 `string`)에 `instanceof Error` 체크를 이중 적용하던 버그 (`비디오 클립 생성 오류` 핸들러) 완전히 해소.
- `extractErrorMessage` 통해 7개 catch 블록 일관성 확보.

**⚠️ 잔존 엣지케이스 (P3 수준, 선행 코드 문제)**

```typescript
// Line 670–672 (내부 JSON 파싱 catch)
} catch (e: any) {
  if (e.message !== "Unexpected end of JSON input" && !e.message.includes("Unexpected token")) throw e;
}
```

이 블록은 이번 PR에서 수정되지 않은 기존 코드입니다. `e`가 `Error` 인스턴스가 아닌 경우 `e.message`는 `undefined`이고, `undefined !== "..."` 조건이 `true`가 되어 예상치 못한 throw가 발생할 수 있습니다. 빈도는 낮지만, SSE 스트림 파싱 루프 내부이므로 파급 범위가 넓습니다.

**권장 조치 (별도 티켓):**
```typescript
} catch (e: any) {
  const msg = extractErrorMessage(e);
  if (!msg.includes("Unexpected end of JSON input") && !msg.includes("Unexpected token")) throw e;
}
```

---

### E — Efficiency (최적화)

**판정: PASS (개선 제안 1건)**

**✅ 개선된 사항**
- 동일 패턴 7회 중복 → `extractErrorMessage` 단일 헬퍼로 추출. 번들 크기 미미하게 감소, 유지보수 비용 절감.
- `extractErrorMessage(e)` 이중 호출 (Line 679, 687): `e`는 동일 객체 참조이므로 결과 동일. 성능 영향 없음.

**⚠️ 개선 제안 (P3 수준)**

현재 `extractErrorMessage`는 `Error` 인스턴스가 아닌 경우 `String(e)`를 반환합니다. 일부 API 클라이언트가 plain object를 throw할 경우 `"[object Object]"` 같은 무의미한 문자열이 사용자에게 노출될 수 있습니다.

```typescript
// 현재
const extractErrorMessage = (e: any): string => e instanceof Error ? e.message : String(e);

// 권장
const extractErrorMessage = (e: any): string =>
  e instanceof Error ? e.message : (e?.message ?? JSON.stringify(e) ?? String(e));
```

이렇게 수정하면 `{ message: "...", code: 422 }` 형태의 API 에러 객체도 의미 있는 메시지를 추출할 수 있습니다.

---

### 종합 판정

| 항목 | 상태 | 비고 |
|------|------|------|
| **보안 (V)** | ✅ PASS | 신규 취약점 없음 |
| **안정성 (I)** | ✅ PASS | no-op 데드코드 잔존 (P2) |
| **동작 정확성 (B)** | ✅ PASS | 내부 JSON catch 타입 가드 미적용 (P3, 선행 코드) |
| **최적화 (E)** | ✅ PASS | non-Error 객체 직렬화 개선 가능 (P3) |

**블로커: 없음.** P1-P3 리팩토링은 에러 파싱 일관성과 상태 관리 안정성을 유의미하게 향상시켰으며, P0 패치 이후의 후속 정리 작업이 명확히 수행되었습니다. 위 세 가지 잔존 항목은 모두 비차단적(non-blocking)이며, 다음 정기 클린업 스프린트에서 처리하는 것을 권장합니다.
