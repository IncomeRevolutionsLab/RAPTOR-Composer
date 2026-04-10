-- SSPS Supabase (PostgreSQL) 초기 스키마 설정

CREATE TABLE public.trend_cache (
    id SERIAL PRIMARY KEY,
    query_keyword VARCHAR(255) UNIQUE NOT NULL, -- 검색된 키워드 (예: '패션의류', '영양제')
    trend_data JSONB NOT NULL,                  -- 네이버 데이터랩에서 긁어온 12개월 배열 및 카테고리 정보
    popularity_score INTEGER DEFAULT 1,         -- 많이 검색될수록 카운트 상승 (스케줄러 우선순위 지정용)
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 인덱스 생성 (데이터 검색 속도 향상)
CREATE INDEX idx_trend_cache_keyword ON public.trend_cache(query_keyword);
CREATE INDEX idx_trend_cache_popularity ON public.trend_cache(popularity_score DESC);

-- RLS (Row Level Security) 설정: 익명 유저가 DB 값을 읽을 수(Select)만 있도록 허용
ALTER TABLE public.trend_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow public read-only access" 
ON public.trend_cache FOR SELECT 
USING (true);
