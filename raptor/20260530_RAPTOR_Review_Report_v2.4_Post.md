 # RAPTOR V2.2 사후 리뷰(Post-Review) 보고서

**Author: Claude Code**
**작성일: 2026-06-03**
**검토 대상: RAPTOR V2.2 상용화 UX 대개편 및 KIE 모델/동적 비용 관리 패치 코드베이스**

---

## ✅ [Resolved] — 완결 처리된 핵심 결함 및 구현 완료 항목

### 1. API 타임아웃 해제 및 세션 유지 (RISK-004)

`src/lib/api-client.ts`를 분석하면, 기존에 문제가 되었던 120초 하드코딩 타임아웃이 완전히 제거되고 `1800000ms`(30분)으로 대체되어 있음을 확인했다.

```typescript
const timeoutId = setTimeout(() => controller.abort(), 1800000); // 30 mins timeout
```

`useWorkflowStore.ts`의 `partialize` 옵션을 보면, `isRendering`, `renderProgress`, `renderedVideoUrl` 등의 volatile 상태가 영속화 대상에서 제외되어 있다. 이에 따라 새로고침 시 렌더링 진행 상태가 자동으로 초기화된다. 또한 `RaptorWorkflow.tsx`의 `useEffect` 내에서 마운트 시점에 명시적으로 `setRenderStatus(false, 0)`을 호출하여 이중으로 보장하고 있다. 이전에 존재하던 `confirm` 팝업 로직 역시 제거되었음을 코드 전반에서 확인했다.

### 2. WAF 우회 및 단일 KIE API 키 아키텍처 (RISK-004)

`main.py`를 분석하면, KIE API 키가 Fernet 대칭키 암호화(`cryptography.fernet.Fernet`)를 통해 서버측에서 안전하게 암·복호화되고, HttpOnly 쿠키(`raptor_key`)에만 저장됨을 확인했다. 프론트엔드에 키 값이 노출되는 경로가 차단되었다.

`KIEHTTPClient` 클래스가 `httpx.Client`를 상속하여 모든 아웃바운드 요청에서 `Authorization: Bearer {decrypted_key}` 헤더와 일반 브라우저 `User-Agent`를 자동 주입한다. 이는 WAF 우회 아키텍처가 의도대로 완성되었음을 입증한다.

`BYOKSettingsForm.tsx`는 `[🔑 KIE API Key]` 단일 입력 필드만 노출하며, `useWorkflowStore.ts`에서 `kieKey`가 `isKeyConfigured` 단일 상태로 통합 관리된다. 하위 호환성 측면에서는 백엔드 `get_decrypted_key` 의존성 주입 함수가 단일 `raptor_key` 쿠키로부터 키를 복호화하여 모든 엔드포인트에 공급하는 구조가 완성되어 있다.

### 3. FFmpeg 오디오-비디오 싱크 픽스 (RISK-004)

`backend/services/ffmpeg_worker.py`에서 `tpad` 필터 적용 로직을 확인했다.

```python
if video_duration > 0.0 and duration > video_duration:
    freeze_dur = duration - video_duration
    filter_str += f",tpad=stop_mode=clone:stop_duration={freeze_dur}"
```

비디오 재생 시간(`video_duration`)을 FFprobe로 측정한 후, TTS 오디오 길이(`duration`)가 더 길 때 `tpad=stop_mode=clone` 으로 마지막 프레임을 복제·정지시켜 오디오가 끝날 때까지 연장하는 로직이 정확히 수술 계획서의 설계대로 구현되어 있다. 기존 `-stream_loop -1` 방식은 코드에서 확인되지 않는다.

### 4. process_scene False Fallback 로직 철거 (RISK-004)

`main.py`의 `/api/render-stream` 엔드포인트 내 `process_scene` 함수를 분석한 결과, 예외 발생 시 `use_image_only: True`로 강제 덮어씌우던 try-catch Fallback 블록이 존재하지 않는다. 비디오 생성 실패 시 `raise Exception(...)` 으로 예외를 상위로 전파하고, SSE 스트림에서 `error` 이벤트로 클라이언트에 즉시 통보하는 구조가 확인된다.

### 5. 5단계 UX 분리 (Step 3 / Step 4) (P1 구현 완료)

