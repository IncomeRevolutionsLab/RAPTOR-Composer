 # RAPTOR V2.9.21 프론트엔드 비디오 렌더링 예외 처리 강화 핫픽스 — 사후 리뷰(Post-Review) 보고서

**Author: Claude Code**
**작성일:** 2026-06-04
**대상 버전:** RAPTOR V2.9.21
**검토 범위:** `src/components/RaptorWorkflow.tsx`, `src/store/useWorkflowStore.ts`, `src/lib/api-client.ts`, `backend/services/ffmpeg_worker.py`, `main.py`, `src/config/kie_pricing.json`

---

## ✅ [Resolved] — 이번 패치로 완전히 해결된 항목

### R-01: `handleRenderVideo` catch 블록 에러 UI 노출 미흡 (NEW-006 완결)

수술 계획서에서 명시한 핵심 결함이다. 패치된 `RaptorWorkflow.tsx`의 `handleRenderVideo` 함수 catch 블록을 확인한 결과, 다음 세 가지 처리가 모두 정상적으로 구현되어 있음을 확인했다.

**`response.ok` false 시 에러 파싱 및 throw:**

```typescript
if (!response.ok) {
  let errorDetail = `API Error (${response.status})`;
  try {
    const errorData = await response.json();
    if (errorData && errorData.detail) {
      errorDetail = errorData.detail;
    }
  } catch (err) { ... }
  throw new Error(errorDetail);
}
```

백엔드 500 에러 발생 시 `response.json()`을 통해 `detail` 메시지를 파싱하여 명시적 Error를 throw하는 로직이 완성되어 있다.

**catch 블록 내 `setErrorMessage` 호출:**

```typescript
setErrorMessage(errorMsg);
setRenderStatus(false, 0);
```

에러가 발생하면 Zustand 스토어의 `setErrorMessage`를 통해 화면 상단의 "System Fault Detected" 오버레이에 에러 메시지가 즉시 노출되며, `isRendering` 상태도 `false`로 해제된다.

**미완료 씬 status 롤백:**

```typescript
const rolledBackScript = latestAssets.script.map((scene: any) => {
  if (!scene.video_url && !scene.use_image_only) {
    return { ...scene, status: 'error', error: e.message || '렌더링 중단' };
  }
  return scene;
});
setFinalAssets({ ...latestAssets, script: rolledBackScript });
```

비디오 URL이 없고 스틸컷 모드도 아닌 미완료 씬들이 모두 `'error'` 상태로 명확히 롤백되어 무한 대기 UX가 방지된다. **완전 해결 확인.**

---

### R-02: Visual Tracker stage4/stage5 에러 판단 조건 보강

수술 계획서 패치 항목 4번에서 요구한 VT 컴포넌트의 에러 분기 조건을 소스 코드에서 직접 확인했다.

```typescript
let stage4Status = 'waiting';
if (completedVideos === totalScenes && totalScenes > 0) stage4Status = 'success';
else if (errorMessage) stage4Status = 'error';
else if (isRendering && renderProgress < 50) stage4Status = 'active';
else if (completedVideos > 0) stage4Status = 'active';

let stage5Status = 'waiting';
if (renderedVideoUrl) stage5Status = 'success';
else if (renderProgress >= 50 && errorMessage) stage5Status = 'error';
else if (isRendering && renderProgress >= 50) stage5Status = 'active';
```

`errorMessage`가 존재할 경우 stage4는 즉시 `'error'`로, stage5는 `renderProgress >= 50` 조건과 결합하여 `'error'`로 전환된다. VT UI가 '오류/중단' 뱃지(붉은 pulse 애니메이션)로 정확히 표시되는 구조이다. **완전 해결 확인.**

---

### R-03: WAF 우회 KIE HTTP 클라이언트 구현 (RISK-004 연계)

`main.py`의 `KIEHTTPClient` 클래스에서 WAF 차단 우회 로직이 완성되어 있다.

```python
class KIEHTTPClient(httpx.Client):
    def send(self, request, *args, **kwargs):
        if "x-api-key" in request.headers:
            del request.headers["x-api-key"]
        request.headers["Authorization"] = f"Bearer {self.decrypted_key}"
        request.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
        return super().send(request, *args, **kwargs)
```

`x-api-key` 헤더를 제거하고 `Authorization: Bearer` 방식으로 교체하며, 브라우저 User-Agent를 주입하여 WAF 필터링을 우회한다. Claude API 호출 시 이 클라이언트가 일관되게 적용되는 것을 모든 관련 엔드포인트(`/generate-plan`, `/refine-prompt`, `/auth/review-plan`, `/auth/post-review`)에서 확인했다. **완전 해결 확인.**

