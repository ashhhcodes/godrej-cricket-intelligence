// =====================================================================
// Power Query (M) Script: reporting_views.pq
// Project: Godrej Cricket Intelligence
// Target: PostgreSQL 16+ on localhost:5432 / godrej_cricket_db
// Connectivity Mode: DirectQuery
//
// Usage Instructions:
// 1. In Power BI Desktop, open Power Query Editor (Home -> Transform Data).
// 2. For each query below, click 'New Source' -> 'Blank Query'.
// 3. Open 'Advanced Editor' and paste the corresponding section code.
// 4. Rename the query to the exact view name (e.g., v_live_match_summary).
// 5. Ensure DirectQuery mode is maintained (do not switch to Import).
// =====================================================================

// ---------------------------------------------------------------------
// 1. SHARED CONNECTION PARAMETERS (Optional Power Query Parameters)
// ---------------------------------------------------------------------
let
    ServerAddress = "localhost:5432",
    DatabaseName = "godrej_cricket_db"
in
    DatabaseName


// ---------------------------------------------------------------------
// 2. QUERY: v_live_match_summary
// Primary conformed match dimension, live scorecard header, and change detection.
// ---------------------------------------------------------------------
let
    Source = PostgreSQL.Database("localhost:5432", "godrej_cricket_db"),
    public_Schema = Source{[Schema="public"]}[Data],
    v_live_match_summary_View = public_Schema{[Name="v_live_match_summary"]}[Data],
    #"Set Column Types" = Table.TransformColumnTypes(v_live_match_summary_View, {
        {"match_id", Int64.Type},
        {"provider_match_id", type text},
        {"series_name", type text},
        {"match_name", type text},
        {"match_type", type text},
        {"competition_category", type text},
        {"venue", type text},
        {"match_date_utc", type datetimezone},
        {"team_a", type text},
        {"team_b", type text},
        {"toss_winner", type text},
        {"toss_choice", type text},
        {"match_winner", type text},
        {"result_status", type text},
        {"is_live", type logical},
        {"is_completed", type logical},
        {"is_abandoned", type logical},
        {"is_simulated", type logical},
        {"data_provenance_badge", type text},
        {"current_status_summary", type text},
        {"current_innings_number", Int16.Type},
        {"batting_team", type text},
        {"bowling_team", type text},
        {"current_runs", Int32.Type},
        {"current_wickets", Int16.Type},
        {"current_overs", type number},
        {"current_run_rate", type number},
        {"required_run_rate", type number},
        {"target_runs", Int32.Type},
        {"last_api_poll_utc", type datetimezone},
        {"last_source_update_utc", type datetimezone},
        {"state_updated_at_utc", type datetimezone}
    })
in
    #"Set Column Types"


// ---------------------------------------------------------------------
// 3. QUERY: v_current_batting_scorecard
// Batter figures per innings, strike rate, and boundary percentages.
// ---------------------------------------------------------------------
let
    Source = PostgreSQL.Database("localhost:5432", "godrej_cricket_db"),
    public_Schema = Source{[Schema="public"]}[Data],
    v_current_batting_scorecard_View = public_Schema{[Name="v_current_batting_scorecard"]}[Data],
    #"Set Column Types" = Table.TransformColumnTypes(v_current_batting_scorecard_View, {
        {"batting_id", Int64.Type},
        {"match_id", Int64.Type},
        {"provider_match_id", type text},
        {"match_name", type text},
        {"is_simulated", type logical},
        {"innings_number", Int16.Type},
        {"innings_name", type text},
        {"batting_team", type text},
        {"provider_player_id", type text},
        {"player_name", type text},
        {"batting_position", Int16.Type},
        {"dismissal_info", type text},
        {"is_dismissed", type logical},
        {"runs", Int32.Type},
        {"balls_faced", Int32.Type},
        {"fours", Int32.Type},
        {"sixes", Int32.Type},
        {"strike_rate", type number},
        {"boundary_runs", Int32.Type},
        {"boundary_run_percentage", type number},
        {"updated_at_utc", type datetimezone}
    })
in
    #"Set Column Types"


