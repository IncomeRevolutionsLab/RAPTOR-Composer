# Post-Review Report — [P0] Edge-TTS 전면 전환
**RAPTOR v2.19.x | 2026-06-17 | VIBE Framework**

---

## 1. 변경 범위 요약

| 파일 | 변경 내용 |
|------|-----------|
| `backend/services/ffmpeg_worker.py` | `generate_tts()` 전면 재작성: OpenAI HTTP 호출 → `edge-tts` CLI 서브프로세스 |
| `requirements.txt` | `edge-tts` 패키지 추가 |
| `src/components/RaptorWorkflow.tsx` | 보이스 드롭다운 옵션값 교체 (한글 레이블 → Neural voice ID) |
| `src/store/useWorkflowStore.ts` | `voiceType` 초기값 교체 |

---

## 2. Security (보안)

### S-001 — **[CRITICAL] CLI 인수 미검증 — Command Injection 노출**
```python
# ffmpeg_worker.py:36
cmd = ['edge-tts', '--voice', voice, '--text', text, '--write-media', output_path]
```
`text`는 프론트엔드에서 넘어온 사용자 입력(스크립트 대사)이다. `_run_subprocess`는 리스트 형태로 `subprocess.run`에 전달하므로 shell injection 자체는 방어되지만, `voice` 값은 프론트엔드 `<select>` option의 `value`가 그대로 전달된다.

**문제**: API 레이어에서 `voice` 파라미터를 **서버 사이드 허용 목록으로 검증하지 않는다.** 클라이언트 조작으로 임의 voice ID가 주입되면 edge-tts 내부 오류를 넘어, 향후 CLI 래핑 방식이 변경될 때 공격 벡터가 될 수 있다.

**권고**: 백엔드 진입점(FastAPI route)에서 `voice` 값을 허용 목록(`ALLOWED_VOICES = {"ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-BongJinNeural"}`)에 대조하는 검증 1줄 추가.

### S-002 — **[LOW] `openai_key` 시그니처 잔류**
```python
async def generate_tts(self, text: str, voice: str, output_path: str, openai_key: str):
```
`openai_key` 파라미터가 함수 시그니처에 남아 있고 호출부(`render_video:145`)에서도 계속 전달된다. 사용되지 않는 키 값이 메모리 상에 머무르며, 향후 로깅 코드가 함수 인수를 덤프할 경우 키 노출 위험이 있다.

**권고**: `openai_key` 파라미터를 시그니처와 호출부 양쪽에서 제거. `render_video` 시그니처에는 남겨도 되지만 `generate_tts` 전달 라인에서 삭제 필요.

---

## 3. Stability (안정성)

### ST-001 — **[HIGH] `edge-tts` CLI 실행 실패 시 빈 오디오 파일 생성 가능**
```python
await self._run_subprocess(cmd, check=True)
return output_path
```
`subprocess.run(..., check=True)`가 `CalledProcessError`를 발생시키면 예외 경로로 빠지므로 일반 실패는 잡힌다. **그러나 edge-tts가 exit 0으로 종료하면서 빈 파일(0 bytes)을 남기는 엣지 케이스가 존재한다** — 특히 네트워크 타임아웃이나 voice ID 인식 실패 시.

이후 `render_video:148`의 Integrity Check(`size < 1000`)가 이를 잡아내지만, 에러 메시지가 "Audio file missing or too small"로만 표기되어 TTS 실패임을 진단하기 어렵다.

**권고**: `generate_tts` 반환 전 파일 존재 + 최소 크기 검증 추가:
```python
if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
    raise Exception(f"Edge-TTS output empty or missing: {output_path}")
```

### ST-002 — **[HIGH] `edge-tts` CLI PATH 의존 — 컨테이너 환경 취약**
```python
cmd = ['edge-tts', ...]
```
`edge-tts`가 시스템 PATH에 설치되어 있어야 실행된다. `requirements.txt`에 추가는 되었으나, Koyeb 컨테이너 이미지가 Python 패키지만 설치하면 `edge-tts` CLI는 `~/.local/bin` 또는 `/usr/local/bin`에 위치하게 된다. 이 경로가 PATH에 포함되지 않는 컨테이너 환경에서는 `FileNotFoundError`로 전체 렌더링이 실패한다.