`RaptorWorkflow.tsx`에서 Step 3과 Step 4가 명확하게 분리되어 있음을 확인했다. Step 3에서는 이미지 생성 및 에셋 편집만 이루어지고, `[🎬 비디오 생성/렌더링 단계로 이동 (Step 4)]` 버튼을 통해 명시적으로 Step 4로 전환하도록 설계되어 있다. Step 4에서 비로소 비디오 엔진, 성우, 재생 길이를 설정하고 `[🎬 최종 비디오 렌더링 시작]` 버튼이 노출된다.

### 6. kie_pricing.json 외부 단가 파일 분리 및 비용 대시보드 연동 (P1 구현 완료)

`src/config/kie_pricing.json`이 신설되었고, `credit_rate`, `text`, `image`, `video`, `tts` 단가가 정의되어 있음을 확인했다. `RaptorWorkflow.tsx`에서 이 파일을 동적으로 import하여 `calculateEstimatedCost()`와 `calculateActualCost()` 함수가 실시간으로 예상 소모 비용 및 실제 누적 비용을 계산한다. `credits_consumed` 필드가 `process_scene_inner` 내에서 KIE API 폴링 응답으로부터 추출되어 씬 데이터에 주입되고 있다.

### 7. ZIP 다운로드 타임스탬프 및 무결성 보완 (P0 구현 완료)

`handleDownloadPackage` 함수에서 `YYYYMMDD_HHMMSS` 포맷의 타임스탬프가 파일명에 부착되고, ZIP 파일 내 항목으로 최종 비디오, 썸네일, 씬별 이미지, 프롬프트 텍스트, 대사 텍스트, 업로드 패키지 텍스트 6종이 모두 포함됨을 코드에서 확인했다.

### 8. refine-prompt DALL-E 직접 호출 에러 해결 (RISK-004)

`main.py`의 `/api/refine-prompt` 엔드포인트에서 이미지 재생성 API 호출 URL이 `https://api.kie.ai/v1/images/generations`으로 교체되어 있음을 확인했다. OpenAI 직접 호출로 인한 잔존 에러가 완결 처리되었다.

### 9. NEW-002: 실사 이미지 업로드 씬 할당 상태 충돌 방지

`RaptorWorkflow.tsx`의 `handleGenerateImages` 함수 내에서 `scene.image_source === 'manual'` 조건으로 수동 업로드 씬을 AI 일괄 생성 루프에서 스킵하는 로직이 구현되어 있음을 확인했다. `updateSceneScript(i, 'image_source', 'manual')` 호출도 파일 업로드 핸들러에 적용되어 있다.

### 10. NEW-003: 모델 파라미터 기본값 폴백

`/api/generate-images` 및 `/api/refine-prompt` 엔드포인트 모두에서 `request.model or "gpt-image-2"` 폴백이 적용되어 있어, 프론트엔드에서 모델이 누락될 경우에도 안전하게 기본값을 사용한다.

---

## 🟡 [Pending] — 잔여 리스크 및 추적 관찰 필요 항목

### 1. RISK-002: Supabase FIFO 쿼터 로직의 다중 사용자 비안전성

`check_and_enforce_user_limits` 함수가 `user_videos_beta.json`이라는 로컬 파일 기반 DB를 사용하며, 파일 읽기-수정-쓰기가 `await` 없이 동기 방식(`open`, `json.load`, `json.dump`)으로 순차 처리된다. 다중 사용자 동시 렌더링 환경에서 Race Condition으로 인해 FIFO 삭제 로직이 오작동하거나 레코드가 손상될 위험이 여전히 존재한다. Supabase 연동이 옵션(try/except로 실패 무시)으로만 처리되어 있어 실서비스 전환 시 구조 정비가 필요하다.

### 2. RISK-003: 크로스 플랫폼 폰트 경로 하드코딩

`backend/services/ffmpeg_worker.py`에서 `font_path = "C:/Windows/Fonts/malgun.ttf"` 가 코드에 그대로 남아 있다. 수술 계획서에서 이번 개편 범위 밖으로 명시했으나, 리스크 트래커의 상태가 여전히 `[New]`로 유지되어야 하며 Docker 또는 Linux 배포 전환 시 즉시 터지는 P0 결함이다.

### 3. NEW-001: hasHydrated SSR 환경 호환성

`useWorkflowStore.ts`의 `storage` 설정에서 `typeof window !== 'undefined' ? localStorage : sessionStorage`로 SSR 가드가 적용되어 있으나, `BYOKSettingsForm.tsx`의 `useEffect`에서 `hasHydrated`를 의존성으로 사용하는 패턴이 완전한 보장은 아니다. `hasHydrated`가 `false`인 동안 `api.get('/auth/check-key')`가 억제되지만, Next.js App Router 환경에서의 스트리밍 SSR 시나리오에서 추가 검증이 권장된다.

