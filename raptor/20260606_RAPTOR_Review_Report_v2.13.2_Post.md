# 📋 RAPTOR v2.13.2-fix 사후 아키텍처 리뷰 보고서 (Post-Review)

- **리뷰 수행일:** 2026-06-06
- **대상 코드:** `main.py` / `backend/services/ffmpeg_worker.py` / `src/components/RaptorWorkflow.tsx` / `e2e_recheck.js`
- **리뷰 툴:** Claude CLI (B모드 아키텍처 감사)

---

## 1. 성능 저하 / 메모리·디스크 누수

### [CRITICAL] `ffmpeg_worker.py` — `temp_dir` 미정리 (디스크 무한 누수)

`render_video`는 `temp_{task_id}/` 디렉토리를 생성하고 씬 이미지·오디오·중간 MP4를 채우지만, 최종 MP4 생성 후 해당 디렉토리를 삭제하지 않는다.

```python
# render_video() 끝부분 — temp_dir 정리 없음
if os.path.exists(final_output):
    yield { "task_id": ..., "status": "completed", ... }
else:
    raise Exception("Physical MP4 creation failed.")
# ← temp_dir이 그대로 남는다
```

렌더링 1회당 씬 수 × (jpg + mp3 + scene_*.mp4) + trimmed_*.mp4 + concat.txt가 누적된다. 씬 5개 기준 30~200 MB/렌더링. 예외 경로에서 `finally` 없이 종료되면 더 심각하다.

**수정 방향:** `try/finally`로 `shutil.rmtree(temp_dir, ignore_errors=True)` 추가.

---

### [HIGH] `main.py` — JSON 파일 DB Read-Modify-Write 무잠금 (Race Condition)

`create_project_in_db`, `create_task_in_db`, `update_task_in_db`가 모두 `json.load → append → json.dump` 패턴을 사용하는데 파일 락이 없다.

`render_stream`에서 `asyncio.create_task`로 N개 씬을 병렬 처리할 때 각 태스크가 동시에 `create_task_in_db`를 호출하면, 마지막으로 `json.dump`한 프로세스만 결과가 남고 나머지 태스크 기록이 유실된다.

**수정 방향:** `asyncio.Lock`을 모듈 레벨 싱글턴으로 선언하고 파일 접근 전 `async with db_lock:`.

---

### [HIGH] `main.py` — `check_and_enforce_user_limits` TOCTOU

월간 카운트 체크(`if monthly_count >= 10: raise`) 직후 실제 프로젝트 생성(`create_project_in_db`) 사이에 다른 비동기 요청이 끼어들면 한도가 유령처럼 통과된다. 위 Race Condition과 합쳐지면 10명의 동시 요청이 모두 월간 1번 호출로 체크되어 전부 통과한다.

---

### [MEDIUM] `RaptorWorkflow.tsx` — `compressImage` Canvas 메모리 해제 없음

`compressImage`에서 `new Image()` + `document.createElement('canvas')`를 생성하지만 `onload` 이후 `canvas.width = canvas.height = 0`(브라우저 메모리 해제 힌트) 처리가 없다. 파일 20개(`images.slice(-20)`) 모두 병렬 처리하면 디코딩된 이미지 버퍼 20개가 GC 수집 전까지 힙에 머문다. Base64 1024px JPEG 기준 약 3~6 MB × 20 = 60~120 MB 일시 점유.

---

### [MEDIUM] `main.py` `/api/generate-videos` — Veo 폴링 루프 절대 상한 하드코딩 불일치

`polling_timeout = 720 if request.engine == "grok" else 900` 이후, 절대 상한인 `if elapsed >= 1800` 체크가 단일 씬 기준이다. `render_stream`에서 N개 씬이 병렬로 각각 최대 1800초씩 실행되면, 실질적 최대 대기는 여전히 1800초(단일 최장 씬)다. 그러나 프론트엔드 타임아웃은 `setTimeout(1800000)` 즉 정확히 1800초로, 폴링 시작 전 Supabase 업로드·태스크 생성 오버헤드(~10s/scene)가 더해지면 프론트엔드가 먼저 abort하고 서버 폴링은 계속 진행되는 구조적 불일치가 발생한다.

---

## 2. 보안 결함

### [CRITICAL] `main.py:1617` — `/api/webhook/kie` 무인증

```python
@app.post("/api/webhook/kie")
async def webhook_kie(payload: KieWebhookPayload):
    # 인증/서명 검증 없음
```

`task_id` 열거가 가능하면(`task_` + 짧은 hex) 임의의 공격자가 `{"task_id": "task_xxx", "status": "completed", "result_url": "https://malicious.com/payload.mp4"}` 를 전송해 레코드를 위조하고 `expires_at`을 부여받을 수 있다.

**수정 방향:** KIE AI의 웹훅 시크릿을 `WEBHOOK_SECRET` 환경변수로 받아 HMAC-SHA256 서명 헤더 검증.

---

### [CRITICAL] `main.py:487` — `/api/user-videos` GET IDOR

```python
@app.get("/api/user-videos")
async def get_user_videos(user_id: str):
```

인증 없이 `?user_id=anyone` 으로 타인의 비디오 목록을 조회할 수 있다. JWT 검증이 render-stream에만 있고 조회 API에는 없다.

---

### [HIGH] `main.py:706` — 하드코딩 개발자 로컬 경로 노출

```python
brain_base_dir = r"C:\Users\webke\.gemini\antigravity-ide\brain"
```

