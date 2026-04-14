---
name: dynamic-scoring-engine
description: 입력된 품목의 성격(계절성, 가격대, 산업군)을 파악하여 네이버, 다이소, 올리브영 데이터의 반영 비중을 동적으로 조정해 랭킹을 계산한다. 단순 평균 합산은 절대 금지한다.
---

# Dynamic Scoring Engine Skill

## 역할 (Role)
이 스킬은 SSPS 시스템의 **두뇌**입니다. 카테고리 특성을 인식하여 각 데이터 소스의 가중치를 동적으로 할당하고, 공정한 최종 점수를 계산합니다.

## ⚠️ 핵심 규칙: 단순 평균 합산 금지
모든 소스의 점수를 동일한 비중으로 더하는 것을 **절대적으로 금지**합니다.  
반드시 카테고리 타입에 따른 **동적 가중치**를 적용해야 합니다.

## 동적 가중치 테이블

| 카테고리 타입 | 네이버(w_n) | 올리브영(w_o) | 다이소(w_d) | 우대 이유 |
|---|---|---|---|---|
| BEAUTY | 0.20 | **0.70** | 0.10 | 올리브영이 뷰티 구매 의사결정의 핵심 플랫폼 |
| LOWPRICE | 0.30 | 0.10 | **0.60** | 다이소 랭킹이 충동구매형 저가 수요를 가장 정확히 반영 |
| SEASONAL | **0.65** | 0.20 | 0.15 | 네이버 데이터랩만 1년치 계절성 트렌드 조회 가능 |
| GENERAL | 0.40 | 0.30 | 0.30 | 균등 분산 (특정 플랫폼 우세 불명확) |

## 스코어링 공식

### 기본 공식
```
Final_Score = (Naver_Score × w_n) + (OliveYoung_Score × w_o) + (Daiso_Score × w_d)
```

### 점수 정규화 (0~100 척도)
각 소스 원시 점수를 0~100으로 정규화:
```
Normalized_Score = ((raw_score - min_score) / (max_score - min_score)) × 100
```

### 소스별 점수 산출 기준
- **Naver_Score**: 검색 클릭 지수(0~100) × 조회수 가중 + 기간 내 증가율 보너스
- **OliveYoung_Score**: 랭킹 역수(1위=100, 30위=3.3) × 리뷰 수 로그 × 평점(5점 만점/5)
- **Daiso_Score**: 베스트 랭킹 역수(1위=100) × 카테고리 상위 노출 보너스

### 소스 부재 시 처리 (Circuit Breaker 발동 시)
```python
# 사용 가능한 소스만으로 가중치 재정규화
available_weights = {k: v for k, v in weights.items() if source_status[k] == "OK"}
total = sum(available_weights.values())
normalized_weights = {k: v/total for k, v in available_weights.items()}
```

## 최종 랭킹 계산 절차

```
Step 1: Input Router가 카테고리 타입 결정
Step 2: Weight Allocator가 해당 카테고리 가중치 로드
Step 3: 각 소스 점수를 0~100으로 정규화
Step 4: 가중 합산으로 Final_Score 계산
Step 5: Final_Score 기준 내림차순 정렬
Step 6: Top 10 상품군 추출
Step 7: 각 상품군당 Top 3~5 SKU 선발
```

## 품질 검증 체크리스트 (기획자 감시용)
- [ ] 카테고리별 가중치가 위 테이블과 정확히 일치하는가?
- [ ] 어떤 경우에도 세 소스를 1/3씩 단순 평균하지 않는가?
- [ ] Circuit Breaker 발동 시 나머지 소스만으로 가중치 재정규화 되는가?
- [ ] 소스가 1개만 남아도 스코어링이 실패하지 않는가?
