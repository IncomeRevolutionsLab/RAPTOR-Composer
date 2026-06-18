# Claude Review Report — KIE API 422 Deep Debug (Architectural Scan)

**Date:** 2026-06-17  
**Status:** 📋 Scan & Report Completed  
**Target Files:**  
- `main.py` (L8, L332, L1510)  
- `backend/services/ffmpeg_worker.py` (L422–423)  
- `src/components/RaptorWorkflow.tsx` (L380, L505)

---

## 🔍 KIE 422 및 백엔드 안정성 스캔 결과

### 1. 모델명 매핑(Mapping) 누락 추적
- **스캔 대상:** `/api/generate-images` 및 `/api/refine-prompt` 엔드포인트 내부
- **검증 결과:** **✅ 정상 적용 (누락 없음)**
  - `/api/generate-images` (L1193) 및 `/api/refine-prompt` (L1607) 내부에서 `createTask` 페이로드 조립 직전 `model_val = map_image_model(request.model)`이 정상 호출되고 있습니다.
  - 프론트엔드에서 `"dall-e-3"` 등 원시 문자열을 보내더라도 백엔드의 `map_image_model` 헬퍼 함수를 거쳐 KIE 공식 모델명인 `"gpt-image-2-text-to-image"`로 정확하게 파싱 및 매핑되어 전달되고 있음을 확인했습니다. 원시 문자열이 그대로 유입되는 맹점은 없습니다.

### 2. 프론트엔드 Request Body 불일치 확인
- **스캔 대상:** `RaptorWorkflow.tsx` 및 백엔드 Pydantic DTO 스키마
- **검증 결과:** **⚠️ DTO 정의 누락 및 일치성 확인**
  - **이미지 생성 (`/generate-images`):** 프론트엔드가 `model: imageEngine || "gpt-image-2"` 형태로 전송하고 있으며, 백엔드의 `ImageGenRequest` DTO가 이를 받아 정상적으로 바인딩하고 있습니다. 구조는 일치합니다.
  - **이미지 재생성 (`/refine-prompt`):** 프론트엔드는 정상적으로 `model`을 전달하고 있으나, 백엔드 `main.py` 내에 **`RefinePromptRequest` Pydantic 모델의 정의가 원천적으로 누락**되어 있습니다. 이로 인해 백엔드 기동 및 호출 시 `NameError`와 422/400 바인딩 에러의 도화선이 되고 있습니다.

### 3. KIE API 페이로드 스펙 및 가비지 데이터 검토
- **스캔 대상:** `main.py` 내 `createTask` `input` 딕셔너리 페이로드 조립부
- **검증 결과:** **✅ 정상 구성 (가비지 데이터 없음)**
  - `main.py` 내 DALL-E 3 모델용 페이로드 조립부는 `prompt`와 `aspect_ratio`만 남기고 이전에 지적되었던 불필요한 파라미터(`n`, `size`, `quality` 등)를 완전히 소거하여 격리 전송하고 있습니다. KIE 공식 명칭 스펙에 부합합니다.
  - **422 (Unsupported Model) 에러의 실제 잔존 원인:**
    - 소스코드 상에서 KIE 이미지 공식 명칭인 `"gpt-image-2-text-to-image"`는 올바르게 설정되어 있습니다.
    - 그럼에도 발생하는 422 에러는 KIE AI API Key의 크레딧 부족(Billing Lock), 또는 KIE 내부 서버의 일시적인 모델 서비스 오프라인/오작동 등 **외부 인프라 계정 환경 결함**에서 기인할 확률이 큽니다.

### 4. 백엔드 기동 크래시 결함 발견 (NameError & ImportError)
- **`Query` 임포트 누락:** `main.py` L655 에셋 다운로드 엔드포인트의 `Query` 타입 힌트가 있으나 `fastapi` 임포트 목록에 누락되어 `NameError` 발생.
- **`ffmpeg_worker` 인스턴스화 누락:** `main.py` L22에서 `ffmpeg_worker` 인스턴스를 임포트하려 하나, `ffmpeg_worker.py` 하단에 싱글턴 생성 코드(`ffmpeg_worker = FFmpegWorker()`)가 빠져 `ImportError` 발생.

---

## 🛠️ 해결 코드 및 조치 방안 제안

사용자 및 클로드 코드가 작업을 수행할 수 있도록, 소스코드를 건드리지 않고 아래와 같이 정밀 수정 스니펫을 제시합니다.

### 1. `backend/services/ffmpeg_worker.py` 수술 (싱글턴 생성 추가)
- **수정 위치:** 파일 최하단 (L422-423 이후)
- **제안 코드:**
```python
# backend/services/ffmpeg_worker.py 맨 아래 추가
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

ffmpeg_worker = FFmpegWorker()
```

### 2. `main.py` 수술 (FastAPI Query 임포트 및 RefinePromptRequest DTO 추가)
- **수정 위치 1:** `fastapi` 임포트 구문 (L8)
- **제안 코드:**
```python
# main.py L8 수정
from fastapi import FastAPI, Header, HTTPException, Request, Depends, Cookie, UploadFile, File, BackgroundTasks, Query
```

- **수정 위치 2:** `ImageGenRequest` DTO 정의 하단 (L337 부근)
- **제안 코드:**
```python
# main.py L332-L337 수정 및 RefinePromptRequest 추가
class ImageGenRequest(BaseModel):
    product_name: str
    scenes: List[dict]
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    model: Optional[str] = "gpt-image-2-text-to-image"

class RefinePromptRequest(BaseModel):
    product_name: str
    current_scene: dict
    user_feedback: str
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    model: Optional[str] = "gpt-image-2-text-to-image"
```
*(참고: KIE 공식 명칭인 `"gpt-image-2-text-to-image"`는 훼손하지 않고 스펙대로 유지합니다.)*
