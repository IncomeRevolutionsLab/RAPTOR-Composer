# Claude Post-Review Report
**대상 커밋:** `64ab324` (feat) + `b5fcbbe` (fix)
**검토 일자:** 2026-06-19
**검토 기준:** VIBE (Validity · Impact · Bugs · Edge Cases)

---

## 변경 요약

| 항목 | 변경 전 | 변경 후 |
|------|---------|---------|
| 월간 프로젝트 생성 한도 | 10개 | 1000개 |
| 예외 타입 (한도 초과) | `raise Exception(...)` | `raise HTTPException(status_code=403, ...)` |
| 에러 메시지 | "베타 테스트 월간 프로젝트 생성 한도(10개)를 초과했습니다. 다음 달에 다시 이용해 주세요." | "월간 프로젝트 생성 한도(1000개)를 초과했습니다. 비정상적인 접근 방지를 위해 제한됩니다." |
| DB 삽입 실패 예외 (b5fcbbe) | `raise Exception(...)` | `raise HTTPException(status_code=500, ...)` |

---

## V — Validity (변경 타당성)

### 한도 1000 상향: **타당**

BYOK(Bring Your Own Key) 아키텍처에서 사용자는 `x-byok-kie` 헤더로 자신의 KIE API 키를 직접 제공한다(`main.py:147–150`). 핵심 API 비용이 서버 운영자가 아닌 사용자 키에 귀속되므로 월 10개 제한은 BYOK 전환 이후 근거를 잃는다. 1000은 사실상 남용 방지(anti-abuse) 하한선으로만 기능하는 값(월 기준 하루 ~33회)이며, 이 수준의 트래픽이 실제로 발생할 경우 DB·스토리지 비용이 문제가 될 수 있으나 FIFO LIMIT(하단 분석)이 물리적 저장 상한을 별도로 강제하고 있어 복합적으로 타당하다.

### 에러 메시지 변경: **타당, 단 부수 효과 있음** (아래 B 항목 참조)

"베타 테스트" 레이블 제거는 서비스 정식 운영 단계로의 이행을 올바르게 반영한다. 메시지 어조를 "다음 달에 다시 이용하세요" → "비정상적 접근 방지" 로 바꾼 것은 악용 억지 목적상 적절하다.

---

## I — Impact (영향 범위)

`check_and_enforce_user_limits`는 세 곳에서 호출된다.

| 호출 위치 | 라인 | 호출 컨텍스트 |
|-----------|------|--------------|
| `POST /api/projects` | 595 | `async with db_lock:` 블록 내, FastAPI 라우터 직접 호출 |
| `generate_stream()` (KIE generate) | 2061 | `StreamingResponse` 제너레이터 내부 |
| `generate_stream()` (FFmpeg render) | 2403 | `StreamingResponse` 제너레이터 내부 |

**`POST /api/projects` (line 595):** FastAPI 라우터가 `HTTPException`을 직접 수신하므로 변경 전후 모두 올바른 403 JSON 응답이 반환된다. **영향 없음.**

**`generate_stream()` (lines 2061, 2403):** 두 위치 모두 `except Exception as e:` 블록으로 감싸져 있고, `HTTPException`은 `Exception`의 서브클래스이므로 catch된다. 단, 에러를 SSE 스트림으로 직렬화할 때 `str(e)` 표현이 달라진다.

```
# 변경 전 (bare Exception)
str(e)  → "베타 테스트 월간 프로젝트 생성 한도(10개)를 초과했습니다..."

# 변경 후 (HTTPException)
str(e)  → "403: 월간 프로젝트 생성 한도(1000개)를 초과했습니다..."
```

Starlette `HTTPException.__str__`은 `"{status_code}: {detail}"` 형식을 반환한다. SSE 페이로드가 `{"error": "403: 월간 프로젝트..."}` 로 바뀌므로 **프론트엔드가 `error` 문자열을 파싱하거나 그대로 표시하는 경우 UI에 "403: " 프리픽스가 노출될 수 있다.**

---

## B — Bugs (버그·결함)

### 식별된 결함 1: SSE 에러 메시지 내 "403: " 프리픽스 노출 (경증)

```python
# main.py:2067, 2409
yield f"data: {json.dumps({'error': str(e)})}\n\n"
```

