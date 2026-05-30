# ─────────────────────────────────────────────────────────────────────────────
# Existing tables
# ─────────────────────────────────────────────────────────────────────────────

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
    id                TEXT    PRIMARY KEY,
    parent_id         TEXT    NOT NULL,
    filename          TEXT    NOT NULL,
    upload_date       TEXT    NOT NULL,
    chunk_count       INTEGER NOT NULL,
    file_path         TEXT    NOT NULL,
    processing_status TEXT    NOT NULL DEFAULT 'indexed',
    extraction_error  TEXT,
    summary           TEXT,
    report_type       TEXT,
    report_date       TEXT,
    provider          TEXT,
    status            TEXT    NOT NULL DEFAULT 'active'
);
"""

CREATE_DOCUMENTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_documents_parent
    ON documents (parent_id);
"""

CREATE_HEALTH_INSIGHTS_TABLE = """
CREATE TABLE IF NOT EXISTS health_insights (
    id                  TEXT    PRIMARY KEY,
    parent_id           TEXT    NOT NULL,
    query               TEXT    NOT NULL,
    insight             TEXT    NOT NULL,
    source_document_ids TEXT    NOT NULL DEFAULT '[]',
    model               TEXT    NOT NULL DEFAULT 'groq:llama-3.3-70b-versatile',
    created_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_HEALTH_INSIGHTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_health_insights_parent_created
    ON health_insights (parent_id, created_at);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Users
# ─────────────────────────────────────────────────────────────────────────────

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id          TEXT    PRIMARY KEY,
    email       TEXT    NOT NULL UNIQUE,
    name        TEXT    NOT NULL,
    is_admin    INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login  TEXT
);
"""

