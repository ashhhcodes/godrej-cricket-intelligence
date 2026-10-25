# Power BI Desktop Report Layout & Visual Assembly Specification
## Godrej Cricket Intelligence — Phase 4 Visual Assembly

This document specifies the exact visual configurations, containers, formatting properties, field bindings, and layout coordinates for authoring the 4-page report in Microsoft Power BI Desktop.

---

## 1. Global Report Settings & Canvas Setup

* **Page Dimensions:** 16:9 Standard Widescreen (1280px width $\times$ 720px height).
* **Typography:** `Segoe UI` (System standard) across all text elements.
* **DirectQuery Data Source:** `localhost:5432/godrej_cricket_db` (using M queries from [`powerbi/reporting_views.pq`](file:///d:/Godrej_RealTime_Dashboard/powerbi/reporting_views.pq)).
* **Semantic Relationships:** `v_live_match_summary` (1:*) to fact tables. **Assume Referential Integrity: Disabled (Unchecked)** for guaranteed query safety.

---

## 2. Page 1: Live Match Center (Dark Scoreboard `#11161B`)

### Canvas Formatting
* **Page Name:** `Live Match Center`
* **Page Background Color:** `#11161B` (Pitch Dark, Transparency: 0%).
* **Card / Container Background:** `#1A2129` (Dark Container, Border: 1px solid `#2D3748`, Corner Radius: 4px).
* **Automatic Page Refresh (APR):**
  * Type: `Change detection`
  * Measure: `[Latest Change Detection Timestamp]`
  * Check every: `15 Seconds` (or fixed APR `30 Seconds`).

### Visual Containers & Field Mappings

#### 1. Header Banner & Provenance Ribbon (Top Full Width)
* **Position:** $X=15$, $Y=15$, $W=1250$, $H=65$
* **Visual Type:** Card / Text Box with Measure Binding
* **Left Element:** Match Title (`v_live_match_summary[match_name]`, 14pt Bold `#F8FAFC`), Venue & Series (`10pt #94A3B8`).
* **Right Badge (Provenance):**
  * Measure: `[Data Provenance Banner]`
  * Typography: 11pt Bold, Font Color `#D97706` (Amber) on simulated data, `#1E5631` (Green) on live source.

#### 2. KPI Summary Strip (4 Cards across X=15 to X=1265, Y=90, H=85)
* **Card 1: Current Score & Overs ($W=300$):**
  * Primary Measure: `[Live Score Headline]` or `[Current Innings Runs]` & `[Current Innings Wickets]`
  * Sub-text: `[Current Innings Overs Display]` & ` ov`
  * Text Color: `#F8FAFC` (32pt Bold), Secondary: `#94A3B8` (12pt).
* **Card 2: Current Run Rate ($W=290$):**
  * Measure: `[Current Run Rate]`
  * Format: `0.00`
  * Text Color: `#1E5631` (Deep Field Green Accent, 28pt Semibold).
* **Card 3: Target & Required Run Rate ($W=290$):**
  * Measure: `[Required Run Rate]` (with `[Target Runs]` in sub-label)
  * Format: `0.00` (Blank during Innings 1)
  * Text Color: `#D97706` (Amber Accent, 28pt Semibold).
* **Card 4: Match Status / Toss ($W=330$):**
  * Field: `v_live_match_summary[current_status_summary]`
  * Typography: 13pt Semibold `#F8FAFC`.

#### 3. Live Batting Scorecard Table (Left Side)
* **Position:** $X=15$, $Y=190$, $W=720$, $H=280$
* **Visual Type:** Table
* **Filter Context:** Visual-level filter: `v_current_batting_scorecard[innings_number] = [Active Innings Number]`
* **Columns & Formatting:**
  1. `player_name` (Batter, Left-aligned, Bold `#F8FAFC`)
  2. `dismissal_info` (Dismissal, Left-aligned, 9pt `#94A3B8`)
  3. `runs` (R, Right-aligned, Bold `#F8FAFC`)
  4. `balls_faced` (B, Right-aligned, `#94A3B8`)
  5. `fours` (4s, Right-aligned, `#94A3B8`)
  6. `sixes` (6s, Right-aligned, `#94A3B8`)
  7. `strike_rate` (SR, Right-aligned, `#F8FAFC`, format `0.00`, displays blank if balls=0)
  8. `boundary_run_percentage` (Bnd %, Right-aligned, `#1E5631`, format `0.0%`)
* **Styling:** Alternating rows subtle dark `#1A2129` / `#161D24`, Gridlines `#2D3748`.

#### 4. Live Bowling Figures Table (Left Side Lower)
* **Position:** $X=15$, $Y=485$, $W=720$, $H=215$
* **Visual Type:** Table
* **Filter Context:** Visual-level filter: `v_current_bowling_scorecard[innings_number] = [Active Innings Number]`
* **Columns & Formatting:**
  1. `player_name` (Bowler, Left-aligned, Bold `#F8FAFC`)
  2. `overs_bowled` (O, Right-aligned, `#F8FAFC`, format `0.0`)
  3. `maidens` (M, Right-aligned, `#94A3B8`)
  4. `runs_conceded` (R, Right-aligned, `#F8FAFC`)
  5. `wickets` (W, Right-aligned, Bold `#C53030`)
  6. `economy_rate` (Econ, Right-aligned, `#1E5631`, format `0.00`)
  7. `dots` (Dots, Right-aligned, `#94A3B8`)

#### 5. Over-by-Over Worm Progress Chart (Right Side)
* **Position:** $X=750$, $Y=190$, $W=515$, $H=510$
* **Visual Type:** Line Chart
* **Source Table:** `v_worm_comparison`
* **X-Axis:** `overs` (Continuous or Categorical, `#94A3B8`, Title: "Overs Bowled")
* **Y-Axis:** `runs` (Integer, Title: "Cumulative Runs", Gridlines `#2D3748`)
* **Legend:** `batting_team`
* **Line Styling:**
  * Innings 1 Team: Solid `#1E5631` (Deep Field Green, 2.5px width)
  * Innings 2 Team: Solid `#D97706` (Amber / Gold, 2.5px width)
* **Data Points:** Markers enabled at over ends.

---

## 3. Page 2: Batting Analytics (Light Paper `#F8F9FA`)

### Canvas Formatting
* **Page Name:** `Batting Analytics`
* **Page Background Color:** `#F8F9FA` (Clean paper surface, Transparency: 0%).
* **Card Container:** `#FFFFFF` (Crisp White, Border: 1px solid `#E2E8F0`, Corner Radius: 4px).
* **Text Ink:** `#0F172A` (Primary Dark), `#64748B` (Secondary Muted).

### Visual Containers & Field Mappings
1. **Header Ribbon ($X=15$, $Y=15$, $W=1250$, $H=50$):**
   * Title: "Godrej Cricket Intelligence — Batting Performance & Boundary Profile" (16pt Bold `#0F172A`).
2. **Boundary Run % vs. Strike Rate Scatter Matrix ($X=15$, $Y=75$, $W=750$, $H=625$):**
   * **Visual Type:** Scatter Plot / Clustered Matrix
   * **Values / Details:** `v_current_batting_scorecard[player_name]`
   * **X-Axis:** `boundary_run_percentage` (0% to 100%)
   * **Y-Axis:** `strike_rate` (0 to 400+)
   * **Size / Marker:** `runs` (bubble size proportional to total runs)
   * **Color Accent:** `#1E5631` (Deep Field Green)
3. **Dismissal Breakdown Donut / Bar ($X=780$, $Y=75$, $W=485$, $H=300$):**
   * **Visual Type:** Donut Chart / Horizontal Bar
   * **Legend / Axis:** `v_current_batting_scorecard[dismissal_info]`
   * **Values:** `COUNTROWS(v_current_batting_scorecard)` (where `is_dismissed = TRUE`)
4. **Top Boundary Contributors ($X=780$, $Y=390$, $W=485$, $H=310$):**
   * **Visual Type:** Clustered Bar Chart
   * **Y-Axis:** `player_name` (sorted descending by runs)
   * **X-Axis:** `boundary_runs` (Stack: `fours * 4` vs `sixes * 6`)
   * **Colors:** Fours (`#1E5631`), Sixes (`#11161B`)

---

## 4. Page 3: Bowling Spell Efficiency (Light Paper `#F8F9FA`)

### Canvas Formatting
* **Page Name:** `Bowling Spell Efficiency`
* **Page Background Color:** `#F8F9FA`. Containers: `#FFFFFF` (1px `#E2E8F0`). Text: `#0F172A`.

### Visual Containers & Field Mappings
1. **Header Ribbon ($X=15$, $Y=15$, $W=1250$, $H=50$):**
   * Title: "Godrej Cricket Intelligence — Bowling Spell Efficiency & Economy Analytics"
2. **Economy Rate vs. Bowling Average Matrix ($X=15$, $Y=75$, $W=750$, $H=625$):**
   * **Visual Type:** Scatter Chart / Matrix
   * **Details:** `v_current_bowling_scorecard[player_name]`
   * **X-Axis:** `economy_rate` (Runs per over; lower indicates tighter spell)
   * **Y-Axis:** `bowling_average` (Runs per wicket; blank values excluded)
   * **Size:** `wickets`
3. **Dot Ball Pressure Bar Chart ($X=780$, $Y=75$, $W=485$, $H=300$):**
   * **Visual Type:** Clustered Bar Chart
   * **Y-Axis:** `player_name`
   * **X-Axis:** `dots` (Dot balls bowled)
   * **Color:** Deep Field Green (`#1E5631`)
4. **Wickets Tally & Conceded Runs ($X=780$, $Y=390$, $W=485$, $H=310$):**
   * **Visual Type:** Bar Chart
   * **Y-Axis:** `player_name`
   * **X-Axis:** `wickets` (with `runs_conceded` displayed in tooltip)

---

## 5. Page 4: Tournament / Innings Progression (Light Paper `#F8F9FA`)

### Canvas Formatting
* **Page Name:** `Innings Progression`
* **Page Background Color:** `#F8F9FA`. Containers: `#FFFFFF`. Text: `#0F172A`.

### Visual Containers & Field Mappings
1. **Head-to-Head Innings Comparison Cards ($X=15$, $Y=75$, $W=1250$, $H=120$):**
   * **Visual Type:** Multi-row Card / Table
   * **Source Table:** `v_match_innings_summary`
   * **Columns:** `innings_name`, `total_runs`, `total_wickets`, `total_overs`, `run_rate`, `extras_total`
2. **Cumulative Over-by-Over Worm Progression ($X=15$, $Y=210$, $W=800$, $H=490$):**
   * **Visual Type:** Line Chart
   * **X-Axis:** `overs` (from `v_worm_comparison`)
   * **Y-Axis:** `runs`
   * **Legend:** `batting_team`
3. **Extras Conceded Breakdown ($X=830$, $Y=210$, $W=435$, $H=490$):**
   * **Visual Type:** Stacked Column Chart
   * **X-Axis:** `innings_name`
   * **Y-Axis:** `extras_wides`, `extras_no_balls`, `extras_byes`, `extras_leg_byes`
   * **Colors:** Wides (`#D97706`), No-Balls (`#C53030`), Byes (`#64748B`), Leg-Byes (`#94A3B8`)
