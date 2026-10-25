# Data Dictionary & Schema Specification
## Godrej Cricket Intelligence

This document defines the data schema, relational constraints, column descriptions, NULL-handling rules, and data provenance standards for Godrej Cricket Intelligence.

---

## 1. Provenance & Integrity Standards

### Explicit Provenance Rule
To maintain complete integrity during academic presentations:
* Every record originating from offline simulation is tagged with `is_simulated = TRUE`.
* Live records ingested from external APIs are tagged with `is_simulated = FALSE`.
* DirectQuery views expose `data_provenance_badge` (`'OFFICIAL LIVE SOURCE'` vs. `'DEMO / SIMULATED DATA'`), allowing Power BI to render a prominent banner in the dashboard header.

### Strict NULL vs. Zero Semantics
* **Batting Strike Rate (`strike_rate`):**
  * `balls_faced = 0`: Mathematically undefined $\to$ **`NULL`**. Never default to `0.00` (which would falsely imply the batter faced balls without scoring).
  * `balls_faced > 0` and `runs = 0`: Genuine duck $\to$ **`0.00`**.
* **Bowling Economy Rate (`economy_rate`):**
  * `overs_bowled = 0.0`: Undefined $\to$ **`NULL`**.
  * `overs_bowled > 0.0`: Computed as $\frac{\text{runs}}{\text{balls}} \times 6.0$.
* **Dot Balls (`dots`):**
  * Stored as **`NULL`** if the provider API does not track dot balls for a given match, distinguishing it from an over where zero dots were bowled.

---

## 2. Relational Table Specifications

### 2.1 `matches` Table
Master record for discovered international, IPL, and domestic cricket fixtures.

| Column | Data Type | Nullable | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `BIGSERIAL` | No | Auto | Surrogate primary key. |
| `provider_match_id` | `VARCHAR(100)` | No | — | Stable external identifier from provider or Cricsheet (`UNIQUE`). |
| `series_name` | `VARCHAR(255)` | Yes | `NULL` | Tournament or series title (e.g., "Indian Premier League 2026"). |
| `match_name` | `VARCHAR(255)` | No | — | Human-readable fixture title (e.g., "India vs Australia, 1st T20I"). |
| `match_type` | `VARCHAR(50)` | No | — | Format code: `'t20'`, `'odi'`, `'test'`. |
| `competition_category` | `VARCHAR(50)` | No | `'Other'` | Competition group: `'IPL'`, `'International'`, `'Domestic'`, `'Other'`. |
| `venue` | `VARCHAR(255)` | Yes | `NULL` | Stadium and city location. |
| `match_date_utc` | `TIMESTAMPTZ` | No | — | Scheduled match date and start time in UTC. |
| `team_a` | `VARCHAR(100)` | No | — | Name of first team. |
| `team_b` | `VARCHAR(100)` | No | — | Name of second team. |
| `toss_winner` | `VARCHAR(100)` | Yes | `NULL` | Team that won the toss. |
| `toss_choice` | `VARCHAR(20)` | Yes | `NULL` | Decision on toss: `'bat'` or `'bowl'`. |
| `match_winner` | `VARCHAR(100)` | Yes | `NULL` | Team that won the match (populated upon conclusion). |
| `result_status` | `VARCHAR(255)` | Yes | `NULL` | Textual status (e.g., "CSK won by 5 wickets", "Match in progress"). |
| `is_live` | `BOOLEAN` | No | `FALSE` | Flag indicating match is currently in progress. |
| `is_completed` | `BOOLEAN` | No | `FALSE` | Flag indicating match has concluded with a result. |
| `is_abandoned` | `BOOLEAN` | No | `FALSE` | Flag indicating match was abandoned or washed out without a result. |
| `is_simulated` | `BOOLEAN` | No | `FALSE` | Provenance flag: `TRUE` for replay simulation, `FALSE` for live API. |
| `created_at_utc` | `TIMESTAMPTZ` | No | `NOW()` | Record creation timestamp. |
| `updated_at_utc` | `TIMESTAMPTZ` | No | `NOW()` | Last record update timestamp. |

---

### 2.2 `match_state` Table
Single-row in-play snapshot per match, optimized for DirectQuery Change Detection.

