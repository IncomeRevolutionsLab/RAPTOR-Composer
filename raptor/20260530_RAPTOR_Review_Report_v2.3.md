# RAPTOR V2.2 4대 핵심 결함 사전 리뷰 보고서 (Pre-Review Report v2.3)

*   **작성일자:** 2026-05-30
*   **작성자:** Antigravity (Architect & Integrator)
*   **대상 범위:** 4대 핵심 결함 핫픽스(세션 유지, WAF 우회, FFmpeg 싱크, 단가 연동) 및 KIE 모델/동적 비용 관리 통합 계획 교차 검증

---

## 1. 🟢 [Resolved] 해결 및 보완 완료 항목

이번 개편 계획과 코드베이스 상태를 검증한 결과, 기존의 4대 핵심 결함이 완벽하게 해결 및 보완되었음을 확인했습니다.

### ① 세션 유지 및 Next.js 타임아웃 픽스 (P0)
*   **해결 내용:** 
    *   `src/lib/api-client.ts`에 존재하던 120초 타임아웃 제한을 완전히 제거하고 30분(`1800000ms`)으로 대폭 완화하여 대용량 비디오/오디오 처리 시 연결이 조기 종료되지 않도록 보장했습니다.
    *   `src/store/useWorkflowStore.ts`에서 volatile 상태인 `isRendering`과 `renderProgress`를 Zustand의 `partialize` 옵션에서 명시적으로 제외했습니다. 이를 통해 새로고침 시 로컬 스토리지에 락이 걸리지 않고 해당 상태가 깔끔하게 리셋되어 세션 단절과 화면 프리징 현상을 방지합니다.

### ② WAF 우회 및 KIE API 키 단일화 (P1)
*   **해결 내용:**
    *   `src/components/forms/BYOKSettingsForm.tsx` 및 스토어를 개편하여, 복잡하게 분산되어 있던 다중 키 입력을 완전히 폐기하고 오직 **[🔑 KIE API Key]** 단 1개만 입력받아 Zustand에 바인딩하도록 UI를 극소화했습니다.
    *   백엔드 `main.py`에서는 이 단일 키를 HttpOnly Cookie(`raptor_key`)와 Fernet 복호화 기반으로 수집하여 Anthropic Claude, OpenAI DALL-E, Grok/Veo API 호출 시 Bearer 토큰으로 공통 적용되게 함으로써 WAF 제약 우회와 하위 호환성을 동시에 달성했습니다.

### ③ FFmpeg 싱크 및 오디오 잘림 픽스 (P0)
*   **해결 내용:**
    *   `backend/services/ffmpeg_worker.py`에서 비디오 클립 시간보다 TTS 오디오 재생 시간이 길 때 오디오가 끊기던 현상을 해결하기 위해, 비디오의 마지막 프레임을 연장하는 `tpad` 필터(`tpad=stop_mode=clone:stop_duration={freeze_duration}`)를 적용했습니다. 기존의 무한 반복(`-stream_loop -1`) 방식을 완전히 철거하여 싱크가 정확히 맞도록 개선했습니다.
    *   `main.py`에서 비디오 생성 오류 발생 시 임의로 스틸컷으로 덮어 리턴하던 try-catch Fallback 로직을 완전히 제거(Exception raise)하여 실패 지점을 정확하게 파악하고 사용자가 직접 재시도를 유도할 수 있도록 통제권을 확보했습니다.

### ④ 단가 연동 및 비용 대시보드 (P1)
*   **해결 내용:**
    *   단가 하드코딩을 방지하기 위해 `src/config/kie_pricing.json`에 단가 구조(`credit_rate: 0.01` 및 텍스트/이미지/비디오 단가)를 분리 구축했습니다.
    *   프론트엔드 `src/components/RaptorWorkflow.tsx`에서 이 JSON을 임포트하여 렌더링 전 예상 소모 비용(`calculateEstimatedCost`)과 KIE 응답의 `credits_consumed`를 역추적해 실제 누적 비용(`calculateActualCost`)을 비용 대시보드에 실시간으로 시뮬레이션 및 렌더링하고 있습니다.

---

## 2. 🟡 [Pending] 진행 중 / 보류 리스크 (위험 요소)

### ① 비디오 엔진 및 단가 확장 의존성
*   **상태 및 원인:** 
    *   현재 `kie_pricing.json`에는 요금이 수동으로 고정 기입되어 있으며, 백엔드 `main.py`에서 비디오 엔진(Veo / Grok)에 따른 단가 매핑 및 SSE 스트림 내의 분기 처리가 여전히 하드코딩 형식에 의존하고 있습니다.
    *   신규 모델이 추가되거나 KIE AI 단가 체계가 동적으로 바뀔 경우 백엔드 라우팅 함수와 JSON 파일이 동시에 수정되어야 하는 모니터링 리스크가 존재합니다.

### ② Supabase Storage FIFO 용량 제한
*   **상태 및 원인:**
    *   `main.py`에 적용된 FIFO 기반 스페이스 확보 로직(`check_and_enforce_user_limits`)이 하드코딩된 특정 사용자 `beta_tester`를 기준으로만 작동하고 있습니다.
    *   실제 다중 사용자 로그인 환경으로 서비스를 전환할 경우 개별 사용자별 고유 스토리지 쿼터 제한 및 동시성 락(Concurrency Lock)에 따른 삭제 충돌 예외가 발생할 가능성이 남이 있습니다.

---

## 3. 🔴 [New] 신규 식별된 리스크 및 개선안

### ① 크로스 플랫폼 폰트 경로 호환성 결함 (보안 및 이식성)
*   **리스크 내용:** `ffmpeg_worker.py` 내의 자막 렌더링을 위한 폰트 경로(`C:/Windows/Fonts/malgun.ttf`)가 Windows 환경으로 강제 하드코딩되어 있습니다.
*   **영향:** 코드가 리눅스 기반 클라우드(AWS, Vercel 등)나 Docker 컨테이너 환경으로 배포될 경우 FFmpeg 렌더링 과정에서 폰트 파일을 찾지 못해 빌드 및 렌더링 전체가 중단되거나 시스템 오류가 발생하게 됩니다.
*   **대응책:** OS 환경을 감지하여 리눅스의 경우 `/usr/share/fonts` 하위의 기본 한글 폰트(Noto Sans CJK 등)를 선택하거나, 프로젝트 내 로컬 폴더(예: `assets/fonts/`)에 폰트 파일을 포함하여 상대 경로로 가져오도록 폴백 로직을 보완해야 합니다.

### ② ZIP 일괄 다운로드 시 CORS 및 이미지 유실 위험
*   **리스크 내용:** `RaptorWorkflow.tsx`에서 일괄 다운로드 패키지(ZIP) 구성 시 외부 저장소(OpenAI Blob 등)에 있는 원본 이미지를 받아오기 위해 프록시 서버(`/api/proxy-image`)를 경유하고 있습니다.
*   **영향:** 만약 프록시 엔드포인트에 일시적인 네트워크 병목이 생기거나 허용 도메인 필터(`ALLOWED_PROXY_DOMAINS`)에 어긋날 경우 ZIP 파일 내에 일부 씬의 원본 이미지나 썸네일이 누락되는 데이터 무결성 훼손 가능성이 있습니다.
