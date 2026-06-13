소스 코드 검증 완료. 이제 사후 리뷰 보고서를 작성합니다.

---

# 📋 RAPTOR v2.14.4 P1/P2 결함 멸균 수술 사후 리뷰 보고서 (Post-Review)

**리뷰 일자:** 2026-06-10  
**리뷰 대상:** `src/components/AuthDashboard.tsx`, `main.py`  
**검증 방법:** 소스 코드 직접 교차 검증 (실제 파일 읽기 기반)

---

## 1. [P1] 이메일 미인증 에러 세분화 평가

### 에러 분기 우선순위 정확성 — **PASS ✅**

`AuthDashboard.tsx:204-213`의 실제 분기 순서를 검증:

```
1순위: "failed to fetch" / "networkerror" / TypeError   (L204)
2순위: "email not confirmed" / "email_not_confirmed"     (L206) ← 수정됨
3순위: "already" / "registered"                          (L209)
4순위: "invalid login credentials" / "credentials"       (L211)
```

`"email not confirmed"` 분기가 `"credentials"` 분기보다 명확히 앞에 위치. `errLower.includes("email not confirmed")` 조건이 우선 평가되므로 교차 적중 없음. **분기 우선순위 정확.**

---

### Supabase 에러 전달 경로 분석 — **PASS ✅**

백엔드 `main.py:675-677` 실측 코드:

```python
error_msg = resp_data.get("error_description") or resp_data.get("msg") or "로그인 실패"
raise HTTPException(status_code=resp.status_code, detail=error_msg)
```

전달 경로 추적:

| 단계 | 내용 |
|------|------|
| Supabase 반환 | `{"error_description": "Email not confirmed", ...}` |
| `main.py` 가공 | `resp_data.get("error_description")` → `detail: "Email not confirmed"` |
| 프론트엔드 수신 | `throw new Error(data.detail)` → `err.message = "Email not confirmed"` |
| 소문자 변환 | `errLower = "email not confirmed"` |
| 분기 매칭 | `errLower.includes("email not confirmed")` → **true** |

백엔드가 Supabase의 `error_description` 필드를 그대로 `detail`로 프록시하여 전달. 프론트엔드 분기 조건과 완전히 일치.

> **주의 사항 (잠재적 위험):** Supabase가 향후 에러 메시지를 `"Email not confirmed"` → `"Email address not confirmed"` 등으로 변경할 경우 분기가 무력화될 수 있음. `email_not_confirmed` 스네이크케이스 폴백(L207)을 함께 포함한 것은 이에 대한 방어책으로 긍정 평가.

---

## 2. [P1] 약관 링크 연결 평가

### 링크 적용 완결성 — **PASS ✅**

`AuthDashboard.tsx:406-417` 실측:
- `이용약관` → `<a href="https://docs.google.com/...">` 연결 ✓
- `개인정보 처리방침` → `<a href="https://docs.google.com/...">` 연결 ✓
- 두 링크 모두 동일한 Google Docs URL 사용

---

### 보안 속성(rel) 적용 — **PASS ✅**

두 `<a>` 태그 모두:
```html
target="_blank" rel="noopener noreferrer"
```
적용 완료. `noopener`로 Reverse Tabnabbing 방어, `noreferrer`로 Referrer 정보 누출 차단.

---

### 단일 URL 사용의 법적 충분성 평가 — **조건부 PASS ⚠️**

이용약관과 개인정보처리방침이 **동일한 Google Docs URL** 하나를 공유하고 있음:

```
https://docs.google.com/document/d/18YmLQIcpjq8cghU5zukMWhu6W13QJo7WrGm-hl7TQuw/edit?usp=sharing
```

**현재 판단:** 베타 서비스 단계에서는 하나의 문서에 두 내용이 모두 포함된 것으로 간주 가능하며, 법적 효력을 완전히 무효화하지는 않음.

**잔여 위험:** 국내 「개인정보 보호법」 및 「정보통신망법」은 개인정보처리방침을 별도 문서 혹은 명확히 구분된 섹션으로 제시할 것을 권고. 향후 정식 서비스 전환 시 별개 URL로 분리 필요. 현재 링크 텍스트가 "이용약관"과 "개인정보 처리방침"으로 명칭 구분되어 있어 최소한의 명시성은 확보됨.

---

## 3. [P2] 모달 닫기 상태 초기화 평가

### 2곳 모두 수정 여부 — **PASS ✅**

| 위치 | 라인 | 코드 |
|------|------|------|
| 백드롭 클릭 | L314 | `setIsModalOpen(false); setPreviewVideoUrl(null); setAuthSuccess(null); setAuthError(null);` |
| ✕ CLOSE 버튼 | L326 | `setIsModalOpen(false); setPreviewVideoUrl(null); setAuthSuccess(null); setAuthError(null);` |

두 이벤트 핸들러 모두 `authSuccess(null)`, `authError(null)` 초기화 포함 확인.

---

### 기존 useEffect와의 충돌 여부 — **PASS ✅**

`AuthDashboard.tsx:63-67`의 기존 useEffect:

```javascript
useEffect(() => {
  if (!isModalOpen && !authLoading) {
    setPassword('');       // ← password만 초기화
  }
}, [isModalOpen, authLoading]);
```

