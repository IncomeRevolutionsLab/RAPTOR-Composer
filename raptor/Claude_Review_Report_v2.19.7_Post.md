## Post-Review 핵심 결과 요약

### 백엔드 (main.py): 🟡 조건부 PASS

**✅ 정상 확인:**
- `map_image_model()`: 프론트 `"gpt-image-2"` → KIE 공식명 `"gpt-image-2-text-to-image"` 변환 정확
- Git Diff 기준 소거 완료: `"aspect_ratio": "3:2"` (grok 하드코딩), `"aspect_ratio": "auto"` (gpt/banana 하드코딩) 완전 제거
- 프론트엔드 전송 `n`, `size`, `quality` → Pydantic `ImageGenRequest`에 필드 없어 silently discard, KIE 누출 없음
- `/refine-prompt` 엔드포인트도 동일 패턴 적용, 양 엔드포인트 일관성 유지

**⚠️ 신규 리스크 (R-01):** `nano-banana-2`가 이전에 `"aspect_ratio": "auto"` 강제 주입받던 코드가 제거됨. 현재 `"9:16"` 그대로 전달됨. banana-2가 이 포맷 지원하는지 실서버 검증 필요. 미지원 시 422 재발 가능.

**ℹ️ Dead code 3건:** `hasattr` 체크(항상 True), `"auto"` fallback(절대 실행 불가), `img_size` 변수(페이로드 미포함) — 기능 영향 없음.

---

### 프론트엔드 (RaptorWorkflow.tsx): 🔴 FAIL (P0 2건)

**✅ 정상 동작하는 패치:**
- MP4 업로드 락 해제: `video/*` 허용 (`line 1478, 1551`)
- 스틸컷 100% 방어 해제: `completedVideos = s.video_url || s.use_image_only` (`line 1759`)
- `handleRenderFinal` 스틸컷 통과: `allVideosReady = s.video_url || s.use_image_only` (`line 653`) ✅
- KIE 오류 마스킹 해제: 에러 원문 노출 (`line 365`)

---

**🚨 [P0-B01] `TrafficLightUX` 미정의 컴포넌트 (line 1289)**

```tsx
{step === 3 && finalAssets && (
  <TrafficLightUX />   // ← 파일 내 정의/임포트 없음
<div ...>
```

파일 전체 grep 결과 정의 없음. `next.config.ts`에 `ignoreBuildErrors` 없으므로 TypeScript `TS2304` 빌드 오류 발생. 추가로 JSX 표현식에 Fragment 없이 형제 요소 2개가 배치되어 JSX 구조 위반 중첩.

---

**🚨 [P0-B02] Step 4 버튼 IIFE 스코프 버그 (lines 1917, 1932)**

`completedImages`, `completedVideos`, `totalScenes`는 line 1753 IIFE 내부에서만 정의되고 `})()}` (line 1834)에서 스코프 종료. 그런데 line 1917, 1932의 버튼 렌더링 조건식이 이 변수들을 외부에서 참조:

```tsx
{completedImages === totalScenes && completedVideos < totalScenes && (
  <button>비디오 클립 생성 시작</button>   // → undefined === N = false → 미표시
)}
{completedVideos === totalScenes && totalScenes > 0 && (
  <button>최종 렌더링 시작</button>         // → 동일하게 미표시
)}
```

두 버튼이 Step 4에서 절대 렌더링되지 않아 **사용자가 비디오 생성 단계에서 완전히 진행 불가**.

---

**⚠️ [P1-B03] 스틸컷 배지 조건 오류 (line 1615)**

`scene.use_image_only && scene.status === 'success'` → `use_image_only` 씬은 비디오 생성을 건너뛰므로 `status`가 `'success'`가 되는 코드 경로 없음. "스틸컷 연출 준비완료" 배지 영구 미표시.  
수정: `scene.use_image_only && !!scene.image_url`

---

**결론:** Vercel 배포 실패(빌드 에러) 혹은 프로덕션 마비가 확실시되므로 `P0-B01`, `P0-B02` 및 `P1-B03` 결함을 해결하는 핫픽스 절차에 즉시 돌입할 것을 권고합니다.
