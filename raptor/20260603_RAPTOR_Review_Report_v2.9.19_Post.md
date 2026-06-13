코드 분석 완료. 이제 보고서를 작성합니다.

---

# RAPTOR V2.9.19 사후 리뷰(Post-Review) 보고서

**Author:** Claude Code
**Date:** 2026-06-03
**Version:** V2.9.19 Post-Review
**대상 패치:** 자동 로그인 바이패스 / 예상 비용 UI 대시보드 이전 / KIE 비동기 이미지 생성 파이프라인 개편

---

## ✅ [Resolved] 해결된 항목

---

### [R-01] 자동 로그인 바이패스 — RaptorWorkflow.tsx 마운트 시 즉시 처리 구현 완료

**검증 위치:** `src/components/RaptorWorkflow.tsx` — 첫 번째 `useEffect` 훅 (마운트 트리거)

```javascript
const store = useWorkflowStore.getState();
if (store.isKeyConfigured) {
  if (!store.user) {
    const mockUser = { id: 'beta_tester', email: 'auto_logged_in@kie.ai' };
    store.setUser(mockUser);
  }
  if (store.step === 0) {
    store.setStep(1);
  }
}
```

마운트 시점에 Zustand 스토어를 직접 참조(`getState()`)하여 `isKeyConfigured === true`인 경우 Mock user 주입과 Step 1 전환을 원자적으로 처리. `if (!store.user)` 조건 가드로 이미 로그인된 세션의 Mock user 중복 덮어씌움도 방지됨. `handleRenderVideo` 함수의 `if (!store.user) return` 체크를 통해 자동 로그인된 Mock user가 렌더링 플로우를 정상 통과함을 확인.

---

### [R-02] 자동 로그인 바이패스 — AuthDashboard.tsx 새로고침 세션 복원 구현 완료

**검증 위치:** `src/components/AuthDashboard.tsx` — `checkSession` 함수 (hasHydrated 의존 useEffect)

```javascript
useEffect(() => {
    if (!hasHydrated) return; // ← Zustand hydration 완료 대기 가드 ✅
    const checkSession = async () => {
        const { data: { session } } = await supabase.auth.getSession();
        if (session?.user) {
            setUser(session.user);
        } else {
            const currentUser = useWorkflowStore.getState().user;
            if (!currentUser) {
                if (store.isKeyConfigured) {
                    const mockUser = { id: 'beta_tester', email: 'auto_logged_in@kie.ai' };
                    setUser(mockUser);
                } else {
                    setUser(null);
                }
            }
        }
    };
    checkSession();
}, [setUser, hasHydrated]);
```

RaptorWorkflow.tsx와 달리 `hasHydrated` 가드를 정확히 적용하여 Zustand hydration 전 조기 실행을 방지. Supabase 세션이 없는 새로고침 상황에서도 `isKeyConfigured`가 복원되어 있으면 Mock user를 자동 복원함. 요건인 "로그인 창 우회" 완벽 충족.

---

### [R-03] Step 3 예상 소모 비용 UI 제거 완료

**검증 위치:** `src/components/RaptorWorkflow.tsx` — `step === 3 && finalAssets` 렌더링 블록 전체

Step 3 헤더 영역(`<div className="flex flex-col md:flex-row ...">`)과 우측 사이드바(`<div className="flex flex-col gap-6">`)를 전수 검사한 결과, 예상 소모 비용 및 실제 누적 비용 UI 요소가 전혀 존재하지 않음을 확인. Step 3 우측 사이드바에는 "Global Asset Pack" 카드만 포함되어 있음. 비용 표시는 Step 4 헤더에만 위치. 요건인 "Step 3 화면 우측 제거" 완전 충족.

---

### [R-04] AuthDashboard 비용 계산 헬퍼 및 통계 카드 UI 마이그레이션 완료

**검증 위치:** `src/components/AuthDashboard.tsx` — `calculateEstimatedCost`, `calculateActualCost` 함수 및 대시보드 카드 섹션

두 헬퍼 함수가 AuthDashboard에 독립적으로 이식되었으며, `pricingData`, `finalAssets`, `imageEngine`, `textEngine`, `claudeModel` 등 필요 상태를 `useWorkflowStore`에서 직접 구독함. 대시보드 통계 카드 UI가 2열 그리드 형태로 구현됨:

