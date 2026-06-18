파일 쓰기 권한을 승인해주시면 저장하겠습니다. 아래에 리포트 전체 내용을 출력합니다.

---

# RAPTOR VIBE Code Review — P0 Emergency Hotfix
**Commit**: `cb179e4` — `fix(p0): add missing os and api imports to resolve render and vercel crashes`
**Date**: 2026-06-16 | **Files**: `main.py` (+5/-10), `RaptorWorkflow.tsx` (+24/-19)

---

## 총평 (Executive Summary)

| 구분 | 원인 | 심각도 | 수정 완결성 |
|---|---|---|---|
| Python `IndentationError` | `except` 블록 들여쓰기 오류로 FastAPI 앱 시작 불가 | **P0 / Critical** | 완전 해결 |
| TypeScript `TS2345` | `api.post()` axios 타입 충돌로 Vercel 빌드 실패 | **P0 / Critical** | 완전 해결 |

---

## V — Verification (수정 정확성 검증)

### [1] Python `IndentationError` — `main.py:2327`

**근본 원인**: `except Exception as e:` 블록에 유효한 실행문이 없고(공백 줄만 존재), `if "veo" in str(e).lower():` 블록이 `except`와 **동일한 들여쓰기 수준**, 즉 블록 외부에 위치했습니다.

Python은 `except` 절에 최소 하나의 실행문을 요구하므로 **모듈 파싱 시점에 `IndentationError`가 발생**, FastAPI 앱 전체가 시작되지 않습니다. Render Worker가 기동 자체를 못 하는 P0 장애의 직접 원인입니다.

추가로, Python 3는 `except` 블록 종료 시 `e` 변수를 소멸시키므로, 설령 파싱을 통과했어도 블록 외부의 `str(e)` 호출은 런타임 `NameError`를 유발했을 것입니다.

```python
# AFTER (fixed) — if/else가 except 내부로 이동
except Exception as e:
    if "veo" in str(e).lower():
        yield f"data: {json.dumps({'status': 'error', 'message': 'Veo3.1 비디오 생성 실패. 툴팁 참조.'})}\n\n"
    else:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"
    return
```

**판정**: 정확함. `return`이 `except` 안에 있는 것도 올바릅니다 — async generator에서 `return`은 `StopAsyncIteration`을 발생시켜 에러 발생 시 스트림을 종료합니다.

---

### [2] TypeScript `TS2345` — `RaptorWorkflow.tsx:1474, 1517, 1568`

**근본 원인**: axios `api.post()` 호출 시 `headers: { 'Content-Type': 'multipart/form-data' }` 리터럴 타입이 axios 타입 정의와 불일치하여 `TS2345` 발생. Vercel은 빌드 시 strict TS 검사를 통과해야 하므로 배포 자체가 불가능한 상태였습니다.

**fix**: native `fetch()`로 전환. 타입 오류 제거와 함께 두 가지 동작 개선이 부수효과로 달성됩니다:

1. **`Content-Type` 헤더 미설정** → 브라우저가 `boundary=...` 포함한 올바른 헤더를 자동 설정 (명시 시 boundary 누락으로 실제 업로드 실패 가능성 있었음)
2. **Authorization 헤더 추가** → 기존 `api.post()` 호출에서 누락되었던 Supabase JWT 인증 헤더 포함

**판정**: 정확함. axios 우회가 타입 안전성과 실제 동작 모두를 개선하는 더 나은 선택이었습니다.

---

## I — Impact (영향 범위)

| 사용자 흐름 | 이전 상태 | 이후 상태 |
|---|---|---|
| Render 백엔드 기동 | 실패 (앱 시작 불가) | 정상 |
| Vercel 프론트엔드 빌드 | 실패 (TS 빌드 오류) | 정상 |
| 장면 이미지 등록 / 변경 | 미제공 (빌드 실패) | 정상, 인증 포함 |
| 장면 비디오 등록 | 미제공 (빌드 실패) | 정상, 인증 포함 |

