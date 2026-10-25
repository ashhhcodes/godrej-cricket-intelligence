# Power BI DAX Measure Dictionary
## Godrej Cricket Intelligence — Real-Time Cricket Analytics

This document defines the formal DAX measures for Godrej Cricket Intelligence in Microsoft Power BI Desktop. Every measure is designed to fold cleanly into native SQL when querying PostgreSQL (`localhost:5432/godrej_cricket_db`) via **DirectQuery**.

---

## 1. Domain Standards & Safeguards

### 1.1 Cricket Overs Math vs Decimal Overs
> [!CRITICAL]
> **Never add or average decimal-looking cricket notation numbers!**
> In cricket notation, `19.5` means **19 completed overs and 5 legal deliveries** ($19 \times 6 + 5 = 119\text{ balls}$). It is **NOT** 19.5 decimal overs ($119 / 6.0 = 19.8333\dots$).
> Furthermore, adding `2.4` overs (16 balls) and `3.5` overs (23 balls) equals **39 balls = 6.3 overs**, whereas naive decimal addition yields $2.4 + 3.5 = 5.9$ (which is invalid cricket notation).
> 
> All DAX measures in this model:
> 1. Convert overs into **legal balls** ($(\text{Completed Overs} \times 6) + \text{Remaining Balls}$).
> 2. Perform all aggregations on total legal balls.
> 3. Convert balls to decimal overs ($\text{balls} / 6.0$) strictly for rate calculations.
> 4. Format balls into cricket notation string (`"Overs.Balls"`) strictly for visual display.

### 1.2 Strict NULL vs. Zero Semantics
* **Batting Strike Rate:** Must return `BLANK()` (SQL `NULL`) if a player faced 0 balls (did not bat). Must return `0.00` if a player faced $\ge 1$ ball but scored 0 runs (duck).
* **Bowling Economy Rate:** Must return `BLANK()` if a bowler has bowled 0 legal balls.
* **Bowling Average & Bowling Strike Rate:** Must return `BLANK()` if 0 wickets have been taken (division by zero undefined).
* **Boundary Run Percentage:** Returns `0.0%` if total runs is 0, avoiding divide-by-zero errors.

### 1.3 Active Innings vs. Whole-Match Grain
Visuals on Page 1 (Live Match Center) must reflect the active innings currently in progress (`v_live_match_summary[current_innings_number]`), while historical tournament pages aggregate across all innings. Measures are partitioned accordingly.

---

## 2. Measure Dictionary

### 2.1 Cricket Overs & Delivery Aggregations

#### Measure 1: `[Total Bowling Balls]`
* **Purpose:** Converts the `overs_bowled` column into exact integer legal balls for every bowler record.
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Total Bowling Balls = 
SUMX(
    v_current_bowling_scorecard,
    VAR OversCol = v_current_bowling_scorecard[overs_bowled]
    VAR CompletedOvers = INT(OversCol)
    VAR BallRemainder = ROUND((OversCol - CompletedOvers) * 10, 0)
    RETURN (CompletedOvers * 6) + BallRemainder
)
```
* **Expected Output:**
  * Bowler bowled `2.4` overs $\to 16$ balls.
  * Bowler bowled `4.0` overs $\to 24$ balls.
  * Spell A (`2.4`) + Spell B (`3.5`) $\to 16 + 23 = 39$ balls.

---

#### Measure 2: `[Overs Display]`
* **Purpose:** Formats the aggregated legal deliveries back into cricket notation (`"Overs.Balls"`).
* **Format:** Text.
* **DAX Formula:**
```dax
Overs Display = 
VAR TotalBalls = [Total Bowling Balls]
VAR CompletedOvers = INT(DIVIDE(TotalBalls, 6))
VAR RemainingBalls = MOD(TotalBalls, 6)
RETURN
    IF(
        ISBLANK(TotalBalls) || TotalBalls = 0,
        "0.0",
        FORMAT(CompletedOvers, "0") & "." & FORMAT(RemainingBalls, "0")
    )
