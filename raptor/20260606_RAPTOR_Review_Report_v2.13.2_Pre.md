# 📋 RAPTOR v2.13.2-fix 사전 아키텍처 리뷰 보고서 (Pre-Review)

- **리뷰 수행일:** 2026-06-06
- **대상 계획서:** `implementation_plan.md` (v2.13.2-fix)
- **리뷰 툴:** Claude CLI (B모드 아키텍처 감사)

---

## 1. 🟢 [Resolved] — 계획서를 통해 해결 완료 예정인 리스크

### 🛠️ N-10 | 1:1 비율 UI 옵션의 실질적 미지원 결함
- **상태:** `[New]` ➔ `[Resolved]` (패치 적용 후 해결 예정)
- **분석:** 기존 핫픽스(v2.13.2)에서의 단순 프론트엔드 버튼 차단 꼼수를 걷어내고, 백엔드 `ffmpeg_worker.py`와 `main.py` 단에서 해상도 매핑 및 FFmpeg 필터(zoompan, scale/crop)를 동적화하여 1:1 및 16:9 비율 출력을 완전하게 연동하므로 근본적으로 해결됩니다.

---

## 2. 🟡 [Pending] — 조치 보류 또는 간접 리스크 및 추가 권고

### 🛠️ RISK-002 | KIE 모델 단가 분기 및 Supabase Storage FIFO 쿼터 한계
- **상태:** `[Pending]`
- **분석:** 이번 해상도 패치로 인해 veo/grok API 호출 페이로드가 다변화되므로, veo_fast 단가 연동 누락 시의 단가 계산 로직 오작동 정합성을 모니터링해야 합니다.

### 🛠️ P-01 | (N-08) 50ms setTimeout 레이스 컨디션 위험
- **연관 파일:** `RaptorWorkflow.tsx`
- **상태:** `[Pending]`
- **분석:** 동적 종횡비 변경 시 초기화-재랜더 체인 상에서 레이스 컨디션이 촉발되지 않도록 주의해야 합니다. 이번 패치 중 함께 원복하여 안전하게 구조를 정리할 것을 권고합니다.

### 🛠️ P-06 | (PND-001·002) 미사용 import 정리
- **연관 파일:** `RaptorWorkflow.tsx`
- **상태:** `[Pending]`
- **권고:** 종횡비 버튼 원복 수술 시 동일 import 라인에서 `Share2`, `RefreshCw` 동시 제거.

### 🛠️ P-07 | (RISK-003) 크로스플랫폼 폰트 경로 회귀 위험
- **연관 파일:** `ffmpeg_worker.py`
- **상태:** `[Resolved]` (주의 필요)
- **분석:** RISK-003은 이미 해결 완료된 항목이나, 이번 패치가 `ffmpeg_worker.py` 전체 `render_video` 로직을 대규모 수술하므로, 기존 구축된 Linux 배포용 폰트 분기 로직이 손상되지 않도록 보존할 필요가 있습니다.

---

## 3. 🔴 [New] — 이번 v2.13.2-fix 설계에서 신규 식별된 아키텍처 리스크

### 🔴 ARCH-01 | `VideoGenRequest.aspect_ratio` 필드 입력 유효성 검증 부재
- **연관 파일:** `main.py`
- **영향도:** 높음 (High)
- **내용:** `VideoGenRequest`에 `aspect_ratio: str = "9:16"` 필드를 추가하는 방식은 타입이 `str`이라 임의의 문자열이 그대로 통과됩니다. 
- **권고:** `aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"` 으로 Pydantic `Literal` 타입을 명시하여 FastAPI 레이어에서 422 Early Rejection 처리하도록 계획서에 강제 주입.

### 🔴 ARCH-03 | `drawtext`/워터마크 overlay Y좌표 종횡비 연동 누락
- **연관 파일:** `ffmpeg_worker.py`
- **영향도:** 높음 (High)
- **내용:** `1:1(h=720)` 또는 `16:9(h=720)` 렌더 시 기존 하드코딩된 절대값 Y좌표(예: `y=1200`)를 쓰면 자막이 화면 바깥으로 나가 보이지 않게 됩니다.
- **권고:** `drawtext y` 및 워터마크 `overlay` 좌표를 `h * 0.9` 등 비율 기반 표현식으로 교체하도록 계획서 보강.

### 🔴 ARCH-04 | `/api/refine-prompt` 호출 시 `aspect_ratio` 전달 체인 불명확
- **연관 파일:** `main.py`
- **영향도:** 높음 (High)
- **내용:** 이미지 재생성 `/api/refine-prompt` 경로 상에서도 KIE API 요청 규격 크기(`size`)를 맞출 수 있도록 해당 API의 Request Body 모델도 업데이트되어야 합니다.
- **권고:** `/api/refine-prompt` 엔드포인트의 Request 모델(`RefinePromptRequest`)에도 `aspect_ratio` Literal 필드를 추가할 것.

### 🔴 ARCH-05 | E2E 자동화 검증 스크립트의 다종횡비 시나리오 커버리지 부재
- **연관 파일:** `e2e_recheck.js`
- **영향도:** 보통 (Medium)
- **내용:** 기존 E2E 검증이 9:16 기준으로만 수행되므로, 1:1 및 16:9 렌더링 시 KIE API 전달 여부와 FFmpeg 해상도가 일치하는지 추가 케이스 검증이 필요합니다.
- **권고:** `e2e_recheck.js`에 `aspectRatio` 검증 로직 또는 수동 Verification 단계를 명확히 수립할 것.

---

### 📌 종합 평가
계획서의 동적 해상도 수술 설계는 타당하며, 추가 지적된 `ARCH-01` Pydantic Literal 검증, `ARCH-03` Y좌표 비율 연동, `ARCH-04` 이미지 재생성 aspect_ratio 추가 사양을 수용함으로써 무결한 수술이 보장됩니다. 본 계획에 의거한 개발 착수를 권고합니다.
