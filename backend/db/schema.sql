-- 로컬 SQLite 스키마 (DB_DESIGN.md §2 그대로). 서버 시작 시마다 실행되며 이미 있으면 건너뛴다.

CREATE TABLE IF NOT EXISTS projects (
  id         TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 36),
  name       TEXT NOT NULL CHECK (name = trim(name) AND length(name) > 0),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_projects_name_ci ON projects (lower(name));

CREATE TABLE IF NOT EXISTS todos (
  id         TEXT PRIMARY KEY NOT NULL CHECK (length(id) = 36),
  project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
  title      TEXT NOT NULL CHECK (length(trim(title)) > 0),
  is_done    INTEGER NOT NULL DEFAULT 0 CHECK (is_done IN (0, 1)),
  due_date   TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_todos_project_id ON todos (project_id);
