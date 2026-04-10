---
description: /start-ssps [분야명] - SSPS 전체 파이프라인 실행 워크플로우
---

# /start-ssps [분야명] 워크플로우

이 워크플로우는 사용자가 분야명을 입력하면 SSPS 전체 파이프라인을 자동으로 실행하고 RAPTOR GEM용 JSON을 출력합니다.

## 실행 단계

### Step 1: 카테고리 판별 (Input Router)
`backend/engine/input_router.py`를 실행하여 입력된 분야명을 분석합니다.
- 카테고리 타입 감지: BEAUTY / LOWPRICE / SEASONAL / GENERAL
- 가격대 추정: low / mid / high
- 시즌성 점수 계산: 0.0 ~ 1.0

```bash
python -c "from backend.engine.input_router import InputRouter; r = InputRouter(); print(r.analyze('[분야명]'))"
```

### Step 2: 소스별 가중치 할당 (Weight Allocator)
카테고리 타입에 따라 데이터 소스의 가중치를 자동으로 할당합니다.
- BEAUTY → 올리브영 70%, 네이버 20%, 다이소 10%
- LOWPRICE → 다이소 60%, 네이버 30%, 올리브영 10%
- SEASONAL → 네이버 65%, 올리브영 20%, 다이소 15%
- GENERAL → 네이버 40%, 올리브영 30%, 다이소 30%

### Step 3: 맞춤형 데이터 수집 (Mall Data Collector)
가중치가 높은 소스부터 우선 수집합니다.

// turbo
```bash
cd "c:\Antigravity Work" && python -m backend.connectors.run_collectors --domain "[분야명]"
```

### Step 4: 정규화 (Normalization)
수집된 원시 데이터를 0~100 척도로 정규화합니다.

### Step 5: 동적 가중치 스코어링 (Dynamic Scoring Engine)
`Final_Score = (Naver_Score × w_n) + (OliveYoung_Score × w_o) + (Daiso_Score × w_d)`

// turbo
```bash
cd "c:\Antigravity Work" && python -m backend.engine.scoring_engine --domain "[분야명]"
```

### Step 6: RAPTOR GEM JSON 추출 (JSON Packager)
최종 결과를 ssps.v1 스키마로 패키징합니다.

// turbo
```bash
cd "c:\Antigravity Work" && python -m backend.engine.json_packager --domain "[분야명]" --output output/result.json
```

### Step 7: 관리자 대시보드 결과 확인
브라우저에서 `http://localhost:8000` 접속하여 결과 확인.

## 에러 처리
- Circuit Breaker 발동 시 Mock 데이터로 자동 폴백 (파이프라인 중단 없음)
- 모든 소스 실패 시에도 네이버 데이터만으로 GENERAL 모드 스코어링 실행

## 전체 원클릭 실행
```bash
cd "c:\Antigravity Work" && python -m backend.main --domain "[분야명]"
```

POST 요청으로도 실행 가능:
```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d "{\"domain\": \"[분야명]\"}"
```
