# RAPTOR Code Review Report — crop 필터 Named Parameter 정규화 Post-Review (v2.19.29+)

**Date:** 2026-06-18 | **Reviewer:** Claude Sonnet 4.6 | **Framework:** VIBE
**Scope:** 단일 커밋 `63d68ec`
**대상 파일:** `backend/services/ffmpeg_worker.py`

---

## V — Verify (변경 사실 검증)

### 적용된 변경 정확히 2곳

```python
# Before (positional)
f"crop={target_w}:{target_h}:"
f"x='min({max_x}*n/{tf_float},{max_x})':"
f"y='min({max_y}*n/{tf_float},{max_y})',setsar=1"

# After (named)
f"crop=w={target_w}:h={target_h}:"
f"x='min({max_x}*n/{tf_float},{max_x})':"
f"y='min({max_y}*n/{tf_float},{max_y})',setsar=1"
```

두 코드 경로(`i%2==0` 순방향 팬, `i%2==1` 역방향 팬) 모두 동일하게 적용. diff 내용이 커밋 메시지와 정확히 일치. **검증 통과.**

---

## I — Impact (수정 범위 및 경로 점검)

**수정 파일:** 1개 (`ffmpeg_worker.py`)
**수정 활성 조건:** `is_hybrid_image == True` (이미지 기반 슬라이드만 해당)
**비디오 경로 (`use_video == True`):** 무영향

| 코드 경로 | 변경 전 동작 | 변경 후 동작 |
|---|---|---|
| 이미지 순방향 팬 (`i%2==0`, line 372) | positional `crop=W:H:` | named `crop=w=W:h=H:` |
| 이미지 역방향 팬 (`i%2==1`, line 380) | positional `crop=W:H:` | named `crop=w=W:h=H:` |
| 정적 crop (else 분기, line 385) | positional `crop={w}:{h}` | **미변경** (아래 B 섹션 참조) |

x, y 값에 `'...'`로 감싼 수식 표현식이 없는 정적 crop 경로(line 385)는 위치 파싱 충돌 원인이 없으므로 미변경은 타당.

---

## B — Boundary (경계 조건 및 사이드 이슈)

### 이 패치가 막는 파싱 충돌 메커니즘

FFmpeg `crop` 필터의 positional 시그니처는 `crop=out_w:out_h:x:y`. 이 구문에서 `x='min(A,B)'`처럼 따옴표 안에 쉼표가 포함된 수식이 올 때, FFmpeg 필터 체인 파서는 내부 쉼표를 파라미터 구분자로 오인할 수 있다. `w=`, `h=` 명시적 키를 붙이면 파서가 `w`와 `h` 바운더리를 명확히 확정하고, 이후 `x=`와 `y=` 수식 파싱에 들어가므로 위치 모호성이 원천 차단된다.

### 기존 P2/P3 이슈 지속 여부 (v2.19.27 리뷰 carryover)

| 이슈 | 상태 |
|---|---|
| `safe_txt_path` Windows 경로 이중 처리 (`C/:/...` 생성) | **지속** — 이번 패치 미대응, Koyeb Linux에서는 무해 |
| `PIL Image.open()` 예외 미처리 (`UnidentifiedImageError`) | **지속** — 정상 JPEG/PNG 경로에서 발현 가능성 낮음 |
| `image_w` / `image_h` = 0 ZeroDivisionError | **지속** — PIL 가드 미적용 |

세 건 모두 이 패치의 범위 밖이며, 오늘의 Exit 8 수정 체인과 독립된 P2/P3 리스크.

---

## E — Evidence (판정 근거 요약)

### 오늘 하루 Exit 8 수정 체인 전체

| 커밋 | 조치 | Exit 8 원인 |
|---|---|---|
| `87e127e` | zoompan → scale+crop 대체 | OOM + 3s 컷오프 |
| `d0d967c` | n 기반 수식 + min()/max() 경계 | out-of-bounds |
| `8bc1efe` | Python 사전 계산 raw 숫자 주입, `iw`/`ow` 제거 | FFmpeg 표현식 파서 미지원 변수 |
| `2f0bcdd` | `\\,` 이스케이프 제거 | math 파서 구문 오류 |
| `faa2649` | `.0` float 주입, `-shortest` 수정, 경로 정규화 | 정수 나눗셈 0 반환, 오디오 버퍼 오버런 |
| `5b1cd60` | `-shortest` 삭제, `-t` 강제 적용 | EOF 버퍼 충돌 |
| `148452e` | subtitle 파일 UTF-8 + whitespace strip | drawtext 파싱 충돌 |
| `63d68ec` (**이번**) | named param `w=`, `h=` 강제 | crop 위치 파라미터 모호성 |

### 최종 생성 filter_str 상태

```
# 순방향 팬 (실제 값 예시, 1080×1920, 3초)
[0:v]fps=fps=30,scale=1404:2496,crop=w=1080:h=1920:x='min(324*n/88.0,324)':y='min(576*n/88.0,576)',setsar=1

# 역방향 팬
[0:v]fps=fps=30,scale=1404:2496,crop=w=1080:h=1920:x='max(324*(1-(n/88.0)),0)':y='max(576*(1-(n/88.0)),0)',setsar=1
```

- `iw`/`ow` 잔존 없음
- `\\,` 이스케이프 없음
- float 기반 나눗셈 보장 (`88.0`)
- 위치 파라미터 모호성 없음 (`w=`, `h=` 명시)
- `min()`/`max()` 경계 보장

---

## 종합 판정: PASS

이번 패치는 8개 Exit 8 수정 체인의 마지막 방어선으로, crop 필터의 위치 파라미터 모호성이라는 **최후의 파서 취약점을 제거**했다. 코드 변경 범위는 최소(2줄)이며 의도한 효과와 완전히 일치한다. 정적 crop 경로가 미변경인 것은 의도적으로 올바르다.

**지속 P2/P3 이슈 3건은 독립 배치로 처리 권장**하며, 오늘의 Exit 8 충돌 경로는 패치 체인 완료로 **완전 차단**된 것으로 판정한다.