**보안 개선**: 이전 `api.post()` 호출에 없었던 Authorization 헤더가 추가됨. 백엔드의 JWT 검증 강도에 따라 실질적인 사용자 격리가 강화됨.

---

## B — Breakage Risk (회귀 위험 및 잔존 이슈)

### [B-1] 비디오 업로드 `try` 블록 들여쓰기 불일치 ⚠️ Minor
`RaptorWorkflow.tsx:1519-1520` — `try {` 와 그 첫 줄이 동일한 들여쓰기 수준입니다. JS/TS는 들여쓰기가 의미에 영향을 주지 않으므로 **런타임 동작은 정상**이나, 이미지 업로드 블록(1477, 1571)과 일관성이 깨진 상태로 린터 경고 대상이 됩니다.

### [B-2] 비디오 업로드 실패 시 사용자 피드백 없음 ⚠️ Minor (기존 버그)
`RaptorWorkflow.tsx:1538` — 비디오 catch 블록은 `console.error`만 출력하고 사용자 알림이 없습니다. 이미지 업로드는 `alert()`을 제공하는 것과 다릅니다. 이번 핫픽스 도입 버그가 아니나 수정 시 함께 처리되지 않았습니다.

### [B-3] 토큰 없을 시 비인증 요청 전송 ℹ️ Informational
`headers: token ? { 'Authorization': `Bearer ${token}` } : {}` — 세션 만료/로그아웃 상태에서 헤더 없이 요청이 전송됩니다. 백엔드가 `401`을 반환하면 `throw new Error("업로드 에러")`로 처리되어 기능적으로는 안전하나, 클라이언트 사전 차단은 없습니다.

---

## E — Efficiency (효율성 및 구현 품질)

### [E-1] fetch 패턴 3중 중복 — 후속 리팩터링 대상
동일한 fetch 로직이 이미지 업로드 2곳 + 비디오 업로드 1곳에 반복됩니다. P0 핫픽스 성격상 최소 변경이 올바른 판단이었으나, 향후 `uploadFile(endpoint, file)` 헬퍼 함수 추출을 권장합니다.

### [E-2] Python 스트림 에러 응답 형식 비일관성 ℹ️
Veo 에러는 `{ status: 'error', message: '...' }`, 기타 에러는 `{ error: '...' }` 형식으로 클라이언트가 두 형식을 모두 처리해야 합니다. 기존 구조 유지이므로 이번 수정의 문제는 아니나, 향후 통일 필요합니다.

---

## 후속 권장 사항

| 우선순위 | 항목 | 위치 |
|---|---|---|
| P1 | 비디오 업로드 실패 사용자 alert 추가 | `RaptorWorkflow.tsx:1538` |
| P1 | 비디오 업로드 try 블록 들여쓰기 정렬 | `RaptorWorkflow.tsx:1519` |
| P2 | 토큰 없을 시 업로드 사전 차단 | `RaptorWorkflow.tsx` (3곳) |
| P3 | fetch 업로드 헬퍼 함수 추출 | `RaptorWorkflow.tsx` |
| P3 | 스트림 에러 응답 형식 통일 | `main.py` |

---

## 최종 판정

> **APPROVED — P0 수정 목적 달성, 프로덕션 배포 적합**

두 크래시 버그 모두 근본 원인이 정확히 제거되었습니다. 수정 범위가 최소화되어 있고 의도치 않은 동작 변경이 없습니다. fetch 전환은 타입 오류 해결과 동시에 multipart boundary 자동 설정 및 인증 헤더 추가라는 실질적 개선을 달성했습니다. 잔존 이슈는 모두 P1 이하이며 시스템 안정성에 직접적인 영향을 주지 않습니다.

---

파일 쓰기 권한을 승인해주시면 `Claude_Review_Report_v2.19.10_P0_Hotfix_Post.md`로 저장하겠습니다.
