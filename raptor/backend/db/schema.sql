-- RAPTOR 프로덕션 DB 스키마 정의 (Supabase PostgreSQL 호환)

-- 1. Projects 테이블 생성
CREATE TABLE IF NOT EXISTS public.projects (
    project_id VARCHAR(255) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    user_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    plan_snapshot JSONB
);

-- Index 설정 (유저별 프로젝트 조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON public.projects(user_id);

-- 2. Tasks 테이블 생성 (프로젝트 삭제 시 Cascade Delete)
CREATE TABLE IF NOT EXISTS public.tasks (
    task_id VARCHAR(255) PRIMARY KEY,
    project_id VARCHAR(255) REFERENCES public.projects(project_id) ON DELETE CASCADE,
    task_type VARCHAR(50) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending' NOT NULL,
    result_url TEXT,
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL
);

-- Index 설정 (프로젝트별 태스크 매핑 성능 향상)
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON public.tasks(project_id);

-- 3. User Video Assets 테이블 생성 (개별 업로드 동영상 에셋 관리)
CREATE TABLE IF NOT EXISTS public.user_video_assets (
    id VARCHAR(255) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    duration_seconds DOUBLE PRECISION DEFAULT 5.0 NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT TIMEZONE('utc'::text, NOW()) NOT NULL,
    user_id UUID NOT NULL
);

-- Index 설정 (유저별 에셋 조회 성능 향상)
CREATE INDEX IF NOT EXISTS idx_user_video_assets_user_id ON public.user_video_assets(user_id);

-- Row Level Security (RLS) 활성화 설정
ALTER TABLE public.projects ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_video_assets ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policies 설정 (인증된 유저가 자신의 데이터만 접근할 수 있도록 보안 격리)

-- Projects Policies
CREATE POLICY "Users can insert their own projects" 
    ON public.projects FOR INSERT 
    TO authenticated 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view their own projects" 
    ON public.projects FOR SELECT 
    TO authenticated 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update their own projects" 
    ON public.projects FOR UPDATE 
    TO authenticated 
    USING (auth.uid() = user_id) 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can delete their own projects" 
    ON public.projects FOR DELETE 
    TO authenticated 
    USING (auth.uid() = user_id);

-- Tasks Policies (조인 성능 및 단순화를 위해 프로젝트 소유주 확인)
CREATE POLICY "Users can insert tasks for their projects" 
    ON public.tasks FOR INSERT 
    TO authenticated 
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.projects 
            WHERE projects.project_id = tasks.project_id 
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can view tasks for their projects" 
    ON public.tasks FOR SELECT 
    TO authenticated 
    USING (
        EXISTS (
            SELECT 1 FROM public.projects 
            WHERE projects.project_id = tasks.project_id 
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update tasks for their projects" 
    ON public.tasks FOR UPDATE 
    TO authenticated 
    USING (
        EXISTS (
            SELECT 1 FROM public.projects 
            WHERE projects.project_id = tasks.project_id 
            AND projects.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete tasks for their projects" 
    ON public.tasks FOR DELETE 
    TO authenticated 
    USING (
        EXISTS (
            SELECT 1 FROM public.projects 
            WHERE projects.project_id = tasks.project_id 
            AND projects.user_id = auth.uid()
        )
    );

-- User Video Assets Policies
CREATE POLICY "Users can insert their own video assets" 
    ON public.user_video_assets FOR INSERT 
    TO authenticated 
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can view their own video assets" 
    ON public.user_video_assets FOR SELECT 
    TO authenticated 
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own video assets" 
    ON public.user_video_assets FOR DELETE 
    TO authenticated 
    USING (auth.uid() = user_id);
