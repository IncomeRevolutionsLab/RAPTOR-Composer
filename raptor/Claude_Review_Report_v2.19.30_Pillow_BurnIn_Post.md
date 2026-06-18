---

## VIBE Post-Review — Pillow 번인 기반 자막 아키텍처 개편 (abfaf75)

### 핵심 변경 확인

- import에 `ImageDraw`, `ImageFont` 추가 (`Image`는 기존 유지)
- `ImageFont.truetype()`, `ImageDraw.Draw()` 를 이용해 `captioned_bg_0.jpg` 에 텍스트를 직접 렌더링 (번인)
- filter_complex에서 `drawtext` 완전 소멸 확인

### I — Impact (변경 범위 및 영향도)

- **이미지 씬 자막 (Linux/Koyeb & Windows dev):** Pillow 번인으로 성공적인 자막 렌더링
- **비디오 씬 자막:** 기능 미구현 유지 (`is_hybrid_image == False` 분기). (기존 렌더 파이프라인에서 꺼져있던 것과 동일)
- **Exit 8 (drawtext 기인):** 구조적으로 불가
- **폰트 경로 이스케이프 문제:** filter_complex에서 폰트 경로 자체가 소멸

### B — Boundary (경계 조건 및 잠재 위험)

**[해결] drawtext 기인 Exit 8 — 구조적 차단 완료**
FFmpeg filter_complex 문자열에서 `drawtext=fontfile=...` 구문 자체가 사라짐. 폰트 경로 이스케이프(`\\:`, `/` 혼용), textfile 경로 파싱, 한글 멀티바이트 문자 처리 모두 FFmpeg 파서를 거치지 않으므로 Exit 8 발생 경로가 구조적으로 차단됨.

**[해결] `_ensure_font` 반환 경로 역변환**
`clean_font_path = font_path.replace("\\:", ":")` 로 이스케이프를 제거하여 올바른 윈도우 OS 경로를 추출.

#### 잔존 위험
1. **[P2] 비디오 씬 (`use_video == True`) 자막 미지원**: Pillow로는 영상 위에 자막을 그릴 수 없으므로, 현재 비디오 씬은 자막이 출력되지 않음.
2. **[P2] Pillow RGBA → RGB 합성 경로 시각 정확성**: Pillow 버전에 따라 반투명 알파 채널 적용 여부가 다를 수 있으므로 `Pillow>=8.0.0` 이 보장되어야 함.
3. **[P3] `if w` guard 조건 오타**: `font_size = ... if w else 40` 에서 `w`가 아닌 `img_w`가 더 논리적이나, 작동에는 무리가 없음.

### E — Evidence (버그 수정 증거 정리)

| Exit 8 발생 원인 | 해결 방식 | 상태 |
|---|---|---|
| `fontfile='C\:/...'` Windows 경로 파싱 실패 | drawtext 제거 → filter_complex에 폰트 경로 없음 | **완전 해결** |
| `textfile='C\:/...'` Windows 경로 파싱 실패 | `text_file_path` 생성 로직 전체 제거 | **완전 해결** |
| 한글 텍스트 drawtext 멀티바이트 파싱 실패 | Pillow가 TTF 직접 로드하여 유니코드 렌더링 | **완전 해결** |
| drawtext 미지원 FFmpeg 빌드 (Alpine/Koyeb) | drawtext 의존성 자체 소멸 | **구조적 차단** |

---

## 최종 판정

**프로덕션(Koyeb Linux) 기준 Exit 8 완전 차단 — PASS**

Pillow 사전 합성 아키텍처는 FFmpeg drawtext 기인 Exit 8의 모든 발생 경로를 구조적으로 소멸시켰다. 자막 렌더링이 Python 레이어로 완전 흡수되어 플랫폼 독립성이 확보되었다. 프로덕션 배포 적합 판정.
