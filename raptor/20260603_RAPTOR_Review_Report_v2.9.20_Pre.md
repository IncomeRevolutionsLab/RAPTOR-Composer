# RAPTOR V2.9.20 — 2차 HIL 피드백 5대 결함 핫픽스 사전 리뷰(Pre-Review) 보고서

| 항목 | 내용 |
|---|---|
| **Author** | Claude Code |
| **검토 대상** | 2차 HIL 테스트 기반 5대 결함 핫픽스 구현 계획서(implementation_plan.md) |
| **참조 문서** | Risk_Tracker.md (누적 리스크 추적서) |
| **작성일** | 2026-06-03 |
| **기준 버전** | RAPTOR V2.9.20 (pre-patch) |

---

## 검토 방법론

본 보고서는 계획서에 기술된 변경 사항을 실제 코드베이스(`useWorkflowStore.ts`, `RaptorWorkflow.tsx`, `AuthDashboard.tsx`, `main.py`, `kie_pricing.json`)와 교차 검증하여 작성되었습니다. 각 항목은 아래 3개 카테고리로 엄격히 분류합니다.

---

## ✅ [Resolved] — 이번 패치를 통해 해결되는 결함 및 리스크

### R-1. 자동 로그인 시 하드코딩 계정(`beta_tester`) 덮어쓰기 버그

**해결 방법:** `useWorkflowStore.ts`의 `partialize` 반환 객체(현재 코드 L.240–267)에 `user: state.user` 필드가 누락되어 있음을 코드베이스에서 직접 확인. 이를 추가하면 로컬스토리지에 실제 Supabase 사용자 정보가 보존되어, 수화(Rehydrate) 직후 `store.user`가 비어 있지 않게 된다. `RaptorWorkflow.tsx` 마운트 `useEffect`(L.122–130)의 `if (!store.user)` 가드와 연계되어, 기존 로그인 세션이 있을 경우 `beta_tester` 더미 계정으로 덮어쓰이지 않는다.

**근거:** `AuthDashboard.tsx`에는 이미 `supabase.auth.getSession()` 기반 가드(L.36–45)가 구현되어 있어, 실제 Supabase 세션이 존재할 경우 mock 유저를 방어하는 계층이 하나 더 존재함.

---

### R-2. 메인 워크플로우 화면(Step 0~4) 비용 UI 조기 노출 문제

**해결 방법:** `AuthDashboard.tsx`의 메인 대시보드 화면에서 예상 소모 비용(`Estimated Project Cost`) 및 누적 실제 비용(`Accumulated Actual Cost`) 카드를 제거하고, `isDrawerOpen === true`인 드로어 영역으로 이전. `RaptorWorkflow.tsx` Step 4 헤더의 비용 블록을 전면 제거. 사용자가 명시적으로 `[내 보관함]` 드로어를 열 때만 비용이 렌더링되어 정보 과잉 노출 문제가 해소됨.

---

### R-3. 404 및 에러 캐시 잔재

**해결 방법:** `useWorkflowStore.ts`의 `onRehydrateStorage` 콜백 내부에 방어 코드를 추가하여, 수화 완료 시점에 `finalAssets.script` 배열을 순회하며 깨진 `image_url`을 감지, `null`로 클리어하고 `status: 'waiting'`으로 초기화한다. 이전에 실패한 생성 결과물이 다음 세션까지 잔존하는 문제를 차단함.

---

### R-4. AI 이미지 일괄 생성 버튼 비활성화 누락

**해결 방법:** `RaptorWorkflow.tsx`에 `allImagesReady` 상태를 도출하고, `[AI 이미지 일괄 생성 시작]` 버튼에 `disabled={allImagesReady}` 가드 및 회색조 스타일을 적용. 모든 씬에 유효한 이미지가 이미 할당된 상태에서 의도치 않은 재생성 트리거를 방지함.

---

### R-5. KIE 비디오 파싱 에러 및 예외 처리 오류

**해결 방법 (2건 코드베이스 직접 확인):**

1. **`render_stream` 파싱 로직 비대칭성:** `main.py` L.1568에 `if is_veo:` 조건 가드가 걸려 있어 Grok 엔진 사용 시 `resultJson` 파싱이 통째로 스킵되는 결함을 코드베이스에서 직접 확인. 계획서대로 해당 조건 가드를 제거하고 모든 엔진에 대해 `resultJson → resultUrls` 추출 경로를 적용하면 해소됨.

2. **`generate_videos` fail 케이스 상세 에러 미전달:** `main.py` L.1122–1123에서 `state == 'fail'`일 때 고정 메시지만 던지고 KIE API 응답의 `failMsg`/`reason`을 추출하지 않는 결함을 확인. 계획서대로 `failMsg` 또는 `reason`을 추출해 예외 메시지에 포함하고, `render_stream`의 SSE 예외 전파 파이프라인(L.1626–1628)을 통해 프론트엔드에 전달하면 해소됨.

---

### R-6. `AuthDashboard.tsx` 빈 상태(Empty State) UI 미정의 (NEW-004 부분 해소)

