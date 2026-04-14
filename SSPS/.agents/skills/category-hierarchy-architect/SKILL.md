# Hierarchical Structure DB Schema Construction SKILL

복잡한 계층형 데이터(카테고리, 조직도 등)를 설계하고 DB화하여 안정적으로 운영하기 위한 표준 아키텍처 가이드입니다.

## 1. 아키텍처 4단계 표준 로직

### Phase 1: 카테고리 마스터 구축 (DB + 구조 정의)
계층 구조를 안정적으로 저장하고 대량 데이터 조회 성능을 확보합니다.
- **Table 1: category_master**: 기본 정보 저장 (`id`, `name_ko`, `depth`, `parent_id`, `is_leaf` 등)
- **Table 2: category_closure**: 조상-자손 관계를 매핑하여 무한 뎁스 조회 및 그룹 연산 성능 최적화
- **Table 3: category_collection_log**: 수집/마이그레이션 이력 관리

### Phase 2: 수집 엔진 (BFS 탐색)
구조화된 데이터를 누락 없이 수집하기 위한 알고리즘입니다.
- **BFS(너비 우선 탐색)** 방식을 채택하여 Depth 1부터 순차적으로 탐색
- 동일 `cat_id` 발견 시 최초 데이터만 유지하는 중복 처리 로직 필수
- 수집 실패 시 재시도 및 실패 노드(Failed Nodes) 기록 관리

### Phase 3: 검증 & 정제 (Data Quality)
DB 저장 전 데이터의 무결성을 보장하는 필터링 규칙입니다.
- **부모 검증**: Depth > 1일 때 부모 노드 존재 여부 확인
- **Deep/Path 검증**: 실제 Depth와 계층 경로(Full Path)의 일관성 확인
- **Leaf 검증**: `is_leaf=true`인 노드에 자식이 있는지 체크
- **Orphan 제거**: 부모가 없는 고립 노드 제거

### Phase 4: 트렌드 데이터 수집 (Batch Processing)
카테고리와 매핑된 트렌드 데이터를 API 할당량 내에서 효율적으로 수입합니다.
- **우선순위(Priority) 큐**: 핵심 카테고리나 최신 트렌드 위주로 먼저 호출
- **Rate Limit 준수**: 하루 API 호출 제한(예: 1,000회)을 고려한 스케줄링
- **다차원 데이터**: 날짜, 성별, 연령별 비율(Ratio) 등 상세 세그먼트 저장

## 2. 권장 기술 스택
- **Database**: PostgreSQL (Supabase) - Recursive CTE 및 GIST 인덱스 활용 가능
- **Indexing**: `parent_id`, `depth`, `naver_cat_id` 유니크 인덱스
- **Library**: `pandas` (데이터 정제), `supabase-py` (DB 연동)

## 3. 적용 가이드라인
1. 모든 카테고리 변경 이력은 기록되어야 함 (`updated_at`)
2. `category_master`의 `is_active` 필드를 통해 삭제 대신 비활성화 처리 권장
3. 대량 조회 시에는 `category_closure` 테이블을 조인하여 성능 최적화
