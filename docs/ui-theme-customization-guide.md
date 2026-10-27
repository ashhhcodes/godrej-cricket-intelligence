# Power BI Theme & UI Template Customization Guide
## Team Elite Crew — Godrej Cricket Intelligence

This guide explains how to apply the custom glassmorphism stadium backgrounds and UI theme uploaded for **Team Elite Crew**, mapping each pre-drawn glass container to live PostgreSQL DirectQuery metrics.

---

## 1. Assets Overview

The 5 widescreen (16:9) background templates have been organized into [`powerbi/assets/`](file:///d:/Godrej_RealTime_Dashboard/powerbi/assets):

| Template File | Target Page Name | Description & Navigation State |
| :--- | :--- | :--- |
| **`01_Home_Background.png`** | **Home** | Welcome portal with 4 navigation cards (**Home** button highlighted). |
| **`02_Live_Match_Background.png`** | **Live Match** | Real-time match center with KPI slots, scorecard tables, and worm chart (**Live Match** button highlighted). |
| **`03_Batting_Background.png`** | **Batting** | Batting performance breakdown with 6 KPI slots and boundary matrix (**Batting** button highlighted). |
| **`04_Bowling_Background.png`** | **Bowling** | Bowling efficiency breakdown with 6 KPI slots and economy matrix (**Bowling** button highlighted). |
| **`05_Innings_Background.png`** | **Innings** | Multi-innings head-to-head progression and extras breakdown (**Innings** button highlighted). |

---

## 2. Fast Setup: 3 Steps to Apply the UI

### Step 1: Import the Custom Theme (Makes Visuals Glass-Transparent)
1. In Power BI Desktop, go to the **View** tab in the top ribbon.
2. Click the **Themes** dropdown $\to$ **Browse for themes...**
3. Select [`powerbi/godrej_cricket_theme.json`](file:///d:/Godrej_RealTime_Dashboard/powerbi/godrej_cricket_theme.json).
   * *This sets visual backgrounds to transparent so the glowing glass cards show through seamlessly, and switches fonts to clean Segoe UI white/mint.*

---

### Step 2: Set the Canvas Background on Each Page
For each page in your report:
1. Create 5 pages at the bottom tabs and name them:
   * `Home`, `Live Match`, `Batting`, `Bowling`, `Innings`
2. Click on the empty canvas of the page.
3. Open the **Format page** pane on the right (paintbrush icon).
4. Expand **Canvas background**:
   * Click **Browse...** (or Image).
   * Pick the corresponding PNG from [`powerbi/assets/`](file:///d:/Godrej_RealTime_Dashboard/powerbi/assets).
   * Set **Image fit:** `Fit` (or `Fill`).
   * Set **Transparency:** **`0%`** *(Crucial: Power BI defaults to 100% transparent; move the slider to 0% so the image appears!)*.

---

### Step 3: Populate the Pre-Drawn Glass Containers

Because the glowing neon-green containers are already drawn on the background, **all you do is place transparent cards, tables, and charts directly inside the boxes!**

---

## 3. Visual Placement Mapping (Page-by-Page)

### Page 1: Home (Welcome Landing Portal)
* **Background:** `01_Home_Background.png`
* **Left Text:** Pre-rendered in the image ("CRICKET ANALYTICS DASHBOARD / TEAM ELITE CREW").
* **4 Big Navigation Tiles (Right Side):**
  * Insert 4 transparent **Buttons** or **Cards** over the 4 tiles:
    1. Over `LIVE MATCH CENTER` tile: Insert a Blank Button $\to$ Action: **Page navigation** $\to$ Destination: **Live Match**.
    2. Over `BATTING ANALYTICS` tile: Action: **Page navigation** $\to$ Destination: **Batting**.
    3. Over `BOWLING ANALYTICS` tile: Action: **Page navigation** $\to$ Destination: **Bowling**.
    4. Over `TOURNAMENT INSIGHTS` tile: Action: **Page navigation** $\to$ Destination: **Innings**.

---

### Page 2: Live Match (In-Play Match Center)
* **Background:** `02_Live_Match_Background.png`
* **Top Row:**
  * **Top Left Wide Box:** Card with `v_live_match_summary[match_name]` and `[Data Provenance Banner]`.
  * **Top Right Top Box 1:** Card with `[Live Score Headline]` (e.g. `Gujarat Titans 57/2 (5.0 ov)`).
  * **Top Right Top Box 2:** Card with `[Current Run Rate]` (e.g. `8.40`).
  * **Top Right Lower Box 1:** Card with `[Target Runs]`.
  * **Top Right Lower Box 2:** Card with `[Required Run Rate]`.
  * **Top Right Lower Box 3:** Card with `v_live_match_summary[current_status_summary]`.
* **Middle Row:**
  * **Middle Left Wide Box:** Table visual from `v_current_batting_scorecard`:
    * Fields: `player_name`, `runs`, `balls_faced`, `fours`, `sixes`, `strike_rate`, `dismissal_info`.
  * **Middle Right Wide Box:** Table visual from `v_current_bowling_scorecard`:
    * Fields: `player_name`, `overs_bowled`, `maidens`, `runs_conceded`, `wickets`, `economy_rate`, `dots`.
* **Bottom Row:**
  * **Bottom Left Wide Box:** Line Chart from `v_worm_comparison`:
    * X-axis: `overs` | Y-axis: `runs` | Legend: `batting_team`.
  * **Bottom Right Wide Box:** Multi-row card or bar chart from `v_match_innings_summary` (Extras & Innings totals).

---

### Page 3: Batting Analytics
* **Background:** `03_Batting_Background.png`
* **Top Row (6 Small KPI Slots):**
  * 1: Total Runs (`[Total Runs]`)
  * 2: Total 4s (`SUM(v_current_batting_scorecard[fours])`)
  * 3: Total 6s (`SUM(v_current_batting_scorecard[sixes])`)
  * 4: Boundary Run % (`[Boundary Run %]`)
  * 5: Top Strike Rate (`MAX(v_current_batting_scorecard[strike_rate])`)
  * 6: Total Dismissals (`COUNTROWS(FILTER(v_current_batting_scorecard, [is_dismissed] = TRUE))`)
* **Middle Row:**
  * **Left Big Box:** Scatter Chart or Table of `boundary_run_percentage` vs `strike_rate`.
  * **Right Big Box:** Donut Chart of `dismissal_info` (Modes of dismissal).
* **Bottom Row (3 Boxes):**
  * 1: Bar chart of Top Run Scorers (`player_name` by `runs`).
  * 2: Bar chart of Top 4s Hitters.
  * 3: Bar chart of Top 6s Hitters.

---

### Page 4: Bowling Spell Efficiency
* **Background:** `04_Bowling_Background.png`
* **Top Row (6 Small KPI Slots):**
  * 1: Total Wickets (`[Wickets Taken]`)
  * 2: Best Economy (`MIN(v_current_bowling_scorecard[economy_rate])`)
  * 3: Total Maidens (`SUM(v_current_bowling_scorecard[maidens])`)
  * 4: Total Dot Balls (`SUM(v_current_bowling_scorecard[dots])`)
  * 5: Best Average (`MIN(v_current_bowling_scorecard[bowling_average])`)
  * 6: Best Bowling SR (`MIN(v_current_bowling_scorecard[bowling_strike_rate])`)
* **Middle Row:**
  * **Left Big Box:** Scatter Chart of `economy_rate` vs `bowling_average`.
  * **Right Big Box:** Bar chart of Top Wicket Takers (`player_name` by `wickets`).
* **Bottom Row (3 Boxes):**
  * 1: Dot Ball Pressure Bar Chart (`player_name` by `dots`).
  * 2: Runs Conceded Bar Chart.
  * 3: Bowling Order comparison.
* **Bottom Long Banner Box:** Multi-row summary of extras conceded (wides and no-balls).

---

### Page 5: Innings Progression & Tournament
* **Background:** `05_Innings_Background.png`
* **Top Row (2 Wide Boxes):**
  * Box 1: Innings 1 Summary Card (Team A Runs, Wickets, Overs, CRR).
  * Box 2: Innings 2 Summary Card (Team B Runs, Wickets, Overs, CRR).
* **Middle Row:**
  * Comparative Worm Progress Line Chart.
* **Bottom Row:**
  * Stacked Bar Chart of Extras (Wides, No Balls, Byes, Leg Byes).
