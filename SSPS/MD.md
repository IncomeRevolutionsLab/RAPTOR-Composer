# SSPS (Intelligent Shopping Short-form Product Selection) MD v3.6
(Model Design: Pipeline & Module Architecture)

## 1. 데이터 분석 파이프라인 설계
본 시스템은 네이버 쇼핑 트렌드를 감지하여 수익화 가능한 숏폼 기획안으로 변환하는 5단계 파이프라인을 따릅니다.

1. **트래킹(Tracking)**: 네이버 쇼핑인사이트 API를 통해 5,807개 카테고리의 1년치 검색 비중 데이터를 배치(3개 주제어) 단위로 수집.
2. **정규화(Normalization)**: 앵커링(Anchoring) 로직을 적용하여 배치 간 상대적 크기 차이를 보정하고 트렌드 지수를 표준화.
3. **영속화(Persistence)**: 롤링 업데이트(Rolling Update) 방식으로 `active_version` 테이블에 즉시 반영하여 데이터 연속성 확보.
4. **시각화(Visualization)**: ECharts-GL 3D 엔진을 통해 시간-카테고리-비중의 3축 트렌드를 사용자 대시보드에 투영.
5. **연결(Monetization)**: 선정된 키워드를 쿠팡 파트너스 API/검색과 연동하여 최종 수익화 링크 생성.

## 2. 입출력 스키마 규격
### 입력(API Request)
- `category_id`: 8자리-10자리 네이버 카테고리 코드
- `time_unit`: date/week/month (기본 date)
### 출력(Trend Data JSON)
```json
{
  "category": "화장품/미용",
  "period": ["2025-05-01", "2026-05-01"],
  "data": [
    {"date": "2026-05-01", "ratio": 85.5},
    ...
  ],
  "anchored_ratio": 1.25
}
```

## 3. 모듈 풀 설계 (Module Pool Catalog)
| 모듈 ID | 기능 정의 | 입력 | 출력 | 버전 |
| :--- | :--- | :--- | :--- | :--- |
| **NAVER-CONN** | 네이버 쇼핑인사이트 API 인터페이스 | CatID, Header | Raw JSON | v3.6 |
| **CAT-ARCHITECT** | 4-Depth 트리 구조 및 경로 관리 | Keyword/ID | Path List | v3.5 |
| **SUPA-SYNC** | Supabase DB CRUD 및 버전 제어 | Data Object | Success/Fail | v3.6 |
| **TREND-CORE** | 앵커링 기반 데이터 정규화 엔진 | Raw Ratios | Scaled Index | v3.6 |
| **COUPANG-MAP** | 키워드별 쿠팡 파트너스 링크 매핑 | Keyword | Affiliate URL | v1.0 |

## 4. 프롬프트 세트 (RAPTOR GEM 연동)
- **Role**: "너는 숏폼 콘텐츠 수익화 전문가로서, 주어진 트렌드 데이터를 분석하여 구매 전환율이 가장 높을 상품 3가지를 선정한다."
- **Task**: 
  1. 트렌드 급상승 지점 분석
  2. 쿠팡 내 해당 상품군 리뷰 및 평점 예측
  3. 숏폼 스크립트 핵심 후킹 포인트(Hooking Point) 추출

## 5. 자동화 및 오케스트레이션
- **Trigger**: `trend_collector.py` (Daily Cron / APScheduler)
- **Action**:
  1. API 호출 → 2. DB 저장 → 3. 텔레그램 봇 리포트 발송
- **Status Reporting**: 텔레그램 봇을 통해 실시간 수집 진행률(%) 및 서버 상태 보고.

## 6. 데이터 보관 및 버전 관리
- **Raw Data**: `trend_raw` 테이블에 영구 보존 (Audit Trail)
- **Active Data**: `trend_cache` 테이블에 실시간 롤링 업데이트
- **Versioning**: `v_beta`, `v_stable` 태그를 이용한 데이터 버전 스왑 제어