```jsx
<div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
    {/* 보라 카드: Estimated Project Cost */}
    <div className="bg-purple-500/5 border border-purple-500/20 rounded-2xl p-5">
        ${calculateEstimatedCost()} USD
    </div>
    {/* 에메랄드 카드: Accumulated Actual Cost */}
    <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-2xl p-5">
        ${calculateActualCost()} USD
    </div>
</div>
```

로그인한 사용자의 대시보드 뷰에서 비용 정보가 카드 형태로 표시됨.

---

### [R-05] `/api/generate-images` — createTask + recordInfo 비동기 폴링 파이프라인 구현 완료

**검증 위치:** `main.py` — `generate_images` 함수 전체

이전 방식의 OpenAI 직접 동기 호출이 완전히 제거되고 KIE 비동기 2단계 파이프라인으로 전환됨:

- **1단계 createTask:** `POST https://api.kie.ai/api/v1/jobs/createTask` 호출 후 `taskId` 추출 (다중 필드 폴백: `taskId` → `data.taskId` → `id` → `data.id`)
- **2단계 recordInfo 폴링:** `GET https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}` 3초 인터벌, 최대 180초 타임아웃. `state == 'success'`시 `resultJson → resultUrls[0]`에서 이미지 URL 추출, 다중 폴백 필드 처리(`image_url`, `file_url`, `url`) 포함
- **에러 처리:** `state == 'fail'` 및 서버 500 응답 즉시 예외 발생, 3회 exponential backoff 재시도(3s → 6s → 12s) 내장
- **모델 기본값:** `request.model or "gpt-image-2"` 안전 폴백 구현 (구 NEW-003 해결)

---

### [R-06] `/api/refine-prompt` — createTask + recordInfo 비동기 폴링 파이프라인 구현 완료

**검증 위치:** `main.py` — `refine_prompt` 함수 내 이미지 생성 블록

이전 RISK-004에서 지적된 `https://api.openai.com/v1/images/generations` 직접 호출 하드코딩이 완전 제거됨:

```python
# 이전 (하드코딩 직접 호출 — 제거됨):
# POST https://api.openai.com/v1/images/generations

# 현재 (KIE 프록시 비동기 파이프라인):
dalle_res = await http_client.post(
    "https://api.kie.ai/api/v1/jobs/createTask",
    json={"model": request.model or "gpt-image-2", ...}
)
task_id = ...
while True:
    poll_res = await http_client.get(
        f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}", ...
    )
    if status == 'success':
        new_image_url = urls[0]
        break
```

`generate_images`와 완전히 동일한 `createTask → recordInfo` 폴링 패턴으로 통일됨. 3회 자동 재시도, 3분 타임아웃, `request.model or "gpt-image-2"` 폴백 모두 내장.

---

### [R-07] NEW-002 — 수동 업로드 이미지 AI 생성 덮어씌움 방지 구현 확인

**검증 위치:** `src/components/RaptorWorkflow.tsx` — `handleGenerateImages` 및 이미지 직접 등록 `onChange` 핸들러

이중 방어 레이어 구현 확인:

```javascript
// 1차 방어: image_url 있으면 일괄 생성 스킵
if (scene.image_url) {
    console.log(`[SKIP] Scene ${index+1} already has an image.`);
    return;
}

// 2차 방어: 수동 업로드 시 image_source 마킹
updateSceneScript(i, 'image_source', 'manual');
```

`image_url` 점유 여부로 스킵하므로, 수동 업로드 씬이 AI 일괄 생성 루프에서 안전하게 보호됨.

---

### [R-08] NEW-003 — `/api/refine-prompt` 모델 파라미터 기본값 폴백 구현 확인

**검증 위치:** `main.py` — `RefinePromptRequest` Pydantic 모델

```python
class RefinePromptRequest(BaseModel):
    model: Optional[str] = "gpt-image-2"  # Pydantic 레벨 기본값
```

Pydantic 레벨과 런타임 폴백(`request.model or "gpt-image-2"`) 이중 방어로 프론트엔드에서 `None`이 넘어와도 422/500 에러 없이 처리됨.

---

### [R-09] NEW-004 — AuthDashboard 빈 상태(Empty State) UI 및 5개 한도 구현 확인

