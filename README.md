# Godrej Cricket Intelligence — Real-Time Analytics Dashboard
### Team Elite Crew | College Project for Godrej Data Analysis Training Program

An enterprise-grade, real-time cricket analytics platform that integrates a **Python 3.11** data pipeline, a **PostgreSQL 16** relational data warehouse with analytical DirectQuery reporting views, and a **Microsoft Power BI Desktop** live broadcast scoreboard dashboard with 30-second Automatic Page Refresh (APR).

---

## 🌟 Key Highlights & Engineering Features

1. **Decoupled 3-Tier Refresh Architecture:**
   * Solves the free-tier API quota limit (100 hits/day on CricketData.org / CricAPI) by decoupling external polling (120s–300s) from Power BI rendering (30s).
   * Power BI queries the local PostgreSQL warehouse via **DirectQuery**, consuming **zero external API calls**.
2. **Deterministic Offline Replay Engine:**
   * Built-in simulation engine replaying real ball-by-ball deliveries from historical Cricsheet IPL fixtures (ODC-By v1.0).
   * Fully restartable and idempotent — automatically finalizes matches and resets for continuous, non-stop presentations.
3. **Strict Cricket Domain Math:**
   * Accurately converts cricket overs notation (e.g., `19.5`) into integer legal balls ($19 \times 6 + 5 = 119\text{ balls}$) to compute true decimal overs ($19.833$) for Run Rate and Economy calculations, avoiding naive decimal addition traps ($2.4\text{ ov} + 3.5\text{ ov} = 39\text{ balls} = 6.3\text{ ov}$, never $5.9$).
4. **Strict NULL vs. Zero Semantics:**
   * Batters who did not face a ball receive a `NULL` strike rate (never `0.00`, which falsely represents a duck).
   * Bowlers who bowled 0 overs receive a `NULL` economy rate.
5. **Data Provenance Transparency:**
   * All simulated data is tagged with `is_simulated = TRUE` and displayed with a clear banner (`● DEMO / SIMULATED DATA (OFFLINE REPLAY)`).
6. **100% Automated Test Coverage:**
   * 44 automated unit, integration, and calculation-parity tests passing in `pytest`.

---

## 🚀 Teammate Quickstart Guide (5 Minutes Setup)

Follow these steps to run the project on your machine from where we left off.

### 1. Prerequisites
* **Windows 10 / 11** (64-bit)
* **Python 3.11+** installed and added to PATH
* **PostgreSQL 16+** installed on port `5432`
* **Microsoft Power BI Desktop** installed (Microsoft Store or standalone MSI)

---

### 2. Clone Repository & Setup Python
```bash
git clone https://github.com/ashhhcodes/godrej-cricket-intelligence.git
cd godrej-cricket-intelligence

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# Install required dependencies
pip install -r requirements.txt
```

---

### 3. Setup Local PostgreSQL Database
1. Open `psql` or pgAdmin and create the dedicated database:
   ```sql
   CREATE DATABASE godrej_cricket_db;
   ```
2. Copy the environment configuration template:
   ```bash
   cp .env.example .env
   ```
3. Open `.env` and set your local PostgreSQL password:
   ```env
   POSTGRES_HOST=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=godrej_cricket_db
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=your_actual_password_here
   ALLOW_LIVE_API=false
   INGESTION_MODE=fixture_replay
   ```
4. Verify database connection and apply migrations:
   ```bash
   python src/main.py test-connection
   python src/main.py migrate
   ```
   *This automatically applies `sql/001_initial_schema.sql` (8 tables) and `sql/002_reporting_views.sql` (6 DirectQuery views).*

---

### 4. Run Automated Tests
Verify that all 44 automated tests pass on your machine:
```bash
pytest -v
```

---

