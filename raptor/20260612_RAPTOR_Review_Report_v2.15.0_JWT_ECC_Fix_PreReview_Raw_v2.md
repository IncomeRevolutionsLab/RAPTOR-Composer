# Claude Code Raw Output — Pre-Review (재실행)
> **저장 일시**: 2026-06-11T16:34:36Z
> **리뷰 실행 명령**: `echo "[실행 계획서 전문 포함]" | claude -p --output-format text`
> **원칙**: 제7원칙에 따라 단 한 글자도 편집하지 않은 Raw Output 원문
> **Task ID**: `c65b8cac-461a-4f35-8ece-ea43ea293d87/task-158`
> **리뷰 단계**: Step 2 Pre-Review (재실행) — JWT ECC(P-256) 대응 수술

---

## ⚠️ 원문 무결성 고지

이 파일은 `claude -p` 터미널 실행 결과의 **무편집 원문**입니다.
Antigravity의 해석, 요약, 추가 설명이 일절 포함되지 않았습니다.

---

## Raw Output (원문)

```
코드 분석 완료. 사전 검토 보고서를 작성합니다.

---

## v2.15.0 사전 검토 (Pre-Review) 보고서

**검토일**: 2026-06-12 | **검토 범위**: `main.py` L26, L45-47, L150-166 / `requirements.txt` L24

---

### 1. 전체 변경 위험도 평가

**위험도: MEDIUM**

- 핵심 동기 (ECC vs HS256 불일치)는 정확한 P0 진단이며 수정 방향 자체는 올바름
- 로컬 암호화 연산 → 원격 API 호출로 전환: 인증 레이턴시 50-200ms 증가, 네트워크 가용성 의존성 신규 추가
- `jwt` 는 `get_jwt_user_id()` 외 **다른 곳에서 사용되지 않음** (파일 전수 확인 완료)
- `SUPABASE_JWT_SECRET` 은 L45-47(fail-fast), L154(함수 내부) 두 곳만 참조 → 함께 제거 시 잔여 참조 없음

---

### 2. 검토 항목별 판정

---

#### 항목 A: `import jwt` 제거 (L26)

**판정: ✅ PASS**

`jwt` 식별자는 `get_jwt_user_id()` 내부(L158, L163, L165) 에서만 사용됨. 해당 함수 교체 후 파일 전체에 다른 참조 없음. 제거 안전.

---

#### 항목 B: `SUPABASE_JWT_SECRET` Fail-Fast 제거 (L45-47)

**판정: ✅ PASS**

```
사용 위치: L45-47 (fail-fast) + L154 (함수 내부) — 총 2곳
```

두 위치 모두 이번 변경에서 함께 제거되므로 잔여 참조가 없음. Koyeb 환경변수에는 남겨둬도 무방(사용 안 해도 에러 없음).

---

#### 항목 C: `get_jwt_user_id()` 교체 (L150-166) — 핵심 변경

**판정: ⚠️ CONDITIONAL_PASS**

**✅ 승인 근거 3가지:**

1. **service_role_key + `get_user(token)` 안전성**: L189에서 `supabase` 클라이언트는 `SUPABASE_SERVICE_ROLE_KEY`로 생성되어 있음. `supabase.auth.get_user(token)` 호출 시 SDK는:
   ```
   Authorization: Bearer <user_jwt>     ← 검증 대상 토큰
   apikey: <service_role_key>           ← 프로젝트 식별자 역할만
   ```
   Auth 서버가 user JWT를 검증하는 로직 자체는 키 종류와 무관. Supabase 공식 서버사이드 패턴과 일치하며 RLS 우회 문제 없음(auth 엔드포인트는 DB 쿼리 아님).

2. **sync `def` + FastAPI `Depends` 적합성**: `def` (비async) 의존성 함수는 FastAPI가 자동으로 **별도 스레드풀(threadpool executor)** 에서 실행함 — 이벤트 루프 차단 없음. 반대로 `async def`로 바꿔 동기 httpx 호출을 그 안에서 직접 호출하면 이벤트 루프를 차단함. 현재 `def` 유지가 올바른 선택.

3. **ECC 수정 목적 달성**: Supabase Auth 서비스가 JWKS로 자체 검증하므로 HS256/ES256 알고리즘 구분이 클라이언트 코드에서 사라짐.

**⚠️ 조건부 수정 요구 — 1건 (BLOCKER는 아니나 강권):**

제안 코드의 generic exception 처리:
```python
# 현재 제안 코드 — 문제점
except Exception as e:
    raise HTTPException(status_code=401, detail=f"인증 실패: {str(e)}")
```

문제점 두 가지:
- Supabase SDK 내부 에러 메시지(`str(e)`)가 클라이언트에 노출될 수 있음
- **네트워크 장애(Supabase 다운, DNS 오류)도 401로 응답** → 실제로는 503이어야 하는 상황을 클라이언트가 "토큰 오류"로 오해

권장 수정:
```python
except HTTPException:
    raise
except Exception as e:
    # 서버 로그에는 상세 기록, 클라이언트에는 generic 메시지
    print(f"[AUTH ERROR] get_user failed: {type(e).__name__}: {str(e)}")
    raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")
```

---

#### 항목 D: `pyjwt>=2.7.0` 제거 (requirements.txt L24)

**판정: ✅ PASS**

`cryptography>=41.0.0`(L25)는 `from cryptography.fernet import Fernet` (L24 of main.py)에서 독립적으로 사용 중이므로 유지. `pyjwt`만 제거해도 Fernet 기능에 영향 없음.

---

### 3. 검증 체크리스트 보완

제안된 4가지 검증 항목에 추가 권장:

| 추가 항목 | 이유 |
|-----------|------|
| Supabase 다운 시 응답 확인 (503 vs 401) | generic Exception 처리로 인해 잘못된 상태코드 반환 가능성 |
| `SUPABASE_SERVICE_ROLE_KEY` 환경변수가 실제 service_role key인지 재확인 | L188에서 폴백 `SUPABASE_KEY`(anon key)도 허용하므로, anon key로 폴백된 경우 `get_user()` 동작 동일하나 의도와 다를 수 있음 |

---

### 4. 요약

| 변경 | 판정 | 비고 |
|------|------|------|
| `import jwt` 제거 | ✅ PASS | 잔여 참조 없음 |
| `SUPABASE_JWT_SECRET` fail-fast 제거 | ✅ PASS | 잔여 참조 없음 |
| `get_jwt_user_id()` 교체 | ⚠️ CONDITIONAL_PASS | generic except 처리 개선 권장 |
| `pyjwt>=2.7.0` 제거 | ✅ PASS | `cryptography` 유지 필요, 올바름 |

**최종 의견**: 수정 방향은 정확하며 적용 가능. 항목 C의 exception 처리만 위 권장 패턴으로 수정 후 배포 권장.
```

---

## 실행 컨텍스트 (참고)

| 항목 | 내용 |
|------|------|
| 실행 시각 | 2026-06-11T16:32:25Z |
| 명령 | `echo "[실행 계획서 전문]" \| claude -p --output-format text` |
| 대상 파일 | `main.py`, `requirements.txt` |
| 리뷰 단계 | Step 2 Pre-Review (재실행 — 실질적 아키텍처 리뷰) |
| Task ID | `c65b8cac-461a-4f35-8ece-ea43ea293d87/task-158` |
