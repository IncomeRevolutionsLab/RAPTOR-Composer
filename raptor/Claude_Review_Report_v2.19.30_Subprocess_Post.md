---

## VIBE Post-Review — `subprocess.run` stderr 캡처 및 강제 예외 개편 (ab3e6d3)

**리뷰 기준일:** 2026-06-18
**대상 커밋:** `ab3e6d3` (fix(p0): capture and expose FFmpeg stderr logs to debug Exit 8 crashes on production)
**대상 파일:** `backend/services/ffmpeg_worker.py`, 특히 `render_video()` Phase 2 (씬 렌더링 루프, L441~L461)

---

### V — Validity (변경의 타당성)

**판정: PASS (조건부)**

변경의 핵심 동기는 타당하다. 기존 코드는 `await self._run_subprocess(cmd_scene, check=True, capture_output=True, text=True, cwd=temp_dir)`를 호출했는데, `_run_subprocess`는 내부적으로 `loop.run_in_executor`에서 `subprocess.run`을 wrapping한 async 헬퍼다. 이 구조에서 `check=True`로 발생한 `CalledProcessError`는 executor 내부에서 raise되어 asyncio 이벤트 루프로 올라오는 과정에서 실제 `.stderr` 속성이 유실되거나 로그가 누락될 여지가 있었다. 이를 직접 `subprocess.run(... stderr=subprocess.PIPE)`로 변경하고 returncode를 명시적으로 검사하는 방식은 구조적으로 더 안전한 접근이다.

단, **주의할 점**: 이 변경으로 인해 해당 씬 렌더링 호출이 `_run_subprocess` 헬퍼를 **우회하여 동기 호출**로 바뀌었다. `subprocess.run`은 blocking call이므로, 이벤트 루프를 점령할 수 있다. 나머지 FFmpeg 호출(L225, L315, L478)은 여전히 `_run_subprocess`(→ `run_in_executor`) 경로를 사용하고 있어 이 씬 렌더링 단계만 일관성이 깨졌다.

---

### I — Intent Alignment (의도와 구현의 일치)

**판정: PARTIAL PASS**

의도: "Exit 8 발생 시 FFmpeg의 진짜 stderr를 프로덕션 로그에 노출한다"
구현: `result.stderr`를 `RuntimeError` 메시지에 직접 포함시켜 상위 호출 스택으로 전파.

**잘 된 부분:**
- `error_message`에 실행 커맨드(`' '.join(cmd_scene)`)와 `result.stderr`를 함께 포함시켜, 로그 하나로 재현 가능한 정보를 모두 담았다. 이는 프로덕션 디버깅 효율을 실질적으로 높인다.
- `raise RuntimeError(error_message)` → Exception chaining (`from e`)을 통해 traceback 연속성을 유지했다.

**부족한 부분:**
- `except Exception as e: raise RuntimeError(f"렌더링 중단 안내:\n{e}") from e` 블록은 바로 위 try 블록에서 이미 `RuntimeError`를 raise하는 구조인데, 이 catch가 그것을 한 번 더 wrapping한다. 즉 **정상 실패 경로에서 RuntimeError가 RuntimeError를 감싸는 이중 포장**이 발생한다. 가독성과 traceback 오염 측면에서 의도 없는 노이즈다.
- `result.stdout`은 캡처하고 있으나 어디에도 사용되지 않는다. FFmpeg는 stdout에 출력하지 않으므로 낭비는 아니지만, 명시적으로 `subprocess.DEVNULL`로 처리하지 않은 점은 미완성 감을 준다.

---

### B — Blast Radius (영향 범위)

**판정: MEDIUM RISK**

이 변경은 씬 렌더링 루프(`Phase 2`) 전체에 적용된다. 렌더링 요청 하나당 장면 수만큼 이 코드가 실행되므로, 동기 blocking이 이벤트 루프에 미치는 영향은 누적적이다. Koyeb 환경의 싱글 프로세스 서버 구조상, 렌더링이 오래 걸리는 요청이 들어오면 다른 async 작업이 starve될 가능성이 있다.

단, `render_semaphore = asyncio.Semaphore(2)`로 동시 렌더 슬롯을 2개로 제한하고 있고, FFmpeg 자체가 CPU-bound이기 때문에 실제 이벤트 루프 점유 문제가 현재 프로덕션에서 관측되지 않을 수는 있다. 다만 이 패턴은 향후 concurrent 요청이 늘어날 때 회귀 포인트가 된다.

---

### E — Effectiveness (디버깅 효과)

**판정: PASS**

핵심 목적인 "Exit 8 원인 파악"에 대해서는 실질적으로 효과적이다.

기존에 `CalledProcessError`가 executor에서 escape되면서 stderr가 `print`로만 출력되어 Koyeb 로그에 잡히지 않거나 누락될 수 있었다. 이제 `RuntimeError`의 메시지 본문에 FFmpeg stderr 전체가 포함되므로, 상위 API 핸들러나 Koyeb 로그 수집기에서 해당 에러를 캡처하면 Exit 8의 직접 원인(잘못된 필터 문법, 파일 없음, 코덱 불일치 등)을 즉시 확인할 수 있다.

실전 디버깅 가치 측면에서 이 변경은 "Exit 8 발생 → 원인 추정 → 가설 수정" 사이클을 눈에 띄게 단축한다.

---

### 종합 판정: CONDITIONAL PASS

| 항목 | 판정 |
|------|------|
| Validity | PASS (조건부 — 동기 blocking 이슈) |
| Intent Alignment | PARTIAL PASS (이중 wrapping 노이즈) |
| Blast Radius | MEDIUM RISK (이벤트 루프 blocking 잠재) |
| Effectiveness | PASS |

---

### 권고 후속 조치 (우선순위 순)

1. **[P1] 동기 호출 복구** — `subprocess.run(...)`을 `await asyncio.get_event_loop().run_in_executor(None, lambda: subprocess.run(...))`로 wrapping하거나, 기존 `_run_subprocess` 헬퍼를 확장하여 stderr PIPE를 지원하도록 수정. 이벤트 루프 blocking을 방지하고 코드 일관성 회복.

2. **[P2] 이중 RuntimeError wrapping 제거** — 현재 `try/except` 구조에서 `raise RuntimeError` 후 즉시 `except Exception as e: raise RuntimeError(...) from e`가 그것을 재감싼다. `except Exception` 블록은 `subprocess.run` 자체가 OS 레벨에서 실패하는 극단적 케이스(FFmpeg 바이너리 없음 등)를 위한 것이라면, 해당 의도를 주석으로 명시하거나 `except OSError`처럼 범위를 좁혀야 한다.

3. **[P3] stdout 처리 명확화** — `stdout=subprocess.PIPE` 대신 `stdout=subprocess.DEVNULL`로 변경하거나, 향후 verbose 모드 활용 의도가 있다면 `result.stdout`을 디버그 로그에 포함.