| Column | Data Type | Nullable | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `BIGSERIAL` | No | Auto | Surrogate primary key. |
| `match_id` | `BIGINT` | No | — | Foreign key referencing `matches(id)` (`UNIQUE`). |
| `current_status_summary`| `VARCHAR(255)` | No | — | Summary line (e.g., "India 182/4 (18.3 ov)"). |
| `current_innings_number`| `SMALLINT` | Yes | `NULL` | Active innings number (1, 2, 3, or 4). |
| `batting_team` | `VARCHAR(100)` | Yes | `NULL` | Team currently batting. |
| `bowling_team` | `VARCHAR(100)` | Yes | `NULL` | Team currently bowling. |
| `current_runs` | `INT` | Yes | `NULL` | Cumulative runs in active innings. |
| `current_wickets` | `SMALLINT` | Yes | `NULL` | Cumulative wickets lost in active innings. |
| `current_overs` | `NUMERIC(4,1)` | Yes | `NULL` | Current overs completed (e.g., 18.3). |
| `current_run_rate` | `NUMERIC(5,2)` | Yes | `NULL` | Current run rate (CRR) for active innings. |
| `required_run_rate` | `NUMERIC(5,2)` | Yes | `NULL` | Required run rate (RRR) for chasing team. |
| `target_runs` | `INT` | Yes | `NULL` | Target score in second innings. |
| `last_api_poll_utc` | `TIMESTAMPTZ` | No | — | Timestamp of last API poll or simulation tick. |
| `last_source_update_utc`| `TIMESTAMPTZ` | Yes | `NULL` | Provider's internal update timestamp. |
| `is_live` | `BOOLEAN` | No | `FALSE` | In-play indicator. |
| `created_at_utc` | `TIMESTAMPTZ` | No | `NOW()` | Record creation timestamp. |
| `updated_at_utc` | `TIMESTAMPTZ` | No | `NOW()` | **DirectQuery Change Detection measure polling target.** |

---

### 2.3 `innings` Table
Summary statistics for each completed or ongoing innings.

| Column | Data Type | Nullable | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `BIGSERIAL` | No | Auto | Surrogate primary key. |
| `match_id` | `BIGINT` | No | — | Foreign key referencing `matches(id)`. |
| `innings_number` | `SMALLINT` | No | — | Innings sequence (1, 2, 3, 4). |
| `innings_name` | `VARCHAR(150)` | No | — | Innings label (e.g., "Australia Innings 1"). |
| `batting_team` | `VARCHAR(100)` | No | — | Team batting in this innings. |
| `bowling_team` | `VARCHAR(100)` | No | — | Team bowling in this innings. |
| `total_runs` | `INT` | No | `0` | Total runs scored. |
| `total_wickets` | `SMALLINT` | No | `0` | Total wickets lost. |
| `total_overs` | `NUMERIC(4,1)` | No | `0.0` | Total overs bowled. |
| `run_rate` | `NUMERIC(5,2)` | Yes | `NULL` | Final innings run rate. |
| `extras_total` | `INT` | No | `0` | Total extra runs conceded. |
| `extras_byes` | `INT` | No | `0` | Extras from byes. |
| `extras_leg_byes` | `INT` | No | `0` | Extras from leg byes. |
| `extras_wides` | `INT` | No | `0` | Extras from wides. |
| `extras_no_balls` | `INT` | No | `0` | Extras from no-balls. |
| `is_declared` | `BOOLEAN` | No | `FALSE` | Innings declared flag (Tests). |
| `is_completed` | `BOOLEAN` | No | `FALSE` | Innings concluded flag. |

---

### 2.4 `batting_scorecard` Table
Detailed individual batter performances per innings.

| Column | Data Type | Nullable | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `BIGSERIAL` | No | Auto | Surrogate primary key. |
| `innings_id` | `BIGINT` | No | — | Foreign key referencing `innings(id)`. |
| `match_id` | `BIGINT` | No | — | Foreign key referencing `matches(id)`. |
| `provider_player_id` | `VARCHAR(100)` | No | — | Provider or Cricsheet player identifier. |
| `player_name` | `VARCHAR(150)` | No | — | Batter's display name. |
| `batting_position` | `SMALLINT` | Yes | `NULL` | Batting order position (1..11). |
| `dismissal_info` | `VARCHAR(255)` | Yes | `NULL` | Dismissal description (e.g., "c Dhoni b Pathirana", "not out"). |
| `is_dismissed` | `BOOLEAN` | No | `FALSE` | `TRUE` if batter has lost their wicket. |
| `runs` | `INT` | No | `0` | Runs scored by batter. |
| `balls_faced` | `INT` | No | `0` | Legal and no-ball deliveries faced. |
| `fours` | `INT` | No | `0` | Boundary fours hit. |
| `sixes` | `INT` | No | `0` | Boundary sixes hit. |
| `strike_rate` | `NUMERIC(6,2)` | Yes | `NULL` | Strike rate: **`NULL` if balls=0, `0.00` if balls>0 & runs=0.** |

