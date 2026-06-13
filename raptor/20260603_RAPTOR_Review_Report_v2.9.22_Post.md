## Current Build Settings Report

### R-3 — `onRehydrateStorage` 검증

**상태: ✓ OK**

`onRehydrateStorage` 콜백은 정상 작동합니다:
- `setHasHydrated(true)` → 컴포넌트 마운트 이전에 신호 전달 ✓
- `setErrorMessage(null)` / `setRenderStatus(false, 0, null)` → stale 상태 클리어 ✓
- `step 4 → 3` 롤백 정상 ✓
- 깨진 image_url (scheme 미검증, 'error'/'fail' 포함) → `null` + `status: 'waiting'` 리셋 ✓
- `partialize`에서 `data:image` base64 localStorage 저장 차단 ✓

레이스 컨디션 위험 없음 — Zustand rehydration은 React 마운트 이전에 완료되고 `hasHydrated` 플래그가 렌더를 게이팅합니다.

---

### P-5 — `allImagesReady` 계산 및 한국어/수동 입력 흐름

#### `allImagesReady` 게이트: ✓ OK
```tsx
finalAssets.script.every((s) =>
  s.image_url &&
  s.image_url.trim() !== "" &&
  (s.image_url.startsWith('http') || s.image_url.startsWith('data:image')) &&
  s.status !== 'rendering' &&
  s.status !== 'error'
)
```
`null image_url + status='done'` 우회 경로 없음. status 값은 `waiting/rendering/ready/error` 4종이며 `done`은 존재하지 않습니다.

#### `targetLanguage` (한국어) 전달: ✓ OK
자동/수동 양쪽 분기 모두 `target_language: productData.targetLanguage`로 올바르게 전달됩니다.

---

#### ⚠️ P-5 CRITICAL: `manualAdditions` 데이터 손실 버그

**상태: BUG**

| 단계 | 상태 |
|------|------|
| UI에서 `pain_points` / `strengths` 수집 | ✓ 정상 |
| `manualAdditions` localStorage 저장 | ✓ 정상 |
| UI 화면에 표시 | ✓ 정상 |
| **백엔드 API 페이로드에 포함** | ❌ **미포함** |

`inputMode === 'manual'`일 때 `/generate-plan` API 호출에 `manualAdditions`가 **전혀 전송되지 않습니다.** 백엔드는 `mode: "manual"` 플래그만 받고 실제 수동 입력 데이터는 수신하지 못하므로, 수동 모드가 자동 모드와 기능적으로 동일합니다.

**수정 방향 (Write/Edit 미수행, 방향 제시):**

```tsx
// api.post('/generate-plan', { ... }) 호출 시 추가:
manual_additions: inputMode === 'manual' ? manualAdditions : undefined
```

백엔드가 이미 `manual_additions` 필드를 처리하는지 확인 후 프론트엔드 페이로드 추가가 필요합니다.

---

### 요약

| 항목 | 파일 | 판정 |
|------|------|------|
| R-3 onRehydrateStorage 전체 흐름 | `useWorkflowStore.ts` | ✓ OK |
| P-5 `allImagesReady` 게이트 로직 | `RaptorWorkflow.tsx` | ✓ OK |
| P-5 한국어 `targetLanguage` 전달 | `RaptorWorkflow.tsx` | ✓ OK |
| P-5 수동 모드 `manualAdditions` API 전달 | `RaptorWorkflow.tsx` | ⚠️ **BUG** |

**다음 액션**: `manualAdditions` 페이로드 전송 수정을 진행할까요? 백엔드 수신 여부도 함께 확인이 필요합니다.