**검증 위치:** `src/components/AuthDashboard.tsx` — 내 보관함 드로어(Drawer) UI

```jsx
} : videos.length === 0 ? (
    <div className="flex flex-col items-center justify-center py-20 gap-4 ...">
        <p className="text-sm font-black text-white">보관함이 비어 있습니다</p>
        <p className="text-xs text-gray-500 ...">아래 워크플로우를 완료하여 첫 번째 쇼핑 숏폼 영상 패키지를 렌더링하고 보관해보세요.</p>
    </div>
) : (
    // 데이터 테이블...
```

전용 Empty State UI 구현됨. 최대 5개 한도는 Supabase 쿼리(`&limit=5`)와 JSON 폴백(`user_records[:5]`) 양쪽에서 일관되게 적용됨.

---

## ⚠️ [Pending] 미해결 잔여 리스크

---

### [P-01] RISK-003 지속 — ffmpeg_worker.py 크로스 플랫폼 폰트 경로 하드코딩

**관련 파일:** `backend/services/ffmpeg_worker.py:213`
**영향도:** 보통 (Medium)

소스 코드 직접 확인 결과, 폰트 경로 하드코딩이 그대로 잔존:

```python
font_path = "C:/Windows/Fonts/malgun.ttf".replace(":", "\\:")
```

V2.9.19 패치 범위에 `ffmpeg_worker.py`가 포함되지 않아 미해결 상태 지속. Linux/Docker 배포 환경에서 `drawtext` 필터 적용 시 폰트 파일을 찾지 못해 자막 합성이 중단될 위험이 있음.

---

### [P-02] RISK-002 지속 — check_and_enforce_user_limits의 다중 사용자 대응 미비

**관련 파일:** `main.py` — `check_and_enforce_user_limits` 함수

```python
async def check_and_enforce_user_limits(user_id: str = "beta_tester"):
```

함수 파라미터 기본값이 `beta_tester`로 고정되어 있으며, `render_stream`에서 Mock user인 경우 `jwt_user_id`가 `request.user_id` 값(프론트엔드의 `store.userId`, 기본값 `'beta_tester'`)으로 세팅됨. 결국 모든 Mock user가 단일 `beta_tester` 쿼터를 공유함.

추가로, FIFO 삭제 로직의 동시 쓰기 취약점도 잔존:

```python
if len(user_records) >= 5:
    to_delete = user_records[:len(user_records) - 4]
    for old_rec in to_delete:
        ...
        records = [r for r in records if r.get("task_id") != old_task]
with open(db_path, "w", ...) as f:
    json.dump(records, ...)
```

`user_videos_beta.json` 파일에 대한 파일 락(lock) 메커니즘이 없어, 복수 렌더링 요청이 동시에 들어올 경우 JSON DB의 race condition이 발생할 수 있음.

---

### [P-03] NEW-001 부분 해결 — RaptorWorkflow.tsx 자동 로그인의 hasHydrated 미체크

**관련 파일:** `src/components/RaptorWorkflow.tsx` — 마운트 useEffect
**영향도:** 높음 (High, 조건적)

`AuthDashboard.tsx`는 `if (!hasHydrated) return`으로 Zustand hydration 완료를 명시적으로 대기하지만, `RaptorWorkflow.tsx`의 자동 로그인 로직은 `hasHydrated` 체크 없이 직접 스토어를 참조함:

```javascript
// AuthDashboard.tsx — 올바른 패턴
useEffect(() => {
    if (!hasHydrated) return; // ✅ 가드 있음
    ...
}, [setUser, hasHydrated]);

// RaptorWorkflow.tsx — 불완전한 패턴
useEffect(() => {
    setMounted(true);
    ...
    const store = useWorkflowStore.getState(); // ❌ hasHydrated 체크 없음
    if (store.isKeyConfigured) { ... }
}, [setErrorMessage]);
```

localStorage 기반 Zustand persist는 동기적으로 hydration되므로 대부분의 환경에서 실제 장애가 발생하지 않음. 그러나 저사양 디바이스, 스토리지 용량 임박 상황, 또는 향후 비동기 스토리지(IndexedDB) 전환 시 `isKeyConfigured`가 `false`로 읽혀 자동 로그인이 무시되는 레이스 컨디션이 잠재함.

---

