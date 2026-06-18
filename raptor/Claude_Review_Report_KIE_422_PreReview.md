# Claude Review Report — KIE 422 Fix Pre-Review

**Date:** 2026-06-17  
**Status:** 📋 Pre-Review (수정 전 현황 스냅샷)  
**Reviewer:** Claude Sonnet 4.6  
**목적:** 아래 3개 결함의 **수정 전 실제 코드 상태**를 기록하여, 수정 후 검증(Post-Review)의 기준선으로 삼는다.

---

## 요약 — 검증된 결함 목록

| # | 심각도 | 파일 | 위치 | 결함 유형 | 증상 |
|---|--------|------|------|----------|------|
| 1 | 🔴 P0 | `main.py` | L8 | `Query` 임포트 누락 | 서버 기동 시 `NameError` |
| 2 | 🔴 P0 | `main.py` | L337 부근 | `RefinePromptRequest` DTO 정의 누락 | 서버 기동 시 `NameError` → `/api/refine-prompt` 502 |
| 3 | 🔴 P0 | `backend/services/ffmpeg_worker.py` | L422 (파일 끝) | `FFmpegWorker()` 싱글턴 인스턴스 미생성 | `main.py` L22 임포트 시 `ImportError` |

---

## 결함 1 — `Query` 임포트 누락

### 현재 코드 (`main.py` L8)
```python
from fastapi import FastAPI, Header, HTTPException, Request, Depends, Cookie, UploadFile, File, BackgroundTasks
```

### 문제
- `Query`가 임포트 목록에 없다.
- `main.py` **L655**에서 `token: str = Query(...)` 형태로 사용 중.
- Python 모듈 로딩 순서상, L655 파싱 시점에 `Query`가 미정의(NameError)이므로 FastAPI 앱 자체가 기동 불가.

### 목표 코드 (수정 후 예상)
```python
from fastapi import FastAPI, Header, HTTPException, Request, Depends, Cookie, UploadFile, File, BackgroundTasks, Query
```

---

## 결함 2 — `RefinePromptRequest` DTO 정의 누락

### 현재 코드 (`main.py` L332–L337)
```python
class ImageGenRequest(BaseModel):
    product_name: str
    scenes: List[dict]
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    model: Optional[str] = "gpt-image-2-text-to-image"

class VideoGenRequest(BaseModel):   # ← ImageGenRequest 바로 다음에 VideoGenRequest가 나옴
    ...
```

- `ImageGenRequest` (L332)와 `VideoGenRequest` (L338) 사이에 `RefinePromptRequest` 정의가 **없다**.
- `main.py` **L1510**에서 `request: RefinePromptRequest`로 사용하고 있어 서버 기동 시 `NameError` 발생.

### 사용처 (`main.py` L1508–L1513)
```python
@app.post("/api/refine-prompt")
async def refine_prompt(
    request: RefinePromptRequest,          # ← 미정의 심볼
    decrypted_key: str = Depends(get_decrypted_key),
    verify: None = Depends(verify_csrf)
):
```

### 목표 코드 (수정 후 예상 — `ImageGenRequest` 아래에 삽입)
```python
class RefinePromptRequest(BaseModel):
    product_name: str
    current_scene: dict
    user_feedback: str
    aspect_ratio: Literal["9:16", "1:1", "16:9"] = "9:16"
    model: Optional[str] = "gpt-image-2-text-to-image"
```

---

## 결함 3 — `ffmpeg_worker` 싱글턴 인스턴스 미생성

### 현재 코드 (`backend/services/ffmpeg_worker.py` 파일 끝, L418–422)
```python
                if os.path.exists(final_output):
                    yield {
                        "task_id": task_id,
                        "status": "completed",
                        "output_url": f"/outputs/raptor_{task_id}.mp4",
                        "size_bytes": os.path.getsize(final_output)
                    }
                else:
                    raise Exception("Physical MP4 creation failed.")
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)
# ← 파일 종료. ffmpeg_worker = FFmpegWorker() 없음.
```

### 문제
- `main.py` **L22**에서 `from backend.services.ffmpeg_worker import ffmpeg_worker`를 시도.
- `ffmpeg_worker.py` 모듈 내에 `ffmpeg_worker = FFmpegWorker()` 인스턴스 생성 라인이 존재하지 않아 `ImportError: cannot import name 'ffmpeg_worker'` 발생.
- 결과적으로 `main.py` 자체가 임포트 단계에서 크래시.

### 목표 코드 (수정 후 예상 — 파일 최하단에 추가)
```python
            finally:
                shutil.rmtree(temp_dir, ignore_errors=True)

ffmpeg_worker = FFmpegWorker()
```

---

## 수정 범위 및 영향도 분석

| 수정 항목 | 변경 성격 | 기존 로직 영향 | 위험도 |
|-----------|-----------|---------------|--------|
| `Query` 임포트 추가 (L8) | 임포트 라인 1개 심볼 추가 | 없음 (추가만) | 🟢 없음 |
| `RefinePromptRequest` DTO 삽입 (L337 뒤) | 새 Pydantic 모델 클래스 삽입 | 없음 (추가만) | 🟢 없음 |
| `ffmpeg_worker = FFmpegWorker()` 추가 (파일 끝) | 모듈 수준 싱글턴 생성 라인 추가 | 없음 (추가만) | 🟢 없음 |

**모든 수정은 순수 추가(Add-only)**이며, 기존 코드 라인을 수정·삭제하지 않는다.

---

## KIE 422 에러 외부 요인 (수정 불가)

딥디버그 보고서에서 확인된 바와 같이, 위 3개 결함 수정 후에도 KIE API가 **402/422**를 반환하는 경우는 아래 외부 요인에 해당하며 코드 수정으로 해결 불가:
- KIE AI API Key 크레딧 소진(Billing Lock)
- KIE 내부 모델 서비스 일시 오프라인

---

## Post-Review 검증 항목 (수정 후 확인 목록)

- [ ] `main.py` L8: `Query` 포함 확인
- [ ] `main.py` L337~341: `RefinePromptRequest` 클래스 정의 존재 확인
- [ ] `backend/services/ffmpeg_worker.py` 최하단: `ffmpeg_worker = FFmpegWorker()` 존재 확인
- [ ] `uvicorn main:app` 기동 시 `NameError` / `ImportError` 없음 확인
- [ ] `/api/refine-prompt` 엔드포인트 호출 시 422 DTO 바인딩 에러 미발생 확인
