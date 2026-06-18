# Vercel JSX Fragment 빌드 에러 사후 리뷰 (Post-Review)

**검토일:** 2026-06-14  
**검토 커밋:** `97a6408` — `fix(p0): wrap adjacent JSX elements in Fragment to pass Vercel build`

---

## 클로드 코드(Claude Code) 리뷰 원문

이제 전체 구조를 파악했습니다. 사후 리뷰 결과를 정리합니다.

### 변경 내용 요약

`RaptorWorkflow.tsx`의 `step === 3` 블록:
- **Before (L1294):** `<div className="animate-in ...">` 하나만 직접 반환
- **After (L1297, L1737):** `<>...</>` Fragment로 감싼 뒤 내부에 `<div>` 유지

---

### 구조적 정확성 분석

**Fragment 개폐 일치 여부 — ✅ 정상**

| 위치 | 코드 | 역할 |
|------|------|------|
| L1296 | `{step === 3 && finalAssets && (` | 조건부 렌더링 시작 |
| L1297 | `<>` (8 spaces) | Fragment 열기 |
| L1298 | `<div className="animate-in ...">` (10 spaces) | 최상위 컨테이너 |
| L1736 | `</div>` (10 spaces) | animate-in div 닫기 |
| L1737 | `</>` (8 spaces) | Fragment 닫기 |
| L1738 | `)}` | 조건부 렌더링 끝 |

`<>` → `<div>` → ... → `</div>` → `</>` → `)}` 계층이 정확히 맞음.

**내부 자식 구조 — ✅ 유효**

`animate-in` div (L1298~L1736) 안에 3개의 자식이 올바르게 중첩:
1. **IIFE** (L1299~L1364) — JS 표현식이므로 JSX 인접 요소 문제 없음
2. **대사 모아보기 div** `bg-white/5` (L1367~L1380) — `</div>` L1380으로 정상 닫힘
3. **씬 그리드 div** `grid-cols-1 lg:grid-cols-3` (L1382~L1735) — `</div>` L1735로 정상 닫힘

세 개의 `</div>` (L1380, L1735, L1736)가 각각의 열기 태그에 올바르게 대응됨.

---

### 발견된 이슈

**[관찰] Fragment가 기술적으로 불필요 — 빌드에 무해**

현재 코드에서 `<>` Fragment의 직접 자식 JSX 요소는 `<div className="animate-in...">` 하나뿐임. React는 `<>{singleElement}</>` 구문을 허용하므로 컴파일 오류 없음. 다만 인접 JSX 요소가 없는 상태에서의 Fragment는 불필요한 노드.

가장 유력한 시나리오: 커밋 98dc7e4에서 div를 제거한 이후에도 외부 서브 구조가 정리되지 않아 인접 요소 오류가 남아 있었거나, 방어적 목적으로 Fragment를 추가한 것. 어느 경우든 현재 구조는 유효.

**[관찰] IIFE 들여쓰기 불일치 — 기능 무관**

```tsx
1298          <div className="animate-in ...">   // 10 spaces (부모)
1299          {(() => {                           // 10 spaces (자식인데 같은 레벨처럼 보임)
```

IIFE가 div와 동일한 들여쓰기라서 형제처럼 보이나, JSX는 태그 기반 중첩이므로 실제로는 div의 자식. 빌드 영향 없음.

---

### 빌드 차단 해소 여부 — ✅ 문제 없음

| 항목 | 결과 |
|------|------|
| Fragment 개폐 정합성 | ✅ 통과 |
| 인접 JSX 요소 잔존 여부 | ✅ 없음 (Fragment로 해소) |
| TypeScript 타입 오류 신규 유입 | ✅ 없음 |
| Step 4 블록 (L1740~) 영향 | ✅ 없음, 독립적 |
| 런타임 렌더링 영향 | ✅ 없음 (Fragment는 DOM 노드 추가 안 함) |

**결론:** 커밋 97a6408의 Fragment 래핑은 올바르게 적용되었으며, Vercel 빌드 차단 요인이 아닙니다. 현재 step === 3 블록의 JSX 구조는 유효하고 컴파일 가능한 상태입니다. 다음 Vercel 빌드에서 이 오류로 인한 실패는 발생하지 않을 것으로 판단됩니다.
