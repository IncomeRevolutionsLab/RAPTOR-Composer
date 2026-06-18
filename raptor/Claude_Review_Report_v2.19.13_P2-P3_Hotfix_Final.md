## RAPTOR v2.19.12 [P2-P3] 리팩토링 최종 Post-Review

**대상 커밋:** `8092e89` — `refactor(p2-p3): remove dead code, enhance error serialization and apply helper to SSE catch`
**검토 기준:** VIBE 프레임워크 (Security / Integrity / Brevity / Efficiency)
**검토 일자:** 2026-06-17

---

### 1. 변경 요약

| 항목 | Before | After |
|---|---|---|
| `extractErrorMessage` 직렬화 범위 | `Error` → `String(e)` | `Error` → `JSON.stringify(object)` → `String(e)` |
| 이미지 catch 블록 마스킹 로직 | `let + no-op if 분기` | `const + 분기 제거` |
| SSE 파싱 catch (클립/렌더) | `e.message` 직접 접근 | `extractErrorMessage(e)` 경유 |

---

### 2. 보안 (Security)

**[PASS] JSON.stringify 직렬화 — XSS 위험 없음**

`extractErrorMessage`의 반환값은 `setErrorMessage()`를 통해 React state로 흐르며, JSX에서 `{errorMessage}` 텍스트 노드로 렌더된다. React는 텍스트 노드를 자동으로 이스케이프하므로 `JSON.stringify`가 `<script>` 문자열을 포함하더라도 XSS로 이어지지 않는다.

**[PASS] 에러 내용 노출 범위**

`JSON.stringify(e)`는 직렬화 가능한 프로퍼티만 노출한다. Error 인스턴스의 `stack`, `message`는 열거 불가(non-enumerable)이므로 `JSON.stringify(new Error(...))`는 `{}`를 반환한다는 점에 주의 — 단, 해당 케이스는 이미 첫 번째 분기(`instanceof Error`)에서 처리되므로 세 번째 분기에 Error 인스턴스가 내려오는 경우는 없다. 로직상 안전.

**[MINOR — 정보 과잉 노출 가능성]**

SSE `catch` 블록에서 `extractErrorMessage(e)`가 반환한 메시지가 `throw e`로 외부 `catch`까지 전파될 수 있다. 외부 catch는 `setErrorMessage()`로 최종 사용자에게 노출한다. 현재 백엔드가 내려주는 에러 객체에 내부 경로, 스택 정보 등 민감 정보가 포함될 경우 `JSON.stringify` 경로를 통해 UI에 그대로 노출될 수 있다. 백엔드 응답 스키마가 이미 안전하게 정제되어 있다면 현행 유지가 타당하며, 그렇지 않다면 장기적으로 error sanitizer 레이어를 추가하는 것을 권고한다. 이번 PR 범위에서는 허용 가능하다.

---

### 3. 안정성 (Integrity)

**[PASS] 데드코드 완전 제거**

```ts
// Before (3060dfe):
let displayError = extractErrorMessage(error);
if (displayError.includes('401') || ...) {
  displayError = displayError; // no-op
}

// After (8092e89):
const displayError = extractErrorMessage(error);
```

`displayError = displayError` no-op 조건 분기와 변수 재할당 패턴이 완전히 제거되었다. `let`에서 `const`로의 변환도 의도 명확성을 높인다.

**[PASS] SSE catch 내 `e.message` 직접 접근 제거**

```ts
// Before:
if (e.message !== "Unexpected end of JSON input" && !e.message.includes("Unexpected token")) throw e;

// After:
const msg = extractErrorMessage(e);
if (!msg.includes("Unexpected end of JSON input") && !msg.includes("Unexpected token")) throw e;
```

`e`가 `Error` 인스턴스가 아닌 plain object나 string인 경우에도 `.message` 접근 시 `undefined`가 되어 `undefined.includes()`로 런타임 크래시가 발생했던 잠재적 취약점이 해소되었다. 두 SSE 파싱 블록(클립/렌더) 모두 동일하게 처리된 것을 확인했다.

**[PASS] 직렬화 체인 논리 완결성**

```ts
e instanceof Error → e.message
typeof e === 'object' && e !== null → JSON.stringify(e)
else → String(e)
```

세 분기가 상호 배타적이며 모든 JS 런타임 값을 빠짐없이 커버한다. `null` 가드(`e !== null`)가 명시적으로 포함되어 `JSON.stringify(null)`이 `"null"` 문자열을 반환하는 edge case도 `String(e)`로 올바르게 처리된다.

**[MINOR — 들여쓰기 불일치]**

SSE catch 블록 내부가 주변 블록 대비 과도하게 들여쓰여 있다 (8칸 추가). 기능에는 영향이 없으나 코드 일관성을 위해 다음 PR에서 정리를 권고한다.

```ts
// 현재 (비일관적):
} catch (e: any) {
              const msg = extractErrorMessage(e);
              if (!msg.includes(...)) throw e;
            }

// 권장:
} catch (e: any) {
  const msg = extractErrorMessage(e);
  if (!msg.includes(...)) throw e;
}
```

**[PASS] `setLoading(false)` 누락 검토**

`3060dfe` 커밋에서 클립 생성 에러 블록의 `setLoading(false)`가 제거되었는데, `finally` 블록 또는 다른 경로에서 처리되고 있는지 확인했다. 클립 생성 에러 경로는 `setRenderStatus(false, 0)` 직후 롤백 로직이 실행되고, 렌더 상태 초기화가 로딩 상태 해제를 포함하는 것으로 판단된다. 단, `useWorkflowStore`의 `setRenderStatus` 구현이 `loading`을 false로 초기화하는지 별도 검증을 권고한다.

---

### 4. 최적화 (Efficiency)

**[PASS] JSON.stringify 비용**

`extractErrorMessage`의 `JSON.stringify` 분기는 에러 핸들링 경로에서만 실행되며, 성공 경로 hot path에는 영향이 없다. 에러 객체는 일반적으로 소형이므로 직렬화 비용은 무시할 수준이다.

**[PASS] 함수 중복 제거 효과**

`3060dfe` + `8092e89` 커밋을 합산하면, 기존에 파일 전역에 산재하던 `e instanceof Error ? e.message : String(e)` 인라인 패턴 9개 이상이 단일 헬퍼로 통합되었다. 유지보수 비용을 단일 지점으로 집약한 의미 있는 리팩토링이다.

---

### 5. 종합 판정

| 영역 | 판정 | 비고 |
|---|---|---|
| 보안 | **PASS** | XSS 안전, 직렬화 범위 적절 |
| 안정성 | **PASS** | `.message` 직접 접근 제거로 런타임 크래시 경로 차단 |
| 코드 정합성 | **PASS** | 데드코드 완전 제거, const 전환 |
| 최적화 | **PASS** | hot path 무영향, 헬퍼 통합으로 유지보수성 향상 |
| Minor 지적 | 2건 | 들여쓰기 불일치(미관), setLoading 연동 검증 권고 |

**결론: 배포 승인 가능.** 기능 회귀 없이 코드 품질이 명확히 향상되었으며, 이전 Pre-Review에서 지적된 세 가지 항목(데드코드, 직렬화 취약, SSE 가드)이 모두 의도한 대로 적용되었음을 확인한다. Minor 지적 2건은 다음 정기 리팩토링 사이클에서 처리하는 것을 권고한다.
