-- ============================================================================
-- AeroSentinel — Intelligent AWS Anomaly Detection & Quality Control (SIH26073)
-- Production Supabase PostgreSQL Schema, Indexes, Triggers, RLS & Storage
-- ============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ----------------------------------------------------------------------------
-- 1. ENUMS
-- ----------------------------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE station_status AS ENUM ('active', 'maintenance', 'decommissioned');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE qc_verdict AS ENUM ('valid', 'suspect', 'anomalous');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE alert_severity AS ENUM ('low', 'medium', 'high', 'critical');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE alert_status AS ENUM ('open', 'acknowledged', 'resolved');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE feedback_label AS ENUM ('confirmed_fault', 'false_alarm', 'unsure');
EXCEPTION WHEN duplicate_object THEN null; END $$;

DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'forecaster', 'qc_analyst', 'data_quality_officer', 'field_technician', 'viewer');
EXCEPTION WHEN duplicate_object THEN null; END $$;

-- ----------------------------------------------------------------------------
-- 2. CORE TABLES
-- ----------------------------------------------------------------------------

-- PROFILES (Synchronized with Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'viewer',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- STATIONS
CREATE TABLE IF NOT EXISTS public.stations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    station_code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    elevation_m DOUBLE PRECISION,
    state VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    install_date DATE,
    sensor_specs JSONB NOT NULL DEFAULT '{}'::jsonb,
    status station_status NOT NULL DEFAULT 'active',
    last_seen TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RAW READINGS (OBSERVATIONS)
CREATE TABLE IF NOT EXISTS public.raw_readings (
    id BIGSERIAL PRIMARY KEY,
    station_id UUID NOT NULL REFERENCES public.stations(id) ON DELETE CASCADE,
    timestamp TIMESTAMPTZ NOT NULL,
    temperature DOUBLE PRECISION,
    humidity DOUBLE PRECISION,
    pressure DOUBLE PRECISION,
    temperature_raw DOUBLE PRECISION,
    pressure_raw DOUBLE PRECISION,
    humidity_raw DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    wind_direction DOUBLE PRECISION,
    rainfall DOUBLE PRECISION,
    solar_radiation DOUBLE PRECISION,
    ingest_source VARCHAR(50) NOT NULL DEFAULT 'simulator',
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_station_timestamp UNIQUE (station_id, timestamp)
);

-- QC RESULTS (ANOMALIES)
CREATE TABLE IF NOT EXISTS public.qc_results (
    id BIGSERIAL PRIMARY KEY,
    reading_id BIGINT NOT NULL REFERENCES public.raw_readings(id) ON DELETE CASCADE,
    station_id UUID NOT NULL REFERENCES public.stations(id) ON DELETE CASCADE,
    variable VARCHAR(50) NOT NULL,
    verdict qc_verdict NOT NULL,
    reason_code VARCHAR(50) NOT NULL,
    fault_type VARCHAR(50),
    confidence DOUBLE PRECISION NOT NULL,
    ml_model_version VARCHAR(50),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ALERTS
CREATE TABLE IF NOT EXISTS public.alerts (
    id BIGSERIAL PRIMARY KEY,
    station_id UUID NOT NULL REFERENCES public.stations(id) ON DELETE CASCADE,
    qc_result_id BIGINT NOT NULL REFERENCES public.qc_results(id) ON DELETE CASCADE,
    title VARCHAR(255),
    severity alert_severity NOT NULL,
    status alert_status NOT NULL DEFAULT 'open',
    message TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_by UUID,
    acknowledged_at TIMESTAMPTZ,
    channel_sent JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

-- SYSTEM TASKS (MAINTENANCE TASKS)
CREATE TABLE IF NOT EXISTS public.system_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    station_id UUID REFERENCES public.stations(id) ON DELETE SET NULL,
    assigned_to UUID,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    failure_probability DOUBLE PRECISION,
    assigned_role VARCHAR(50) NOT NULL,
    priority VARCHAR(50) NOT NULL DEFAULT 'medium',
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    category VARCHAR(50) NOT NULL DEFAULT 'general',
    station_code VARCHAR(50),
    assigned_to_name VARCHAR(255),
    due_date VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- DATA UPLOADS
CREATE TABLE IF NOT EXISTS public.data_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    uploaded_by UUID,
    filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(500),
    file_type VARCHAR(50) NOT NULL DEFAULT 'csv',
    file_size BIGINT NOT NULL DEFAULT 0,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    records_processed INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- FEEDBACK
CREATE TABLE IF NOT EXISTS public.feedback (
    id BIGSERIAL PRIMARY KEY,
    qc_result_id BIGINT NOT NULL REFERENCES public.qc_results(id) ON DELETE CASCADE,
    user_id UUID,
    label feedback_label NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- MODEL REGISTRY
CREATE TABLE IF NOT EXISTS public.model_registry (
    id BIGSERIAL PRIMARY KEY,
    model_type VARCHAR(50) NOT NULL,
    variable VARCHAR(50) NOT NULL,
    version VARCHAR(50) NOT NULL,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    training_data_range VARCHAR(100),
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    artifact_path VARCHAR(500) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE
);

-- MAINTENANCE PREDICTIONS
CREATE TABLE IF NOT EXISTS public.maintenance_predictions (
    id BIGSERIAL PRIMARY KEY,
    station_id UUID NOT NULL REFERENCES public.stations(id) ON DELETE CASCADE,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    failure_probability_30d DOUBLE PRECISION NOT NULL,
    top_factors JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- AUDIT LOGS
CREATE TABLE IF NOT EXISTS public.audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID,
    user_email VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource VARCHAR(100) NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ROLES & PERMISSIONS
CREATE TABLE IF NOT EXISTS public.roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.permissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(100) UNIQUE NOT NULL,
    module VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.role_permissions (
    id BIGSERIAL PRIMARY KEY,
    role_id UUID NOT NULL REFERENCES public.roles(id) ON DELETE CASCADE,
    permission_id UUID NOT NULL REFERENCES public.permissions(id) ON DELETE CASCADE,
    CONSTRAINT uq_role_permission UNIQUE (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS public.system_settings (
    id BIGSERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB NOT NULL DEFAULT '{}'::jsonb,
    description TEXT,
    updated_by VARCHAR(255),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- 3. VIEWS & ALIASES (Ensures logical compatibility with SIH & API specs)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE VIEW public.observations AS
    SELECT 
        id,
        station_id,
        timestamp AS observed_at,
        temperature,
        pressure,
        humidity,
        temperature_raw,
        pressure_raw,
        humidity_raw,
        ingest_source AS source,
        ingested_at AS created_at
    FROM public.raw_readings;

CREATE OR REPLACE VIEW public.anomalies AS
    SELECT 
        id,
        station_id,
        reading_id AS observation_id,
        fault_type AS anomaly_type,
        CASE 
            WHEN confidence >= 0.85 THEN 'critical'::alert_severity
            WHEN confidence >= 0.70 THEN 'high'::alert_severity
            ELSE 'medium'::alert_severity
        END AS severity,
        confidence,
        confidence AS score,
        details AS explanation,
        verdict AS status,
        created_at AS detected_at,
        NULL::timestamptz AS resolved_at
    FROM public.qc_results;

CREATE OR REPLACE VIEW public.maintenance_tasks AS
    SELECT 
        id,
        station_id,
        assigned_to,
        title,
        description,
        failure_probability,
        priority,
        status,
        due_date,
        created_at,
        updated_at
    FROM public.system_tasks;

-- ----------------------------------------------------------------------------
-- 4. PERFORMANCE INDEXES
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_stations_lat_lon ON public.stations (latitude, longitude);
CREATE INDEX IF NOT EXISTS idx_stations_code ON public.stations (station_code);

-- Critical High-Volume Observation Index (station_id + observed_at DESC)
CREATE INDEX IF NOT EXISTS idx_raw_readings_station_time_desc ON public.raw_readings (station_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_raw_readings_timestamp ON public.raw_readings (timestamp);

CREATE INDEX IF NOT EXISTS idx_qc_results_station_created ON public.qc_results (station_id, created_at);
CREATE INDEX IF NOT EXISTS idx_qc_results_verdict ON public.qc_results (verdict);

CREATE INDEX IF NOT EXISTS idx_alerts_station_id ON public.alerts (station_id);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON public.alerts (status);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON public.alerts (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_system_tasks_role ON public.system_tasks (assigned_role);
CREATE INDEX IF NOT EXISTS idx_system_tasks_status ON public.system_tasks (status);

CREATE INDEX IF NOT EXISTS idx_data_uploads_user ON public.data_uploads (uploaded_by);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON public.audit_logs (created_at DESC);

-- ----------------------------------------------------------------------------
-- 5. SUPABASE AUTH TRIGGER (Default new signups to 'viewer')
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name, role, created_at, updated_at)
    VALUES (
        new.id,
        new.email,
        COALESCE(new.raw_user_meta_data->>'full_name', split_part(new.email, '@', 1)),
        'viewer',
        NOW(),
        NOW()
    )
    ON CONFLICT (id) DO UPDATE
    SET 
        email = EXCLUDED.email,
        updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ----------------------------------------------------------------------------
-- 6. ROW LEVEL SECURITY (RLS) POLICIES
-- ----------------------------------------------------------------------------
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.raw_readings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.qc_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.data_uploads ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Helper function to fetch requesting user's role from profiles
CREATE OR REPLACE FUNCTION public.current_user_role()
RETURNS text AS $$
    SELECT role FROM public.profiles WHERE id = auth.uid();
$$ LANGUAGE sql STABLE SECURITY DEFINER;

-- PROFILES Policies
CREATE POLICY "Profiles readable by authenticated users"
    ON public.profiles FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Users can update own profile"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (id = auth.uid())
    WITH CHECK (id = auth.uid());

CREATE POLICY "Admins can update any profile"
    ON public.profiles FOR UPDATE
    TO authenticated
    USING (public.current_user_role() = 'admin')
    WITH CHECK (public.current_user_role() = 'admin');

-- STATIONS Policies (Read-only for viewer/public, edit for admin/technician)
CREATE POLICY "Stations readable by everyone"
    ON public.stations FOR SELECT
    TO authenticated, anon
    USING (true);

CREATE POLICY "Admins can manage stations"
    ON public.stations FOR ALL
    TO authenticated
    USING (public.current_user_role() IN ('admin', 'field_technician'))
    WITH CHECK (public.current_user_role() IN ('admin', 'field_technician'));

-- OBSERVATIONS (RAW READINGS) Policies
CREATE POLICY "Observations readable by authenticated users"
    ON public.raw_readings FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Ingestion allowed for authorized operators and service role"
    ON public.raw_readings FOR INSERT
    TO authenticated
    WITH CHECK (public.current_user_role() IN ('admin', 'forecaster', 'qc_analyst'));

-- QC RESULTS (ANOMALIES) Policies
CREATE POLICY "QC results readable by authenticated users"
    ON public.qc_results FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "QC analysts and admins can update QC verdicts"
    ON public.qc_results FOR UPDATE
    TO authenticated
    USING (public.current_user_role() IN ('admin', 'qc_analyst', 'data_quality_officer'))
    WITH CHECK (public.current_user_role() IN ('admin', 'qc_analyst', 'data_quality_officer'));

-- ALERTS Policies
CREATE POLICY "Alerts readable by authenticated users"
    ON public.alerts FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Operators can acknowledge and resolve alerts"
    ON public.alerts FOR UPDATE
    TO authenticated
    USING (public.current_user_role() IN ('admin', 'forecaster', 'qc_analyst', 'field_technician'))
    WITH CHECK (public.current_user_role() IN ('admin', 'forecaster', 'qc_analyst', 'field_technician'));

-- SYSTEM TASKS Policies
CREATE POLICY "Tasks readable by authenticated users"
    ON public.system_tasks FOR SELECT
    TO authenticated
    USING (true);

CREATE POLICY "Operators can update assigned tasks"
    ON public.system_tasks FOR ALL
    TO authenticated
    USING (public.current_user_role() IN ('admin', 'field_technician', 'qc_analyst'))
    WITH CHECK (public.current_user_role() IN ('admin', 'field_technician', 'qc_analyst'));

-- DATA UPLOADS Policies
CREATE POLICY "Uploads readable by uploader or admin"
    ON public.data_uploads FOR SELECT
    TO authenticated
    USING (uploaded_by = auth.uid() OR public.current_user_role() = 'admin');

CREATE POLICY "Operators can log data uploads"
    ON public.data_uploads FOR INSERT
    TO authenticated
    WITH CHECK (public.current_user_role() IN ('admin', 'qc_analyst', 'forecaster'));

-- AUDIT LOGS Policies (Insert for actions, read for admin)
CREATE POLICY "Admins can view audit logs"
    ON public.audit_logs FOR SELECT
    TO authenticated
    USING (public.current_user_role() = 'admin');

CREATE POLICY "Authenticated users can create audit log entries"
    ON public.audit_logs FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- ----------------------------------------------------------------------------
-- 7. SUPABASE STORAGE BUCKETS
-- ----------------------------------------------------------------------------
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES 
    ('aerosentinel-uploads', 'aerosentinel-uploads', false, 52428800, ARRAY['text/csv', 'application/json', 'text/plain']),
    ('aerosentinel-reports', 'aerosentinel-reports', false, 52428800, ARRAY['application/pdf', 'text/csv', 'application/json'])
ON CONFLICT (id) DO NOTHING;

-- Storage Policies: aerosentinel-uploads
CREATE POLICY "Authenticated operators can upload sensor batches"
    ON storage.objects FOR INSERT
    TO authenticated
    WITH CHECK (bucket_id = 'aerosentinel-uploads');

CREATE POLICY "Authenticated operators can read sensor batches"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (bucket_id = 'aerosentinel-uploads');

-- Storage Policies: aerosentinel-reports
CREATE POLICY "Authenticated operators can read reports"
    ON storage.objects FOR SELECT
    TO authenticated
    USING (bucket_id = 'aerosentinel-reports');

CREATE POLICY "Backend service can write reports"
    ON storage.objects FOR INSERT
    TO authenticated
    WITH CHECK (bucket_id = 'aerosentinel-reports');

-- ----------------------------------------------------------------------------
-- 8. SUPABASE REALTIME REPLICATION PUBLICATION
-- ----------------------------------------------------------------------------
DO $$ BEGIN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.stations;
    ALTER PUBLICATION supabase_realtime ADD TABLE public.alerts;
    ALTER PUBLICATION supabase_realtime ADD TABLE public.qc_results;
    ALTER PUBLICATION supabase_realtime ADD TABLE public.system_tasks;
EXCEPTION WHEN others THEN null; END $$;
