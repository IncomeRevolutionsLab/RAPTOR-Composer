# Post-Review Report — [P0] Edge-TTS Python Native API 전환 후속 패치
**RAPTOR v2.19.x | 2026-06-17 | VIBE Framework**
**대상 커밋**: `5dfb47c` → `4308478`
**대상 파일**: `backend/services/ffmpeg_worker.py`, `src/store/useWorkflowStore.ts`

---

## 1. 변경 범위 요약

| 파일 | 커밋 | 변경 내용 |
|------|------|-----------|
| `ffmpeg_worker.py` | `4308478` | `generate_tts()` — voice 화이트리스트 검증 + fallback 추가, `openai_key` 파라미터 제거, 파일 무결성 검증 내재화 |
| `useWorkflowStore.ts` | `4308478` | `onRehydrateStorage` — 구버전 voiceType 검증 + fallback 추가 |

---

## 2. 이슈별 해소 검증

### S-001 — **[CRITICAL → RESOLVED]** voice 파라미터 서버사이드 검증 누락

```python
# ffmpeg_worker.py:35-37
allowed_voices = {"ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-BongJinNeural"}
if voice not in allowed_voices:
    voice = "ko-KR-SunHiNeural"
```

**검증 결과**: ✅ **완전 해소**

`generate_tts()` 진입부에 허용 목록 대조 로직이 추가되었다. 권고 위치는 FastAPI route 레이어였으나, 이번 패치에서 Python native API로 전환이 완료된 시점에서는 CLI 인수 주입 자체가 불가능하므로 위협 모델이 사전 소멸되었고 worker 레이어 검증으로도 방어 효과는 동등하다.

**관찰**: fallback이 예외 발생(raise) 없이 silent substitution으로 구현되어 있어, 조작된 값 수신 시 서버 로그에 기록이 남지 않는다. 이는 보안 감사 측면의 미세한 약점이나, 현재 위협 수준에서 추가 패치 불필요.

---

### S-002 — **[LOW → RESOLVED]** `openai_key` 시그니처 잔류

```python
# 이전 (5dfb47c)
async def generate_tts(self, text: str, voice: str, output_path: str, openai_key: str):

# 이후 (4308478)
async def generate_tts(self, text: str, voice: str, output_path: str):
```

**검증 결과**: ✅ **완전 해소**

`generate_tts` 시그니처와 호출부(`render_video` 내 호출 라인)에서 `openai_key` 파라미터가 모두 제거되었다. `render_video` 함수 시그니처(line 108)에는 `openai_key: str = None`이 잔류하나, 이는 이전 리뷰에서 "남겨도 된다"고 명시한 범위로 S-002 스코프 밖이다.

---

### ST-001 — **[HIGH → RESOLVED]** exit 0 + 빈 파일 케이스 미처리

```python
# ffmpeg_worker.py:43-44
if not os.path.exists(output_path) or os.path.getsize(output_path) < 1000:
    raise Exception(f"Edge-TTS output empty or missing: {output_path}")
```

**검증 결과**: ✅ **완전 해소**

`generate_tts()` 내부에서 `communicate.save()` 반환 직후 파일 존재 + 최소 크기(1 KB) 검증을 수행한다. 에러 메시지가 "Edge-TTS output empty or missing"으로 TTS 실패를 명확히 식별할 수 있다. 검증이 `save()` 성공 반환 후에 위치하므로 exit 0 + 빈 파일 케이스를 정확히 포착한다.

---

### ST-002 — **[HIGH → RESOLVED]** CLI PATH 의존 — 컨테이너 환경 취약

```python
# 이전 (5dfb47c) — CLI 서브프로세스
cmd = ['edge-tts', '--voice', voice, '--text', text, '--write-media', output_path]
await self._run_subprocess(cmd, check=True)

# 이후 (4308478) — Python native API
communicate = edge_tts.Communicate(text, voice)
await communicate.save(output_path)
```

**검증 결과**: ✅ **완전 해소**

`edge_tts.Communicate.save()`는 동일 Python 프로세스 내 asyncio로 실행되며 시스템 PATH에 독립적이다. `import edge_tts` (line 5)와 실제 사용이 일치하여 이전 불일치 상태도 해소되었다. `_run_subprocess` wrapper를 거치지 않으므로 프로세스 스폰 오버헤드(O-001)도 함께 제거되었다.

---

### ST-004 — **[MEDIUM → RESOLVED]** Zustand persist store 구버전 voice 값

```typescript
// useWorkflowStore.ts:244-250
onRehydrateStorage: () => (state) => {
  if (state) {
    const allowedVoices = ["ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-BongJinNeural"];
    if (!allowedVoices.includes(state.voiceType)) {
      state.setVoiceType("ko-KR-SunHiNeural");
    }
```

**검증 결과**: ✅ **완전 해소**

`onRehydrateStorage` 콜백에서 허용 목록 대조 후 구버전 값("여성-발랄한" 등)을 `"ko-KR-SunHiNeural"`로 폴백 처리한다. store version bump나 `migrate` 함수 없이 rehydration-time 검증으로 구현한 방식은 현재 케이스(단순 값 유효성 교체)에서 동등한 효과를 가지며 코드 복잡도가 낮다. store 초기값(line 141)도 `'ko-KR-SunHiNeural'`로 올바르게 설정되어 있다.

---

## 3. 신규 관찰 사항

**N-001 — [LOW] `render_video` 시그니처의 `openai_key` 잔류**

```python
# ffmpeg_worker.py:108
async def render_video(self, ..., openai_key: str = None, ...):
```

`render_video`의 `openai_key` 파라미터는 현재 함수 내에서 `generate_tts` 호출 시 전달되지 않으며 내부에서도 사용되지 않는다. 다만 FastAPI route에서 이 시그니처를 통해 파라미터를 수신하는지 여부에 따라 클리어 여부가 결정된다. 이번 패치 스코프 밖이나 다음 리팩토링 시 정리 권고.

---

## 4. 종합 평가

| 이슈 ID | 심각도 | 이전 상태 | 현재 상태 |
|---------|--------|-----------|-----------|
| S-001 | CRITICAL | 미처리 | ✅ 해소 |
| S-002 | LOW | 미처리 | ✅ 해소 |
| ST-001 | HIGH | 미처리 | ✅ 해소 |
| ST-002 | HIGH | 미처리 | ✅ 해소 |
| ST-004 | MEDIUM | 미처리 | ✅ 해소 |
| N-001 | LOW | (신규) | 미처리 (다음 리팩 대상) |

**최종 판정**: **APPROVED — 조건부 완전 해소**

이전 리뷰에서 지적된 5개 이슈(S-001, S-002, ST-001, ST-002, ST-004) 전체가 해소 확인되었다. 특히 ST-002(CLI → Python native API 전환)가 S-001(command injection 위협 모델 소멸), O-001(프로세스 오버헤드), O-002(미사용 import 불일치)를 연쇄 해소한 점이 이번 패치의 핵심 품질 향상 지점이다. 신규 발견 N-001은 기능 영향 없음, 다음 정기 리팩 시 처리 권고.
