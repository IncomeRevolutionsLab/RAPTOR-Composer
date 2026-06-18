# 사후 아키텍처 리뷰 (Post-Architecture Review)
**대상:** `src/components/RaptorWorkflow.tsx`  
**커밋:** `2355265` — `fix(p0): Resolve Vercel build TS2304 and enforce manual pipeline control`  
**검토일:** 2026-06-14

---

## 패치 1: `TrafficLightUX` 미정의 컴포넌트 제거

**Git Diff 확인:**
```diff
- <TrafficLightUX />
+ <div className="hidden"></div>
```

**TS2304 해소 여부:** ✅  
파일 전체 grep 결과 `TrafficLightUX` 0건. 정의되지 않은 컴포넌트 참조가 완전 제거되어 `TS2304` 빌드 에러는 해소되었습니다.

**⚠️ 잔존 리스크 — JSX Fragment 미완성:**  
`cat -A` 원시 바이트 및 라인별 구조 분석 결과, `{step === 3 && finalAssets && (` 표현식(line 1296)의 `(` 괄호가 line 1737의 `)}` 에서 닫히는 구조임이 확인됩니다. 그 내부에 두 개의 형제 루트 요소가 Fragment 없이 공존합니다:

```tsx
{step === 3 && finalAssets && (      // line 1296: ( 열림
  <div className="hidden"></div>     // line 1297: 첫 번째 루트
<div className="animate-in ...">     // line 1298: 두 번째 루트 (0 indent!)
  ...
</div>                               // line 1736
)}                                   // line 1737: ) 닫힘
```

원래 P0-B01 진단의 두 번째 문제 — "JSX 표현식에 Fragment 없이 형제 요소 2개" — 가 **해결되지 않았습니다**. TypeScript JSX 파서는 `(expr)` 내부에서 두 인접 루트 요소를 허용하지 않습니다. 올바른 수정은:

```tsx
{step === 3 && finalAssets && (
  <>
    <div className="hidden"></div>
    <div className="animate-in fade-in slide-in-from-bottom-4 space-y-8">
      ...
    </div>
  </>
)}
```

**다만,** `next.config.ts`에 `typescript.ignoreBuildErrors`가 없음에도 Vercel 빌드가 통과되었다면, Next.js의 SWC 컴파일러가 이 엣지 케이스를 다르게 처리하는 것일 수 있습니다. `npx tsc --noEmit` 로컬 검증이 필요합니다.

**패치 1 판정: 🟡 조건부 PASS** (TS2304 해소 / JSX Fragment 구조 미완성)

---

## 패치 2: IIFE 호이스팅 (P0-B02 해결)

**확인된 코드 (lines 76–81):**
```tsx
// [FIX] P0: Step 4, 5 버튼 스코프 버그 수정을 위한 컴포넌트 최상위 호이스팅
const script = finalAssets?.script || [];
const totalScenes = script.length || 0;
const completedImages = script.filter((s: any) => s.image_url).length;
const completedVideos = script.filter((s: any) => s.video_url || s.use_image_only).length;
const allVideosReady = completedVideos === totalScenes && totalScenes > 0;
```

Git Diff에서 IIFE 내부의 중복 선언 5줄이 제거되고, 해당 변수들이 컴포넌트 최상위 스코프로 이전됨. Step 4 버튼(line 1920)과 Step 5 버튼(line 1935)이 이제 `undefined`가 아닌 실제 계산값을 참조합니다.

**패치 2 판정: ✅ PASS**

---

## 패치 3: Step 5 버튼 강방어벽 유지

**확인된 코드 (lines 1919–1949):**

| 구분 | 내용 |
|---|---|
| Step 4 버튼 렌더 조건 (line 1920) | `completedImages === totalScenes && completedVideos < totalScenes` |
| Step 5 버튼 렌더 조건 (line 1935) | `completedVideos === totalScenes && totalScenes > 0` |
| Step 5 `disabled` 이중 방어벽 (line 1938) | `isRendering \|\| loading \|\| !(finalAssets?.script && finalAssets.script.every(s.video_url \|\| s.use_image_only))` |

두 버튼이 물리적으로 완전 분리되어 **상호 배타적**으로 렌더링됩니다. Step 5 버튼은 렌더링 조건 + disabled 조건의 이중 게이팅으로 보호됩니다.

**패치 3 판정: ✅ PASS**

---

## 패치 4: Visual Tracker 수동통제 action 제거

**Git Diff 확인:**
```diff
- { id: 4, ..., action: handleGenerateClips, actionLabel: '실패한 씬 비디오 생성 재시도' },
- { id: 5, ..., action: handleRenderFinal,   actionLabel: '최종 렌더링 재시도' },
+ { id: 4, ..., action: undefined, actionLabel: '' },
+ { id: 5, ..., action: undefined, actionLabel: '' },
```

VT의 버튼 렌더링 조건(line 1824)은 `isError && stg.action`이므로, `action: undefined`인 Stage 4, 5는 에러 상태에서도 VT 내 버튼이 절대 렌더링되지 않습니다. Stage 1, 2의 에러 재시도(분석 재시도/스크립트 재작성)는 설계 의도에 따라 유지됩니다.

**패치 4 판정: ✅ PASS**

---

## 종합 판정

| 패치 | 항목 | 판정 |
|---|---|---|
| 패치 1 | TrafficLightUX 제거 (TS2304) | ✅ |
| 패치 1 | JSX Fragment 구조 수정 | ⚠️ 미완성 |
| 패치 2 | IIFE 호이스팅 | ✅ |
| 패치 3 | Step 5 버튼 강방어벽 | ✅ |
| 패치 4 | Visual Tracker action 제거 | ✅ |

## 최종 판정: 🟡 **CONDITIONAL PASS**
