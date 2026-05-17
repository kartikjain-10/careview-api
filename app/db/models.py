CREATE_SNAPSHOTS_TABLE = """
CREATE TABLE IF NOT EXISTS wearable_snapshots (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id           TEXT    NOT NULL,
    date                TEXT    NOT NULL,
    steps               INTEGER NOT NULL,
    sleep_hours         REAL    NOT NULL,
    resting_heart_rate  INTEGER NOT NULL,
    active_minutes      INTEGER NOT NULL,
    mood_score          INTEGER NOT NULL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_SNAPSHOTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_snapshots_parent_date
    ON wearable_snapshots (parent_id, date);
"""

CREATE_DOCUMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS documents (
    id          TEXT    PRIMARY KEY,
    parent_id   TEXT    NOT NULL,
    filename    TEXT    NOT NULL,
    upload_date TEXT    NOT NULL,
    chunk_count INTEGER NOT NULL,
    file_path   TEXT    NOT NULL
);
"""

CREATE_DOCUMENTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_documents_parent
    ON documents (parent_id);
"""
