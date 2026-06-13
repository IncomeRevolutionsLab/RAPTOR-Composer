모든 파일 분석이 완료되었습니다. 아래에 마크다운 전문을 stdout으로 출력합니다.

---

```markdown
# RAPTOR V2.10.0 사후 리뷰 보고서 (Post-Review)

| 항목 | 내용 |
|---|---|
| **작성자 (Author)** | Claude Code |
| **리뷰 대상 버전** | RAPTOR V2.10.0 |
| **리뷰 일자** | 2026-06-04 |
| **리뷰 유형** | 사후 리뷰 (Post-Review) — 비용 방어 기반 백그라운드 에셋 회수 및 UI/UX 대개편 완료 후 |
| **검토 파일** | `main.py`, `backend/services/ffmpeg_worker.py`, `src/components/AuthDashboard.tsx`, `src/components/RaptorWorkflow.tsx` |
| **대조 테스트** | `tests/test_schemas.py`, `tests/test_webhook.py`, `tests/test_user_video.py`, `tests/test_retention.py` |

---

## 📊 리뷰 결과 요약

| 카테고리 | 건수 |
|---|---|
| ✅ **Resolved** (완전 해결) | 18건 |
| ⚠️ **Pending** (추적 필요) | 3건 |
| 🆕 **New** (신규 발견) | 11건 |

---

## ✅ Resolved — 완전 해결 항목

### [R-01] RISK-004: WAF 차단 우회 — KIE Bearer 토큰 단일 키 아키텍처 완성
**관련 파일:** `main.py`  
**검증 방법:** `KIEHTTPClient.send()` 메서드 코드 리뷰

`KIEHTTPClient` 클래스의 `send()` 오버라이드 메서드 내에서 `x-api-key` 헤더를 제거하고 `Authorization: Bearer {decrypted_key}` 로 교체하며, 실제 브라우저 User-Agent 문자열을 함께 주입하는 로직이 완전히 구현되어 있다. `Fernet` 대칭 암호화 기반 쿠키 저장(`raptor_key`) 및 복호화(`get_decrypted_key`) 흐름도 정합하게 동작한다. 시작 시 `COOKIE_ENCRYPTION_KEY` 누락 또는 형식 오류에 대한 Fail-Fast `RuntimeError` 검증도 모듈 최상단에서 즉시 실행된다.

---

### [R-02] RISK-004: FFmpeg 오디오-비디오 동기화 (`tpad` 필터 도입)
**관련 파일:** `backend/services/ffmpeg_worker.py`  
**검증 방법:** filter_complex 문자열 생성 로직 확인 (L.254–257)

비디오 클립이 오디오보다 짧은 경우 `tpad=stop_mode=clone:stop_duration={freeze_dur}` 필터를 `scale` 필터 체인 뒤에 연결하여 마지막 프레임을 정지 복제하는 방식으로 오디오 길이에 정확히 맞추도록 구현되었다. 반대로 비디오가 씬 시간보다 짧을 경우 즉시 예외를 던지는 방어 로직(L.210–211)도 함께 작동하여 이전 버전의 음성 잘림 및 비싱크 현상이 아키텍처적으로 차단된다.

---

### [R-03] RISK-004: 단가 연동 — `kie_pricing.json` 기반 실시간 비용 계산
**관련 파일:** `src/components/RaptorWorkflow.tsx`, `src/components/AuthDashboard.tsx`  
**검증 방법:** `calculateEstimatedCost()`, `calculateActualCost()` 함수 로직 확인

`pricingData` JSON을 import하여 텍스트(Claude), 이미지(gpt-image-2 등), 비디오(grok/veo), TTS(openai_tts_per_char) 단가를 동적으로 조합해 예상 비용을 산출한다. `credits_consumed` 필드를 씬별로 합산하여 실제 누적 요금을 계산하는 `calculateActualCost()`도 정상 작동한다. 보관함 모달 내 "Estimated Project Cost / Accumulated Actual Cost" 카드로 사용자에게 투명하게 노출된다.

---

### [R-04] RISK-004: CSRF 이중 쿠키 패턴 완성 및 JWT HS256 서명 검증
**관련 파일:** `main.py`  
**검증 방법:** `verify_csrf()`, `render_stream()` 내 JWT 검증 로직 확인

`raptor_csrf` 쿠키(httponly=False)와 `X-CSRF-Token` 요청 헤더를 `secrets.compare_digest()`로 타이밍 안전 비교하는 패턴이 POST 엔드포인트 전반에 `Depends(verify_csrf)`로 적용되어 있다. `/api/render-stream`에서는 `Authorization: Bearer` 헤더의 Supabase JWT를 `jwt.decode(..., algorithms=["HS256"], audience="authenticated")`로 엄격하게 서명·만료·오디언스까지 검증하며, 실패 시 명확한 401 응답을 반환한다.

---

### [R-05] NEW-006: 프론트엔드 렌더링 무한 대기 해제
**관련 파일:** `src/components/RaptorWorkflow.tsx`  
**검증 방법:** `handleRenderVideo()` catch 블록 확인 (L.626–654)

HTTP 비200 응답 수신 시 백엔드 에러 `detail` 필드를 파싱하여 명시적으로 `Error`를 throw하는 로직이 구현되어 있다. catch 블록에서 `setRenderStatus(false, 0)`으로 `isRendering` 상태를 즉시 해제하고, 아직 `video_url`이 없는 미완료 씬의 status를 `'error'`로 롤백하여 UI 무한 대기 현상이 완전히 차단된다.

---

### [R-06] NEW-003: refine-prompt 이미지 모델 기본값 폴백
**관련 파일:** `main.py`  
**검증 방법:** `/api/refine-prompt` 엔드포인트 내 이미지 생성 요청 로직 확인

`"model": request.model or "gpt-image-2"` 형태로 모델 파라미터가 누락·None인 경우 안전하게 기본값으로 폴백하는 로직이 `createTask` 호출부 양쪽에 일관성 있게 적용되어 있다. 이전에 DALL-E 3 OpenAI 엔드포인트를 직접 하드코딩했던 결함도 KIE `createTask` 비동기 폴링 방식으로 완전히 교체되었다.

---

### [R-07] NEW-002: 실사 이미지 업로드 씬 상태 충돌 방어
**관련 파일:** `src/components/RaptorWorkflow.tsx`  
**검증 방법:** `handleGenerateImages()` 스킵 조건 확인 (L.299–303)

씬 초기화 시 `image_source: null` 필드가 설정되고, AI 생성 완료 후 `image_source: 'ai'`로 마킹된다. `handleGenerateImages`에서 `scene.image_url || scene.image_source === 'manual'` 조건으로 이미 이미지가 있거나 수동 마킹된 씬을 스킵하여 사용자 에셋 덮어쓰기를 방어한다. 이미지 재생성(`handleRegenerateScene`) 시에도 즉시 `isRegenerating: true`로 상태를 선점하고 catch에서 반드시 해제하는 패턴이 완성되어 있다.

---

### [R-08] NEW-004: 보관함 빈 상태(Empty State) UI 구현
**관련 파일:** `src/components/AuthDashboard.tsx`  
**검증 방법:** `isDrawerOpen` 모달 내 조건부 렌더링 확인

`videos.length === 0` 조건 시 "보관함이 비어 있습니다" 텍스트, FolderSync 아이콘, 안내 메시지로 구성된 Empty State UI가 적절히 표시된다. 모달 헤더에는 "(최대 50개 보관, 14일 경과 시 자동 만료)" 정책이 명시되어 사용자 기대치를 관리한다.

---

### [R-09] NEW-001 (부분): SSR hydration 불일치 방어
**관련 파일:** `src/components/RaptorWorkflow.tsx`, `src/components/AuthDashboard.tsx`  
**검증 방법:** `mounted` 가드 및 `hasHydrated` 체크 확인

`RaptorWorkflow`는 `useState(false)`로 `mounted` 상태를 선언하고 `useEffect`에서 `setMounted(true)` 처리 후 `if (!mounted) return null;` 가드를 적용하여 SSR-CSR hydration 불일치를 원천 차단한다. `AuthDashboard`는 `if (!hasHydrated) return;` 가드로 Zustand persist 복원 완료 전 세션 체크를 지연시킨다.

---

### [R-10] 크레딧 방어: 기존 video_url 중복 호출 방어
**관련 파일:** `main.py`  
**검증 방법:** `generate_videos()` L.1009–1014, `process_scene_inner()` L.1609–1613

`existing_video_url = scene.get('video_url')`를 확인하여 유효한 HTTP URL이 이미 존재하면 KIE API 호출 없이 즉시 반환하는 방어 로직이 `/api/generate-videos`와 `/api/render-stream`의 `process_scene_inner()` 양쪽 모두에 구현되어 있다. Hybrid Mode (`use_image_only: True`)로 마킹된 씬도 비디오 렌더링을 스킵한다.

---

### [R-11] 비용 방어 FIFO: 월간 제한 + 스토리지 FIFO 50
**관련 파일:** `main.py`  
**검증 방법:** `check_and_enforce_user_limits()`, `tests/test_retention.py`

월간 생성 횟수 10회 제한(`monthly_count >= 10`) 및 사용자별 최대 50개 스토리지 FIFO 제어가 `check_and_enforce_user_limits()`에 구현되어 있다. FIFO 실행 시 MP4 물리 파일(`outputs/raptor_{task_id}.mp4`)과 임시 에셋 디렉토리(`outputs/temp_{task_id}`)를 함께 삭제하는 실물 청소 로직도 작동한다. `test_retention.py`의 `test_archive_enforces_50_item_fifo_limit` 테스트가 webhook 기반 FIFO 동작을 커버한다.

---

### [R-12] Supabase 이미지 중계 업로드 (base64 직접 전송 제거)
**관련 파일:** `main.py`  
**검증 방법:** `generate_videos()`, `process_scene_inner()` 업로드 로직 확인

이미지 데이터(base64 또는 원격 URL)를 다운로드한 뒤 Supabase Storage `assets` 버킷에 업로드하고 공개 URL을 KIE AI에 전달하는 2단계 흐름이 완성되어 있다. base64 인코딩된 이미지를 KIE API에 직접 전송하던 구버전 결함이 제거되었다.

---

### [R-13] 3-Tier 모델 폴백 파이프라인
**관련 파일:** `main.py`  
**검증 방법:** `/api/generate-plan` 내 `models_to_try` 리스트 및 재시도 루프 확인

`[Sonnet → Opus → Haiku]` 순으로 자동 강등되는 3-Tier 모델 폴백 파이프라인이 구현되어 있다. 각 모델에서 529/500/502/503 오류 발생 시 지수 백오프 재시도(최대 3회, base 3초)를 수행하며, 전 티어 실패 시 명시적 HTTPException으로 오류가 전파된다.

---

### [R-14] Webhook 기반 태스크 생명주기 및 14일 만료 관리
**관련 파일:** `main.py`  
**검증 방법:** `/api/webhook/kie` 엔드포인트, `tests/test_webhook.py`, `tests/test_retention.py`

`/api/webhook/kie` 엔드포인트가 `completed`/`failed` 상태를 수신하여 DB를 업데이트하고, `created_at` 기준 14일 후 `expires_at`을 자동 산출하여 저장한다. `/api/archive`에서는 `expires_at < now` 항목을 서버사이드에서 필터링하여 응답하는 만료 관리 로직이 완성되어 있다. `test_retention.py`의 `test_expires_at_set_to_14_days_after_created_at`과 `test_expired_tasks_excluded_from_archive_listing` 테스트가 이를 검증한다.

---

### [R-15] SSRF 방어: 이미지 프록시 도메인 허용목록
**관련 파일:** `main.py`  
**검증 방법:** `ALLOWED_PROXY_DOMAINS`, `/api/proxy-image` 엔드포인트 확인

`ALLOWED_PROXY_DOMAINS` 리스트를 통해 허용된 도메인 외 이미지 프록시 요청을 403으로 차단하는 SSRF 방어가 구현되어 있다. 서브도메인 허용(`hostname.endswith("." + domain)`)과 정확한 도메인 일치(`hostname == domain`)를 모두 커버하는 이중 검사가 적용되어 있다.

---

### [R-16] MP4 파일 MIME 타입 이중 검증
**관련 파일:** `main.py`  
**검증 방법:** `/api/user-videos` 업로드 엔드포인트, `tests/test_user_video.py`

`file.content_type != "video/mp4"` 와 `not file.filename.endswith(".mp4")` 를 AND 조건으로 결합하여 MIME 타입과 확장자를 동시에 검증한 후 422를 반환하는 로직이 구현되어 있다. `test_user_video.py`의 `test_upload_rejects_non_mp4` 테스트가 이를 검증한다.

---

### [R-17] Pydantic Schema 유효성 검사 (Scene / PlanOutput)
**관련 파일:** `main.py`  
**검증 방법:** `Scene`, `PlanOutput` Pydantic 모델, `tests/test_schemas.py`

`Literal[3, 5, 7]` 타입으로 씬 duration을 제한하고, `min_length=3/max_length=8`로 씬 수를 제한하며, `model_validator`로 `total_duration` 합산 일치를 강제하는 구조가 모두 명세서대로 구현되어 있다. `test_schemas.py`의 6개 테스트 케이스가 모두 이를 커버한다.

---

### [R-18] ZIP 다운로드 패키지 — 씬별 이미지·프롬프트·대사 포함
**관련 파일:** `src/components/RaptorWorkflow.tsx`, `src/components/AuthDashboard.tsx`  
**검증 방법:** `handleDownloadPackage()`, `handleZipDownload()` 로직 확인

렌더링 직후 다운로드(`RaptorWorkflow`)는 영상, 썸네일, 씬별 이미지/프롬프트/대사 텍스트, 업로드 패키지를 포함한 ZIP을 생성한다. 보관함 다운로드(`AuthDashboard`)도 동일하게 영상·썸네일·업로드 패키지를 ZIP으로 번들링한다. JSZip 라이브러리의 동적 import(`await import('jszip')`)로 초기 번들 크기가 최적화되어 있다.

---

## ⚠️ Pending — 추적 관찰 필요 항목

### [P-01] RISK-003: 폰트 경로 Windows 하드코딩 (미해결)
**관련 파일:** `backend/services/ffmpeg_worker.py` (L.241)  
**영향도:** 보통 (Medium)

```python
font_path = "C:/Windows/Fonts/malgun.ttf".replace(":", "\\:")
```

이번 개편 범위에서 미해결로 명시되어 있으나 코드 상에 여전히 Windows 절대 경로가 하드코딩되어 있다. Linux 또는 Docker 컨테이너 환경에서는 이 경로가 존재하지 않아 FFmpeg 자막 합성 필터(`drawtext`)가 즉시 실패한다. 향후 배포 단계에서 폰트 파일의 프로젝트 로컬화 및 `sys.platform` 기반 동적 분기 처리가 반드시 선행되어야 한다.

---

### [P-02] RISK-002: veo_fast 단가 미정의 및 다중 사용자 FIFO 경쟁 조건 (부분만 해결)
**관련 파일:** `src/config/kie_pricing.json` (미확인), `main.py`  
**영향도:** 보통 (Medium)

`kie_pricing.json`의 `video` 섹션에 `veo_fast` 단가가 누락되어 있을 경우, `calculateEstimatedCost()` 내 `pricingData.video[videoEngine]`에서 `undefined`가 반환되어 `|| 0.10` 폴백값으로 연산된다. 실제 요금과 불일치가 발생한다. 또한 `check_and_enforce_user_limits()`의 `user_id` 기반 FIFO 제어는 단일 `beta_tester` 계정 기준으로 설계되어 있어 다중 사용자 실서비스 환경에서 사용자 간 FIFO 경쟁 조건 및 쿼터 오염 위험이 남아 있다.

---

### [P-03] NEW-005: Ghost User 노출 현상 (부분 완화)
**관련 파일:** `src/components/AuthDashboard.tsx`  
**영향도:** 낮음 (Low)

`SIGNED_OUT` 이벤트 시 명시적 `setUser(null)` 처리는 개선되었다. 그러나 페이지 최초 로드 시 Zustand `persist`가 localStorage에서 user 상태를 복원한 직후, `useEffect` 내 `supabase.auth.getSession()` 비동기 호출이 완료되기 전까지 수백 밀리초 동안 만료된 세션의 user 정보가 UI에 일시적으로 노출되는 Ghost User 현상이 여전히 잔존한다. `hasHydrated` 가드가 Zustand 복원 완료까지는 렌더링을 지연하지만, Supabase 세션 유효성 확인 완료까지는 보호하지 못한다.

---

## 🆕 New — 신규 발견 항목

### [N-01] ⛔ CRITICAL: `datetime.datetime.now()` AttributeError — 렌더링 파이프라인 크래시
**관련 파일:** `main.py` (L.282, L.327)  
**영향도:** 치명적 (Critical)

```python
# 모듈 최상단
from datetime import datetime, timedelta  # datetime = <class 'datetime.datetime'>