### 4. NEW-004: AuthDashboard.tsx Empty State

본 패치에 포함된 소스 코드 목록에 `AuthDashboard.tsx`가 포함되지 않아 구현 여부를 직접 검증할 수 없었다. 리스크 트래커에 해결로 표기되어 있으나, 제공된 코드만으로는 완결을 입증하기 어렵다.

### 5. `veo_fast` 엔진 단가 미정의

`kie_pricing.json`의 `video` 섹션에 `veo_lite`와 `grok`만 정의되어 있으며, `veo_fast` 키가 없다. `RaptorWorkflow.tsx`의 `calculateEstimatedCost()` 함수에서 `pricingData.video[videoEngine]`를 조회할 때 `veo_fast`가 선택되면 `undefined`가 반환되어 `|| 0.10`(grok 기본값) 폴백이 적용된다. 요금 산정 오류로 이어질 수 있다.

---

## 🔴 [New] — 신규 식별된 잠재 위험 및 개선 권장 사항

### 1. BYOKSettingsForm에서 새로고침마다 Post-Review 자동 트리거

`BYOKSettingsForm.tsx`의 `useEffect` 내에 `api.get('/auth/post-review')` 호출이 삽입되어 있다. 이는 사용자가 페이지를 새로고침할 때마다 백엔드에서 Claude API를 실제로 호출하여 리뷰 보고서를 생성함을 의미한다. 인증된 사용자에게 매 새로고침마다 KIE 크레딧이 소모된다. 또한 해당 엔드포인트가 `GET` 방식으로 설계되어 CSRF 검증을 받지 않는다. 자동 트리거는 명시적인 관리자 액션이나 전용 UI 버튼을 통해서만 호출되도록 격리하는 것이 강력히 권장된다.

### 2. generate-images 응답 구조 가정의 취약성

`RaptorWorkflow.tsx`의 `handleGenerateImages`에서 이미지 URL을 `res?.data?.[0]?.url` 또는 `res?.data?.[0]?.b64_json`으로 추출한다. 그런데 `main.py`의 `/api/generate-images` 엔드포인트는 KIE API 응답을 그대로 `return response.json()`으로 반환한다. KIE API의 응답 스키마가 OpenAI 표준과 완전히 동일하다는 보장이 없으며, `nano-banana-2`나 `grok` 이미지 모델이 선택될 경우 응답 필드명이 다를 수 있다. 방어적인 응답 스키마 정규화 레이어가 백엔드에 부재하다.

### 3. ffprobe 경로 처리의 Windows 의존성 잔존

`ffmpeg_worker.py`에서 FFprobe 실행 파일 경로를 아래와 같이 탐색한다.

```python
os.path.join(os.getcwd(), "ffprobe.exe") if os.path.exists(os.path.join(os.getcwd(), "ffprobe.exe")) else "ffprobe"
```

`.exe` 확장자를 명시적으로 먼저 탐색하는 방식은 Windows 환경에 최적화된 것이다. Linux/Docker 환경에서는 `ffprobe.exe`가 존재하지 않아 `"ffprobe"` 폴백으로 넘어가지만, `ffmpeg_path`는 `imageio_ffmpeg.get_ffmpeg_exe()`로 플랫폼 독립적으로 처리되는 것과 일관성이 없다. `ffprobe`도 `imageio_ffmpeg`에서 경로를 가져오거나, `shutil.which("ffprobe")`를 사용하는 방식으로 통일할 것을 권장한다.

### 4. SSRF 방어 허용 도메인 목록에 Supabase 인스턴스 하드코딩

`main.py`의 `ALLOWED_PROXY_DOMAINS` 리스트에 `ulasrprjenbflylxjtcx.supabase.co`가 하드코딩되어 있다. 이 Supabase 프로젝트 ID가 소스코드에 노출되면 공격자가 이미지 프록시 엔드포인트를 통해 해당 스토리지에 우회 접근을 시도하는 벡터가 될 수 있다. 허용 도메인을 환경변수(`os.getenv("SUPABASE_URL")`에서 동적 파싱)로 관리하도록 개선이 필요하다.

### 5. 이미지 재생성 피드백 입력 상태 관리 방식의 아키텍처 결합

`sceneFeedbacks` 상태가 `RaptorWorkflow.tsx` 컴포넌트 로컬 `useState`로 관리된다. 이 상태는 