// ---------------------------------------------------------------------
// 4. QUERY: v_current_bowling_scorecard
// Bowler figures per innings, overs bowled, maidens, economy, and averages.
// ---------------------------------------------------------------------
let
    Source = PostgreSQL.Database("localhost:5432", "godrej_cricket_db"),
    public_Schema = Source{[Schema="public"]}[Data],
    v_current_bowling_scorecard_View = public_Schema{[Name="v_current_bowling_scorecard"]}[Data],
    #"Set Column Types" = Table.TransformColumnTypes(v_current_bowling_scorecard_View, {
        {"bowling_id", Int64.Type},
        {"match_id", Int64.Type},
        {"provider_match_id", type text},
        {"match_name", type text},
        {"is_simulated", type logical},
        {"innings_number", Int16.Type},
        {"innings_name", type text},
        {"bowling_team", type text},
        {"provider_player_id", type text},
        {"player_name", type text},
        {"bowling_order", Int16.Type},
        {"overs_bowled", type number},
        {"maidens", Int16.Type},
        {"runs_conceded", Int32.Type},
        {"wickets", Int16.Type},
        {"economy_rate", type number},
        {"dots", Int32.Type},
        {"wides", Int16.Type},
        {"no_balls", Int16.Type},
        {"bowling_average", type number},
        {"bowling_strike_rate", type number},
        {"updated_at_utc", type datetimezone}
    })
in
    #"Set Column Types"


// ---------------------------------------------------------------------
// 5. QUERY: v_match_innings_summary
// Multi-innings totals, extras breakdown, and innings progression status.
// ---------------------------------------------------------------------
let
    Source = PostgreSQL.Database("localhost:5432", "godrej_cricket_db"),
    public_Schema = Source{[Schema="public"]}[Data],
    v_match_innings_summary_View = public_Schema{[Name="v_match_innings_summary"]}[Data],
    #"Set Column Types" = Table.TransformColumnTypes(v_match_innings_summary_View, {
        {"innings_id", Int64.Type},
        {"match_id", Int64.Type},
        {"match_name", type text},
        {"is_simulated", type logical},
        {"innings_number", Int16.Type},
        {"innings_name", type text},
        {"batting_team", type text},
        {"bowling_team", type text},
        {"total_runs", Int32.Type},
        {"total_wickets", Int16.Type},
        {"total_overs", type number},
        {"run_rate", type number},
        {"extras_total", Int32.Type},
        {"extras_byes", Int32.Type},
        {"extras_leg_byes", Int32.Type},
        {"extras_wides", Int32.Type},
        {"extras_no_balls", Int32.Type},
        {"is_completed", type logical},
        {"updated_at_utc", type datetimezone}
    })
in
    #"Set Column Types"


// ---------------------------------------------------------------------
// 6. QUERY: v_worm_comparison
// Over-by-over cumulative progress points for worm charts.
// ---------------------------------------------------------------------
let
    Source = PostgreSQL.Database("localhost:5432", "godrej_cricket_db"),
    public_Schema = Source{[Schema="public"]}[Data],
    v_worm_comparison_View = public_Schema{[Name="v_worm_comparison"]}[Data],
    #"Set Column Types" = Table.TransformColumnTypes(v_worm_comparison_View, {
        {"snapshot_id", Int64.Type},
        {"match_id", Int64.Type},
        {"match_name", type text},
        {"is_simulated", type logical},
        {"innings_number", Int16.Type},
        {"batting_team", type text},
        {"overs", type number},
        {"runs", Int32.Type},
        {"wickets", Int16.Type},
        {"run_rate", type number},
        {"snapshot_timestamp_utc", type datetimezone}
    })
in
    #"Set Column Types"


// ---------------------------------------------------------------------
// 7. QUERY: v_api_telemetry
// Daily operational health, request quotas, errors, and latency.
// ---------------------------------------------------------------------
let
    Source = PostgreSQL.Database("localhost:5432", "godrej_cricket_db"),
    public_Schema = Source{[Schema="public"]}[Data],
    v_api_telemetry_View = public_Schema{[Name="v_api_telemetry"]}[Data],
    #"Set Column Types" = Table.TransformColumnTypes(v_api_telemetry_View, {
        {"usage_date", type date},
        {"total_requests", Int64.Type},
        {"successful_requests", Int64.Type},
        {"rate_limited_requests", Int64.Type},
        {"server_errors", Int64.Type},
        {"avg_response_time_ms", type number},
        {"max_hits_recorded_today", Int16.Type},
        {"min_credits_remaining", Int16.Type}
    })
in
    #"Set Column Types"
