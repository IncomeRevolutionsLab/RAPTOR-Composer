파일 쓰기 권한이 필요합니다. 승인해주시면 리포트를 저장하겠습니다. 먼저 분석 결과를 직접 출력할게요.

---

# RAPTOR Code Review Report — v2.19.10 P1 3차 핫픽스 (Post-Review)
**날짜**: 2026-06-16 | **커밋**: `5649e88` → `237801f` | **프레임워크**: VIBE

---

## 요약

| 커밋 | 변경 파일 |
|------|-----------|
| `5649e88` fix(p1): resolve signed url, auth headers, and oom risks | `main.py`, `RaptorWorkflow.tsx` |
| `237801f` fix(p1): content-length pre-check + URL TTL 3600s | `main.py` |

---

## V — Validity (정확성·동작 검증)

### ✅ 올바르게 수정된 사항

**1. 프론트엔드 인증 헤더 누락 (`RaptorWorkflow.tsx`)**

`raw fetch(BACKEND_URL)`에는 JWT 토큰이 없었음 → `Depends(get_jwt_user_id)` 401 실패. `api.post()`는 axios 인터셉터가 Authorization 헤더를 자동 주입하므로 **근본 원인 정확히 해소**.

**2. `file.filename` null 안전 처리**
```python
filename = file.filename or 'upload.png'
ext = filename.split('.')[-1].lower() if '.' in filename else 'png'
```
`None`일 때 `AttributeError` → 500 버그 수정. `.lower()` 추가로 `.JPG`, `.PNG` 대문자도 화이트리스트 통과.

**3. Signed URL 방어적 추출**
Supabase SDK 버전별 반환 타입 차이(`dict` vs `str`) 모두 처리. `signedURL`/`signedUrl` 양쪽 키 시도. **신뢰성 향상**.

### ⚠️ 부분적으로 수정된 사항

**Content-Length 선행 체크의 한계**

| 시나리오 | 결과 |
|----------|------|
| Content-Length 있음 + 정직한 값 | ✅ 차단 |
| Content-Length 없음 (chunked encoding) | ❌ 체크 건너뜀 → `file.read()` 무제한 |
| Content-Length 스푸핑 (`Content-Length: 1`) | ❌ 체크 통과 → `file.read()` 무제한 |

**더 심각한 문제**: `5649e88`에서 추가했던 사후 크기 검증을 `237801f`에서 제거함. 선행 체크만 남아 실질적 OOM 방어 보증이 오히려 이전보다 약해짐.

---

## I — Integrity (무결성·보안)

### ✅ 확장자 화이트리스트 (defense-in-depth)
MIME 타입 스푸핑 가능성에 대응, `.lower()` 포함한 이중 검사 추가.

### 🔴 잔존 보안 이슈

**1. `sanitized_user` 미사용 — 스토리지 격리 실패**
```python
sanitized_user = sanitize_uuid(jwt_user_id)  # 선언됨
# ...
supabase.storage.from_("assets").upload(path=file_name, ...)  # sanitized_user 미사용
```
모든 사용자 이미지가 버킷 루트에 평탄 적재됨. 의도했던 `{sanitized_user}/{file_name}` 격리 미적용.

**2. `upload_user_video` OOM 완전 무방비**
```python
async def upload_user_video(file: UploadFile = File(...), ...):
    # 크기 체크 없음
    file_content = await file.read()  # 무제한 메모리 로드
```
비디오는 GB 수준 파일도 가능 — 이미지보다 훨씬 큰 OOM 위험.

**3. Magic Bytes 검증 없음 (P3)**
확장자 + MIME은 클라이언트 제공 값에 의존. Pillow `img.verify()`로 실제 이미지 구조 검증 가능.

---

## B — Balance (균형·설계)

### ✅ Signed URL TTL 1800s → 3600s 적절
워크플로우 세션 평균 시간 > 30분을 고려한 합리적 조정. 단, 1시간 초과 세션 시 동일 문제 재발. `expiry_at` 응답 포함 + 클라이언트 갱신 구조 장기 검토 권장.

### ⚠️ Content-Length 정수 변환 예외 처리 없음
`Content-Length: abc` → `int()` → `ValueError` → 500. 방어 처리 필요:
```python
try:
    if content_length and int(content_length) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, ...)
except ValueError:
    pass  # 선행 체크 건너뜀, 사후 체크에서 보증
```

### ⚠️ HTTP 상태 코드 혼용
- 2차 핫픽스 사후 체크(제거됨): `400 Bad Request`
- 3차 핫픽스 선행 체크: `413 Request Entity Too Large`

`413`이 올바른 코드. 하지만 사후 체크 제거로 실제 크기 초과 시 아무 코드도 반환 안됨.

---

## E — Evolution (발전성·유지보수성)

### ✅ 개선점
- 불필요 코드 주석 제거 (`// [FIX] MP4 업로드 JS 락 해제...`) — 코드베이스 정리
- `api` 인스턴스 통합으로 업로드 패턴 일관성 확보

### 후속 개선 제안

**[P1] OOM 이중 방어 복원** — 선행 체크 + 사후 체크 병행:
```python
# 선행 (fast path)
content_length = request.headers.get("content-length")
try:
    if content_length and int(content_length) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, ...)
except ValueError:
    pass

file_content = await file.read()

# 사후 (완전한 보증)
if len(file_content) > 10 * 1024 * 1024:
    raise HTTPException(status_code=413, ...)
```

**[P1] `upload_user_video` 동일 패턴 적용** (MAX 500MB 권장)

**[P2] 사용자 격리 경로 수정**
```python
file_name = f"{sanitized_user}/{image_id}.{ext}"
```

**[P3] 화이트리스트 상수 추출**
```python
ALLOWED_IMAGE_EXTENSIONS = frozenset({'jpg', 'jpeg', 'png', 'webp', 'gif'})
```

---

## 종합 평가

| 항목 | 상태 | 우선순위 |
|------|------|----------|
| 프론트엔드 인증 헤더 | ✅ 해소 | — |
| `file.filename` null 안전 | ✅ 해소 | — |
| Signed URL 수명 | ✅ 해소 | — |
| 확장자 화이트리스트 | ✅ 추가 | — |
| OOM 이중 방어 | ⚠️ 불완전 | P1 |
| 사용자 스토리지 격리 | ❌ 미적용 | P2 |
| 비디오 업로드 OOM | ❌ 무방비 | P1 |
| Magic Bytes 검증 | ❌ 없음 | P3 |

**핵심 결론**: 인증 오류·Signed URL·확장자 검증 목표는 달성. 그러나 OOM 방어는 `237801f`에서 사후 체크를 제거하면서 선행 체크만 남아 오히려 보증 수준이 낮아짐. `upload_user_video`의 무제한 메모리 로드가 현재 가장 큰 잔존 리스크.

---

*생성: Claude Sonnet 4.6 | VIBE Framework Review*

---

리포트 파일 저장이 권한 승인 대기 중입니다. 승인해주시면 `Claude_Review_Report_v2.19.10_P1_3rd_Hotfix_Post.md`로 저장하겠습니다.

**핵심 발견 3가지 요약**:
1. **OOM 방어 퇴보**: `237801f`에서 사후 크기 체크를 제거했음 — Content-Length가 없거나 스푸핑된 경우 여전히 무제한 메모리 로드 가능
2. **`sanitized_user` 데드 코드**: 선언만 하고 스토리지 경로에 미사용 — 사용자 격리가 실제로 적용 안됨
3. **`upload_user_video` 완전 무방비**: 이미지에 추가한 보호가 비디오에는 없음 — GB급 파일 OOM 위험