---

### R-04: `kie_pricing.json` 단가 연동 구현 (RISK-004 연계)

`RaptorWorkflow.tsx`의 `calculateEstimatedCost` 함수에서 `pricingData`를 직접 import하여 단가를 조회한다.

```typescript
import pricingData from '@/config/kie_pricing.json';
...
const textCost = pricingData.text[(textEngine || claudeModel) as keyof typeof pricingData.text] || 0.015;
const imgUnit = pricingData.image[imageEngine as keyof typeof pricingData.image] || 0.03;
const vidUnit = pricingData.video[videoEngine as keyof typeof pricingData.video] || 0.10;
```

하드코딩에서 JSON 기반 동적 단가 참조로 전환이 완료되었으며, 키가 없을 경우 폴백 값이 명시되어 있다. **완전 해결 확인.**

---

### R-05: FFmpeg tpad 동기화 필터 및 비디오 트림 처리

`ffmpeg_worker.py`에서 비디오가 씬 길이보다 짧을 경우의 처리와, 비디오가 오디오보다 짧을 때 마지막 프레임을 freeze하는 `tpad` 필터가 구현되어 있다.

```python
if video_duration > 0.0 and duration > video_duration:
    freeze_dur = duration - video_duration
    filter_str += f",tpad=stop_mode=clone:stop_duration={freeze_dur}"
```

`tpad` 필터가 drawtext 자막 필터 앞에 위치하여, 연장된 프레임에도 자막이 온전히 오버레이되는 설계가 확인된다. **완전 해결 확인.**

---

### R-06: `Film` import 누락 크래시 해결 (HOT-001 완결)

```typescript
import { ..., Film } from 'lucide-react';
```

import 선언부에 `Film`이 올바르게 포함되어 있어 JSX 렌더링 크래시가 해결되었다. **완전 해결 확인.**

---

### R-07: CSRF 토큰 이중 방어 및 세션 바인딩 구현

`handleRenderVideo` 내에서 CSRF 토큰 선취득 로직과 Supabase JWT 세션 바인딩이 모두 구현되어 있다.

```typescript
const { data: { session } } = await supabase.auth.getSession();
if (session?.access_token) {
  headers['Authorization'] = `Bearer ${session.access_token}`;
}
```

백엔드 `render-stream` 엔드포인트에서도 PyJWT로 HS256 서명을 검증하고 `sub` 클레임에서 `user_id`를 추출하는 로직이 완성되어 있다. **완전 해결 확인.**

---

## 🟡 [Pending] — 여전히 추적 관찰이 필요한 잔여 리스크

### P-01: `veo_fast` 단가 `kie_pricing.json` 누락 (RISK-002 계속)

```json
"video": {
  "veo_lite": 0.15,
  "grok": 0.10
}
```

`veo_fast` 키가 없다. `calculateEstimatedCost` 함수에서 폴백 값 `0.10`(grok과 동일)으로 처리되어 실제 비용보다 낮게 추정될 가능성이 있다. UI에서 `veo_fast` 엔진은 명백히 선택 가능하지만 단가가 미정의 상태이다. 정식 단가 확인 후 추가 필요.

---

### P-02: FIFO 정리 임계값 불일치 (N-05 계속)

`check_and_enforce_user_limits()`에서는 50개 이상 시 49개 보존, `webhook_kie()`에서는 50개 초과 시 50개 보존으로 기준이 여전히 다르다. 코드가 변경되지 않았으므로 N-05가 그대로 잔존한다.

---

### P-03: 크로스 플랫폼 폰트 하드코딩 (RISK-003 계속)

```python
font_path = "C:/Windows/Fonts/malgun.ttf".replace(":", "\\:")
```

이번 패치에서 전혀 수정되지 않았다. Docker/Linux 배포 환경에서 자막 합성이 실패하는 근본 원인이 해소되지 않은 상태다.

---

### P-04: Mock 자동 인증 우회 로직 (N-06 계속)

```typescript
// RaptorWorkflow.tsx useEffect
if (store.isKeyConfigured) {
  if (!store.user) {
    const mockUser = { id: 'beta_tester', email: 'auto_logged_in@kie.ai' };
    store.setUser(mockUser);
  }
  ...
}
```

프로덕션 환경 분기 없이 Mock 계정이 발급되는 로직이 그대로 존재한다. `IS_PROD` 환경변수가 백엔드에는 정의되어 있으나 프론트엔드에는 적용되지 않아, 실서비스 배포 시 인증 체계가 우회될 위험이 여전히 존재한다.