---

### 2.5 `bowling_scorecard` Table
Detailed individual bowler figures per innings.

| Column | Data Type | Nullable | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `BIGSERIAL` | No | Auto | Surrogate primary key. |
| `innings_id` | `BIGINT` | No | — | Foreign key referencing `innings(id)`. |
| `match_id` | `BIGINT` | No | — | Foreign key referencing `matches(id)`. |
| `provider_player_id` | `VARCHAR(100)` | No | — | Provider or Cricsheet player identifier. |
| `player_name` | `VARCHAR(150)` | No | — | Bowler's display name. |
| `bowling_order` | `SMALLINT` | Yes | `NULL` | Order in which bowler was introduced. |
| `overs_bowled` | `NUMERIC(4,1)` | No | `0.0` | Overs bowled (e.g., 3.4). |
| `maidens` | `SMALLINT` | No | `0` | Maiden overs bowled. |
| `runs_conceded` | `INT` | No | `0` | Runs conceded off bowler's spell. |
| `wickets` | `SMALLINT` | No | `0` | Wickets credited to bowler. |
| `economy_rate` | `NUMERIC(5,2)` | Yes | `NULL` | Economy rate: **`NULL` if overs=0.0.** |
| `dots` | `INT` | Yes | `NULL` | Dot balls bowled (`NULL` if unavailable). |
| `wides` | `SMALLINT` | No | `0` | Wide balls conceded. |
| `no_balls` | `SMALLINT` | No | `0` | No-balls conceded. |

---

### 2.6 `score_snapshots` Table
Progress checkpoints at over boundaries for worm and run-rate progression charts.

| Column | Data Type | Nullable | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `BIGSERIAL` | No | Auto | Surrogate primary key. |
| `match_id` | `BIGINT` | No | — | Foreign key referencing `matches(id)`. |
| `innings_id` | `BIGINT` | No | — | Foreign key referencing `innings(id)`. |
| `snapshot_timestamp_utc`| `TIMESTAMPTZ` | No | — | Timestamp of snapshot. |
| `overs` | `NUMERIC(4,1)` | No | — | Over boundary (e.g., 1.0, 2.0). |
| `runs` | `INT` | No | — | Cumulative score at this over. |
| `wickets` | `SMALLINT` | No | — | Cumulative wickets down at this over. |
| `run_rate` | `NUMERIC(5,2)` | Yes | `NULL` | Cumulative run rate at this over. |
| `striker_name` | `VARCHAR(150)` | Yes | `NULL` | Batter on strike at over end. |
| `non_striker_name` | `VARCHAR(150)` | Yes | `NULL` | Non-striking batter. |
| `active_bowler_name` | `VARCHAR(150)` | Yes | `NULL` | Bowler who delivered the over. |

---

### 2.7 `ball_events` Table
Granular ball-by-ball delivery event feed.