CREATE_USERS_EMAIL_INDEX = """
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Family groups + members
# ─────────────────────────────────────────────────────────────────────────────

CREATE_FAMILY_GROUPS_TABLE = """
CREATE TABLE IF NOT EXISTS family_groups (
    id          TEXT    PRIMARY KEY,
    owner_id    TEXT    NOT NULL REFERENCES users(id),
    name        TEXT    NOT NULL DEFAULT 'My Family',
    invite_code TEXT    NOT NULL UNIQUE,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_FAMILY_GROUP_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS family_group_users (
    group_id   TEXT    NOT NULL REFERENCES family_groups(id),
    user_id    TEXT    NOT NULL REFERENCES users(id),
    role       TEXT    NOT NULL DEFAULT 'caregiver',
    status     TEXT    NOT NULL DEFAULT 'active',
    joined_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (group_id, user_id)
);
"""

CREATE_FAMILY_GROUP_USERS_USER_INDEX = """
CREATE INDEX IF NOT EXISTS idx_family_group_users_user
    ON family_group_users (user_id, status);
"""

CREATE_FAMILY_MEMBERS_TABLE = """
CREATE TABLE IF NOT EXISTS family_members (
    id           TEXT    PRIMARY KEY,
    group_id     TEXT    NOT NULL REFERENCES family_groups(id),
    name         TEXT    NOT NULL,
    formal_name  TEXT,
    display_name TEXT,
    color        TEXT    DEFAULT '#00C9A7',
    relationship TEXT    NOT NULL DEFAULT 'Other',
    age          INTEGER,
    sex          TEXT,
    focus        TEXT,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_FAMILY_MEMBERS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_family_members_group
    ON family_members (group_id);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Invitations
# ─────────────────────────────────────────────────────────────────────────────

CREATE_INVITATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS invitations (
    id          TEXT    PRIMARY KEY,
    group_id    TEXT    NOT NULL REFERENCES family_groups(id),
    invited_by  TEXT    NOT NULL REFERENCES users(id),
    email       TEXT,
    phone       TEXT,
    channel     TEXT    NOT NULL DEFAULT 'email',
    token       TEXT    NOT NULL UNIQUE,
    status      TEXT    NOT NULL DEFAULT 'pending',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT    NOT NULL,
    accepted_at TEXT
);
"""

CREATE_INVITATIONS_TOKEN_INDEX = """
CREATE INDEX IF NOT EXISTS idx_invitations_token ON invitations (token);
"""

CREATE_INVITATIONS_GROUP_INDEX = """
CREATE INDEX IF NOT EXISTS idx_invitations_group ON invitations (group_id);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Medicines
# ─────────────────────────────────────────────────────────────────────────────

CREATE_MEDICINES_TABLE = """
CREATE TABLE IF NOT EXISTS medicines (
    id            TEXT    PRIMARY KEY,
    profile_id    TEXT    NOT NULL REFERENCES family_members(id),
    group_id      TEXT    NOT NULL REFERENCES family_groups(id),
    name          TEXT    NOT NULL,
    brand_name    TEXT,
    dosage        TEXT    NOT NULL,
    form          TEXT    NOT NULL DEFAULT 'tablet',
    instructions  TEXT,
    color         TEXT    DEFAULT '#00C9A7',
    is_active     INTEGER NOT NULL DEFAULT 1,
    prescribed_by TEXT,
    start_date    TEXT,
    end_date      TEXT,
    schedules     TEXT    NOT NULL DEFAULT '[]',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_MEDICINES_INDEX = """
CREATE INDEX IF NOT EXISTS idx_medicines_group_profile
    ON medicines (group_id, profile_id);
"""

CREATE_MEDICINE_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS medicine_logs (
    id             TEXT    PRIMARY KEY,
    schedule_id    TEXT    NOT NULL,
    profile_id     TEXT    NOT NULL,
    group_id       TEXT    NOT NULL,
    scheduled_for  TEXT    NOT NULL,
    status         TEXT    NOT NULL,
    taken_at       TEXT,
    skipped_reason TEXT,
    marked_by      TEXT,
    is_late        INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_MEDICINE_LOGS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_medicine_logs_group_profile
    ON medicine_logs (group_id, profile_id, scheduled_for);
"""

CREATE_MEDICINE_STREAKS_TABLE = """
CREATE TABLE IF NOT EXISTS medicine_streaks (
    profile_id               TEXT    PRIMARY KEY,
    group_id                 TEXT    NOT NULL,
    current_streak           INTEGER NOT NULL DEFAULT 0,
    longest_streak           INTEGER NOT NULL DEFAULT 0,
    last_updated             TEXT    NOT NULL DEFAULT (datetime('now')),
    freeze_tokens_remaining  INTEGER NOT NULL DEFAULT 3,
    streak_history           TEXT    NOT NULL DEFAULT '[]'
);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Habits, XP, Badges
# ─────────────────────────────────────────────────────────────────────────────

CREATE_HABIT_LOGS_TABLE = """
CREATE TABLE IF NOT EXISTS habit_logs (
    id            TEXT    PRIMARY KEY,
    profile_id    TEXT    NOT NULL,
    group_id      TEXT    NOT NULL,
    date          TEXT    NOT NULL,
    water_glasses INTEGER DEFAULT 0,
    mood          TEXT,
    activity      TEXT,
    sleep         TEXT,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(profile_id, date)
);
"""

CREATE_HABIT_LOGS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_habit_logs_group_profile_date
    ON habit_logs (group_id, profile_id, date);
"""

CREATE_XP_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS xp_events (
    id          TEXT    PRIMARY KEY,
    profile_id  TEXT    NOT NULL,
    group_id    TEXT    NOT NULL,
    action_type TEXT    NOT NULL,
    xp_amount   INTEGER NOT NULL,
    metadata    TEXT    DEFAULT '{}',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_XP_EVENTS_INDEX = """
CREATE INDEX IF NOT EXISTS idx_xp_events_group_profile
    ON xp_events (group_id, profile_id);
"""

CREATE_MEMBER_BADGES_TABLE = """
CREATE TABLE IF NOT EXISTS member_badges (
    profile_id  TEXT    NOT NULL,
    badge_key   TEXT    NOT NULL,
    group_id    TEXT    NOT NULL,
    earned_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    seen        INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (profile_id, badge_key)
);
"""

# ─────────────────────────────────────────────────────────────────────────────
# Onboarding + doctor shares
# ─────────────────────────────────────────────────────────────────────────────

CREATE_ONBOARDING_STATES_TABLE = """
CREATE TABLE IF NOT EXISTS onboarding_states (
    user_id       TEXT    PRIMARY KEY REFERENCES users(id),
    current_step  TEXT    NOT NULL DEFAULT 'account',
    completed     INTEGER NOT NULL DEFAULT 0,
    steps         TEXT    NOT NULL DEFAULT '{}',
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

CREATE_DOCTOR_SHARES_TABLE = """
CREATE TABLE IF NOT EXISTS doctor_shares (
    id          TEXT    PRIMARY KEY,
    group_id    TEXT    NOT NULL REFERENCES family_groups(id),
    member_id   TEXT    NOT NULL REFERENCES family_members(id),
    created_by  TEXT    NOT NULL REFERENCES users(id),
    title       TEXT    NOT NULL,
    token       TEXT    NOT NULL UNIQUE,
    scope       TEXT    NOT NULL DEFAULT '[]',
    status      TEXT    NOT NULL DEFAULT 'active',
    expires_at  TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    revoked_at  TEXT
);
"""

CREATE_DOCTOR_SHARES_GROUP_INDEX = """
CREATE INDEX IF NOT EXISTS idx_doctor_shares_group
    ON doctor_shares (group_id, created_at);
"""

CREATE_DOCTOR_SHARES_TOKEN_INDEX = """
CREATE INDEX IF NOT EXISTS idx_doctor_shares_token
    ON doctor_shares (token);
"""