---

### P-05: `hasHydrated` SSR 환경 호환성 (NEW-001 계속)

```typescript
storage: createJSONStorage(() => (typeof window !== 'undefined' ? localStorage : sessionStorage)),
```

`typeof window` 가드가 storage 레벨에서만 적용되어 있고, `onRehydrateStorage` 콜백 내 `state.setFinalAssets()` 등이 SSR 환경에서 호출될 경우의 방어 처리가 여전히 불완전하다.

---

### P-06: 미사용 import Dead Code (PND-001, PND-002 계속)

```typescript
import { ..., Share2, ..., RefreshCw, ... } from 'lucide-react';
```

`Share2`와 `RefreshCw`가 import 선언에는 있으나 컴포넌트 본문에서 사용되지 않는다. 이번 패치에서 `Film`은 정상 추가되었으나 두 Dead Code import는 미정리 상태다.

---

### P-07: Ghost User 세션 노출 (NEW-005 계속)

`useWorkflowStore.ts`의 `onRehydrateStorage` 콜백에서 user 정보를 즉시 클리어하는 로직이 없다. 세션 만료 후 새로고침 시 Zustand 로컬 스토리지에서 복원된 user 객체가 Supabase 비동기 세션 확인 전에 일시 노출되는 현상이 해소되지 않았다.

---

## 🔴 [New] — 소스 코드 분석 과정에서 새롭게 식별된 리스크

### NEW-A: `BYOKSettingsForm.tsx`에서 새로고침마다 Post-Review 자동 트리거 — 보안 및 성능 리스크

```typescript
// BYOKSettingsForm.tsx useEffect
api.get('/auth/post-review')
  .then(res => {
    console.log("Post-review triggered and report generated", res);
  })
```

브라우저 새로고침(F5) 시마다 `/auth/post-review`가 자동으로 호출된다. 이 엔드포인트는 Claude API를 호출하고 파일 시스템에 리포트를 기록하는 고비용 작업이다. 실서비스 환경에서 사용자가 새로고침할 때마다 KIE 크레딧이 소모되고, 파일 시스템에 리포트가 무한히 누적되는 문제가 발생할 수 있다. 또한 이 호출은 `raptor_key` 쿠키 없이도 `GET` 요청으로 시도되므로 401 에러가 콘솔에 반복 출력된다(`catch`의 `console.warn`으로 조용히 처리되지만). **개발 전용 기능으로 명시적으로 분리하거나 제거해야 한다.**

---

### NEW-B: `ffprobe` 경로 분기가 Windows 전용으로 하드코딩 — 크로스 플랫폼 오류

```python
cmd_dur = [
    os.path.join(os.getcwd(), "ffprobe.exe") if os.path.exists(os.path.join(os.getcwd(), "ffprobe.exe")) else "ffprobe",
    ...
]
```

`ffprobe.exe` 경로를 먼저 탐색하는 방식이 Windows 환경에 편향되어 있다. `ffmpeg_path`는 `imageio_ffmpeg.get_ffmpeg_exe()`로 플랫폼에 독립적으로 결정되지만, `ffprobe`는 동일한 처리 없이 수동 탐색에 의존한다. Linux/Docker 환경에서 `ffprobe.exe`가 없으면 `ffprobe` 시스템 명령에 fallback하는데, 시스템에 ffprobe가 설치되지 않은 경우 오디오 duration 측정이 실패하여 `duration = 4.0`으로 하드코딩 폴백된다. `imageio_ffmpeg`에서 ffprobe 경로도 함께 획득하거나 `which ffprobe`로 동적 탐색하는 방식으로 개선해야 한다.

---

### NEW-C: `main.py` `/api/auth/review-plan` 엔드포인트의 절대 경로 하드코딩

```python
brain_base_dir = r"C:\Users\webke\.gemini\antigravity-ide\brain"
```

특정 개발자 로컬 머신 경로가 프로덕션 코드에 하드코딩되어 있다. 다른 개발자 환경이나 서버 배포 시 이 경로가 존재하지 않아 `os.path.exists(brain_base_dir)`가 `False`를 반환하고 fallback으로 `os.getcwd()`를 사용하게 되어 예상치 못한 경로에 파일이 생성될 수 있다. 환경 변수로 추출이 필요하다.

---

### NEW-D: `api-client.ts`의 `localhost:8000` 하드코딩 — 멀티 환경 배포 불가

```typescript
const response = await fetch(`http://localhost:8000/api${path}`, fetchOptions);
```

`api-client.ts` 전체와 `RaptorWorkflow.tsx` 내 