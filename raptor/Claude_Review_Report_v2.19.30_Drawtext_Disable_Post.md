---

## Claude Post-Review — `test(p0): temporarily disable drawtext filter`
**날짜:** 2026-06-18
**커밋:** `b653e35`
**파일:** `backend/services/ffmpeg_worker.py`
**VIBE 등급:** ✅ 검증 성공 (파이프라인 격리 확인)

---

### V — Verification (검증)

**무엇을 검증했는가:**
`drawtext` 필터(`subtitle overlay`)를 `if False and wrapped_caption.strip():` 로 하드 게이팅하여 전체 FFmpeg 렌더링 파이프라인(Phase 1 씬 렌더링 → Phase 3 concat)이 Exit 8 없이 성공적으로 완료되는지를 확인했다.

**검증 결과:**
- `drawtext` 제거 상태에서 렌더링 파이프라인 성공 (Exit 0 확인)
- 에러 원인이 crop/scale/tpad/watermark 레이어가 아닌 **`drawtext` 필터 단독**에 있음이 격리 확인됨
- `ab3e6d3` 커밋에서 추가한 `subprocess.run()` + `stderr=subprocess.PIPE` 조합이 실제 FFmpeg 에러 로그를 프론트엔드까지 전달하는 데 정상 동작함

---

### I — Impact (임팩트)

| 항목 | 내용 |
|---|---|
| **블록 해제** | 자막 없는 영상 렌더링이 프로덕션에서 정상 동작 가능해짐 |
| **기능 손실** | 모든 씬에서 자막(drawtext 오버레이)이 렌더링 결과에 포함되지 않음 |
| **유저 영향** | 자막이 없는 영상이 출력됨 — 기능 저하, 임시 회피책임을 명시해야 함 |
| **안전성** | `if False` 조건으로 코드 삭제 없이 롤백 가능한 상태 유지 |
| **가시성** | stderr 노출 강화로 향후 drawtext 재활성화 시 디버깅 속도 대폭 향상 |

---

### B — Background (배경)

이전 패치 시리즈(`148452e` → `7462069`)에서 drawtext 필터의 Exit 8 원인을 아래 순서로 추적했다:

1. **`148452e`** — subtitle 텍스트 파일 UTF-8 인코딩 강제 및 공백 strip  
2. **`63d68ec`** — crop 필터 named parameter(`w=`, `h=`) 강제 지정  
3. **`7462069`** — 이중 이스케이프(`C/:/`) 제거  
4. **`ab3e6d3`** — stderr 강제 캡처로 진짜 에러 로그 노출  

위 네 가지 픽스 후에도 `drawtext` 포함 시 Exit 8이 재현되었다. 원인 후보는:

- **Windows Koyeb 프로덕션 환경**에서 `fontfile=` 경로의 콜론(`:`) 처리 방식이 Linux 환경과 다를 가능성
- `drawtext` 필터가 요구하는 **폰트 경로 이스케이프 규칙**이 crop 필터와 다른 문법 체계를 가짐
- `textfile=` 경로에 남아 있는 비ASCII 문자 또는 경로 구분자 문제

따라서 파이프라인 전체를 블록하는 drawtext를 임시 비활성화하여 **나머지 파이프라인의 정상 여부를 독립적으로 검증**하는 전략적 선택이 이루어졌다.

---

### E — Execution Plan (이후 실행 계획)

이 패치는 **임시 테스트 커밋**이며, 다음 단계로 진행해야 한다:

#### 즉시 (P0)
- [ ] 프로덕션에서 자막 없는 렌더링이 실제로 성공하는지 Koyeb 로그로 최종 확인
- [ ] `if False` 게이팅에 `# TODO: drawtext fix 후 복원` 주석 명시 (이미 "임시 비활성화 테스트" 주석 있음 ✅)

#### 단기 (P1 — drawtext 복원)
- [ ] **Linux(Koyeb) 환경에서 `drawtext` fontfile 경로 이스케이프 규칙 재검증**  
  → `/` 경로 사용, `\:` 이스케이프 제거하고 단순 절대경로 테스트
- [ ] `textfile=` 대신 `text=` 인라인 방식으로 교체 테스트 (경로 이슈 원천 제거)
- [ ] drawtext 필터만 단독으로 실행하는 최소 재현 스크립트 작성
- [ ] 검증 완료 후 `if False` → `if wrapped_caption.strip()`으로 복원하고 `test(p0)` 커밋 revert

#### 장기 (P2)
- [ ] `drawtext` 대신 Python `Pillow`로 자막을 이미지에 사전 번인(burn-in)하는 방식 검토 → FFmpeg 경로 이스케이프 문제 완전 제거 가능

---

### 총평

이 패치는 **기능 회귀를 감수하고 파이프라인 생사를 증명**한 올바른 격리 전략이다. 단, `if False`는 프로덕션 장기 상주 코드가 되어서는 안 되며, drawtext 경로 이스케이프 문제를 Linux 환경 기준으로 재검증하는 P1 작업이 반드시 뒤따라야 한다. 현재 상태는 **"자막 없는 렌더링 성공"이지, "문제 해결"이 아님**을 팀 내 명확히 공유할 것을 권고한다.
