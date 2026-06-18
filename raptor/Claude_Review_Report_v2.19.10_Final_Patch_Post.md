파일 쓰기 권한이 필요합니다. 승인해주시거나, 아래에 리포트 전문을 바로 출력합니다.

---

# RAPTOR Code Review Report — Final Patch (v2.19.10)
**Date:** 2026-06-16 | **Reviewer:** Claude Sonnet 4.6 | **Framework:** VIBE  
**Scope:** `237801f` + `a97f180` — OOM 이중 방어, 비디오 500MB 제한, 스토리지 유저 폴더 격리

---

## 대상 커밋

| 커밋 | 메시지 | 변경 |
|------|--------|------|
| `237801f` | content-length 사전 체크 + URL TTL 3600s 연장 | `main.py` +15/-5 |
| `a97f180` | OOM 이중 방어 완성 + 비디오 제한 + 유저 폴더 격리 | `main.py` +24/-5 |

---

## V — Value (변경의 가치)

이번 패치는 업로드 엔드포인트의 3가지 독립적인 보안/안정성 문제를 동시에 해결한다.

1. **OOM 이중 방어**: `Content-Length` 헤더 사전 체크(1층) + `file.read()` 후 실제 바이트 수 재확인(2층). 헤더 조작으로 1층을 우회해도 2층에서 차단.
2. **비디오 500MB 제한 신규 적용**: 기존에는 비디오 크기 제한이 전혀 없었다. 이미지와 동일한 이중 방어 구조 적용.
3. **스토리지 유저 폴더 격리**: `{file_id}.ext` → `{sanitized_user}/{file_id}.ext`. 이미지·비디오 모두 적용. 유저 간 파일 네임스페이스 충돌 구조적 해결.
4. **서명 URL TTL 연장**: 1800s → 3600s. 30분 초과 작업 시 이미지 만료 문제 완화.
5. **이미지 확장자 화이트리스트**: `jpg/jpeg/png/webp/gif` 외 차단. 기존 MIME 타입만 체크하던 문제 보완.

---

## I — Implementation (구현 품질)

**잘 구현된 부분**

```python
# 1층: 헤더 사전 체크 (메모리 로드 전)
try:
    if content_length and int(content_length) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, ...)
except ValueError:
    pass  # malformed 헤더 → 1층 bypass, 2층에서 잡힘

# 2층: 실제 읽기 후 재확인
file_content = await file.read()
if len(file_content) > 10 * 1024 * 1024:
    raise HTTPException(status_code=413, ...)
```

`ValueError: pass` 패턴이 안전한 이유: 1층 우회 시 2층이 반드시 잡는 구조이기 때문. 설계가 올바르다.

`sanitize_uuid`로 스토리지 경로 인젝션 방어가 기존부터 확립 → `{sanitized_user}/` prefix는 경로 순회(path traversal) 공격에 안전.

**주의가 필요한 부분**

1. **비디오 2층 체크 타이밍**: `file.read()`가 이미 500MB를 메모리에 올린 후 체크한다. FastAPI 구조적 한계이므로 수용 가능하지만, 1층 사전 체크가 핵심 방어선임을 인지해야 한다.
2. **비디오 확장자 화이트리스트 없음**: 이미지는 있는데 비디오는 `content_type.startswith("video/")` MIME 체크만 한다. MIME은 클라이언트가 조작 가능.
3. **응답에 내부 경로 노출**: `"filename": file_name` 반환 시 `{sanitized_user}/{image_id}.ext` 전체가 노출됨. Minor information disclosure.

---

## B — Bugs & Risks

### Medium

**[B-01] 비디오 로컬 파일 영구 저장 (디스크 고갈 위험)**  
`outputs/{video_id}.mp4`로 저장 후 정리 로직이 없다. Worker가 소비 후 삭제하는지 확인 필요.

### Low

**[B-02] `ValueError: pass` 시 로그 없음**  
비정상 Content-Length 헤더가 와도 조용히 무시 → 공격 시도 탐지 불가.

**[B-03] 비디오 Supabase 업로드 실패 시 예외 처리 확인 필요**  
`main.py:1957` except 블록에 `raise`가 없으면 업로드 실패해도 200 응답이 나간다.

**[B-04] GIF bomb 이론적 가능성**  
10MB 제한으로 실질적 위험은 낮음. GIF가 실제로 필요한지만 확인.

---

## E — Enhancements

### 즉시 적용 권장

**[E-01] 매직 넘버 상수화**
```python
MAX_IMAGE_SIZE = 10 * 1024 * 1024   # 10MB
MAX_VIDEO_SIZE = 500 * 1024 * 1024  # 500MB
```
두 함수에서 같은 숫자가 각각 2번씩 반복 중.

**[E-02] `ValueError` catch 시 경고 로그**
```python
except ValueError:
    print(f"[Upload Warning] Malformed Content-Length: {content_length!r}")
```

**[E-03] 비디오 확장자 화이트리스트**
```python
ALLOWED_VIDEO_EXTS = {'mp4', 'mov', 'webm'}
ext = (file.filename or 'upload.mp4').split('.')[-1].lower()
if ext not in ALLOWED_VIDEO_EXTS:
    raise HTTPException(status_code=422, ...)
```

---

## 종합 평가

| 항목 | 점수 | 코멘트 |
|------|------|--------|
| 보안 | ★★★★☆ | 이중 방어 구조 올바름, 비디오 확장자 화이트리스트 누락 |
| 안정성 | ★★★★☆ | OOM 구조 적절, 로컬 파일 정리 로직 확인 필요 |
| 코드 품질 | ★★★★☆ | 매직 넘버 반복 외 전반적으로 양호 |
| 설계 | ★★★★☆ | 유저 폴더 격리 구조 명확, 서명 URL 비대칭 의도 확인 필요 |

**결론**: 핵심 목표(OOM 이중 방어, 500MB 제한, 유저 폴더 격리)를 모두 올바르게 달성했다. Critical 이슈 없음. **E-01~E-03** 개선을 다음 패치에서 적용 권장.

---

파일로 저장하려면 쓰기 권한을 승인해주세요. 이슈 중 B-03(비디오 Supabase 업로드 실패 처리)을 바로 확인해드릴까요?
