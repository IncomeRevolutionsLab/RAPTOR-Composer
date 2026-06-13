-- ============================================================
-- RAPTOR v2 — Supabase 초기 스키마 구성 SQL (init_schema.sql)
-- 생성일: 2026-06-12
-- 대상: 신규 Supabase 인스턴스
-- main.py 전수 분석 기반: projects, tasks, user_video_assets
-- ============================================================

-- ============================================================
-- 0. 확장 모듈 활성화
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- 1. ENUM 타입 정의
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_type_enum') THEN
        CREATE TYPE task_type_enum AS ENUM (
            'text_generation',
            'image_generation',
            'video_generation',
            'final_render'
        );
    END IF;
END$$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'task_status_enum') THEN
        CREATE TYPE task_status_enum AS ENUM (
            'pending',
            'processing',
            'success',
            'failed',
            'completed'
        );
    END IF;
END$$;

-- ============================================================
-- 2. projects 테이블
-- main.py 참조:
--   project_id (str/UUID), product_name (str), created_at (datetime),
--   user_id (str/UUID, FK → auth.users), plan_snapshot (dict/JSONB)
-- ============================================================
CREATE TABLE IF NOT EXISTS projects (
    project_id      TEXT        PRIMARY KEY,                     -- 형식: uuid4 문자열
    product_name    TEXT        NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id         UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    plan_snapshot   JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- 인덱스: user_id 기반 조회 최적화 (enforce_user_fifo_limit, get_user_videos 등)
CREATE INDEX IF NOT EXISTS idx_projects_user_id ON projects(user_id);
CREATE INDEX IF NOT EXISTS idx_projects_user_created ON projects(user_id, created_at DESC);

-- ============================================================
-- 3. tasks 테이블
-- main.py 참조:
--   task_id (str), project_id (FK → projects), task_type (ENUM),
--   description (str), status (ENUM), result_url (str|null),
--   error (str|null), created_at (datetime)
-- ============================================================
CREATE TABLE IF NOT EXISTS tasks (
    task_id         TEXT            PRIMARY KEY,
    project_id      TEXT            NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    task_type       task_type_enum  NOT NULL,
    description     TEXT            NOT NULL DEFAULT '',
    status          task_status_enum NOT NULL DEFAULT 'pending',
    result_url      TEXT,
    error           TEXT,
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

-- 인덱스: project_id 기반 조회 (get_dashboard_projects, enforce_user_fifo_limit)
CREATE INDEX IF NOT EXISTS idx_tasks_project_id ON tasks(project_id);
-- 인덱스: final_render + success 필터 (get_user_videos)
CREATE INDEX IF NOT EXISTS idx_tasks_type_status ON tasks(task_type, status);

-- ============================================================
-- 4. user_video_assets 테이블
-- main.py 참조 (L1783-1791):
--   id (str/video_id), filename (str), duration_seconds (float),
--   uploaded_at (datetime), user_id (str/UUID, FK → auth.users)
-- ============================================================
CREATE TABLE IF NOT EXISTS user_video_assets (
    id                  TEXT        PRIMARY KEY,                  -- video_id (UUID 문자열)
    filename            TEXT        NOT NULL,
    duration_seconds    FLOAT       NOT NULL DEFAULT 0.0,
    uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id             UUID        NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE
);

-- 인덱스: user_id 기반 조회
CREATE INDEX IF NOT EXISTS idx_user_video_assets_user_id ON user_video_assets(user_id);

-- ============================================================
-- 5. RLS(Row Level Security) 활성화 및 정책 설정
-- 백엔드는 SUPABASE_SERVICE_ROLE_KEY 사용 → RLS 우회 (L189-192 주석 참조)
-- 프론트엔드 직접 접근 시 RLS로 데이터 보호
-- ============================================================

-- 5-1. projects RLS
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

-- 자신의 프로젝트만 조회 가능
CREATE POLICY "projects_select_own" ON projects
    FOR SELECT
    USING (auth.uid() = user_id);

-- 자신의 프로젝트만 생성 가능
CREATE POLICY "projects_insert_own" ON projects
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- 자신의 프로젝트만 수정 가능
CREATE POLICY "projects_update_own" ON projects
    FOR UPDATE
    USING (auth.uid() = user_id);

-- 자신의 프로젝트만 삭제 가능
CREATE POLICY "projects_delete_own" ON projects
    FOR DELETE
    USING (auth.uid() = user_id);

-- 5-2. tasks RLS
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- 자신의 project에 속한 task만 조회 가능
CREATE POLICY "tasks_select_own" ON tasks
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.project_id = tasks.project_id
              AND projects.user_id = auth.uid()
        )
    );

-- 자신의 project에 속한 task만 생성 가능
CREATE POLICY "tasks_insert_own" ON tasks
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.project_id = tasks.project_id
              AND projects.user_id = auth.uid()
        )
    );

-- 자신의 project에 속한 task만 수정 가능
CREATE POLICY "tasks_update_own" ON tasks
    FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.project_id = tasks.project_id
              AND projects.user_id = auth.uid()
        )
    );

-- 자신의 project에 속한 task만 삭제 가능
CREATE POLICY "tasks_delete_own" ON tasks
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM projects
            WHERE projects.project_id = tasks.project_id
              AND projects.user_id = auth.uid()
        )
    );

-- 5-3. user_video_assets RLS
ALTER TABLE user_video_assets ENABLE ROW LEVEL SECURITY;

-- 자신의 영상 자산만 조회 가능
CREATE POLICY "user_video_assets_select_own" ON user_video_assets
    FOR SELECT
    USING (auth.uid() = user_id);

-- 자신의 영상 자산만 생성 가능
CREATE POLICY "user_video_assets_insert_own" ON user_video_assets
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- 자신의 영상 자산만 삭제 가능
CREATE POLICY "user_video_assets_delete_own" ON user_video_assets
    FOR DELETE
    USING (auth.uid() = user_id);

-- ============================================================
-- 6. Supabase Storage Bucket 생성 (assets)
-- upload_image_to_supabase(L220-228) 및 user_video upload(L1774) 참조
-- ============================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('assets', 'assets', false)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: 자신이 업로드한 파일만 접근 가능
-- (백엔드 SERVICE_ROLE_KEY는 RLS 우회하여 업로드/Signed URL 발급)
CREATE POLICY "assets_select_own" ON storage.objects
    FOR SELECT
    USING (
        bucket_id = 'assets'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "assets_insert_own" ON storage.objects
    FOR INSERT
    WITH CHECK (
        bucket_id = 'assets'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "assets_delete_own" ON storage.objects
    FOR DELETE
    USING (
        bucket_id = 'assets'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- ============================================================
-- 완료 확인 메시지
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE 'RAPTOR 스키마 초기화 완료: projects, tasks, user_video_assets 테이블 생성 및 RLS 정책 적용됨';
END$$;