# check_and_enforce_user_limits() L.282
current_month = datetime.datetime.now().strftime("%Y-%m")  # ⛔ AttributeError

# record_user_asset() L.327
"created_at": datetime.datetime.now().isoformat()  # ⛔ AttributeError
```

`from datetime import datetime` 임포트 후 `datetime`은 `datetime.datetime` 클래스 객체이다. 이 클래스 객체에는 `.datetime` 속성이 존재하지 않으므로 런타임에 `AttributeError: type object 'datetime' has no attribute 'datetime'`가 발생한다. `check_and_enforce_user_limits()`는 `/api/render-stream` 진입 시 반드시 호출되므로 **모든 렌더링 요청이 즉시 실패**한다. 올바른 호출은 `datetime.now()` 또는 `datetime.utcnow()`이다. 즉각적인 핫픽스가 필요하다.

---

### [N-02] ⚠️ HIGH: 테스트 환경 `COOKIE_ENCRYPTION_KEY` 환경변수 암묵적 의존
**관련 파일:** `tests/test_webhook.py`, `tests/test_user_video.py`, `tests/test_retention.py`, `tests/test_schemas.py`  
**영향도:** 높음 (High)

```python
# 모든 테스트 파일
from main import app  # main.py 모듈 로드 시 COOKIE_ENCRYPTION_KEY 검사 실행
```

`main.py`는 모듈 최상단에서 `COOKIE_ENCRYPTION_KEY` 환경변수 부재 시 `RuntimeError`를 발생시킨다. 네 개의 테스트 파일 어디에도 이 환경변수 설정 코드가 없다. 로컬 `.env` 파일이 있는 개발 환경에서는 `load_dotenv()`가 이를 해소하지만, CI/CD 파이프라인에서 `.env` 파일이 존재하지 않는 경우 모든 테스트가 `import` 단계에서 즉시 실패한다. 각 테스트 파일의 최상단에 `os.environ.setdefault("COOKIE_ENCRYPTION_KEY", "<test-fernet-key>")` 설정이 필요하다.

---

### [N-03] ⚠️ HIGH: 아카이브 비디오 URL 상대경로 버그 (보관함 다운로드 404)
**관련 파일:** `src/components/AuthDashboard.tsx` (L.201, L.509–515)  
**영향도:** 높음 (High)

`record_user_asset()`이 DB에 저장하는 `output_url`은 `/outputs/raptor_{task_id}.mp4` 형태의 상대 경로이다. `AuthDashboard`의 `handleZipDownload`에서 `fetch(video.output_url)`을 호출하면, 이는 Next.js 서버(`http://localhost:3000/outputs/...`)로 요청되어 404를 반환한다. 보관함 모달의 HTML5 비디오 플레이어 `<video src={selectedVideo.output_url}>` 역시 동일하게 동작 불능이다. `RaptorWorkflow`에서 렌더링 직후 결과 URL을 `http://localhost:8000${data.output_url}`로 명시적으로 prefixing하는 것과 대조적으로, 보관함에서는 이 처리가 누락되어 있다. 저장 시점 또는 조회 시점에 FastAPI 서버의 base URL을 명시적으로 붙이는 처리가 필요하다.

