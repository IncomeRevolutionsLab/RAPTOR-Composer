#### 📄 1. _RAPTOR_APP_MD_v1.3.md (설계서)

#### 📜 Changelog
*   **v1.0 - v1.2:** 초기 아키텍처 및 Grok/OpenAI 기반 파이프라인.
*   **v1.3 (Current):** 
    *   **Changed:** 기본 분석 및 기획 엔진을 OpenAI에서 **Anthropic Claude 3.5 Sonnet**으로 전면 교체.
    *   **Added:** **HIL (Human-in-the-loop) 한글 자동 번역 레이어** 추가. 사용자가 한글로 수정 제안 시 백엔드에서 영문 프롬프트로 자동 변환.
    *   **Removed:** OpenAI(ChatGPT) 의존성 제거.
    *   **Improved:** 가짜 렌더링을 폐기하고 FFmpeg 기반의 실제 미디어 합성 파이프라인 구축.

---

**1. 아키텍처 및 모듈 분리 설계 (Architecture & Modularization)**
*   **프론트엔드 (Next.js / React / TypeScript):**
    *   **UI/UX:** HIL 대응을 위한 한글 프롬프트 수정 인터페이스 추가.
*   **백엔드 (FastAPI / Pydantic):**
    *   **기획 엔진:** Claude 3.5 Sonnet (Vision 지원)을 통한 고정밀 상품 분석 및 스크립트 생성.
    *   **미들웨어:** 한글 -> 영문 프롬프트 번역 레이어 (Auto-Translation Layer).
    *   **미디어 워커:** FFmpeg 기반 실물 MP4 생성 엔진.

**2. 입출력 규격 계약 (Input-Output Contract)**
*   **GEM V2.1 기획 API (`POST /api/generate-plan` / `/api/generate-assets`):**
    *   **Headers:** `{"X-BYOK-Claude": "sk-ant-..."}`
    *   **Input Body:** `{ "product_name": str, "description": str, "images": list, "duration": int }`
    *   **Output Body:** `{ "script": list, "upload_package": dict }`
*   **미디어 렌더링 큐 API (`POST /api/render-task`):**
    *   **Input Body:** `{ "product_name": str, "scenes": list, "voice_type": str, "aspect_ratio": str }`
    *   **Output Body:** `{ "task_id": str, "status": "completed", "output_url": str, "size_bytes": int }`

**3. 품질 기준 (QoS) 및 보안**
*   **보안 원칙:** 사용자의 BYOK(Claude 등)는 로컬 스토리지에 유지하고 API 호출 시 커스텀 헤더(`X-BYOK-Claude`)로 전달.
*   **신뢰성 원칙:** 생성된 .mp4 파일은 물리적으로 존재해야 하며, 0바이트 파일은 실패로 간주.

