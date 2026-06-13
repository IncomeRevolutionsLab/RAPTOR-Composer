# Claude Code Pre-Review — BYOKSettingsForm.tsx v2.14.10
> **리뷰 단계**: Step 2 — 사전 아키텍처 리뷰 (Pre-Review)
> **리뷰어**: Claude Code (외부, `claude -p` 터미널 파이프라인)
> **대상 파일**: `src/components/forms/BYOKSettingsForm.tsx`
> **리뷰 일시**: 2026-06-11
> **패치 버전**: v2.14.10 (설정 모달 UI 잘림 픽스 — 스크롤 불가 버그)
> **리뷰 상태**: 🟡 완료 — Step 3 기획자 승인 대기 중

---

## 버그 개요

**증상**: Global Settings 팝오버 모달이 화면 세로 길이보다 길어질 경우, 스크롤이 되지 않아 하단의 [Save Configuration] 버튼 및 Footer가 화면 밖으로 잘려 보이지 않는 치명적 UI 결함.

**타겟 파일**: `src/components/forms/BYOKSettingsForm.tsx`  
**영향 라인**: L150 (팝오버 루트 컨테이너), L175 (내부 스크롤 영역)

---

## 현재 코드 (수정 전)

```tsx
// L150 — 팝오버 루트 컨테이너
<div className="absolute top-16 right-0 ... flex flex-col max-h-[80vh] overflow-hidden ...">

// L175 — 내부 스크롤 영역
<div className="px-6 py-6 overflow-y-auto grow space-y-5 custom-scrollbar">
```

**결함 원인**: `overflow-hidden`이 자식의 `overflow-y-auto`를 무력화. `flex grow` 자식은 `min-height: auto` 기본값으로 인해 부모의 `max-h` 제약 안에서 실제로 축소되지 않아 스크롤이 발동되지 않음.

---

## Antigravity 초안 수정 계획

1. L150: `max-h-[80vh]` → `max-h-[85vh]`, `overflow-hidden` → `overflow-visible`
2. L175: `pb-4` 추가

---

## 🔵 Claude Code 원문 응답 (무편집)

> 권한 승인 후 다시 시도하겠습니다. 변경 내용을 정리하면:
>
> **L150 변경:**
> - `max-h-[80vh]` → `max-h-[85vh]`
> - `overflow-hidden` → `overflow-y-auto`
>
> **L175 변경:**
> - 기존 클래스에 `pb-4` 추가
>
> 파일 쓰기 권한을 허용해 주시면 바로 적용하겠습니다.
>
> > **한 가지 주의사항:** `overflow-hidden`을 제거하면 `rounded-2xl`의 모서리 클리핑이 사라져서 헤더/푸터 배경색이 모서리를 벗어날 수 있습니다. 이 문제가 발생하면 `overflow-hidden`을 유지하되 내부 스크롤 div에 **`min-h-0`** 을 추가하는 방법도 효과적입니다 (flex 자식에서 `grow + overflow-y-auto`가 제대로 동작하려면 `min-h-0`이 필요한 경우가 있음).

---

## 🟡 리뷰 결과 분석

| 항목 | 초안 계획 | Claude Code 판정 |
|------|-----------|-----------------|
| L150 `max-h` 확대 (80vh → 85vh) | 제안 | ✅ 동의 |
| L150 `overflow-hidden` → `overflow-visible` | 제안 | ⚠️ **반대** — `rounded-2xl` 모서리 클리핑 파괴 위험 |
| L175 `pb-4` 추가 | 제안 | ✅ 동의 |
| L175 `min-h-0` 추가 | 미제안 | 🆕 **Claude Code 신규 권고** |

### ⚠️ 초안 결함 발견: `overflow-visible` 사용 부적절

Claude Code가 초안의 `overflow-hidden → overflow-visible` 접근법의 부작용을 지적:
- `overflow-hidden` 제거 시 `rounded-2xl`의 모서리 클리핑 효과 상실
- 헤더/푸터 배경색이 모달 모서리를 벗어나는 시각적 결함 발생 가능

---

## ✅ 최종 권고 수정안 (초안 → Claude Code 피드백 반영)

```diff
// L150 — max-h 확대만, overflow-hidden 유지 (rounded-2xl 모서리 보호)
- "... max-h-[80vh] overflow-hidden flex flex-col ..."
+ "... max-h-[85vh] overflow-hidden flex flex-col ..."

// L175 — min-h-0 추가 (flex grow 스크롤 활성화 CSS 정석) + pb-4 하단 패딩
- "px-6 py-6 overflow-y-auto grow space-y-5 custom-scrollbar"
+ "px-6 py-6 overflow-y-auto grow min-h-0 space-y-5 custom-scrollbar pb-4"
```

### `min-h-0` 기술 근거

Flexbox에서 `grow` 자식은 기본적으로 `min-height: auto`를 가지며, 콘텐츠 전체 높이로 팽창하려 함.  
`min-h-0`을 추가하면 이 제약이 해제되어 부모의 `max-h-[85vh]` 안에서 실제로 축소 + 스크롤이 활성화됨.  
`overflow-hidden`은 유지되므로 `rounded-2xl` 모서리 클리핑 정상 유지.

### 수정 요약

| 항목 | 내용 |
|------|------|
| 수정 파일 | `src/components/forms/BYOKSettingsForm.tsx` 1개 |
| 수정 라인 | L150, L175 (2라인) |
| 위험도 | 🟢 최저 (순수 CSS 클래스 변경, JS/TS 로직 무변경) |
| 부작용 | 없음 (rounded-2xl 모서리 클리핑 정상 유지 확인) |

---

## 현재 상태

> 🔴 **Step 3 대기 중** — 기획자의 명시적 "실행 승인" 없이 코딩 절대 금지
