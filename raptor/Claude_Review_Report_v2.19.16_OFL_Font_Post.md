# Claude Post-Review: v2.19.16 [P0] OFL 폰트 파이프라인 & 상단 UI 동기화
**리뷰 대상 커밋:** `4011201` (feat: OFL 폰트 파이프라인), `4308478` (refactor: Edge-TTS Native API)
**리뷰 일시:** 2026-06-17
**VIBE 프레임워크 기반**

---

## VIBE 종합 평가

| 항목 | 점수 | 판정 |
|------|------|------|
| **V**alidity (코드 동작 유효성) | 1 / 5 | FAIL |
| **I**ntegrity (견고성 & 에러 처리) | 3 / 5 | CONDITIONAL |
| **B**ehavior (사용자 경험 & UI) | 3 / 5 | CONDITIONAL |
| **E**fficiency (품질 & 유지보수성) | 3 / 5 | CONDITIONAL |
| **종합** | **10 / 20** | **FAIL — 즉시 핫픽스 필요** |

---

## CRITICAL: 즉각 배포 차단 결함 (P0 BLOCKER)

### [BUG-C1] `SyntaxError` — `else:` 블록 고아 발생 (ffmpeg_worker.py:302)

**심각도:** CRITICAL / 배포 불가

`4011201` 커밋에서 기존 `if/else` 폰트 분기 로직의 `if` 라인 3줄은 제거되었으나, `else:` 블록(lines 302–330)은 삭제되지 않았습니다.

```python
# 현재 코드 (BROKEN)
font_path = await self._ensure_font(subtitle_font)
else:                          # ← 매칭되는 if 없음 → SyntaxError
    font_candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        ...
    ]
```

**결과:** Python이 `ffmpeg_worker.py` 모듈을 import할 때 즉시 `SyntaxError: invalid syntax` 발생 → 백엔드 서버 시작 불가 → 전체 렌더링 파이프라인 중단.

**수정:** lines 302–330의 `else:` 블록 전체를 삭제.

```python
# 수정 후 (CORRECT)
font_path = await self._ensure_font(subtitle_font)
safe_text_file_path = os.path.abspath(text_file_path).replace("\\", "/").replace(":", "\\:")
```

---

## HIGH: 기능 결함 (P1 수준)

### [BUG-H1] Linux 폰트 폴백에서 폰트명 반환 → FFmpeg `fontfile=` 실패

**위치:** `backend/services/ffmpeg_worker.py:68`

`_ensure_font()` 메서드의 Linux 폴백 경로에서 폰트 **이름**(`"DejaVu Sans"`)을 반환합니다. 그러나 호출부에서는 이를 FFmpeg의 `fontfile=` 파라미터에 직접 사용합니다.

```python
# _ensure_font() 내부 Linux 폴백
return "DejaVu Sans"   # ← 파일 경로가 아닌 폰트 이름

# ffmpeg_worker.py:351 호출부
f",drawtext=fontfile='{font_path}':"  # ← fontfile= 은 절대 경로 필요
```

OFL 폰트 다운로드가 실패하는 경우(네트워크 오류, GitHub 접근 불가 등) Linux 배포에서 자막 렌더링이 파괴됩니다. 기존의 시스템 폰트 후보 탐색 로직(현재 고아 `else:` 블록)을 `_ensure_font()` 내부 폴백으로 이식해야 합니다.

**수정 방향:**
```python
# Linux 폴백 수정
else:
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c.replace(":", "\\:")
    return "DejaVu Sans"  # 최후 수단으로만 허용
```

---

## MEDIUM: 견고성 & 품질 이슈

### [BUG-M1] 스텝 인디케이터 레이블 vs 실제 워크플로우 불일치

**위치:** `src/components/RaptorWorkflow.tsx:996-999`

UI는 6단계(0–5)를 표시하지만, `setStep(5)` 호출이 코드 어디에도 없습니다.

| 스텝 | 인디케이터 레이블 | 실제 워크플로우 |
|------|-----------------|----------------|
| 0 | 시작 모드 | ✅ |
| 1 | 기본 설정 | ✅ |
| 2 | 분석 리포트 | ✅ (`setStep(2)`) |
| 3 | 이미지 생성 | ✅ (`setStep(3)`) |
| 4 | 비디오 생성 | ✅ (`setStep(4)`) — 여기서 실제 렌더링 실행 |
| 5 | 최종 렌더링 | ❌ `setStep(5)` 없음, `step === 5` 렌더링 없음 |

렌더링이 step 4에서 완료됨에도 불구하고 인디케이터의 step 5("최종 렌더링")는 영구적으로 미활성화됩니다. 사용자는 마지막 단계가 달성되지 않은 것처럼 인식합니다.

**수정 옵션 A:** 스텝을 다시 0–4로 줄이고 레이블을 재매핑.
**수정 옵션 B:** 렌더링 완료 시 `setStep(5)` 호출을 추가하고 step 5 UI 블록 구현.