## 🆕 [New] 신규 식별 리스크

---

### [N-01] AuthDashboard calculateEstimatedCost의 videoEngine 하드코딩 불일치

**관련 파일:** `src/components/AuthDashboard.tsx` — `calculateEstimatedCost` 함수
**영향도:** 낮음 (Low)

`AuthDashboard.tsx`에서 비디오 단가를 `'grok'`으로 하드코딩:

```javascript
// AuthDashboard.tsx — 고정값
const vidUnit = pricingData.video['grok'] || 0.10; // ❌ 항상 $0.10

// RaptorWorkflow.tsx — 동적 참조
const vidUnit = pricingData.video[videoEngine as keyof typeof pricingData.video] || 0.10; // ✅
```

`kie_pricing.json` 분석 결과 `veo_lite: 0.15`, `grok: 0.10`으로 단가가 다름. `veo_fast`는 JSON에서 **누락**됨(기존 RISK-002에서 언급된 veo_fast 단가 누락 문제 지속). 사용자가 `veo_lite`(0.15) 또는 `veo_fast`(단가 미정) 엔진을 선택해도 AuthDashboard에서는 항상 grok 기준($0.10)으로 비용이 표시되어 실제 비용과 괴리 발생. 또한 `videoEngine`은 `RaptorWorkflow.tsx`의 로컬 `useState`이므로 AuthDashboard에서 원천적으로 접근 불가.

**권장 수정:** `videoEngine` 상태를 `useWorkflowStore`로 끌어올려 persist 대상에 포함하거나, 비용 계산 공통 유틸리티 함수를 `src/lib/` 하위로 분리하여 양 컴포넌트가 동일 로직을 공유하도록 설계.

---

### [N-02] Step 4 비용 UI 잔존 — 대시보드와 이중 표시

**관련 파일:** `src/components/RaptorWorkflow.tsx` — Step 4 헤더 영역
**영향도:** 낮음 (Low)

패치 요건이 "AuthDashboard로 완전히(完全히) 마이그레이션"이었으나, Step 4 헤더에 비용 표시 UI가 잔존:

```jsx
{/* Step 4 헤더 — 잔존 */}
<span>💸 예상 소모 비용: 약 ${calculateEstimatedCost()}</span>
<span>💰 실제 누적 비용: 약 ${calculateActualCost()}</span>
```

로그인한 사용자는 AuthDashboard 대시보드와 Step 4 헤더 양쪽에서 동일한 비용 정보를 이중으로 보게 됨. 이 상황이 의도된 설계(렌더링 컨텍스트 내 즉시 참조)라면 기획서에 명시 필요. 그렇지 않다면 Step 4에서도 해당 UI 제거 검토 권장.

---

### [N-03] 자동 로그인 useEffect dependency array 불완전 — 키 설정 후 즉시 로그인 미트리거

**관련 파일:** `src/components/RaptorWorkflow.tsx` — 마운트 useEffect
**영향도:** 보통 (Medium)

```javascript
useEffect(() => {
    ...
    const store = useWorkflowStore.getState();
    if (store.isKeyConfigured) { ... } // 마운트 당시 상태만 체크
}, [setErrorMessage]); // ❌ isKeyConfigured 미포함
```

`useEffect`의 dependency array에 `isKeyConfigured`가 포함되지 않아, 자동 로그인 체크가 컴포넌트 마운트 시 1회만 실행됨. 사용자가 BYOKSettingsForm에서 API Key를 신규 입력하여 `isKeyConfigured`가 `false → true`로 변경되더라도, 이미 Step 0에 있는 상태에서는 자동 Step 1 전환이 트리거되지 않음 — 별도의 페이지 새로고침이 필요함.

**권장 수정:** BYOKSettingsForm.tsx에서 키 설정 성공 후 `setStep(1)` 명시 호출을 추가하거나, 아래와 같이 별도 effect 분리:

```javascript
const isKeyConfigured = useWorkflowStore(s => s.isKeyConfigured);
useEffect(() => {
    if (isKeyConfigured && !user && step === 0) {
        store.setUser(mockUser);
        setStep(1);
    }
}, [isKeyConfigured]);
```

---

### [N-04] review_plan 엔드포인트의 Windows 절대 경로 하드코딩