`HTTPException`이 stream 내부에서 catch되면 `str(e)` = `"403: ..."` 이 된다. 프론트엔드에서 이 문자열을 toast/modal에 그대로 표시할 경우 사용자에게 HTTP 상태 코드가 노출된다. 수정 권고:

```python
# 권고 수정안 (두 위치 동일하게 적용)
except Exception as e:
    detail = e.detail if isinstance(e, HTTPException) else str(e)
    if "veo" in str(e).lower():
        yield f"data: {json.dumps({'status': 'error', 'message': 'Veo3.1 비디오 생성 실패. 툴팁 참조.'})}\n\n"
    else:
        yield f"data: {json.dumps({'error': detail})}\n\n"
```

### 식별된 결함 2: `select("*")` 성능 낭비 (경증)

```python
# main.py:496
res_projects = supabase.table("projects").select("*").eq("user_id", sanitized_user).execute()
```

월간 카운트와 FIFO 정리에는 `project_id`와 `created_at`만 필요하다. `select("*")`는 `plan_snapshot`(JSON 대용량 필드 포함) 전체를 전송하므로 불필요한 네트워크 비용이 발생한다. 이번 변경과 직접 관련은 없으나 한도가 1000으로 높아져 이 쿼리 실행 빈도도 높아질 수 있으므로 기록해 둔다.

### b5fcbbe 커밋 (`create_project_in_db`): **결함 없음**

`HTTPException(status_code=500, ...)`으로 변경하면 FastAPI가 올바른 500 응답을 반환한다. 해당 함수는 `POST /api/projects` 라우터에서만 호출되며, `StreamingResponse` 외부이므로 exception handler가 정상 동작한다.

---

## E — Edge Cases (엣지 케이스 및 리스크)

### EC-1: 월간 한도(1000) vs. FIFO 물리 저장 한도(9) 불일치

```python
# main.py:501, 505
if monthly_count >= 1000:
    raise HTTPException(status_code=403, ...)
await enforce_user_fifo_limit(sanitized_user, 9)
```

월 1000개 생성을 허용하지만 물리적으로는 최신 9개만 보존된다. 즉 사용자는 매월 최대 1000개의 프로젝트를 생성할 수 있으나 이전 프로젝트는 FIFO로 자동 삭제된다. **이는 의도된 설계인지 확인이 필요하다.** 만약 BYOK 사용자에게 더 많은 프로젝트를 보존시킬 의도라면 FIFO limit도 별도로 조정해야 한다.

### EC-2: 1850라인 근방 별도 enforce_user_fifo_limit 호출

```python
# main.py:1859
await enforce_user_fifo_limit(u_id, 50)
```

별도 엔드포인트에서 limit=50으로 FIFO를 호출하고 있다. `check_and_enforce_user_limits`의 limit=9와 불일치하며, 이 경로는 이번 변경의 영향을 받지 않으나 한도 정책의 일관성을 위해 검토가 필요하다.

### EC-3: 동시성 보호 부재 (generate_stream 내)

`POST /api/projects`는 `async with db_lock:` 으로 보호되어 있으나, `generate_stream()` 내부의 `check_and_enforce_user_limits` 호출(lines 2061, 2403)은 lock 없이 실행된다. 월 한도가 10개일 때는 경쟁 조건이 발생해도 큰 피해가 없었지만, 1000개로 높아진 현 구조에서는 영향도가 낮다. 그러나 이 호출이 월간 생성 카운트를 단순 읽기로만 체크하고 실제 기록은 별도 흐름에서 이루어지므로 TOCTOU 문제는 원래부터 존재하며 이번 변경으로 악화되지는 않는다.

---

## 종합 판정

| 기준 | 판정 | 비고 |
|------|------|------|
| **Validity** | ✅ 타당 | BYOK 전환에 부합하는 한도 완화 |
| **Impact** | ⚠️ 조건부 허용 | SSE 경로에서 "403: " 프리픽스 노출 가능 |
| **Bugs** | ⚠️ 경증 1건 | `str(HTTPException)`의 SSE 직렬화 불일치 |
| **Edge Cases** | ⚠️ 검토 필요 | FIFO 9 vs 월간 1000 정책 일관성, line 1859 별도 limit=50 |

**릴리즈 블로커 없음.** 단, SSE 경로의 `str(e)` 직렬화 문제는 다음 패치에서 수정을 권고한다. FIFO 한도 정책(9 vs 50 vs 1000)은 제품 의도를 재확인한 후 통일하는 것이 바람직하다.