**해결 방법:** 보관함 목록 테이블이 드로어 내부로 이전되면서 UI 재설계가 이루어지는 과정에서, 이력이 없는 사용자에게 노출되던 빈 테이블 프레임 문제가 병행 해소됨. 단, 명시적 Empty State 컴포넌트 적용 여부는 구현 완료 후 사후 검증 필요.

---

## 🟡 [Pending] — 이번 계획에서도 미해결로 추적 관찰이 필요한 잔여 리스크

### P-1. `veo_fast` 모델 단가 누락 (RISK-002 하위 항목)

**기술적 원인:** `kie_pricing.json`을 직접 확인한 결과 `video` 객체에 `veo_lite`와 `grok`만 정의되어 있고 `veo_fast` 항목이 존재하지 않음.

```json
"video": {
    "veo_lite": 0.15,
    "grok": 0.10
    // ← veo_fast 단가 누락
}
```

`RaptorWorkflow.tsx`의 `calculateEstimatedCost`(L.79)는 `pricingData.video[videoEngine]`을 참조하므로, `veo_fast` 선택 시 fallback 값 `0.10`으로 처리되어 예상 비용이 부정확하게 계산됨. 이번 패치 범위에 포함되어 있지 않으므로 지속 추적 필요.

---

### P-2. KIE 단가 동적화 및 다중 사용자 스토리지 쿼터 한계 (RISK-002 본체)

**기술적 원인:** `kie_pricing.json`과 백엔드 라우팅 로직 간 결합도 및 `check_and_enforce_user_limits`의 단일 `beta_tester` 기준 하드코딩 문제는 이번 개편 범위 밖으로 명시됨. 다중 사용자 배포 전 반드시 해소 필요.

---

### P-3. 크로스 플랫폼 폰트 경로 하드코딩 (RISK-003)

**기술적 원인:** `ffmpeg_worker.py`의 자막 합성 경로(`C:/Windows/Fonts/malgun.ttf`)가 Windows 고정. 이번 범위 밖으로 명시되었으나 Docker 또는 Linux 배포 계획 시 선결 조건.

---

### P-4. `hasHydrated` SSR 환경 호환성 미검증 (NEW-001)

**기술적 원인:** 이번 패치에서 `user` 필드가 `partialize` 대상으로 복귀되면 수화(Hydration) 시점 로직이 변경된다. `useWorkflowStore.ts`의 `onRehydrateStorage` 및 `AuthProvider.tsx`의 `hasHydrated` 체크 흐름이 이 변경 이후에도 SSR 환경에서 `window` 참조 없이 안전한지 재검증이 필요하나, 계획서에 명시적 언급이 없음.

---

### P-5. 실사 이미지 업로드 씬 할당 상태 충돌 (NEW-002 미완결)

**기술적 원인:** `Risk_Tracker.md`의 NEW-002 해결 방안은 각 씬에 `image_source: 'manual'` 필드를 도입하여 AI 일괄 생성 루프에서 해당 씬을 스킵하도록 설계하는 것이었다. 그러나 이번 계획서에서 제시된 해결책은 `allImagesReady` 전역 가드(모든 씬에 이미지가 채워진 경우 버튼 전체 비활성화)뿐이다. "일부 씬은 사용자가 직접 업로드, 나머지 씬은 미생성" 혼합 상태에서 `[AI 이미지 일괄 생성]`을 실행하면 수동 업로드 씬이 AI 생성 결과로 덮어씌워질 위험이 여전히 존재한다.

---

### P-6. NEW-003 리스크 트래커 상태 동기화 미완

**기술적 원인:** `main.py` L.1230을 직접 확인한 결과 `"model": request.model or "gpt-image-2"` 폴백이 이미 구현되어 있어, NEW-003(`/api/refine-prompt` 모델 파라미터 기본값 폴백)은 실질적으로 해소된 상태다. 그러나 `Risk_Tracker.md`의 NEW-003 상태가 `[New]`로 남아 있어 `[Resolved]` 업데이트가 필요하다.

---

## 🔴 [New] — 이번 개편 계획에서 새롭게 식별된 잠재적 위험 및 개선 권장 사항

### N-1. `user` 재직렬화로 인한 Stale Supabase 사용자 객체 잔존 위험

**위험 내용:** `user` 필드를 `partialize` 대상에 추가하면, 세션이 만료된 이후에도 이전 로그인 시 직렬화된 Supabase 사용자 객체가 로컬스토리지에 잔존하게 된다. `AuthDashboard.tsx`의 `checkSession`이 완료되기 전까지 stale user 객체가 UI에 반영되는 짧은 ghost user 플래시 현상이 발생할 수 있다. 특히 세션이 만료되었고 `isKeyConfigured`도 false인 경우, 로그아웃 UI가 표시되어야 하지만 만료된 user 객체로 인해 인증된 상태로 오판될 위험이 있다.

**개선 권장:** `onRehydrateStorage` 내에서 `user` 복원 직후 `supabase.auth.getSession()` 결과를 비동기로 확인하고, 세션이 없을 경우 복원된 `user`를 즉시 `null`로 클리어하는 방어 로직을 추가할 것.

---

### N-2. `onRehydrateStorage` URL 필터 False Positive 위험

