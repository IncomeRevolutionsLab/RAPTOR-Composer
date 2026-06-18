이제 충분한 정보가 있습니다. 리뷰 결과를 정리해 드릴게요.

---

## Draft_Implementation_Plan.md 리뷰

### 전반적 평가

계획서의 P0 식별과 수정 방향은 **전반적으로 정확합니다.** 실제 코드와 교차 검증했을 때 핵심 버그들이 올바르게 포착되었습니다.

---

### P0 항목별 검증

#### P0-1: `<TrafficLightUX />` 제거 ✅ 정확

Line 1289에서 실제로 존재하며, import/define 없이 쓰인 것이 확인됩니다. 단, **JSX 구조 손상도 함께 존재**합니다:

```tsx
// 현재 코드 (1288-1290)
{step === 3 && finalAssets && (
  <TrafficLightUX />        // ← 제거 대상
<div className="animate-in ...">  // ← 들여쓰기도 깨져있음
```

계획서의 패치 2처럼 `<TrafficLightUX />`를 `<div ...>`로 교체하는 방식이 올바릅니다. 단순 삭제만 하면 여는 괄호 `(`가 `<div>`를 감싸는 구조가 되므로 패치 2대로 교체하는 것이 맞습니다.

---

#### P0-2: IIFE 스코프 버그 ✅ 정확

Line 1753-1834 IIFE에서 `completedImages`, `completedVideos`, `totalScenes`가 정의되고, Line 1917/1932 버튼 조건문에서 이 변수들을 IIFE 외부에서 참조합니다. 컴포넌트 최상위로 호이스팅하는 수정 방향이 맞습니다.

다만 **패치 4의 Step 5 버튼에서 disabled 조건이 현재 코드보다 단순화되어 있습니다:**

```tsx
// 현재 코드 (line 1935) — 더 강한 disabled 조건
disabled={isRendering || loading || !(finalAssets?.script && finalAssets.script.every((s: any) => s.video_url || s.use_image_only))}

// 계획서 패치 4 — 단순화됨 (조건 누락)
disabled={isRendering || loading}
```

패치 적용 시 기존의 `every()` 조건을 반드시 유지해야 합니다. 이게 누락되면 Step 5 버튼이 `allVideosReady`는 충족하지만 실제로는 아직 처리 중인 씬이 있을 때 활성화될 수 있습니다.

---

#### P0-3: 파이프라인 수동 제어 ✅ 현재 코드는 이미 안전

Line 618-621에서 `clips_ready` 처리를 직접 확인했습니다:

```tsx
if (data.clips_ready) {
  setLoading(false);
  // 클립 생성 완료 표시
}
```

`handleRenderFinal()` 자동 호출이 없으므로 이미 안전합니다. 계획서 P0-3의 "확인" 항목은 맞습니다.

단, **Visual Tracker의 잠재적 위험(감사 보고서 4-2)이 계획서에서 처리 방법이 모호합니다.** Line 1783-1784에서 `isError` 상태가 되면 `handleGenerateClips`와 `handleRenderFinal` 버튼이 자동으로 나타나는 구조인데, 에러 상태 조건이 느슨하면 사용자 의도 없이 버튼이 출현할 수 있습니다. 계획서에서 "방어 코드 적용"이라고만 되어 있고 구체적 조치가 없습니다.

---

#### P0-4: 환경변수 가이드 ✅ 올바름

`NEXT_PUBLIC_BACKEND_URL`을 빈 문자열로 설정하면 `/api/...` 상대경로 호출 → Vercel rewrite 룰 경유 구조가 작동합니다. 올바릅니다.

---

### 보완이 필요한 부분 (요약)

| # | 항목 | 우선순위 |
|---|------|---------|
| 1 | 패치 4의 Step 5 버튼 `disabled` 조건에 `every()` 검사 추가 | **P0 수준** (누락 시 오작동) |
| 2 | Visual Tracker 재시도 버튼의 구체적 처리 방법 명시 필요 | P1 |
| 3 | P1 항목인 Git 브랜치 불일치(`main` vs `master`)는 Vercel 배포 트리거 문제이므로 P0급으로 격상 고려 | P1→P0 검토 |

---

### 결론

P0 버그 식별은 정확합니다. **패치 4에서 `disabled` 조건 누락만 수정하면 계획서대로 실행해도 됩니다.** P0-2 패치를 적용할 때 현재 코드의 `disabled` 조건을 그대로 복사하면 안전합니다.
