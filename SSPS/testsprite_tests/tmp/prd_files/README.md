# SSPS: Intelligent Shopping Short-form Product Selection

SSPS는 다중 쇼핑 플랫폼의 데이터를 통합 분석하여 최적의 숏폼 상품을 선정하는 인텔리전트 대시보드 시스템입니다.

## 🏗️ System Architecture

### 1. Backend (Python/Flask)
- **main.py**: API 엔드포인트 관리 및 라우팅 (Vercel/Render 배포 최적화)
- **engine/category_manager.py**: 5,807개 카테고리 트리 관리 및 앵커링 분석 로직
- **connectors/naver_connector.py**: 네이버 쇼핑인사이트 API 연동 및 데이터 파싱
- **connectors/supabase_client.py**: Supabase DB CRUD 및 데이터 영속성 관리
- **scripts/trend_collector.py**: 일일 자동 수집 스케줄러 및 롤링 업데이트 엔진

### 2. Frontend (Vanilla JS)
- **index.html**: Modern Dark Mode UI & Lucide Icons
- **js/app.js**: API 연동, 데이터 시각화 통제 및 상태 관리
- **js/raptor_extended.js**: RAPTOR GEM AI 연동 및 숏폼 기획안 생성

### 3. Data Flow
1. **Collector**가 네이버 API(3개 배치)로부터 트렌드 데이터를 수집.
2. 수집된 Raw 데이터는 `trend_raw`에, 가공 데이터는 `trend_cache`에 **롤링 업데이트** 방식으로 즉시 저장.
3. 사용자가 특정 카테고리를 클릭하면 **API**가 DB에서 최신 트렌드를 조회하여 반환.
4. **Frontend**에서 ECharts-GL을 사용하여 3D 트렌드 차트 시각화.
5. 최종 선정된 상품은 **쿠팡 파트너스** 링크로 자동 매핑되어 사용자에게 제공.

## 🚀 How to Run (Local)

```powershell
# 1. 저장소 이동
cd SSPS

# 2. 백엔드 실행
python backend/main.py

# 3. 브라우저 접속
http://localhost:5000
```

## 📜 Version History
- **v3.6**: 롤링 업데이트 도입, 쿠팡 우선 연결 로직 고정, UI 청소 완료.
- **v3.5**: 3D 차트 고도화 및 카테고리 트리 앵커링 로직 정석화.
- **v1.0**: 프로젝트 초기화 및 네이버 API 기본 연동.
