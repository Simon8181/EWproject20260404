-- Example table matching mapping.example.yaml — adjust types to match your data.

CREATE TABLE IF NOT EXISTS sheet_mirror (
    id TEXT PRIMARY KEY,
    name TEXT,
    updated_at TEXT
);
