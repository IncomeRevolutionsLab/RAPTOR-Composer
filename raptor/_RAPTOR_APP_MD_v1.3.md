#### 📄 1. _RAPTOR_APP_MD_v1.3.md (설계서)

#### 📜 Changelog
*   **v1.0 - v1.2:** 초기 아키텍처 및 Grok/OpenAI 기반 파이프라인.
*   **v1.3 (Current):** 
    *   **Added:** 기획 API 입출력(I/O) 계약에 MAIN v2.2 JSON 스키마 및 selected_pattern 파라미터 반영.
    *   **Changed:** `POST /api/generate-plan`의 입출력 규격을 엄격한 JSON 스키마로 강제.
    *   **Improved:** 프론트엔드 HIL 제어 변수(`selected_pattern`) 편입으로 사용자 의도 반영 강화.

---

**1. 아키텍처 및 모듈 분리 설계 (Architecture & Modularization)**
*   **프론트엔드 (Next.js / React / TypeScript):**
    *   **UI/UX:** HIL 대응을 위한 한글 프롬프트 수정 및 **숏폼 패턴 선택(selected_pattern)** 인터페이스 추가.
*   **백엔드 (FastAPI / Pydantic):**
    *   **기획 엔진:** Claude 3.5 Sonnet을 통한 고정밀 상품 분석 및 스크립트 생성. 사용자가 선택한 `selected_pattern`을 최우선순위로 반영.
    *   **미들웨어:** 한글 -> 영문 프롬프트 번역 레이어 (Auto-Translation Layer).
    *   **미디어 워커:** FFmpeg 기반 실물 MP4 생성 엔진.

**2. 입출력 규격 계약 (Input-Output Contract)**
*   **GEM V2.1 기획 API (`POST /api/generate-plan`):**
    *   **Headers:** `{"X-BYOK-Claude": "sk-ant-..."}`
    *   **Input Body:** 
        ```json
        {
          "product_name": "str",
          "image_url": "str",
          "video_length": "int",
          "quality": "str",
          "selected_pattern": "str (optional, 프론트엔드 직접 선택값)"
        }
        ```
    *   **Output Body (STRICT JSON):** 
        ```json
        {
          "product_analysis": {
            "pain_point": "str",
            "core_benefit": "str",
            "purchase_trigger": "str",
            "product_ref": "list"
          },
          "strategy": {
            "selected_pattern": "str",
            "hook": "str",
            "wow": "str",
            "cta": "str"
          },
          "scenes": [
            {
              "scene_number": "int",
              "duration_seconds": "int",
              "role": "str",
              "dialogue": "str",
              "visual_description": "str",
              "image_prompt": "str"
            }
          ],
          "upload_package": {
            "titles": "list",
            "description": "str",
            "hashtags": "list",
            "keywords": "list",
            "thumbnail_texts": "list"
          }
        }
        ```
        *(반드시 MAIN v2.2에 명시된 4대 핵심 구조를 포함해야 함)*

*   **미디어 렌더링 큐 API (`POST /api/render-task`):**
    *   **Input Body:** `{ "product_name": str, "scenes": list, "voice_type": str, "aspect_ratio": str }`
    *   **Output Body:** `{ "task_id": str, "status": "completed", "output_url": str, "size_bytes": int }`

**3. 품질 기준 (QoS) 및 보안**
*   **보안 원칙:** 사용자의 BYOK(Claude 등)는 로컬 스토리지에 유지하고 API 호출 시 커스텀 헤더(`X-BYOK-Claude`)로 전달.
*   **JSON 무결성:** 모든 기획 결과물은 파싱 가능한 순수 JSON 형태여야 하며, AI의 불필요한 텍스트 설명을 배제함 (No Markdown Blocks).