```
* **Expected Output:**
  * $0\text{ balls} \to "0.0"$
  * $5\text{ balls} \to "0.5"$
  * $6\text{ balls} \to "1.0"$
  * $39\text{ balls} \to "6.3"$
  * $119\text{ balls} \to "19.5"$

---

#### Measure 3: `[Decimal Overs Bowled]`
* **Purpose:** Computes true decimal overs for rate calculations (Run Rate, Economy).
* **Format:** Decimal Number (`0.00`).
* **DAX Formula:**
```dax
Decimal Overs Bowled = 
DIVIDE([Total Bowling Balls], 6)
```
* **Expected Output:**
  * $119\text{ balls} \to 19.8333\dots$ overs.

---

### 2.2 Batting Measures

#### Measure 4: `[Total Runs]`
* **Purpose:** Sum of runs scored off the bat across the current filter context.
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Total Runs = 
SUM(v_current_batting_scorecard[runs])
```

---

#### Measure 5: `[Total Balls Faced]`
* **Purpose:** Sum of balls faced by batters.
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Total Balls Faced = 
SUM(v_current_batting_scorecard[balls_faced])
```

---

#### Measure 6: `[Batting Strike Rate]`
* **Purpose:** Batting strike rate ($\frac{\text{Runs}}{\text{Balls Faced}} \times 100$). Strictly distinguishes "Did Not Bat" (`BLANK()`) from "Duck" (`0.00`).
* **Format:** Decimal Number (`0.00`).
* **DAX Formula:**
```dax
Batting Strike Rate = 
VAR Balls = [Total Balls Faced]
VAR Runs = [Total Runs]
RETURN
    IF(
        ISBLANK(Balls) || Balls = 0,
        BLANK(),
        DIVIDE(Runs * 100.0, Balls)
    )
```
* **Expected Output:**
  * Balls = 0, Runs = 0 $\to$ `(Blank)` (Did not bat).
  * Balls = 4, Runs = 0 $\to$ `0.00` (Duck).
  * Balls = 19, Runs = 39 $\to$ `205.26`.

---

#### Measure 7: `[Boundary Runs]`
* **Purpose:** Total runs accumulated strictly through 4s and 6s.
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Boundary Runs = 
SUMX(
    v_current_batting_scorecard,
    (v_current_batting_scorecard[fours] * 4) + (v_current_batting_scorecard[sixes] * 6)
)
```

---

#### Measure 8: `[Boundary Run %]`
* **Purpose:** Percentage of a batter's or team's runs derived from boundaries.
* **Format:** Percentage (`0.0%`).
* **DAX Formula:**
```dax
Boundary Run % = 
VAR TotalRunsScored = [Total Runs]
VAR BoundaryRunTotal = [Boundary Runs]
RETURN
    IF(
        ISBLANK(TotalRunsScored) || TotalRunsScored = 0,
        0.0,
        DIVIDE(BoundaryRunTotal, TotalRunsScored)
    )
```
* **Expected Output:**
  * Runs = 0 $\to$ `0.0%`.
  * Runs = 50, Fours = 5, Sixes = 2 (Boundary Runs = 32) $\to$ `64.0%`.

---

### 2.3 Bowling Measures

#### Measure 9: `[Wickets Taken]`
* **Purpose:** Total dismissals credited to bowlers.
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Wickets Taken = 
SUM(v_current_bowling_scorecard[wickets])
```

---

#### Measure 10: `[Runs Conceded]`
* **Purpose:** Total runs conceded by bowlers (including wides and no-balls).
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Runs Conceded = 
SUM(v_current_bowling_scorecard[runs_conceded])
```

---

#### Measure 11: `[Bowling Economy Rate]`
* **Purpose:** Runs conceded per 6-ball over. Strictly returns `BLANK()` if overs bowled is 0.
* **Format:** Decimal Number (`0.00`).
* **DAX Formula:**
```dax
Bowling Economy Rate = 
VAR DecOvers = [Decimal Overs Bowled]
VAR Conceded = [Runs Conceded]
RETURN
    IF(
        ISBLANK(DecOvers) || DecOvers = 0,
        BLANK(),
        DIVIDE(Conceded, DecOvers)
    )
```
* **Expected Output:**
  * DecOvers = 0.0 $\to$ `(Blank)`.
  * DecOvers = 4.0, Conceded = 24 $\to$ `6.00`.
  * Balls = 16 (2.4 ov = 2.6667 dec ov), Conceded = 22 $\to$ `8.25`.