**관련 파일:** `main.py` — `/api/auth/review-plan` 엔드포인트
**영향도:** 보통 (Medium)

```python
brain_base_dir = r"C:\Users\webke\.gemini\antigravity-ide\brain"
```

특정 개발자의 Windows 로컬 환경에 종속된 절대 경로가 하드코딩되어 있음. RISK-003(`ffmpeg_worker.py` 폰트 경로)과 동일한 패턴의 크로스 플랫폼 이슈. Linux 서버나 Docker 배포 시 `os.path.exists()` 판정이 False로 평가되어 fallback으로 graceful 처리가 되어있으나, 의도한 brain 디렉토리를 전혀 탐색하지 못함. 운영 환경 배포 전 `BRAIN_BASE_DIR` 환경 변수화 필요.

---

### [N-05] `kie_pricing.json`에서 veo_fast 단가 누락 — 비용 계산 폴백 의존

**관련 파일:** `src/config/kie_pricing.json`
**영향도:** 보통 (Medium)

실제 JSON 파일을 직접 확인한 결과:

```json
"video": {
    "veo_lite": 0.15,
    "grok": 0.10
    // "veo_fast" 항목 없음 ❌
}
```

`RaptorWorkflow.tsx`의 엔진 선택 드롭다운에는 `veo_fast` 옵션이 존재하나 단가 데이터가 JSON에서 누락되어 있어, 비용 계산 시 `|| 0.10` 폴백값(grok 단가)으로 처리됨. 실제 veo_fast 단가가 0.10보다 높을 경우 비용이 과소 계산되어 사용자에게 오해를 줄 수 있음. 기존 RISK-002에서 예고된 항목이나 이번 패치에서 미해소.

---

### [N-06] generate_images API의 단일 씬 처리 구조적 불일치

**관련 파일:** `main.py` — `/api/generate-images` 엔드포인트
**영향도:** 낮음 (Low)

```python
for scene in request.scenes:
    prompt = scene.get('image_prompt', '')
    if not prompt: continue
    ...
    return {"data": [{"url": image_url}]}  # 첫 번째 성공 씬에서 즉시 반환
```

`ImageGenRequest`는 `scenes: List[dict]`를 받도록 정의되어 있어 배치 처리가 가능한 것처럼 보이지만, 실제로는 첫 번째 유효 씬 처리 후 즉시 `return`하여 나머지 씬이 처리되지 않음. 현재 프론트엔드의 `handleGenerateImages`는 씬별로 개별 API 호출을 하므로 실제 장애는 없지만, API 계약(contract)과 실제 동작 사이의 불일치가 향후 배치 처리 시도나 API 재활용 시 혼란을 야기할 수 있음.

---

## 리스크 현황 요약 (업데이트)

| 상태 | 항목 수 | 주요 항목 |
|------|---------|-----------|
| **[Resolved]** | **9건** | 자동 로그인 바이패스 (R-01, R-02), 비용 UI 이전 (R-03, R-04), KIE 비동기 파이프라인 (R-05, R-06), 수동 이미지 방어 (R-07), 모델 폴백 (R-08), Empty State UI (R-09) |
| **[Pending]** | **3건** | ffmpeg 폰트 하드코딩 (P-01), FIFO 다중 사용자 쿼터 (P-02), hasHydrated 레이스 컨디션 (P-03) |
| **[New]** | **6건** | AuthDashboard videoEngine 비용 불일치 (N-01), Step 4 비용 이중 표시 (N-02), 키 설정 후 로그인 미트리거 (N-03), Windows 경로 하드코딩 (N-04), veo_fast 단가 누락 (N-05), generate_images 배치 불일치 (N-06) |

---

**종합 평가:** 3대 핵심 수술 요건(자동 로그인 바이패스, 비용 UI 마이그레이션, KIE 비동기 파이프라인)은 코드 레벨에서 모두 정확히 구현됨. 특히 `refine_prompt`의 OpenAI 직접 호출 제거와 createTask/recordInfo 폴링 통일은 RISK-004 완결 이후의 아키텍처 일관성을 크게 향상시켰음. 다음 스프린트 우선 처리 권장 항목은 **N-01 (AuthDashboard videoEngine 비용 불일치)**, **N-03 (키 설정 후 자동 로그인 미트리거)**, **N-05 (veo_fast 단가 누락)** 3건.
