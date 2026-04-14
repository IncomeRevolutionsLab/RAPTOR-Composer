-- 1. 카테고리 마스터 테이블 생성
CREATE TABLE IF NOT EXISTS public.category_master (
    naver_cat_id BIGINT PRIMARY KEY,              -- 네이버 카테고리 고유 ID
    name_ko VARCHAR(255) NOT NULL,                -- 카테고리 한글 명칭
    depth INTEGER NOT NULL CHECK (depth BETWEEN 1 AND 4), -- 계층 깊이 (1~4)
    parent_id BIGINT REFERENCES public.category_master(naver_cat_id), -- 부모 카테고리 ID
    full_path TEXT,                               -- 전체 경로 (예: 패션의류 > 여성의류 > 원피스)
    is_leaf BOOLEAN DEFAULT FALSE,                -- 최하위 노드 여부
    is_active BOOLEAN DEFAULT TRUE,                -- 사용 여부
    source_type VARCHAR(50) DEFAULT 'excel',      -- 데이터 출처 (excel, manual, api 등)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 2. 계층 구조 고속 조회를 위한 Closure Table 생성
CREATE TABLE IF NOT EXISTS public.category_closure (
    ancestor_id BIGINT REFERENCES public.category_master(naver_cat_id),   -- 조상 노드 ID
    descendant_id BIGINT REFERENCES public.category_master(naver_cat_id), -- 자손 노드 ID
    depth INTEGER NOT NULL,                                              -- 사이의 거리
    PRIMARY KEY (ancestor_id, descendant_id)
);

-- 3. 수집 및 검증 로그 테이블 생성
CREATE TABLE IF NOT EXISTS public.category_collection_log (
    id SERIAL PRIMARY KEY,
    naver_cat_id BIGINT,
    status VARCHAR(20),                           -- success, fail
    error_message TEXT,
    collected_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 4. 인덱스 설정 (조회 성능 최적화)
CREATE INDEX IF NOT EXISTS idx_category_master_parent_id ON public.category_master(parent_id);
CREATE INDEX IF NOT EXISTS idx_category_master_depth ON public.category_master(depth);
CREATE INDEX IF NOT EXISTS idx_category_closure_descendant ON public.category_closure(descendant_id);

-- 5. RLS 설정 (읽기 전용 공개 허용)
ALTER TABLE public.category_master ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.category_closure ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Allow public read access for master" ON public.category_master;
CREATE POLICY "Allow public read access for master" ON public.category_master FOR SELECT USING (true);

DROP POLICY IF EXISTS "Allow public read access for closure" ON public.category_closure;
CREATE POLICY "Allow public read access for closure" ON public.category_closure FOR SELECT USING (true);
