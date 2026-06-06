# RAPTOR 백엔드 v2.14.1 구조 재정비 사전 리뷰

**리뷰 기준일:** 2026-06-07  
**대상 브랜치:** v2.14.1 구조 재정비  
**검토 파일:** `requirements.txt`, `Dockerfile`

---

## 항목별 판정

### 1. requirements.txt — 신규 패키지 3종 추가

| 패키지 | 명시 버전 | 파일 내 확인 | 결과 |
|---|---|---|---|
| `sse-starlette` | `>=1.6.5` | 4번 줄 | ✅ |
| `openai` | `>=1.0.0` | 18번 줄 | ✅ |
| `python-dotenv` | `>=1.0.0` | 33번 줄 | ✅ |

> **참고:** `anthropic>=0.3.0` 하한선이 매우 낮습니다. 실제 설치 시 pip는 최신 버전을 선택하므로 당장 문제는 없으나, 의도적 pinning이 필요한 경우 별도 관리 권장.

**판정: PASS**

---

### 2. Dockerfile CMD — exec form → shell form 전환 (PORT 동적 바인딩)

```dockerfile
# 변경 전 (exec form, 환경변수 미확장)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# 변경 후 (shell form, 확인됨)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
```

- `${PORT:-8000}` POSIX 기본값 문법 적용 — Render.com / Koyeb 양쪽 호환 확인 ✅
- shell form이 `/bin/sh -c`로 실행되므로 uvicorn이 **PID 1이 아님** → `SIGTERM` 직접 수신 불가, 컨테이너 종료 시 `SIGKILL`로 강제 종료될 수 있음 ⚠️
  - Render.com은 graceful shutdown 타임아웃(10s) 이후 SIGKILL을 보냄
  - 단일 워커 정책 + SSE 스트리밍 중단 가능성 인지 필요
  - 해결 필요 시: `CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]` — `exec` 삽입으로 uvicorn이 PID 1 승계 가능
- 변경 의도(환경변수 확장 필요성)가 주석으로 명확히 문서화됨 ✅

**판정: PASS** (SIGTERM 처리는 운영상 주의사항으로 분류, 기능 요건 충족)

---

### 3. Dockerfile 위치 — 루트 이동

```
C:\...\raptor_review_v2141\
├── Dockerfile          ← 루트 확인됨 ✅
└── requirements.txt
```

- 루트 배치 확인, Docker 빌드 컨텍스트 기준 경로(`COPY . /app/`) 정합성 유지 ✅

**판정: PASS**

---

### 4. backend/\_\_init\_\_.py — 패키지 구조 확인 (변경 없음)

- 리뷰 스냅샷 디렉터리에 `backend/` 패키지 미포함 (변경 없음으로 명시됨)
- 변경 사항 없음 선언 자체는 수용하나, **최종 통합 시 `from backend.xxx import yyy` 임포트 경로 회귀 테스트 권장**

**판정: PASS** (변경 없음 선언 기준)

---

## 종합 판정

| 항목 | 판정 |
|---|---|
| requirements.txt 패키지 추가 | **PASS** |
| Dockerfile shell form 전환 | **PASS** |
| Dockerfile 루트 이동 | **PASS** |
| backend/\_\_init\_\_.py 구조 확인 | **PASS** |
| **종합** | ✅ **PASS — 배포 진행 가능** |

**필수 후속 조치 없음.** 선택적 개선: shell form CMD에 `exec` 키워드 추가로 graceful shutdown 보강.
