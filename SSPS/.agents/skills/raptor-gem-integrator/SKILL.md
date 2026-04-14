---
name: raptor-gem-integrator
description: 최종 선정 리스트를 ssps.v1 표준 JSON 포맷으로 만들고, 상품의 주요 출처 특성(예: 다이소 가성비템, 올리브영 뷰티템 등)을 반영한 숏폼 훅을 패키징한다. JSON에는 썸네일 URL과 숏폼 스크립트가 반드시 포함되어야 한다.
---

# RAPTOR GEM Integrator Skill

## 역할 (Role)
이 스킬은 SSPS의 **최종 출력 패키저**입니다. 스코어링 엔진의 결과물을 RAPTOR GEM이 바로 사용할 수 있는 ssps.v1 표준 JSON으로 변환합니다.

## ⚠️ 필수 포함 필드 (디자이너 감시용)
다음 필드가 하나라도 누락되면 패키징 실패로 간주합니다:
- `schema_version`: "ssps.v1"
- `primary_source_signal`: 해당 상품군 선정의 주요 소스
- `hook_lines`: 최소 2개 이상의 숏폼 훅 문구
- `visual_assets`: 썸네일 이미지 URL (최소 1개)
- `source_weights_applied`: 적용된 가중치 딕셔너리

## 숏폼 훅 생성 규칙

### 소스별 훅 템플릿
- **OliveYoung_Boost**: "올리브영 랭킹 {rank}위! {feature} {product_group} 비교", "뷰티 유튜버가 몰래 쓰는 올리브영 {product_group}"
- **Daiso_Boost**: "다이소에서 {price}원에 파는 {product_group} 실화?", "1000원짜리가 이 퀄리티?! 다이소 {product_group} 리뷰"
- **Naver_Trend**: "요즘 검색 폭발하는 {product_group} 뭐가 다를까?", "{season} 필수템! 네이버 검색 1위 {product_group}"
- **General**: "요즘 SNS에서 난리난 {product_group} TOP {rank}"

### 훅 품질 기준
- 30자 이내로 작성 (숏폼 썸네일 노출 기준)
- 숫자와 감탄 표현 포함 (클릭률 향상)
- 출처 플랫폼 특성 반영 (신뢰도 강조)

## JSON 스키마 (ssps.v1)

```json
{
  "schema_version": "ssps.v1",
  "generated_at": "2024-01-01T00:00:00+09:00",
  "domain": "사용자 입력 분야",
  "category_analysis": {
    "detected_type": "BEAUTY | LOWPRICE | SEASONAL | GENERAL",
    "confidence": 0.95,
    "seasonality_score": 0.3,
    "price_range": "low | mid | high"
  },
  "weights_applied": {
    "naver": 0.20,
    "oliveyoung": 0.70,
    "daiso": 0.10
  },
  "top_product_groups": [
    {
      "rank": 1,
      "group_name": "상품군명",
      "primary_source_signal": "OliveYoung_Boost",
      "scores": {
        "final_score": 85.2,
        "naver_score": 72.0,
        "oliveyoung_score": 91.0,
        "daiso_score": 10.0,
        "source_weights_applied": {
          "naver": 0.20,
          "oliveyoung": 0.70,
          "daiso": 0.10
        }
      },
      "hook_lines": [
        "올리브영 랭킹 1위! 3초 만에 붉은기 진정되는 패드 비교",
        "뷰티 유튜버가 몰래 쓰는 올리브영 트러블 진정템"
      ],
      "skus": [
        {
          "title": "상품명",
          "brand": "브랜드명",
          "price": 11900,
          "source": "oliveyoung",
          "source_rank": 1,
          "url": "https://...",
          "visual_assets": ["https://...jpg"],
          "review_count": 1234,
          "rating": 4.8,
          "tags": ["진정", "패드", "트러블케어"]
        }
      ]
    }
  ],
  "data_source_health": {
    "naver_datalab": "OK",
    "naver_shopping": "OK",
    "oliveyoung": "OK",
    "daiso": "CIRCUIT_OPEN"
  },
  "execution_time_ms": 3240
}
```

## 패키징 검증 절차
```
Step 1: 모든 필수 필드 존재 여부 확인
Step 2: hook_lines 최소 2개, skus 최소 3개 확인
Step 3: visual_assets URL 유효성 검사
Step 4: source_weights_applied 합계 = 1.0 검증
Step 5: final_score 범위 0~100 검증
Step 6: JSON 직렬화 가능 여부 확인
Step 7: 검증 통과 시 파일로 저장 + API 응답 반환
```