이 `useEffect`는 `password` 상태만 다루며, `authSuccess`/`authError`에는 관여하지 않음. 모달 닫기 클릭 핸들러가 먼저 `authSuccess/authError`를 null로 설정하고, 이후 `isModalOpen` 변경으로 `useEffect`가 실행되어 `password`를 초기화하는 순차 흐름. **상태 덮어쓰기 또는 경쟁 조건(race condition) 없음.**

---

## 4. [P2] 인라인 스타일 중복 제거 평가

### 에러/성공 박스 style prop 완전 제거 여부 — **PASS ✅**

| 박스 | 라인 | style prop | Tailwind 대체 |
|------|------|-----------|----------------|
| 에러 박스 | L352 | 없음 ✓ | `z-10 break-words` 적용 ✓ |
| 성공 박스 | L358 | 없음 ✓ | `z-10 break-words` 적용 ✓ |

두 박스 모두 `style={{zIndex: 10, wordBreak: 'break-word', overflowWrap: 'break-word'}}` 완전 제거 확인.

---

### Tailwind 대체 완결성 — **PASS ✅**

| 구 인라인 스타일 | Tailwind 대체 | 동등성 |
|----------------|---------------|--------|
| `zIndex: 10` | `z-10` | ✓ 동일 (`z-index: 10`) |
| `wordBreak: 'break-word'` | `break-words` | ✓ 동일 (`word-break: break-word`) |
| `overflowWrap: 'break-word'` | `break-words` | ✓ 동일 (`overflow-wrap: break-word`) |

Tailwind `break-words`는 `word-break: break-word`와 `overflow-wrap: break-word`를 함께 설정하므로 두 인라인 속성을 하나의 유틸리티로 완전 대체.

**Stacking Context 유효성:** 에러/성공 박스는 `z-[1000]` 모달의 내부 자식 요소. 모달 자체가 별도의 stacking context를 형성하므로 `z-10`은 모달 내부에서 상대적으로 유효하게 작동. 박스가 겹칠 다른 형제 요소가 없으므로 실질적 차이 없음.

---

## 5. 잔여 위험 요소

| 번호 | 심각도 | 설명 | 권고 조치 |
|------|--------|------|----------|
| R-01 | 低 | 이용약관/개인정보처리방침 동일 URL | 정식 출시 전 별개 문서 URL로 분리 |
| R-02 | 低 | Supabase 에러 메시지 문자열 의존성 | Supabase 릴리즈 노트 모니터링, 에러 코드(`error_code` 필드) 기반 분기로 장기 전환 고려 |
| R-03 | 低 | `useEffect`의 `authLoading` 의존성 | `authLoading`이 `true`일 때 모달 닫기를 막는 UX 가드는 없으므로, 로딩 중 백드롭 클릭 시 `authError/authSuccess`는 초기화되나 `authLoading`은 `finally` 블록에서 별도 처리됨. 실질 버그 없음. |

---

## 6. TDD 채점표

| # | 항목 | 세부 검증 포인트 | 결과 |
|---|------|----------------|------|
| 1-A | [P1] 이메일 미인증 에러 세분화 | `email not confirmed` 분기가 `credentials` 앞에 위치 | **PASS ✅** |
| 1-B | [P1] Supabase 에러 전달 경로 | `error_description` → `detail` → `err.message` → 분기 매칭 완전성 | **PASS ✅** |
| 2-A | [P1] 약관 링크 적용 완결성 | `<a>` 태그 + Google Docs URL 연결 (두 링크 모두) | **PASS ✅** |
| 2-B | [P1] 보안 속성(rel) 적용 | `rel="noopener noreferrer"` 두 링크 모두 적용 | **PASS ✅** |
| 2-C | [P1] 단일 URL 법적 충분성 | 동일 URL 사용 — 베타 단계 허용 가능, 정식 출시 전 분리 권고 | **조건부 PASS ⚠️** |
| 3-A | [P2] 모달 닫기 2곳 수정 | 백드롭(L314) + ✕ CLOSE(L326) 양쪽 초기화 포함 확인 | **PASS ✅** |
| 3-B | [P2] useEffect 충돌 여부 | useEffect는 `password`만, 핸들러는 `authSuccess/authError` — 독립적 작동 | **PASS ✅** |
| 4-A | [P2] style prop 완전 제거 | 에러/성공 박스 양쪽 `style` prop 없음 확인 | **PASS ✅** |
| 4-B | [P2] Tailwind 대체 완결성 | `z-10`, `break-words` — 인라인 스타일과 100% 동등 | **PASS ✅** |

**종합 결과: 9개 항목 중 8 PASS / 1 조건부 PASS / 0 FAIL**

---

## 7. 최종 결론 및 잔여 권고사항

**v2.14.4는 v2.14.3 사후 리뷰에서 적발된 P1/P2 결함 4개를 모두 정확하게 수술 완료했다.** 코드 레벨의 오적용, 누락, 부작용 없음.

**권고사항 2가지:**

1. **[단기]** `main.py`의 로그인 에러 파싱 로직을 Supabase의 `error_code` 필드 기반으로 전환 검토 (`error_description` 문자열 의존보다 안정적):
   ```python
   # 현행
   error_msg = resp_data.get("error_description") or ...
   
   # 권고 방향 (장기)
   error_code = resp_data.get("error_code")  # e.g. "email_not_confirmed"
   ```

2. **[정식 출시 전]** 이용약관과 개인정보처리방침을 별개 Google Docs URL로 분리하여 국내 법령 권고사항에 부합하는 형태로 개선 필요.

**v2.14.4 배포 승인: APPROVED ✅**