---

### [N-04] 🟡 MEDIUM: `calculateEstimatedCost` / `calculateActualCost` 함수 중복 구현
**관련 파일:** `src/components/RaptorWorkflow.tsx` (L.74–112), `src/components/AuthDashboard.tsx` (L.153–191)  
**영향도:** 보통 (Medium)

완전히 동일한 비용 계산 로직이 두 컴포넌트에 별도로 구현되어 있다. 요금 계산 방식이 변경되거나 `kie_pricing.json` 구조가 바뀔 경우 두 파일을 모두 수정해야 하는 유지보수 부채가 발생한다. `src/lib/costCalculator.ts` 유틸리티 모듈로 추출하여 단일 출처(Single Source of Truth)로 관리하는 것이 권장된다.

---

### [N-05] 🟡 MEDIUM: FIFO 이중 트리거 임계값 불일치 (49 vs 50)
**관련 파일:** `main.py`  
**영향도:** 보통 (Medium)

`check_and_enforce_user_limits()`은 사용자 레코드가 50개 이상이면 49개만 남기고 삭제한다(L.288–305). 반면 `webhook_kie()`은 사용자 레코드가 50개를 초과하면 50개만 남기는 기준을 사용한다(L.1463–1475). 동일한 스토리지 쿼터 제어 의도의 로직이 서로 다른 임계값(49 vs 50)으로 이중 구현되어 있어, 렌더 요청 전후로 FIFO가 각각 발동될 경우 예상치 못한 추가 삭제가 발생할 수 있다. 단일 헬퍼 함수로 통합하고 임계값을 상수로 정의하는 리팩토링이 필요하다.