| Column | Data Type | Nullable | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `BIGSERIAL` | No | Auto | Surrogate primary key. |
| `match_id` | `BIGINT` | No | — | Foreign key referencing `matches(id)`. |
| `innings_id` | `BIGINT` | No | — | Foreign key referencing `innings(id)`. |
| `over_number` | `SMALLINT` | No | — | 0-indexed over number (0 = 1st over). |
| `ball_number` | `SMALLINT` | No | — | 1-indexed ball in the over (1..6+). |
| `ball_sequence` | `INT` | No | — | Absolute sequential ball index in the innings. |
| `batter_name` | `VARCHAR(150)` | No | — | Striking batter name. |
| `bowler_name` | `VARCHAR(150)` | No | — | Delivering bowler name. |
| `non_striker_name` | `VARCHAR(150)` | Yes | `NULL` | Non-striking batter name. |
| `runs_batter` | `SMALLINT` | No | `0` | Runs scored off the bat. |
| `runs_extra` | `SMALLINT` | No | `0` | Extra runs on delivery. |
| `extra_type` | `VARCHAR(20)` | Yes | `NULL` | `'wide'`, `'no ball'`, `'bye'`, `'leg bye'`, `'penalty'`. |
| `total_ball_runs` | `SMALLINT` | No | `0` | Total runs on the delivery (`batter + extras`). |
| `is_wicket` | `BOOLEAN` | No | `FALSE` | Wicket fallen indicator. |
| `wicket_type` | `VARCHAR(50)` | Yes | `NULL` | Mode of dismissal (`'caught'`, `'bowled'`, `'lbw'`, `'stumped'`). |
| `player_dismissed` | `VARCHAR(150)` | Yes | `NULL` | Batter who was dismissed. |
| `commentary_text` | `TEXT` | Yes | `NULL` | Delivery commentary string. |
| `is_simulated` | `BOOLEAN` | No | `FALSE` | Replay provenance flag. |

---

### 2.8 `api_usage` Table
Operational request-budget tracking and telemetry log.

| Column | Data Type | Nullable | Default | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `BIGSERIAL` | No | Auto | Surrogate primary key. |
| `timestamp_utc` | `TIMESTAMPTZ` | No | `NOW()` | Timestamp request was dispatched. |
| `endpoint` | `VARCHAR(100)` | No | — | API endpoint queried (e.g., `'match_scorecard'`). |
| `http_status` | `SMALLINT` | No | — | HTTP status code (`200`, `429`, `500`). |
| `credits_consumed` | `SMALLINT` | No | `1` | Credits deducted (default 1). |
| `hits_today` | `SMALLINT` | Yes | `NULL` | Provider reported total hits today. |
| `hits_limit` | `SMALLINT` | Yes | `NULL` | Provider reported daily ceiling (100). |
| `credits_remaining` | `SMALLINT` | Yes | `NULL` | Provider reported credits remaining. |
| `response_time_ms` | `INT` | Yes | `NULL` | Network latency in milliseconds. |
| `match_id_queried` | `VARCHAR(100)` | Yes | `NULL` | Match identifier queried. |
| `status_message` | `VARCHAR(255)` | Yes | `NULL` | HTTP status text or error description. |

---

## 3. DirectQuery Analytical Reporting Views

### 3.1 `v_live_match_summary`
Serves the top-line KPI cards, status ribbons, and DirectQuery Change Detection measure.

### 3.2 `v_current_batting_scorecard`
Serves Page 1 live batting and Page 2 tournament batting leaderboards:
* Derives `boundary_runs` ($4 \times \text{fours} + 6 \times \text{sixes}$).
* Derives `boundary_run_percentage` ($\frac{\text{boundary runs}}{\text{total runs}} \times 100$).
* Preserves `strike_rate` as `NULL` if balls faced equals 0.

### 3.3 `v_current_bowling_scorecard`
Serves Page 1 live bowling and Page 3 bowling analytics:
* Derives `bowling_average` ($\frac{\text{runs conceded}}{\text{wickets}}$).
* Derives `bowling_strike_rate` ($\frac{\text{balls bowled}}{\text{wickets}}$).
* Preserves `economy_rate` as `NULL` if overs bowled equals 0.0.

### 3.4 `v_match_innings_summary`
Provides multi-innings head-to-head totals for match result cards.

### 3.5 `v_worm_comparison`
Provides over-by-over cumulative runs for comparative worm charts.

### 3.6 `v_api_telemetry`
Aggregates daily request totals, error rates, and average latency for system monitoring.

---

## 4. Dataset Licensing & Attribution

1. **Cricsheet Historical Cricket Data:**
   * **Source:** [https://cricsheet.org](https://cricsheet.org)
   * **Licence:** Open Data Commons Attribution License (ODC-By) v1.0.
   * **Attribution Requirement:** *"Cricket match event data provided by Cricsheet.org under the ODC-By v1.0 licence."*
2. **CricketData.org (CricAPI v1):**
   * **Source:** [https://cricketdata.org](https://cricketdata.org)
   * **Licence:** Lifetime Free Plan for non-commercial educational use.
   * **Attribution Requirement:** *"Cricket scores and fixture metadata powered by CricketData.org."*