이 경로는 배포 환경에서 존재하지 않아 `os.walk` fallback으로 CWD를 쓰지만, 더 근본적으로 로컬 개발자 경로가 소스코드에 노출된 상태다. `report_path = os.path.join(target_brain_dir, report_filename)`에서 `target_brain_dir`가 walk 결과(`os.walk`)이므로, 예상치 못한 디렉토리에 파일 쓰기가 가능하다.

---

### [HIGH] `main.py:649` — CSRF 쿠키 만료 30일 (CSRF 토큰 수명 과다)

```python
res.set_cookie(key="raptor_csrf", ..., max_age=2592000)  # 30일
```

CSRF 토큰이 30일간 유효하면 세션 탈취 후 공격 창이 매우 넓다. 통상 세션 쿠키 수명(1~24시간)에 맞추는 것이 표준이다.

---

### [MEDIUM] `ffmpeg_worker.py:292` — FFmpeg drawtext 필터 경로 이스케이프 불완전

```python
safe_text_file_path = os.path.abspath(text_file_path).replace("\\", "/").replace(":", "\\:")
```

FFmpeg `drawtext` 필터에서 `'`(홑따옴표), `[`, `]` 문자는 필터 체인 파싱 구분자다. `temp_dir`가 `outputs/temp_{task_id}/`이고 `task_id`가 사용자 입력 파생이면 이론적으로 필터 인젝션 가능성이 있다. 현재 `task_id = str(uuid.uuid4())`로 생성하므로 실제 위험은 낮지만, 방어적 이스케이프가 불충분하다.

---

### [MEDIUM] `main.py:592` — 관리자 API 키로 이메일 미인증 회원가입 직접 호출

```python
url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/admin/users"
headers = {"Authorization": f"Bearer {SUPABASE_KEY}", ...}
data = {"email_confirm": True}
```

`SUPABASE_KEY`는 service role key다. 이 엔드포인트를 백엔드가 직접 노출하면 이메일 인증 없이 임의 계정 생성이 서버에서 항상 가능하다. 공격자가 `/api/auth/signup`에 무한 요청을 보내면 Supabase DB를 임의 계정으로 도배할 수 있다 — rate limiting 없음.

---

## 3. 프론트엔드 폴링 방어 로직 TDD 채점

| 케이스 | 구현 상태 | 점수 | 상세 |
|---|---|---|---|
| **C1** SSE 스트림 정상 종료 후 `finalUrl` null | `throw new Error("결과 URL을 서버로부터 받지 못했습니다.")` (L674) | ✅ PASS | 에러 핸들링 정상 |
| **C2** 30분 클라이언트 타이어아웃 AbortError | `setTimeout(1800000)` + catch AbortError 처리 (L582, L680) | ✅ PASS | 메시지 분기 정상 |
| **C3** AbortError 이후 서버 렌더링 결과 복구 | 복구 메커니즘 없음. 서버 MP4가 완성돼도 클라이언트가 재수신 불가 | ❌ FAIL | `/api/tasks/{task_id}` 폴백 폴링 없음 |
| **C4** SSE 네트워크 일시 단절 후 재연결 | `fetch + ReadableStream` 조합은 자동 재연결 없음. EventSource가 아님 | ❌ FAIL | 단절 시 전체 재시도만 가능 |
| **C5** SSE 청크 파싱 에러 무음 처리 | `"Unexpected end of JSON input"` 등 삼킴 (L656) | ⚠️ WARN | 실제 에러 마스킹 가능성 |
| **C6** `isRendering` 중 페이지 새로고침 | `useEffect`에서 `setRenderStatus(false, 0)` (L95) | ✅ PASS | 좀비 상태 방지 |
| **C7** 씬 롤백 (렌더링 중단 시) | catch 블록에서 `scene.status = 'error'` 롤백 (L689-697) | ✅ PASS | 무한 대기 UX 방지 |
| **C8** e2e: SSE 스트림 완료 및 최종 URL 수신 검증 | 헤더/payload 검증만 있고 스트림 완료 여부 미검증 | ❌ FAIL | `e2e_recheck.js` Step 6에서 `output_url` 수신 확인 없음 |
| **C9** 서버 `generate_stream` 예외 시 temp_dir 정리 | `generate_stream` 내부에 `finally` 블록 없음 | ❌ FAIL | 앞서 언급한 디스크 누수와 연결 |
| **C10** RISK-B Guard: DB에서 기존 완성 비디오 복구 | `process_scene_inner` 초입부 DB 조회 존재 (L1921) | ✅ PASS | 재시도 시 중복 생성 방지 |

**TDD 종합 점수: 5/10 (C1, C2, C6, C7, C10 PASS)**

---

## 4. 즉시 조치 필요 항목 요약

| 우선순위 | 위치 | 결함 |
|---|---|---|
| P0 | `ffmpeg_worker.py` | `temp_dir` 미정리 — 프로덕션 디스크 포화 직결 |
| P0 | `main.py:1617` | `/api/webhook/kie` 무인증 — 태스크 위조 가능 |
| P0 | `main.py:487` | `/api/user-videos` IDOR — 타인 데이터 열람 가능 |
| P1 | `main.py` | JSON DB 파일 락 없음 — 병렬 렌더링 시 데이터 유실 |
| P1 | `RaptorWorkflow.tsx` | 폴링 C3/C4 미구현 — 타임아웃 후 결과 복구 불가 |
| P2 | `main.py:706` | 로컬 절대경로 하드코딩 — 배포 불가 + 경로 노출 |
| P2 | `e2e_recheck.js` | SSE 스트림 완료 검증 없음 — 렌더링 성공 여부 미확인 |
