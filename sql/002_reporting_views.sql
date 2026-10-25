-- =====================================================================
-- Migration: 002_reporting_views.sql
-- Description: DirectQuery-optimized analytical reporting views for Power BI
-- Compatibility: PostgreSQL 16+
-- =====================================================================

-- 1. LIVE MATCH SUMMARY VIEW
-- Primary data source for Page 1 Header, KPI Strips, and DirectQuery Change Detection.
CREATE OR REPLACE VIEW v_live_match_summary AS
SELECT 
    m.id AS match_id,
    m.provider_match_id,
    m.series_name,
    m.match_name,
    m.match_type,
    m.competition_category,
    m.venue,
    m.match_date_utc,
    m.team_a,
    m.team_b,
    m.toss_winner,
    m.toss_choice,
    m.match_winner,
    m.result_status,
    m.is_live,
    m.is_completed,
    m.is_abandoned,
    m.is_simulated,
    CASE 
        WHEN m.is_simulated THEN 'DEMO / SIMULATED DATA'
        ELSE 'OFFICIAL LIVE SOURCE'
    END AS data_provenance_badge,
    ms.current_status_summary,
    ms.current_innings_number,
    ms.batting_team,
    ms.bowling_team,
    ms.current_runs,
    ms.current_wickets,
    ms.current_overs,
    ms.current_run_rate,
    ms.required_run_rate,
    ms.target_runs,
    ms.last_api_poll_utc,
    ms.last_source_update_utc,
    ms.updated_at_utc AS state_updated_at_utc
FROM matches m
LEFT JOIN match_state ms ON m.id = ms.match_id;

-- 2. CURRENT BATTING SCORECARD VIEW
-- Supplies Page 1 live batting card and Page 2 tournament batting analytics.
CREATE OR REPLACE VIEW v_current_batting_scorecard AS
SELECT 
    bs.id AS batting_id,
    bs.match_id,
    m.provider_match_id,
    m.match_name,
    m.is_simulated,
    i.innings_number,
    i.innings_name,
    i.batting_team,
    bs.provider_player_id,
    bs.player_name,
    bs.batting_position,
    COALESCE(bs.dismissal_info, 'not out') AS dismissal_info,
    bs.is_dismissed,
    bs.runs,
    bs.balls_faced,
    bs.fours,
    bs.sixes,
    -- Strictly NULL if balls_faced = 0 (never 0.00 for did not bat)
    CASE 
        WHEN bs.balls_faced = 0 THEN NULL
        ELSE bs.strike_rate 
    END AS strike_rate,
    (bs.fours * 4 + bs.sixes * 6) AS boundary_runs,
    CASE 
        WHEN bs.runs = 0 THEN 0.0
        ELSE ROUND(((bs.fours * 4.0 + bs.sixes * 6.0) / bs.runs::NUMERIC) * 100.0, 2)
    END AS boundary_run_percentage,
    bs.updated_at_utc
FROM batting_scorecard bs
JOIN innings i ON bs.innings_id = i.id
JOIN matches m ON bs.match_id = m.id;

-- 3. CURRENT BOWLING SCORECARD VIEW
-- Supplies Page 1 live bowling card and Page 3 tournament bowling analytics.
CREATE OR REPLACE VIEW v_current_bowling_scorecard AS
SELECT 
    bws.id AS bowling_id,
    bws.match_id,
    m.provider_match_id,
    m.match_name,
    m.is_simulated,
    i.innings_number,
    i.innings_name,
    i.bowling_team,
    bws.provider_player_id,
    bws.player_name,
    bws.bowling_order,
    bws.overs_bowled,
    bws.maidens,
    bws.runs_conceded,
    bws.wickets,
    -- Strictly NULL if overs_bowled = 0.0
    CASE 
        WHEN bws.overs_bowled = 0.0 THEN NULL
        ELSE bws.economy_rate 
    END AS economy_rate,
    bws.dots,
    bws.wides,
    bws.no_balls,
    -- Bowling Average: runs / wickets (NULL if 0 wickets)
    CASE 
        WHEN bws.wickets = 0 THEN NULL
        ELSE ROUND(bws.runs_conceded::NUMERIC / bws.wickets::NUMERIC, 2)
    END AS bowling_average,
    -- Bowling Strike Rate: balls / wickets (NULL if 0 wickets)
    CASE 
        WHEN bws.wickets = 0 THEN NULL
        ELSE ROUND((FLOOR(bws.overs_bowled) * 6 + (bws.overs_bowled - FLOOR(bws.overs_bowled)) * 10)::NUMERIC / bws.wickets::NUMERIC, 2)
    END AS bowling_strike_rate,
    bws.updated_at_utc
FROM bowling_scorecard bws
JOIN innings i ON bws.innings_id = i.id
JOIN matches m ON bws.match_id = m.id;

-- 4. MATCH INNINGS SUMMARY VIEW
-- Detailed overviews of each completed/active innings.
CREATE OR REPLACE VIEW v_match_innings_summary AS
SELECT 
    i.id AS innings_id,
    i.match_id,
    m.match_name,
    m.is_simulated,
    i.innings_number,
    i.innings_name,
    i.batting_team,
    i.bowling_team,
    i.total_runs,
    i.total_wickets,
    i.total_overs,
    i.run_rate,
    i.extras_total,
    i.extras_byes,
    i.extras_leg_byes,
    i.extras_wides,
    i.extras_no_balls,
    i.is_completed,
    i.updated_at_utc
FROM innings i
JOIN matches m ON i.match_id = m.id;

-- 5. WORM COMPARISON VIEW
-- Supplies over-by-over cumulative runs and wickets for worm charts.
CREATE OR REPLACE VIEW v_worm_comparison AS
SELECT 
    s.id AS snapshot_id,
    s.match_id,
    m.match_name,
    m.is_simulated,
    i.innings_number,
    i.batting_team,
    s.overs,
    s.runs,
    s.wickets,
    s.run_rate,
    s.snapshot_timestamp_utc
FROM score_snapshots s
JOIN innings i ON s.innings_id = i.id
JOIN matches m ON s.match_id = m.id
ORDER BY s.match_id, i.innings_number, s.overs ASC;

-- 6. API TELEMETRY VIEW
-- Operational dashboard view of daily API requests, latency, and quota exhaustion.
CREATE OR REPLACE VIEW v_api_telemetry AS
SELECT 
    DATE(timestamp_utc) AS usage_date,
    COUNT(*) AS total_requests,
    COUNT(CASE WHEN http_status = 200 THEN 1 END) AS successful_requests,
    COUNT(CASE WHEN http_status = 429 THEN 1 END) AS rate_limited_requests,
    COUNT(CASE WHEN http_status >= 500 THEN 1 END) AS server_errors,
    ROUND(AVG(response_time_ms), 1) AS avg_response_time_ms,
    MAX(hits_today) AS max_hits_recorded_today,
    MIN(credits_remaining) AS min_credits_remaining
FROM api_usage
GROUP BY DATE(timestamp_utc)
ORDER BY usage_date DESC;
