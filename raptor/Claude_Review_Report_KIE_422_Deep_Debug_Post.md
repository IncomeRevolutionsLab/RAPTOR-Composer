# Claude Review Report — KIE API 422 Deep Debug (Post-Review)

**Date:** 2026-06-17  
**Status:** ✅ All Fixes Verified & Deployed  
**Target Commit:** `73c21df` — fix(p0): resolve backend crashes and inject required resolution param for KIE 422  
**Branch:** main (origin/main — already pushed)

---

## ✅ 최종 검증 결과

### 1. FastAPI `Query` 임포트 누락 → 해결됨
- **검증 위치:** `main.py` L8
- **적용 내용:** `Query`가 `fastapi` 임포트 목록에 정상 포함되어 있음.
- **결과:** 에셋 다운로드 엔드포인트 기동 시 `NameError` 없음. ✅

```python
from fastapi import FastAPI, Header, HTTPException, Request, Depends, Cookie, UploadFile, File, BackgroundTasks, Query
```

---

### 2. `RefinePromptRequest` DTO 정의 누락 → 해결됨
- **검증 위치:** `main.py` L338–343
- **적용 내용:** `RefinePromptRequest` Pydantic 모델이 `ImageGenRequest` 직후에 올바르게 정의됨.
- **결과:** `/api/refine-prompt` 엔드포인트 422/400 바인딩 에러 해소. ✅

```python
class RefinePromptRequest(BaseModel):
    product_name: str
    current_scene: dict
    user_feedback: str
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    model: Optional[str] = "gpt-image-2-text-to-image"
```

---

### 3. `ffmpeg_worker` 싱글턴 생성 누락 → 해결됨
- **검증 위치:** `backend/services/ffmpeg_worker.py` L424
- **적용 내용:** 파일 최하단에 `ffmpeg_worker = FFmpegWorker()` 인스턴스화 코드 추가됨.
- **결과:** `main.py` L22 `from backend.services.ffmpeg_worker import ffmpeg_worker` 임포트 시 `ImportError` 없음. ✅

```python
ffmpeg_worker = FFmpegWorker()
```

---

### 4. `resolution` 파라미터 주입 → 해결됨
- **검증 위치:** `main.py` L1211–1212 (`/api/generate-images`), L1638–1639 (`/api/refine-prompt`)
- **적용 내용:** GPT-Image-2, Grok(`grok-imagine/text-to-image`), Nano-Banana 모델에 대해 `"resolution": "1K"` 강제 주입. 슬래시(`/`) 표기 정상.
- **결과:** KIE API 422 (Unsupported Resolution) 에러 원천 차단. ✅

```python
if input_payload["aspect_ratio"] != "auto" or model_val in [
    "gpt-image-2-text-to-image", "grok-imagine/text-to-image", "nano-banana-2"
]:
    input_payload["resolution"] = "1K"
```

---

## 📊 잔존 리스크 (코드 외부 요인)

| 항목 | 상태 | 비고 |
|------|------|------|
| KIE API Key 크레딧 | 외부 인프라 | 크레딧 부족 시 422 재발 가능 |
| KIE 서버 모델 가용성 | 외부 인프라 | KIE 내부 서비스 오프라인 시 일시적 422 |
| `gpt-image-2-text-to-image` 모델명 유효성 | KIE 공식 스펙 준수 | 정상 유지 중 |

---

## 🚀 배포 상태

- **커밋:** `73c21df` — fix(p0): resolve backend crashes and inject required resolution param for KIE 422
- **브랜치:** `main`
- **Push 상태:** `origin/main`과 동기화 완료 (already up to date)
- **추가 push 불필요**
