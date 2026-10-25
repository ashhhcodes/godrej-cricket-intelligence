-- =====================================================================
-- Migration: 001_initial_schema.sql
-- Description: Core tables, constraints, and indexes for Godrej Cricket Intelligence
-- Compatibility: PostgreSQL 16+
-- =====================================================================

-- 1. MATCHES TABLE
-- Stores master fixture records for international, IPL, and domestic fixtures.
CREATE TABLE IF NOT EXISTS matches (
    id BIGSERIAL PRIMARY KEY,
    provider_match_id VARCHAR(100) NOT NULL UNIQUE,
    series_name VARCHAR(255) NULL,
    match_name VARCHAR(255) NOT NULL,
    match_type VARCHAR(50) NOT NULL, -- 't20', 'odi', 'test'
    competition_category VARCHAR(50) NOT NULL DEFAULT 'Other', -- 'International', 'IPL', 'Domestic', 'Other'
    venue VARCHAR(255) NULL,
    match_date_utc TIMESTAMPTZ NOT NULL,
    team_a VARCHAR(100) NOT NULL,
    team_b VARCHAR(100) NOT NULL,
    toss_winner VARCHAR(100) NULL,
    toss_choice VARCHAR(20) NULL, -- 'bat', 'bowl'
    match_winner VARCHAR(100) NULL,
    result_status VARCHAR(255) NULL, -- 'Live', 'Completed', 'Innings Break', 'Match Abandoned', etc.
    is_live BOOLEAN NOT NULL DEFAULT FALSE,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    is_abandoned BOOLEAN NOT NULL DEFAULT FALSE,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_matches_provider_id ON matches(provider_match_id);
CREATE INDEX IF NOT EXISTS idx_matches_status ON matches(is_live, is_completed, is_abandoned);
CREATE INDEX IF NOT EXISTS idx_matches_date ON matches(match_date_utc DESC);

-- 2. MATCH_STATE TABLE
-- Stores latest single-row active in-play state per match.
-- Optimized for Power BI DirectQuery Change Detection and top-line KPI strip.
CREATE TABLE IF NOT EXISTS match_state (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT NOT NULL UNIQUE REFERENCES matches(id) ON DELETE CASCADE,
    current_status_summary VARCHAR(255) NOT NULL,
    current_innings_number SMALLINT NULL,
    batting_team VARCHAR(100) NULL,
    bowling_team VARCHAR(100) NULL,
    current_runs INT NULL,
    current_wickets SMALLINT NULL,
    current_overs NUMERIC(4, 1) NULL,
    current_run_rate NUMERIC(5, 2) NULL,
    required_run_rate NUMERIC(5, 2) NULL,
    target_runs INT NULL,
    last_api_poll_utc TIMESTAMPTZ NOT NULL,
    last_source_update_utc TIMESTAMPTZ NULL,
    is_live BOOLEAN NOT NULL DEFAULT FALSE,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_match_state_match_id ON match_state(match_id);
CREATE INDEX IF NOT EXISTS idx_match_state_updated ON match_state(updated_at_utc DESC);

-- 3. INNINGS TABLE
-- Summary statistics for each completed or ongoing innings.
CREATE TABLE IF NOT EXISTS innings (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    innings_number SMALLINT NOT NULL, -- 1, 2, 3, 4
    innings_name VARCHAR(150) NOT NULL, -- e.g. "Chennai Super Kings Innings 1"
    batting_team VARCHAR(100) NOT NULL,
    bowling_team VARCHAR(100) NOT NULL,
    total_runs INT NOT NULL DEFAULT 0,
    total_wickets SMALLINT NOT NULL DEFAULT 0,
    total_overs NUMERIC(4, 1) NOT NULL DEFAULT 0.0,
    run_rate NUMERIC(5, 2) NULL,
    extras_total INT NOT NULL DEFAULT 0,
    extras_byes INT NOT NULL DEFAULT 0,
    extras_leg_byes INT NOT NULL DEFAULT 0,
    extras_wides INT NOT NULL DEFAULT 0,
    extras_no_balls INT NOT NULL DEFAULT 0,
    is_declared BOOLEAN NOT NULL DEFAULT FALSE,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_match_innings UNIQUE (match_id, innings_number)
);

CREATE INDEX IF NOT EXISTS idx_innings_match_id ON innings(match_id);

-- 4. BATTING_SCORECARD TABLE
-- Granular batter performances per innings.
-- Strict rule: strike_rate is NULL if balls_faced = 0 (never 0.0 for did not bat).
CREATE TABLE IF NOT EXISTS batting_scorecard (
    id BIGSERIAL PRIMARY KEY,
    innings_id BIGINT NOT NULL REFERENCES innings(id) ON DELETE CASCADE,
    match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    provider_player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(150) NOT NULL,
    batting_position SMALLINT NULL,
    dismissal_info VARCHAR(255) NULL, -- 'not out', 'c Jadeja b Bumrah', 'lbw b Shami'
    is_dismissed BOOLEAN NOT NULL DEFAULT FALSE,
    runs INT NOT NULL DEFAULT 0,
    balls_faced INT NOT NULL DEFAULT 0,
    fours INT NOT NULL DEFAULT 0,
    sixes INT NOT NULL DEFAULT 0,
    strike_rate NUMERIC(6, 2) NULL, -- NULL when balls_faced = 0
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_innings_batter UNIQUE (innings_id, provider_player_id)
);

CREATE INDEX IF NOT EXISTS idx_batting_innings ON batting_scorecard(innings_id);
CREATE INDEX IF NOT EXISTS idx_batting_match ON batting_scorecard(match_id);

-- 5. BOWLING_SCORECARD TABLE
-- Granular bowler performances per innings.
-- Strict rule: economy_rate is NULL if overs_bowled = 0.0.
CREATE TABLE IF NOT EXISTS bowling_scorecard (
    id BIGSERIAL PRIMARY KEY,
    innings_id BIGINT NOT NULL REFERENCES innings(id) ON DELETE CASCADE,
    match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    provider_player_id VARCHAR(100) NOT NULL,
    player_name VARCHAR(150) NOT NULL,
    bowling_order SMALLINT NULL,
    overs_bowled NUMERIC(4, 1) NOT NULL DEFAULT 0.0,
    maidens SMALLINT NOT NULL DEFAULT 0,
    runs_conceded INT NOT NULL DEFAULT 0,
    wickets SMALLINT NOT NULL DEFAULT 0,
    economy_rate NUMERIC(5, 2) NULL, -- NULL when overs_bowled = 0.0
    dots INT NULL, -- NULL if not supplied by provider
    wides SMALLINT NOT NULL DEFAULT 0,
    no_balls SMALLINT NOT NULL DEFAULT 0,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_innings_bowler UNIQUE (innings_id, provider_player_id)
);

CREATE INDEX IF NOT EXISTS idx_bowling_innings ON bowling_scorecard(innings_id);
CREATE INDEX IF NOT EXISTS idx_bowling_match ON bowling_scorecard(match_id);

-- 6. SCORE_SNAPSHOTS TABLE
-- Historical periodic progress points for worm charts and run-rate progression.
-- Preserved separately from latest match_state.
CREATE TABLE IF NOT EXISTS score_snapshots (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    innings_id BIGINT NOT NULL REFERENCES innings(id) ON DELETE CASCADE,
    snapshot_timestamp_utc TIMESTAMPTZ NOT NULL,
    overs NUMERIC(4, 1) NOT NULL,
    runs INT NOT NULL,
    wickets SMALLINT NOT NULL,
    run_rate NUMERIC(5, 2) NULL,
    striker_name VARCHAR(150) NULL,
    non_striker_name VARCHAR(150) NULL,
    active_bowler_name VARCHAR(150) NULL,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_snapshot_unique_over UNIQUE (innings_id, overs)
);

CREATE INDEX IF NOT EXISTS idx_snapshots_match_innings ON score_snapshots(match_id, innings_id, snapshot_timestamp_utc);

-- 7. BALL_EVENTS TABLE
-- Granular ball-by-ball events for replay simulation and deep dive drilldowns.
CREATE TABLE IF NOT EXISTS ball_events (
    id BIGSERIAL PRIMARY KEY,
    match_id BIGINT NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    innings_id BIGINT NOT NULL REFERENCES innings(id) ON DELETE CASCADE,
    over_number SMALLINT NOT NULL, -- 0-indexed over (0 = first over)
    ball_number SMALLINT NOT NULL, -- 1-indexed ball in over (1..6+)
    ball_sequence INT NOT NULL,    -- Sequential absolute ball counter in the innings
    batter_name VARCHAR(150) NOT NULL,
    bowler_name VARCHAR(150) NOT NULL,
    non_striker_name VARCHAR(150) NULL,
    runs_batter SMALLINT NOT NULL DEFAULT 0,
    runs_extra SMALLINT NOT NULL DEFAULT 0,
    extra_type VARCHAR(20) NULL, -- 'wide', 'no ball', 'bye', 'leg bye', 'penalty'
    total_ball_runs SMALLINT NOT NULL DEFAULT 0,
    is_wicket BOOLEAN NOT NULL DEFAULT FALSE,
    wicket_type VARCHAR(50) NULL, -- 'bowled', 'caught', 'lbw', 'run out', etc.
    player_dismissed VARCHAR(150) NULL,
    commentary_text TEXT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    created_at_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_innings_ball_seq UNIQUE (innings_id, ball_sequence)
);

CREATE INDEX IF NOT EXISTS idx_ball_events_lookup ON ball_events(match_id, innings_id, over_number);

-- 8. API_USAGE TABLE
-- Quota accounting, rate-limiting audit log, and circuit-breaker telemetry.
CREATE TABLE IF NOT EXISTS api_usage (
    id BIGSERIAL PRIMARY KEY,
    timestamp_utc TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint VARCHAR(100) NOT NULL,
    http_status SMALLINT NOT NULL,
    credits_consumed SMALLINT NOT NULL DEFAULT 1,
    hits_today SMALLINT NULL,
    hits_limit SMALLINT NULL,
    credits_remaining SMALLINT NULL,
    response_time_ms INT NULL,
    match_id_queried VARCHAR(100) NULL,
    status_message VARCHAR(255) NULL
);

CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp_utc DESC);