**위험 내용:** 계획서의 방어 코드는 `image_url`이 `http`로 시작하지 않거나, `error`, `404`, `fail`, `broken` 문자열을 포함할 경우 해당 URL을 클리어한다. 그러나 KIE CDN URL이나 Supabase Storage URL의 파일명 또는 경로에 이 문자열이 포함될 경우 정상적인 URL이 삭제될 수 있다.

**예시 오탐 케이스:**
- `https://cdn.kie.ai/outputs/v1/404abc-scene.mp4` (파일명에 "404" 포함)
- `https://storage.supabase.co/.../error_free_output.mp4` (파일명에 "error" 포함)

**개선 권장:** 필터링 기준을 URL 전체에 대한 문자열 포함 검색 방식이 아닌, URL 구조 자체의 유효성(유효한 프로토콜, 도메인, 최소 경로 길이) 검증 방식으로 교체할 것.

---

### N-3. `allImagesReady` 판별 로직의 엣지 케이스 미정의

**위험 내용:** 계획서에 `allImagesReady` 판별 기준이 "모든 씬에 유효한 `image_url`이 장착된 상태"로만 기술되어 있어, 아래 엣지 케이스에서 버튼 상태가 예측 불가하다:

- 일부 씬이 `status: 'generating'` 상태(`image_url`이 null이지만 생성 진행 중)인 경우 → 버튼이 활성화되어 중복 생성 트리거 가능
- `image_url`이 빈 문자열(`""`)로 설정된 경우 → falsy 체크에서 누락되어 ready로 오판 가능

**개선 권장:** `allImagesReady` 판별 조건을 `every(scene => scene.image_url && scene.image_url.startsWith('http') && scene.status !== 'generating')`으로 명확히 정의할 것.

---

### N-4. `generate_videos` 엔드포인트의 `failMsg` 전파 경로 미명세

**위험 내용:** `render_stream`은 SSE 스트리밍 방식으로 에러를 `yield error JSON`으로 전달하는 파이프라인(L.1626–1628)이 이미 존재하여 계획서의 예외 보강이 유효하다. 그러나 `generate_videos`(L.1122–1123)는 일반 REST API 엔드포인트로, `raise Exception(...)` 형태의 예외가 FastAPI 기본 500 핸들러로 처리된다. 상세 `failMsg`를 클라이언트에 전달하려면 `HTTPException(status_code=500, detail=fail_msg)` 형태로 명시적 변환이 필요하나, 계획서에 이 변환 경로가 기술되어 있지 않다.

**개선 권장:** `generate_videos`의 fail 처리 시 `raise HTTPException(status_code=500, detail=f"비디오 생성 실패: {fail_msg}")` 형태로 명시하고, 프론트엔드 호출부의 에러 핸들러에서 `detail` 필드를 사용자에게 표시하는 경로를 계획서에 추가할 것.

---

### N-5. 드로어 이전 후 비용 카드 초기 렌더링 지연 가능성

**위험 내용:** 비용 카드가 `isDrawerOpen === true`일 때만 렌더링되도록 변경되면, `calculateEstimatedCost()`와 `calculateActualCost()` 함수가 드로어 오픈 시점에 처음 실행된다. Zustand 수화 타이밍에 따라 드로어를 열었을 때 비용이 `0.0000`으로 깜빡이는(flash) 현상이 발생할 수 있다.

**개선 권장:** 드로어 오픈 시 비용 계산이 처음 수행되는 케이스를 대비해 로딩 스켈레톤(skeleton) UI 또는 `useMemo` 기반 사전 캐싱을 적용하여 사용자 경험 상의 값 깜빡임을 방지할 것.

---

## 📊 종합 평가 및 개발 착수 전 권고사항

| 카테고리 | 건수 | 요약 |
|---|---|---|
| **[Resolved]** | 6건 | 5대 핵심 결함 전체 + NEW-004 부분 해소 — 계획 타당성 확인됨 |
| **[Pending]** | 6건 | 4건은 기존 추적 항목 유지, 2건은 계획서 미완결 항목 신규 진입 |
| **[New]** | 5건 | 계획 실행 과정에서 새로 식별된 위험 |

**착수 전 필수 조치 (Blocking):**

1. **P-5 연계 (N-3):** `allImagesReady` 조건 정의를 코드 작성 전 확정할 것. 혼합 씬 케이스(manual 업로드 + 미생성)에 대한 `image_source` 필드 도입 여부를 동시에 결정할 것.
2. **N-4:** `generate_videos`의 `failMsg` 전파를 `HTTPException` 경로로 명세하고 프론트엔드 에러 핸들러 수정 범위를 계획서에 추가할 것.

**착수 전 권고 조치 (Non-Blocking):**

3. **N-2:** URL 필터 기준을 문자열 포함 검색에서 구조 검증 방식으로 교체하는 것을 권고.
4. **N-1:** `onRehydrateStorage`에 stale user 세션 만료 체크 로직 추가를 권고.
5. **P-6:** `Risk_Tracker.md`의 NEW-003 상태를 `[Resolved]`로 즉시 업데이트할 것.