---

#### Measure 12: `[Bowling Average]`
* **Purpose:** Runs conceded per wicket taken. Returns `BLANK()` if 0 wickets.
* **Format:** Decimal Number (`0.00`).
* **DAX Formula:**
```dax
Bowling Average = 
VAR Wkts = [Wickets Taken]
VAR Conceded = [Runs Conceded]
RETURN
    IF(
        ISBLANK(Wkts) || Wkts = 0,
        BLANK(),
        DIVIDE(Conceded, Wkts)
    )
```

---

#### Measure 13: `[Bowling Strike Rate]`
* **Purpose:** Legal balls bowled per wicket taken. Returns `BLANK()` if 0 wickets.
* **Format:** Decimal Number (`0.00`).
* **DAX Formula:**
```dax
Bowling Strike Rate = 
VAR Wkts = [Wickets Taken]
VAR Balls = [Total Bowling Balls]
RETURN
    IF(
        ISBLANK(Wkts) || Wkts = 0,
        BLANK(),
        DIVIDE(Balls, Wkts)
    )
```

---

### 2.4 Active Innings Filtering & In-Play KPIs

#### Measure 14: `[Active Innings Number]`
* **Purpose:** Dynamically extracts the active innings number from the live match state.
* **Format:** Whole Number (`0`).
* **DAX Formula:**
```dax
Active Innings Number = 
SELECTEDVALUE(v_live_match_summary[current_innings_number], 1)
```

---

#### Measure 15: `[Current Innings Runs]`
* **Purpose:** Runs scored in the active in-play innings only (isolated from prior completed innings).
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Current Innings Runs = 
VAR ActiveInnings = [Active Innings Number]
RETURN
    CALCULATE(
        [Total Runs],
        v_current_batting_scorecard[innings_number] = ActiveInnings
    )
```

---

#### Measure 16: `[Current Innings Wickets]`
* **Purpose:** Wickets fallen in the active in-play innings only.
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Current Innings Wickets = 
VAR ActiveInnings = [Active Innings Number]
RETURN
    CALCULATE(
        [Wickets Taken],
        v_current_bowling_scorecard[innings_number] = ActiveInnings
    )
```

---

#### Measure 17: `[Current Run Rate]`
* **Purpose:** Current run rate (CRR) reported directly from in-play telemetry.
* **Format:** Decimal Number (`0.00`).
* **DAX Formula:**
```dax
Current Run Rate = 
SELECTEDVALUE(v_live_match_summary[current_run_rate])
```

---

#### Measure 18: `[Required Run Rate]`
* **Purpose:** Required run rate (RRR) for the chasing side in Innings 2. Returns `BLANK()` during Innings 1.
* **Format:** Decimal Number (`0.00`).
* **DAX Formula:**
```dax
Required Run Rate = 
SELECTEDVALUE(v_live_match_summary[required_run_rate])
```

---

#### Measure 19: `[Target Runs]`
* **Purpose:** Target score set by the team batting first. Returns `BLANK()` during Innings 1.
* **Format:** Whole Number (`#,##0`).
* **DAX Formula:**
```dax
Target Runs = 
SELECTEDVALUE(v_live_match_summary[target_runs])
```

---

#### Measure 20: `[Live Score Headline]`
* **Purpose:** Primary scoreboard banner string (e.g., `"Gujarat Titans 57/2 (5.0 ov)"`).
* **Format:** Text.
* **DAX Formula:**
```dax
Live Score Headline = 
VAR BatTeam = SELECTEDVALUE(v_live_match_summary[batting_team], "Fixture Pending")
VAR Runs = SELECTEDVALUE(v_live_match_summary[current_runs], 0)
VAR Wkts = SELECTEDVALUE(v_live_match_summary[current_wickets], 0)
VAR OversVal = SELECTEDVALUE(v_live_match_summary[current_overs], 0.0)
RETURN
    BatTeam & " " & Runs & "/" & Wkts & " (" & FORMAT(OversVal, "0.0") & " ov)"
```

