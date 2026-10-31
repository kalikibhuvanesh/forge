-- Reference schema for PostgreSQL. In dev the API creates tables from SQLAlchemy models.
CREATE EXTENSION IF NOT EXISTS vector;  -- pgvector, used later for guideline retrieval

CREATE TABLE users (
  id text PRIMARY KEY, email text UNIQUE NOT NULL, password_hash text NOT NULL,
  role text NOT NULL DEFAULT 'student' CHECK (role IN ('student','support','admin')),
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE student_profiles (
  user_id text PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  data jsonb NOT NULL DEFAULT '{}', updated_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE source_snapshots (
  id text PRIMARY KEY, url text NOT NULL, source_type text NOT NULL, http_status int NOT NULL,
  retrieved_at timestamptz NOT NULL DEFAULT now(), sha256 char(64) NOT NULL, content_text text NOT NULL);

CREATE TABLE schemes (
  id text PRIMARY KEY, scheme_key text NOT NULL, name text NOT NULL, provider text,
  academic_year char(7) NOT NULL, official_url text NOT NULL, guideline_url text,
  application_deadline date, deadline_verified boolean NOT NULL DEFAULT false,
  required_documents jsonb NOT NULL DEFAULT '[]',
  source_snapshot_id text NOT NULL REFERENCES source_snapshots(id),
  retrieved_at timestamptz NOT NULL);

CREATE TABLE rule_sets (
  id text PRIMARY KEY, scheme_id text NOT NULL REFERENCES schemes(id), academic_year char(7) NOT NULL,
  criteria jsonb NOT NULL DEFAULT '[]',
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','retired')),
  approved_by text REFERENCES users(id), approved_at timestamptz);

CREATE TABLE audit_events (
  seq bigserial PRIMARY KEY, event_id text UNIQUE NOT NULL, action_type text NOT NULL,
  occurred_at text NOT NULL, application_ref text, verification_result text, evidence_ref text,
  prev_hash char(64) NOT NULL, event_hash char(64) NOT NULL);
-- Defence in depth: the app role should have INSERT/SELECT only on audit_events (no UPDATE/DELETE).
-- Later slices: documents, extractions (confirmed vs unconfirmed), applications, application_state_history.