---

### [BUG-M2] `fonts_cache` 경로가 `os.getcwd()` 의존

**위치:** `backend/services/ffmpeg_worker.py:41`

```python
cache_dir = os.path.join(os.getcwd(), "fonts_cache")
```

Koyeb 등 클라우드 환경에서 서버 시작 디렉터리가 달라질 경우 캐시 경로가 달라집니다. 동일 인스턴스도 재시작 시 경로가 변경될 수 있습니다.

**수정:**
```python
import os
cache_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../fonts_cache")
```

---

### [BUG-M3] 폰트 무결성 검증 임계값 너무 낮음

**위치:** `backend/services/ffmpeg_worker.py:46, 62`

```python
if not os.path.exists(font_path) or os.path.getsize(font_path) < 1000:
```

GitHub에서 반환되는 HTTP 오류 HTML 응답도 1KB를 넘을 수 있습니다. TTF 폰트의 최소 유효 크기는 최소 20KB 이상입니다.

**수정:** `< 1000` → `< 20000` (20KB)

---

### [BUG-M4] 스토어 주석 오류

**위치:** `src/store/useWorkflowStore.ts:42`

```typescript
subtitleFont: string; // Added for subtitle position control
```

주석이 `subtitlePosition`의 것을 복사-붙여넣기한 흔적입니다. `// Subtitle font selection for OFL pipeline`으로 수정 필요.

---

## LOW: 코드 품질 개선 사항

### [Q1] `_ensure_font()` 내부 중복 import

`import os`, `import httpx`, `import platform`이 메서드 내에서 재선언됩니다. 모두 모듈 상단에 이미 import되어 있거나, 없다면 상단으로 이동해야 합니다.

### [Q2] 보이스 화이트리스트 이중 관리

프론트 (`useWorkflowStore.ts:243`)와 백엔드 (`ffmpeg_worker.py:78`)에 동일한 음성 목록이 하드코딩되어 있습니다. 목록 변경 시 두 곳을 동시에 업데이트해야 하는 유지보수 부채입니다. 백엔드 API에서 허용 목록을 반환하는 엔드포인트를 만들거나, 단일 소스로 관리할 것을 권장합니다.

### [Q3] OFL 폰트 URL이 `main` 브랜치 고정

Google Fonts 레포지터리의 `main` 브랜치를 직접 참조합니다. 상류 변경 시 렌더링 결과가 예고 없이 바뀔 수 있습니다. 특정 커밋 해시 또는 릴리즈 태그로 고정하는 것을 권장합니다.

---

## 잘된 점 (Positive Findings)

- **Edge-TTS Native API 전환** (`4308478`): CLI subprocess 방식 제거 후 `edge_tts.Communicate()`로 전환은 올바른 아키텍처 개선입니다. 보이스 화이트리스트 서버 사이드 적용, 파일 무결성 체크 추가, 스토어 하이드레이션 시 보이스 검증 모두 방어적으로 잘 구현되었습니다.

- **`_ensure_font()` 구조**: 다운로드 → 캐시 → 폴백의 3단계 구조 설계 방향 자체는 올바릅니다.

- **Store/API 계층 간 `subtitleFont` 연동**: `useWorkflowStore` → `RaptorWorkflow` → `RenderStreamRequest` → `render_video()` 까지 데이터 흐름이 일관되게 연결되었습니다.

- **UI 폰트 셀렉터**: 선택 옵션 3개 구성이 간결하고 사용자 친화적입니다.

---

## 수정 우선순위 요약

| ID | 심각도 | 파일 | 수정 내용 |
|----|--------|------|-----------|
| BUG-C1 | **CRITICAL** | `ffmpeg_worker.py:302-330` | 고아 `else:` 블록 전체 삭제 |
| BUG-H1 | HIGH | `ffmpeg_worker.py:68` | Linux 폴백을 파일 경로 탐색으로 교체 |
| BUG-M1 | MEDIUM | `RaptorWorkflow.tsx:996` | 스텝 수를 5개로 복원하거나 step 5 완성 |
| BUG-M2 | MEDIUM | `ffmpeg_worker.py:41` | `getcwd()` → `__file__` 기반 경로 |
| BUG-M3 | MEDIUM | `ffmpeg_worker.py:46,62` | 임계값 1000 → 20000 |
| BUG-M4 | LOW | `useWorkflowStore.ts:42` | 주석 수정 |

**결론:** `4308478` (Edge-TTS 리팩터)는 배포 가능한 수준입니다. `4011201` (OFL 폰트 파이프라인)은 `BUG-C1` Python SyntaxError로 인해 **현재 배포 상태에서 백엔드가 기동 불가**합니다. `BUG-C1`과 `BUG-H1`을 즉시 핫픽스 후 재배포가 필요합니다.