---

#### Measure 21: `[Data Provenance Banner]` (Multi-State Robustness)
* **Purpose:** Displays official data source badge, completely avoiding unsafe binary defaults by handling simulated, live active, completed, mixed, and unknown states.
* **Format:** Text.
* **DAX Formula:**
```dax
Data Provenance Banner = 
IF(
    NOT HASONEVALUE(v_live_match_summary[match_id]),
    -- Multiple matches in filter context
    VAR TotalMatches = DISTINCTCOUNT(v_live_match_summary[match_id])
    VAR SimMatches = CALCULATE(DISTINCTCOUNT(v_live_match_summary[match_id]), v_live_match_summary[is_simulated] = TRUE)
    RETURN
        IF(
            ISBLANK(TotalMatches) || TotalMatches = 0,
            "● NO FIXTURE SELECTED",
            IF(
                SimMatches = TotalMatches,
                "● DEMO / SIMULATED DATA (OFFLINE REPLAY)",
                IF(
                    SimMatches = 0,
                    "● OFFICIAL LIVE SOURCE (MULTIPLE MATCHES)",
                    "▲ MIXED DATA PROVENANCE (SELECT SINGLE FIXTURE)"
                )
            )
        ),
    -- Single match selected
    VAR IsSim = SELECTEDVALUE(v_live_match_summary[is_simulated])
    VAR IsLive = SELECTEDVALUE(v_live_match_summary[is_live])
    VAR IsComp = SELECTEDVALUE(v_live_match_summary[is_completed])
    VAR IsAband = SELECTEDVALUE(v_live_match_summary[is_abandoned])
    RETURN
        IF(
            ISBLANK(IsSim),
            "● PROVENANCE UNKNOWN",
            IF(
                IsSim = TRUE,
                "● DEMO / SIMULATED DATA (OFFLINE REPLAY)",
                IF(
                    IsLive = TRUE,
                    "● OFFICIAL LIVE SOURCE (CRICKETDATA.ORG - IN PLAY)",
                    IF(
                        IsComp = TRUE,
                        "● OFFICIAL LIVE SOURCE (CRICKETDATA.ORG - COMPLETED)",
                        IF(
                            IsAband = TRUE,
                            "● OFFICIAL LIVE SOURCE (MATCH ABANDONED)",
                            "● OFFICIAL LIVE SOURCE (SCHEDULED)"
                        )
                    )
                )
            )
        )
)
```

---

#### Measure 22: `[Latest Change Detection Timestamp]`
* **Purpose:** Polling measure for Power BI Automatic Page Refresh (Change Detection).
* **Format:** Date/Time.
* **DAX Formula:**
```dax
Latest Change Detection Timestamp = 
MAX(v_live_match_summary[state_updated_at_utc])
```

---

## 3. DirectQuery Folding & Measure Constraints

1. **Sum-Before-Divide Rule:** All ratio measures (`Batting Strike Rate`, `Bowling Economy Rate`, `Boundary Run %`) follow the `DIVIDE(SUM(x), SUM(y))` pattern. This guarantees that Power BI pushes single SQL `SELECT SUM(x), SUM(y) FROM table GROUP BY ...` expressions down to PostgreSQL without pulling row-by-row streams into client memory.
2. **No Time-Intelligence in DirectQuery:** Built-in DAX time-intelligence functions (`DATESYTD`, `SAMEPERIODLASTYEAR`) are not supported across non-date surrogate keys in DirectQuery. All temporal grouping uses the native `match_date_utc` or pre-grouped calendar dimensions in `v_api_telemetry`.
3. **Change Detection Polling Interval:** Set the Change Detection polling rate between **10 to 15 seconds** in Power BI Desktop. Setting intervals lower than 5 seconds creates unnecessary connection saturation on local PostgreSQL.