**권고**: CLI 대신 Python API 방식으로 교체:
```python
import edge_tts  # 이미 import 5번 줄에 선재함

async def generate_tts(self, text: str, voice: str, output_path: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return output_path
```
`edge_tts`는 이미 파일 상단 `import edge_tts` (5번 줄)로 임포트되어 있으나 **현재 코드에서 전혀 사용되지 않는다.** CLI 서브프로세스 방식과 Python API 방식이 공존하는 불일치 상태다. Python API 방식을 사용하는 것이 정답이다.

### ST-003 — **[MEDIUM] `asyncio.get_event_loop()` 사용 — Python 3.10+ Deprecation**
```python
# ffmpeg_worker.py:26, 30
loop = asyncio.get_event_loop()
return await loop.run_in_executor(...)
```
이 패턴은 이번 커밋과 직접 관련은 없으나, ST-002 해결 후 `edge_tts.Communicate.save()`는 `async`이므로 `run_in_executor` 없이 직접 `await`하면 이 문제를 함께 우회할 수 있다.

### ST-004 — **[LOW] 보이스 옵션 3개로 축소 — UX 퇴행**
이전 UI는 4개 옵션(여성 발랄/차분, 남성 신뢰감/차분)을 제공했으나, 이번 교체로 3개(SunHi, InJoon, BongJin)로 줄었다. 기능상 문제는 없으나 기존 사용자가 저장한 설정 값("여성-발랄한" 등)이 남아 있을 경우 Zustand persist store에서 구버전 값이 로드되어 **유효하지 않은 voice ID가 edge-tts로 전달**될 수 있다.

**권고**: `useWorkflowStore.ts`에 Zustand `migrate` 함수 또는 store version 범프를 통한 초기화 처리.

---

## 4. Optimization (최적화)

### O-001 — **[MEDIUM] CLI 서브프로세스 오버헤드 vs Python API**
현재 방식은 씬마다 `edge-tts` 프로세스를 새로 스폰한다. Python 프로세스 스폰 비용은 씬 10개짜리 영상 기준 ~0.3–0.5초 누적 오버헤드가 발생한다. ST-002에서 권고한 `edge_tts.Communicate.save()` Python API는 동일 프로세스 내 asyncio로 실행되어 이 오버헤드가 없다.

### O-002 — **[LOW] 미사용 import 잔류**
```python
import httpx  # line 3 — generate_tts에서 OpenAI 제거 후 더 이상 TTS에는 사용 안 됨
import edge_tts  # line 5 — import했으나 미사용
```
`httpx`는 `download_image`(60번 줄)에서 여전히 사용되므로 제거 불가. 그러나 `edge_tts`는 import되어 있으나 실제로 사용되지 않아 린터 경고가 발생한다. ST-002 해결 시 자연스럽게 해소된다.

---

## 5. 종합 평가

| 등급 | 항목 수 | 내용 |
|------|---------|------|
| CRITICAL | 1 | S-001 voice 파라미터 서버사이드 검증 누락 |
| HIGH | 2 | ST-001 빈 파일 케이스 미처리, ST-002 CLI/Python API 불일치 |
| MEDIUM | 2 | ST-004 store 마이그레이션 누락, O-001 프로세스 오버헤드 |
| LOW | 2 | S-002 미사용 키 파라미터, O-002 미사용 import |

**핵심 이슈**: `import edge_tts`가 이미 코드에 존재하는데 CLI를 쓰는 불일치(ST-002)가 가장 시급하다. Python API로 전환하면 ST-001, ST-002, O-001, O-002를 한 번에 해결하고 코드도 5줄로 단순화된다. S-001(voice 허용 목록 검증)은 배포 환경에서 즉시 패치가 필요한 별도 작업이다.
