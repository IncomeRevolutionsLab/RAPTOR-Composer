---

## Pre-Review: FFmpeg drawtext fontfile 이중 치환 버그 (Exit 8)

**버전:** 분석 시점 기준 현재 main 브랜치  
**파일:** `backend/services/ffmpeg_worker.py`  
**핵심 라인:** 103, 336, 393–394

---

### 1. 버그 재현 경로 (데이터 흐름)

```
_ensure_font() → line 103
  os.path.abspath(font_path)
  .replace("\\", "/")   ① 백슬래시 → 슬래시
  .replace(":", "\\:")  ② 콜론 → \: (FFmpeg 이스케이프)
  
  반환값: "C\:/Users/.../font.ttf"
```

```
line 336
  safe_text_file_path = os.path.abspath(text_file_path)
  .replace("\\", "/")   ① 백슬래시 → 슬래시
  .replace(":", "\\:")  ② 콜론 → \: (FFmpeg 이스케이프)
  
  결과값: "C\:/path/to/text.txt"
```

```
line 393–394 (← 이중 치환 발생 지점)
  safe_font_path = str(font_path).replace('\\', '/')
  # "C\:/" 안의 '\' 가 '/' 로 치환됨
  # → "C/:/Users/.../font.ttf"  ← 오염된 경로

  safe_txt_path = str(safe_text_file_path).replace('\\', '/')
  # 동일하게 "C/:/path/to/text.txt" 로 오염
```

---

### 2. 근본 원인

`_ensure_font()`(line 103)와 `safe_text_file_path`(line 336)는 이미 두 가지 작업을 모두 마친 상태로 값을 반환한다:

| 단계 | 처리 내용 | 결과 |
|---|---|---|
| ① | `\\` → `/` | `C:/path/font.ttf` |
| ② | `:` → `\:` | `C\:/path/font.ttf` |

이 값에 line 393-394에서 `.replace('\\', '/')` 를 **한 번 더** 적용하면:

- `\:` 안의 `\` 가 `/` 로 치환
- `C\:/` → `C/:/` 로 경로 드라이브 구분자가 파괴됨
- FFmpeg이 유효하지 않은 경로로 인식 → **Exit 8** (필터 파서 오류)

---

### 3. 수정 방안

#### 원칙
- `font_path`와 `safe_text_file_path`는 이미 FFmpeg 필터용으로 완전히 이스케이프된 값이다.
- line 393-394의 추가 치환은 불필요하며 오히려 파괴적이다.
- **직접 할당으로 교체하는 정답.**

#### 수정 전 (line 392–394)
```python
# [P1 해결] FFmpeg 필터 내부 경로 오류(Exit 8) 방지를 위한 윈도우 백슬래시 정규화
safe_font_path = str(font_path).replace('\\', '/')
safe_txt_path = str(safe_text_file_path).replace('\\', '/')
```

#### 수정 후
```python
# font_path: _ensure_font()에서, safe_text_file_path: line 336에서 이미 FFmpeg 이스케이프 완료
safe_font_path = font_path
safe_txt_path = safe_text_file_path
```

---

### 4. 영향 범위 및 리스크

| 항목 | 평가 |
|---|---|
| 수정 범위 | 2라인 교체 (line 393–394를 직접 할당으로 교체) |
| 사이드이펙트 | 없음 — 이미 이스케이프된 값에서 불필요한 연산만 제거 |
| Linux 환경 | `_ensure_font()` fallback 경로(`/usr/share/fonts/...`)는 `:` 가 없으므로 `.replace(":", "\\:")` 가 무해하게 통과, 동작 불변 |
| 윈도우 환경 | 드라이브 경로 `C\:/` 보존 → FFmpeg 정상 파싱 |
| 테스트 포인트 | 윈도우 경로(`C:\...`) 폰트 + 자막 텍스트 파일이 모두 포함된 drawtext 렌더링 케이스 |

---

### 5. 추가 확인 권고 사항

- **line 336의 `safe_text_file_path`** 와 **line 103의 `_ensure_font()` 반환값**이 이중으로 이스케이프되지 않도록, 향후 경로 처리 로직은 단일 지점에서만 수행하도록 정리를 권장 (현재는 생성 시점에서 이스케이프하고 사용 시점에서는 그대로 씀이 올바른 패턴).
- 동일 패턴의 경로 치환이 다른 필터(watermark overlay 등)에도 존재하는지 검토 필요.

---

**결론:** 수정은 2라인 교체이며, 버그의 원인은 "이미 이스케이프된 값에 이스케이프를 재적용"하는 이중 치환이다. 코드 변경 자체는 단순하고 리스크가 낮다.