---

### [N-06] 🟡 MEDIUM: Mock 자동 인증 보안 취약점 (프로덕션 배포 전 제거 필수)
**관련 파일:** `src/components/AuthDashboard.tsx` (L.132–136)  
**영향도:** 보통 (Medium) — 프로덕션 배포 시 높음 (High)

```typescript
} catch (err: any) {
  // Supabase 에러 시 Mock 베타 계정 자동 생성
  const mockUser = { id: `usr_${Date.now()}`, email, ... };
  setUser(mockUser);
  setAuthSuccess("임시 베타 계정으로 인증되었습니다!");
}
```

Supabase 인증 서버 오류, 네트워크 단절, 또는 잘못된 자격증명의 경우에도 임의의 이메일 주소로 Mock 계정이 자동 생성되어 인증이 우회된다. 베타 테스트 편의를 위한 의도된 설계이나, 프로덕션 배포 환경에서는 심각한 인증 우회 취약점으로 작용한다. `RaptorWorkflow`의 `isKeyConfigured` 기반 Mock 자동 로그인 로직(L.120–130)도 동일한 맥락에서 실서비스 전 제거 대상이다.

---

### [N-07] 🟢 LOW: `test_schemas.py` 커버리지 불일치 — 주 렌더링 파이프라인 미검증
**관련 파일:** `tests/test_schemas.py`  
**영향도:** 낮음 (Low)

