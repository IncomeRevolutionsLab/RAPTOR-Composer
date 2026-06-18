파일 쓰기 권한이 필요합니다. 승인해주시면 리포트를 저장하겠습니다. 아래는 완성된 리뷰 내용입니다.

---

# Claude Code Review Report — v2.19.10 P1 Hotfix (Post-Review)

**Date:** 2026-06-16 | **Framework:** VIBE | **Commits:** `5649e88`, `dca1690`  
**Files:** `main.py` (+43), `RaptorWorkflow.tsx` (+55/-30)

---

## V — Value (목적 달성도)

| 수정 항목 | 달성 |
|-----------|------|
| DALL-E 모델명 파싱 (`"dall-e"`, `"dalle"`) → `gpt-image-2-text-to-image` 라우팅 | ✅ 완전 수정 |
| `FileReader.readAsDataURL()` → `api.post('/api/user-images')` 전환으로 JS OOM 근본 제거 | ✅ 근본 원인 제거 |
| raw `fetch()` → `api` axios 인스턴스 통일로 비디오 업로드 401 수정 | ✅ 완전 수정 |
| S-006 보안 패턴 (Private 버킷 + 30분 Signed URL) 이미지에도 적용 | ✅ 정책 일관성 유지 |

---

## I — Issues (발견된 문제점)

### [P1] 서버 측 OOM 방어 순서 역전 — `main.py:1877`

```python
file_content = await file.read()          # ← 전체 파일을 메모리에 먼저 적재
if len(file_content) > 10 * 1024 * 1024: # ← 그 다음에 체크 (이미 늦음)
```

10MB 초과 파일도 메모리에 올라간 뒤에 에러를 던지므로 서버 OOM 방어가 사실상 무효. `Content-Length` 헤더로 선제 차단하거나 413 status code를 사용해야 함.

**권장 패턴:**
```python
content_length = int(request.headers.get("content-length", 0))
if content_length > 10 * 1024 * 1024:
    raise HTTPException(status_code=413, detail="File size exceeds 10MB limit.")
file_content = await file.read()
```

### [P2] `sanitized_user` 변수 미사용 — `main.py:1875`
`sanitize_uuid(jwt_user_id)` 검증만 실행하고 반환값을 DB 저장에 활용하지 않음. 이미지 소유자 정보가 없어 audit trail 불가. `upload_user_video`는 DB에 저장하는 것과 불일치.

### [P2] 이미지 업로드 핸들러 코드 중복 — `RaptorWorkflow.tsx`
동일한 로직이 두 개의 `onChange` 핸들러에 복붙됨. 공통 훅으로 추출 필요.

### [P3] 파일 확장자 화이트리스트 없음 — `main.py:1873`
`content_type` 검증은 있으나 확장자 검증 없음. 낮은 위험이나 명시적 화이트리스트 권장.

---

## B — Blocks (잠재적 차단 요소)

**[B1] Signed URL 30분 TTL vs. 긴 편집 세션**  
1800초 만료 URL을 씬 상태에 저장. 30분 초과 편집 세션에서 영상 생성 시 만료된 URL로 이미지 요청 → 403 발생 가능.

**[B2] 비디오 URL이 여전히 로컬 `outputs/` 경로 의존**  
이미지는 Supabase 영구 저장, 비디오는 `${BACKEND_URL}/outputs/${id}.mp4` 직접 경로로 혼재. Koyeb 재배포 시 비디오 파일 소실 위험.

---

## E — Enhancements (개선 권고)

| 우선순위 | 항목 | 위치 |
|----------|------|------|
| **P1** | OOM 방어 순서 수정 (Content-Length 선제 체크, 413) | `main.py:1877` |
| **P2** | `useSceneImageUpload(i)` 공통 훅 추출 | `RaptorWorkflow.tsx` |
| **P2** | `sanitized_user` → DB 메타데이터 저장 | `main.py:1875` |
| P3 | 확장자 화이트리스트 (`jpg/jpeg/png/gif/webp`) | `main.py:1873` |
| P3 | Signed URL TTL 환경변수화 (3600초 권장) | `main.py:1891` |

---

## 종합 평가

| 항목 | 점수 |
|------|------|
| 버그 수정 완성도 | 9/10 |
| 보안 | 7/10 |
| 코드 품질 | 7/10 |
| 패턴 일관성 | 8/10 |
| **종합** | **7.8/10** |

**결론:** P0/P1 목표(DALL-E 라우팅, OOM, 401)는 모두 달성. 단, 서버 OOM 방어가 파일 적재 후 체크하는 구조적 결함이 있어 P1 수준의 후속 수정 권고. 나머지는 안정적인 핫픽스 품질.

---

리포트 파일을 저장하려면 쓰기 권한을 승인해주세요. 가장 시급한 후속 조치는 **`main.py:1877` OOM 방어 순서 수정**입니다. 수정하시겠습니까?