### 5. Launch the Power BI Dashboard
1. Open **[`Godrej_Cricket_Intelligence.pbix`](file:///d:/Godrej_RealTime_Dashboard/Godrej_Cricket_Intelligence.pbix)** in **Microsoft Power BI Desktop**.
2. If prompted for PostgreSQL credentials:
   * Select **Database** authentication tab.
   * User: `postgres`, Password: *(your local password)*.
   * If asked about encryption, select **Unencrypted Connection** (standard for `localhost`).
3. You will see **Page 1: Live Match Center** with the custom stadium floodlight background, live match KPIs, batting table, bowling figures, and over progression chart.

---

### 6. Start Live Replay Simulation
In PowerShell:
```bash
python src/main.py replay
```
Keep Power BI Desktop and PowerShell open side-by-side. Every 30 seconds, a new delivery is ingested, and the Power BI dashboard ticks forward live!

---

## 📁 Repository Structure

```text
├── .env.example                       # Safe environment configuration template
├── .gitignore                         # Excludes secrets, logs, and temp files
├── requirements.txt                   # Production Python dependencies
├── Godrej_Cricket_Intelligence.pbix   # Power BI Desktop report with Page 1 Live Scoreboard
├── docs/
│   ├── TEAM_HANDOVER.md               # Detailed handover briefing for teammates
│   ├── ui-theme-customization-guide.md# Guide for assembling Pages 2–5 with custom backgrounds
│   ├── phase-1-architecture.md        # Comprehensive architecture & API budget document
│   ├── implementation-roadmap.md      # Multi-phase project delivery roadmap
│   ├── database-setup.md              # PostgreSQL installation and configuration guide
│   ├── data-dictionary.md             # Schema specification, constraints, and attribution
│   ├── ingestion-runbook.md           # Operational guide for replay and live modes
│   ├── powerbi-directquery-guide.md   # DirectQuery configuration and APR troubleshooting
│   └── dax-measure-dictionary.md      # 22 tested cricket DAX measures
├── powerbi/
│   ├── godrej_cricket_theme.json      # Custom transparent theme with neon green (#00E676)
│   ├── report_layout_specification.md # Coordinate-level visual layout guide for Pages 1–5
│   ├── reporting_views.pq             # Power Query (M) code snippets for the 6 views
│   └── assets/                        # 5 Widescreen (16:9) stadium background PNG templates
│       ├── 01_Home_Background.png
│       ├── 02_Live_Match_Background.png
│       ├── 03_Batting_Background.png
│       ├── 04_Bowling_Background.png
│       └── 05_Innings_Background.png
├── sql/
│   ├── 001_initial_schema.sql         # 8 Operational tables, constraints, and indexes
│   └── 002_reporting_views.sql        # 6 DirectQuery analytical reporting views
├── src/
│   ├── config.py                      # Pydantic configuration loader with strict guards
│   ├── budget_manager.py              # 100-hit daily quota manager with safety buffer
│   ├── cricapi_client.py              # Resilient HTTP client with backoff & circuit-breaker
│   ├── normalizer.py                  # Normalization engine enforcing NULL semantics
│   ├── db.py                          # PostgreSQL repository with idempotent upserts
│   ├── replay_engine.py               # Deterministic Cricsheet ball-by-ball simulator
│   ├── scheduler.py                   # Ingestion orchestrator and loop manager
│   ├── logger.py                      # Sanitizing logger (masks API keys & passwords)
│   └── main.py                        # CLI entrypoint (migrate, replay, live, status)
└── tests/                             # 44 Automated tests across 6 suites
```

---

## 🎯 Next Steps for Your Teammate

1. **Explore the Existing Dashboard:** Open `Godrej_Cricket_Intelligence.pbix` and test live simulation with `python src/main.py replay`.
2. **(Optional) Add Bonus Pages:**
   * Use [`docs/ui-theme-customization-guide.md`](file:///d:/Godrej_RealTime_Dashboard/docs/ui-theme-customization-guide.md) to add:
     * **Page 2: Batting Analytics** (using `03_Batting_Background.png`)
     * **Page 3: Bowling Spell Efficiency** (using `04_Bowling_Background.png`)
     * **Page 4: Innings Progression** (using `05_Innings_Background.png`)
     * **Page 5: Home Portal** (using `01_Home_Background.png`)
3. **Prepare Presentation Slides:** Summarize the architecture from [`docs/phase-1-architecture.md`](file:///d:/Godrej_RealTime_Dashboard/docs/phase-1-architecture.md) for the college viva/demo.

---

## 📜 Attribution & Data Licensing
* **Cricsheet.org:** Ball-by-ball delivery event data provided under the **Open Data Commons Attribution License (ODC-By) v1.0**.
* **CricketData.org (CricAPI v1):** Live match scorecards and fixture discovery used within Lifetime Free Tier academic boundaries.