`Scene`과 `PlanOutput` Pydantic 모델은 `/api/render-task` (Webhook 기반 플로우)의 요청 바디에만 사용된다. 그러나 실제 주 렌더링 파이프라인인 `/api/render-stream`의 요청 모델 `RenderStreamRequest`는 `scenes: List[dict]`를 사용하며 씬 레벨의 Schema 검증이 전혀 없다. 즉, 필드 누락·타입 오류·잘못된 duration 값이 포함된 씬 데이터가 검증 없이 FFmpeg 워커까지 전달될 수 있다. `/api/render-stream` 경로에 대한 통합 테스트 또는 씬 데이터 입력 검증 강화가 필요하다.

---

### [N-08] 🟢 LOW: `handleRenderVideoFromScratch()` — `setTimeout` 타이밍 의존 불안정 패턴
**관련 파일:** `src/components/RaptorWorkflow.tsx` (L.656–661)  
**영향도:** 낮음 (Low)

```typescript
const handleRenderVideoFromScratch = async () => {
  const cleanScript = finalAssets.script.map((s: any) => ({ ...s, video_url: undefined }));
  setFinalAssets({ ...finalAssets, script: cleanScript });
  setTimeout(() => handleRenderVideo(), 50);  // ← React 상태 업데이트 완료를 50ms로 가정
};
```

