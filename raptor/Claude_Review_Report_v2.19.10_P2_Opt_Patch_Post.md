이제 전체 diff를 분석했습니다. VIBE 프레임워크 리뷰 리포트를 작성합니다.

---

## Post-Review: P2 아키텍처 최적화 패치 (로컬 비디오 정리, 에러 처리, 상수화)

### 종합 판정: **PASS with Minor Gaps**

핵심 변경 4건(상수화, 화이트리스트, 에러 전파, 파일 정리)은 모두 올바르게 구현됨. 단, 운영 중 혼선을 유발할 수 있는 **P2 이슈 3건** 발견.

---

### 변경 1: 매직 넘버 상수화 (`MAX_IMAGE_SIZE`, `MAX_VIDEO_SIZE`) — ✅ 동작 정확, ⚠️ 위치 문제

| 항목 | 판정 |
|------|------|
| `content-length` 헤더 체크에 상수 적용 | ✅ |
| body read 후 이중 체크에도 상수 적용 | ✅ |
| 이미지/비디오 두 엔드포인트 모두 반영 | ✅ |
| 상수 위치 (엔드포인트 사이) | ⚠️ |

```python
# 현재 위치: line 1866 — get_archive() 핸들러 직후, upload_user_image() 직전
MAX_IMAGE_SIZE = 10 * 1024 * 1024
MAX_VIDEO_SIZE = 500 * 1024 * 1024

# 권고: 파일 상단 모듈 레벨 상수 영역으로 이동
# 함수 사이에 상수를 정의하면 grep 시 발견이 어렵고, 미래에 재사용할 때
# "어디 있지?" 문제 발생.
```

---

### 변경 2: 비디오 확장자 화이트리스트 — ✅ 완전 통과

| 항목 | 판정 |
|------|------|
| `file.filename or 'upload.mp4'` None 방어 | ✅ |
| 확장자 없는 파일명 폴백 처리 | ✅ |
| mp4/mov/webm 화이트리스트 체크 | ✅ |
| 체크 순서 (content-length → content-type → ext) | ✅ |
| `filename` 변수로 DB insert / response 통일 | ✅ (버그 수정 포함) |

**참고**: 실제 스토리지 저장 경로는 항상 `.mp4`로 하드코딩되어 있어, `.mov`·`.webm` 파일도 `video/mp4` MIME으로 저장됨. 재생 문제 가능성이 있으나 P2 범위 외 이슈.

---

### 변경 3: Supabase 스토리지 업로드 에러 무음 처리 → 전파 — ✅ 완전 통과

| 항목 | 판정 |
|------|------|
| 기존 `Warning` 출력만 하던 로직 제거 | ✅ |
| 500 + 한국어 메시지로 즉시 전파 | ✅ |
| `finally` 블록과 연동 → 에러 시에도 로컬 파일 정리됨 | ✅ |

```python
# 기존 (무음 실패 — P1 리스크):
except Exception as e:
    print(f"[Supabase Storage Upload Warning] {e}")
    # DB insert가 뒤따라 실행되며 스토리지 없는 레코드 생성 가능

# 변경 후 (명시적 실패 전파):
except Exception as e:
    print(f"[Supabase Storage Upload Error] {e}")
    raise HTTPException(status_code=500, detail="비디오 스토리지 업로드 실패")
```

⚠️ **소이슈**: 에러 메시지만 한국어. 동일 파일 내 다른 에러 메시지는 영어 (`"File size exceeds 10MB limit."`, `"Only video files are allowed."` 등). 일관성 권고.

---

### 변경 4: `finally` 블록을 통한 로컬 비디오 파일 정리 — ✅ 로직 정확, ⚠️ 주석 스테일

| 항목 | 판정 |
|------|------|
| 성공 경로에서 파일 삭제 | ✅ |
| 예외 경로에서도 파일 삭제 (`finally`) | ✅ |
| 정리 실패가 원본 예외를 마스킹하지 않음 (inner try-except) | ✅ |
| `os.path.exists()` 방어 체크 | ✅ |

```python
# ⚠️ P2: 이 주석이 현재 동작과 정반대 의미가 됨
# Save file locally for test runner and worker access  ← 삭제 권고
with open(file_path, "wb") as buffer:
    buffer.write(file_content)
# finally 블록이 즉시 파일을 삭제하므로 "worker access" 불가능
```

또한 `file_path = f"outputs/{video_id}.mp4"` 에서 `outputs/` 디렉토리 미존재 시 `FileNotFoundError` 발생 가능. 사전에 `os.makedirs("outputs", exist_ok=True)` 호출 권고 (pre-existing 이슈).

---

### 수정 우선순위

| 우선순위 | 항목 | 수정 규모 |
|----------|------|-----------|
| P2 | `MAX_IMAGE_SIZE`/`MAX_VIDEO_SIZE` 모듈 상단으로 이동 | 위치 이동 |
| P2 | 스테일 주석 `# Save file locally for test runner...` 삭제 | 1줄 |
| P2 | 에러 메시지 언어 통일 (`"비디오 스토리지 업로드 실패"` → 영어) | 1줄 |
| P3 | `os.makedirs("outputs", exist_ok=True)` 추가 | 1줄 (pre-existing) |

---

### 패치 전체 요약

이번 P2 패치는 **이전 P0/P1 핫픽스에서 남겨진 기술 부채를 정리**하는 작업으로, 모든 핵심 의도(디스크 누수 방지, 무음 실패 제거, 매직 넘버 제거)가 올바르게 구현됨. 발견된 3건은 모두 P2 수준으로, 즉각적인 운영 리스크는 없음.

---

위 리포트를 파일로 저장할까요? 그리고 P2 소이슈 수정 작업을 바로 진행할지, 아니면 다음 패치에 포함시킬지 알려주세요.
