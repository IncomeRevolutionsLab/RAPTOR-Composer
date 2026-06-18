---

# VIBE Post-Review — `fix(p0): remove redundant double escaping on font and text paths`

**커밋:** `7462069`
**변경 파일:** `backend/services/ffmpeg_worker.py:394–395`
**리뷰 기준일:** 2026-06-18

---

## V — Verify (근본 원인 검증)

**패치가 실제 오류 원인을 정확히 겨냥했는가?** ✅

경로 처리 파이프라인은 두 단계로 구성된다.

**1단계 — 업스트림 이스케이프 (변경 없음):**
```python
# _ensure_font() → line 103
return os.path.abspath(font_path).replace("\\", "/").replace(":", "\\:")
# 결과: C\:/Users/.../font.ttf

# line 336
safe_text_file_path = os.path.abspath(text_file_path).replace("\\", "/").replace(":", "\\:")
# 결과: C\:/Users/.../scene_0_text.txt
```

**2단계 — 패치 전 (이중 치환 버그):**
```python
safe_font_path = str(font_path).replace('\\', '/')
# C\:/Users/.../font.ttf
#  ↓  \: 의 백슬래시까지 / 로 치환
# C/:/Users/.../font.ttf  ← FFmpeg drawtext 파서 파싱 불가 → Exit 8
```

**2단계 — 패치 후 (치환 제거):**
```python
safe_font_path = str(font_path)
# C\:/Users/.../font.ttf  ← FFmpeg 기대 포맷 그대로 유지 ✅
```

1단계에서 이미 `\:` 이스케이프가 완성된 상태인데, 2단계에서 `.replace('\\', '/')` 를 한 번 더 적용하면 `\:`의 백슬래시가 소멸되어 `C/:`가 생성된다. FFmpeg drawtext 파서는 `fontfile=` 값의 드라이브 구분자를 `C\:` 형식으로만 수용하므로 이것이 Exit 8의 직접적 원인이다. 패치는 해당 이중 치환 호출 2개를 제거하는 것으로 원인을 원천 차단했다.

---

## I — Impact (변경 영향 범위)

| 항목 | 내용 |
|---|---|
| 변경 라인 | +4 / -3 (실질 삭제: `.replace('\\', '/')` 2회 호출) |
| 영향 경로 | `wrapped_caption.strip()` 가 있는 **모든 자막 씬** (폰트 + 텍스트 파일 경로 모두) |
| 사이드이펙트 | 없음 — 업스트림 이스케이프(line 103, 336)는 그대로이므로 경로 형식 불변 |
| Linux 경로 | `_ensure_font()`가 Linux에선 절대경로 그대로 반환하고 `:` 가 없으므로 무영향 |
| 윈도우 이외 환경 | Koyeb(Linux) 배포 경로는 `/usr/share/fonts/...` 형태이므로 이스케이프 불요, 중립 |

---

## B — Boundary (경계 조건 점검)

### ✅ 경로 내 공백 처리
`_ensure_font()`와 line 336 모두 `replace("\\", "/")` 로 슬래시를 통일한 뒤 drawtext 필터 문자열에 `'...'` 단따옴표로 감싸므로 경로에 공백이 포함되어도 FFmpeg 파서에 올바르게 전달된다.

### ✅ `text_file_path` 실제 존재 보장
line 329–331에서 `open(text_file_path, "w", encoding="utf-8")` 로 파일을 먼저 생성한 뒤 line 336에서 경로를 이스케이프하므로, `textfile=` 값이 존재하지 않는 경로를 가리키는 경우는 없다.

### ✅ `font_path` None 방어
`_ensure_font()` 내부에서 Linux fallback(`"DejaVu Sans"`) 포함 모든 분기가 문자열을 반환하며, `None` 을 반환하는 경로가 없다. `str(font_path)` 변환은 안전하다.

### ⚠️ 경고: 미처리 특수문자 (`'`, `:` 외)
현재 이스케이프는 `\` → `/`, `:` → `\:` 두 가지만 처리한다. 경로에 단따옴표(`'`)나 FFmpeg 필터 구분자(`,`, `[`, `]`)가 포함될 경우 파싱 오류가 재발할 수 외에 재발할 수 있다. 현재 `font_path`는 캐시 디렉터리(`~/.raptor_font_cache/`) 내 파일명에서 기인하므로 실질적 위험은 낮지만, `safe_text_file_path`는 `temp_dir` 경로에 의존한다. `temp_dir`가 OS 임시 디렉터리(`tempfile.mkdtemp()`)를 사용하는 경우 경로에 특수문자 개입 가능성은 거의 없으나 기록해둔다.

### ✅ `safe_text_file_path` 이중 이스케이프 해소 확인
```
패치 전: safe_text_file_path = C\:/tmp/.../scene_0_text.txt
          → .replace('\\', '/') → C/:/tmp/.../scene_0_text.txt  ❌
패치 후: safe_txt_path = C\:/tmp/.../scene_0_text.txt           ✅
```
폰트 경로와 동일한 이중 치환 버그가 텍스트 파일 경로에도 존재했으며, 패치에서 함께 제거되었다.

---

## E — Evidence (원천 차단 근거)

**이 패치가 윈도우 환경 drawtext Exit 8을 원천 차단하는가?**

FFmpeg drawtext Exit 8(`AVERROR_INVALIDDATA`)의 발현 조건:
1. `fontfile=` 또는 `textfile=` 값이 FFmpeg이 해석 불가능한 형식일 때
2. 윈도우에서 `C:/` 는 파싱 가능, `C\:/` 는 파싱 가능, `C/:/` 는 파싱 **불가능**

패치 전 생성되던 `fontfile='C/:/...`' 형식은 조건 2를 충족하여 Exit 8을 항상 유발했다. 패치 후 `C\:/` 형식이 유지되므로 이 조건은 성립하지 않는다.

**결론: 이중 치환 제거로 경로 포맷이 FFmpeg 기대값과 일치하게 되었으며, 해당 원인으로 인한 Exit 8은 원천 차단되었다. ✅**

다만 `_RAPTOR_APP_RULES` 상 Path Escaping 정책을 명문화하여, 향후 유사 경로 처리 시 "업스트림 1회 이스케이프 후 하류에서 재처리 금지" 원칙이 일관되게 적용되도록 규정하는 것을 권고한다.