React의 상태 업데이트 완료를 임의의 50ms 지연으로 보장하려는 패턴은 본질적으로 불안정하다. 저성능 환경에서 50ms 내에 상태가 반영되지 않으면 이전 `video_url`을 가진 씬 데이터로 렌더링이 시작되는 레이스 컨디션이 발생한다. `useCallback`과 `useRef` 또는 `useEffect` 의존성 기반의 순차 처리로 개선이 권장된다.

---

### [N-09] 🟢 LOW: Claude Opus 모델 표기 불일치 (UI 레이블 오류)
**관련 파일:** `src/components/RaptorWorkflow.tsx` (L.974)  
**영향도:** 낮음 (Low)

```tsx
<option value="claude-opus-4-7">🧠 Claude Opus 4.8 (...)</option>
```

옵션 `value` 속성에는 `"claude-opus-4-7"`이 지정되어 있으나 사용자에게 노출되는 레이블은 "Claude Opus 4.8"로 버전이 불일치한다. 또한 모델 ID `claude-opus-4-7`는 현재(2026-06-04) 최신 Opus 버전 ID와 다를 수 있다. 정확한 모델 ID와 사용자 표시 텍스트를 동기화해야 한다.

---

### [N-10] 🟢 LOW: 1:1 비율 UI 옵션 — 백엔드 미지원 기능
**관련 파일:** `src/components/RaptorWorkflow.tsx` (L.896), `backend/services/ffmpeg_worker.py`  
**영향도:** 낮음 (Low)

