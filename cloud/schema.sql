CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  progress INTEGER NOT NULL DEFAULT 0,
  message TEXT NOT NULL,
  source_name TEXT NOT NULL,
  source_key TEXT NOT NULL,
  upload_id TEXT NOT NULL,
  settings_json TEXT NOT NULL,
  result_key TEXT,
  candidate_key TEXT,
  source_sha256 TEXT,
  training_json TEXT,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS jobs_created_at_idx ON jobs(created_at DESC);