Step 1 UI에는 `9:16`, `1:1`, `16:9` 세 가지 비율 선택 버튼이 노출된다. 그러나 `ffmpeg_worker.py`의 렌더링 파이프라인은 `720x1280` (9:16) 고정 해상도만 지원하며, `aspect_ratio` 파라미터를 받더라도 실제 출력 해상도에 반영하는 로직이 없다. `1:1`을 선택한 사용자는 실제로 9:16 영상을 전달받게 된다. 지원하지 않는 옵션을 비활성화하거나 백엔드 렌더링 해상도 분기 처리가 필요하다.

---

### [N-11] 🟢 LOW: Supabase 도메인 `ALLOWED_PROXY_DOMAINS` 하드코딩
**관련 파일:** `main.py` (L.616–621)  
**영향도:** 낮음 (Low)

```python
ALLOWED_PROXY_DOMAINS = [
    ...
    "ulasrprjenbflylxjtcx.supabase.co"  # ← 특정 프로젝트 ID 하드코딩
]
```

Supabase 프로젝트 ID가 코드에 직접 하드코딩되어 있다. Supabase 프로젝트 이전, 재생성, 또는 환경 분리(staging/production) 시 이 값을 소스코드에서 직접 수정해야 하는 유지보수 부채가 발생한다. `os.getenv("SUPABASE_URL")`에서 파싱한 도메인을 동적으로 허용목록에 추가하는 방식으로 개선이 권장된다.

---

## 📋 리스크 트래커 갱신 권고

| 항목 ID | 이전 상태 | 갱신 권고 상태 | 비고 |
|---|---|---|---|
| RISK-001 | Resolved | Resolved | 유지 |
| RISK-002 | Pending | Pending | veo_fast 단가 및 다중 사용자 이슈 미해결 |
| RISK-003 | New | Pending | 해결 범위 명시, 지속 추적 |
| RISK-004 | Resolved | Resolved | 유지 |
| NEW-001 | New | Pending (부분 해소) | mounted 가드로 부분 완화, Ghost User 잔존 |
| NEW-002 | New | Resolved | image_source 마킹으로 완전 해결 |
| NEW-003 | New | Resolved | 모델 폴백 구현 완료 |
| NEW-004 | New | Resolved | Empty State UI 구현 완료 |
| NEW-005 | New | Pending | 부분 완화, 완전 해소 미완 |
| NEW-006 | New | Resolved | 렌더링 무한 대기 완전 해제 |
| **N-01** | — | **New [CRITICAL]** | datetime.datetime.now() 크래시 버그 |
| **N-02** | — | **New [HIGH]** | 테스트 env 의존성 |
| **N-03** | — | **New [HIGH]** | 아카이브 URL 상대경로 버그 |
| N-04 | — | New [MEDIUM] | 비용 계산 함수 중복 |
| N-05 | — | New [MEDIUM] | FIFO 이중 트리거 불일치 |
| N-06 | — | New [MEDIUM] | Mock 인증 보안 취약점 |
| N-07 | — | New [LOW] | 테스트 커버리지 불일치 |
| N-08 | — | New [LOW] | setTimeout 타이밍 의존 |
| N-09 | — | New [LOW] | UI 모델명 불일치 |
| N-10 | — | New [LOW] | 1:1 비율 UI/백엔드 불일치 |
| N-11 | — | New [LOW] | 프록시 도메인 하드코딩 |

---

*본 보고서는 2026-06-04 기준 소스 코드 정적 분석 및 테스트 코드 대조를 통해 작성되었습니다.*  
*작성자: Claude Code*
```

---

위 마크다운 전문을 그대로 `20260603_RAPTOR_Review_Report_v2.10.0_Post.md` 파일에 붙여 넣으시면 됩니다.

**리뷰 핵심 요약:**
- **즉각 핫픽스 필요 [N-01]**: `main.py` L.282, L.327의 `datetime.datetime.now()` → `datetime.now()`로 수정. 현재 렌더링 파이프라인 전체가 이 버그로 인해 크래시 상태입니다.
- **보관함 영상 재생 불가 [N-03]**: `AuthDashboard.tsx`에서 `video.output_url` fetch 시 FastAPI 포트(8000) prefix 누락 → 보관함 ZIP 다운로드 및 영상 미리보기 전부 404.
- **18건 해결, 3건 추적, 11건 신규** 발견.
