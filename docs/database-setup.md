# PostgreSQL 16 Database Setup & Administration Guide
## Godrej Cricket Intelligence

This guide walks through installing PostgreSQL 16 on Windows, configuring the local user and database, applying versioned schema migrations, and validating DirectQuery readiness for Microsoft Power BI Desktop.

---

## 1. Prerequisites & PostgreSQL 16 Installation

The Godrej Cricket Intelligence pipeline requires **PostgreSQL 16+** running locally.

### Windows Installation Steps
1. Download the official PostgreSQL 16 installer for Windows x86-64 from the EnterpriseDB repository:
   [https://www.enterprisedb.com/downloads/postgres-postgresql-downloads](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads)
2. Run the installer and select the following components:
   * **PostgreSQL Server**
   * **pgAdmin 4** (GUI management client)
   * **Command Line Tools** (`psql`, `pg_dump`)
3. Set a secure master password for the default `postgres` superuser (record this for your `.env` file).
4. Keep the default port as `5432`.
5. Select `[Default locale]` for regional formatting.
6. Verify the installation by running the following command in PowerShell:
   ```powershell
   psql -U postgres -p 5432 -c "SELECT version();"
   ```

---

## 2. Dedicated Database Creation

It is recommended to run the pipeline in a dedicated, isolated database rather than the default `postgres` catalog.

Open PowerShell or pgAdmin 4 query tool and execute:

```sql
-- Connect as postgres superuser
CREATE DATABASE godrej_cricket_db
    WITH 
    OWNER = postgres
    ENCODING = 'UTF8'
    LC_COLLATE = 'English_United States.1252'
    LC_CTYPE = 'English_United States.1252'
    TABLESPACE = pg_default
    CONNECTION LIMIT = -1;

COMMENT ON DATABASE godrej_cricket_db
    IS 'Operational data store for Godrej Cricket Intelligence real-time analytics';
```

---

## 3. Environment Variable Configuration

Create your local `.env` file in the project root by copying the template:

```powershell
Copy-Item .env.example .env
```

Populate the database credentials in `.env`:

```ini
# --- Local PostgreSQL Database Configuration ---
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=godrej_cricket_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_actual_password_here
```

> [!CAUTION]
> **Credential Hygiene Rule:**
> Never commit `.env` or hardcode passwords in scripts. `.gitignore` is pre-configured to exclude all `.env` files.

---

## 4. Applying Schema Migrations

The repository provides automated schema migrations that provision all 8 core operational tables, foreign keys with cascade constraints, indexes, and Power BI DirectQuery analytical views.

### Method A: Automated Migration Runner (Recommended)
Run the built-in CLI migration command:

```powershell
python src/main.py migrate
```

**Expected Output:**
```text
[2026-10-25 15:30:00] [INFO] [main] Executing database migrations...
[2026-10-25 15:30:00] [INFO] [db_repository] Applying migration: 001_initial_schema.sql
[2026-10-25 15:30:01] [INFO] [db_repository] Applying migration: 002_reporting_views.sql
[2026-10-25 15:30:01] [INFO] [db_repository] Successfully applied 2 migrations.
[2026-10-25 15:30:01] [INFO] [main] Successfully applied migrations: ['001_initial_schema.sql', '002_reporting_views.sql']
```

### Method B: Manual Migration via `psql`
Alternatively, you can apply migrations manually via command line:

```powershell
psql -U postgres -d godrej_cricket_db -f sql/001_initial_schema.sql
psql -U postgres -d godrej_cricket_db -f sql/002_reporting_views.sql
```

---

## 5. Connectivity Verification

Validate that the Python pipeline can connect to PostgreSQL using:

```powershell
python src/main.py test-connection
```

**Successful Output:**
```text
[2026-10-25 15:30:00] [INFO] [main] Testing PostgreSQL connection...
[2026-10-25 15:30:00] [INFO] [main] PostgreSQL database connection verified successfully!
```

---

## 6. Table & View Inventory

Applying migrations provisions the following structures in `public`:

### Core Relational Tables
1. [`matches`](file:///d:/Godrej_RealTime_Dashboard/sql/001_initial_schema.sql#L10-L33): Master record for international, IPL, and domestic fixtures.
2. [`match_state`](file:///d:/Godrej_RealTime_Dashboard/sql/001_initial_schema.sql#L37-L61): Latest active in-play score, CRR, RRR, target, and last update timestamp.
3. [`innings`](file:///d:/Godrej_RealTime_Dashboard/sql/001_initial_schema.sql#L65-L89): Innings breakdown with runs, wickets, overs, and extras.
4. [`batting_scorecard`](file:///d:/Godrej_RealTime_Dashboard/sql/001_initial_schema.sql#L93-L115): Individual batter figures with strict NULL vs. zero strike rates.
5. [`bowling_scorecard`](file:///d:/Godrej_RealTime_Dashboard/sql/001_initial_schema.sql#L119-L143): Individual bowler figures with economy rates and maiden counts.
6. [`score_snapshots`](file:///d:/Godrej_RealTime_Dashboard/sql/001_initial_schema.sql#L147-L167): Over-by-over historical points for worm and run-rate progression charts.
7. [`ball_events`](file:///d:/Godrej_RealTime_Dashboard/sql/001_initial_schema.sql#L171-L198): Granular delivery-level events for replay simulation and commentary.
8. [`api_usage`](file:///d:/Godrej_RealTime_Dashboard/sql/001_initial_schema.sql#L202-L219): Hard audit log of every outbound request, response code, and quota consumption.

### DirectQuery Analytical Views
1. [`v_live_match_summary`](file:///d:/Godrej_RealTime_Dashboard/sql/002_reporting_views.sql#L8-L41): Flattened active match summary for Page 1 KPI cards and APR Change Detection.
2. [`v_current_batting_scorecard`](file:///d:/Godrej_RealTime_Dashboard/sql/002_reporting_views.sql#L43-L73): Live batting card with calculated boundary percentages and dismissal texts.
3. [`v_current_bowling_scorecard`](file:///d:/Godrej_RealTime_Dashboard/sql/002_reporting_views.sql#L75-L111): Live bowling card with bowling strike rates, averages, and economy rates.
4. [`v_match_innings_summary`](file:///d:/Godrej_RealTime_Dashboard/sql/002_reporting_views.sql#L113-L135): Innings totals for head-to-head score comparisons.
5. [`v_worm_comparison`](file:///d:/Godrej_RealTime_Dashboard/sql/002_reporting_views.sql#L137-L153): Cumulative runs by over for dual-line worm charts.
6. [`v_api_telemetry`](file:///d:/Godrej_RealTime_Dashboard/sql/002_reporting_views.sql#L155-L169): System observability view aggregating daily request volumes and error rates.

---

## 7. Troubleshooting & Common Pitfalls

| Issue | Root Cause | Solution |
| :--- | :--- | :--- |
| `FATAL: password authentication failed for user "postgres"` | Incorrect password in `.env` | Update `POSTGRES_PASSWORD` in `.env` to match the password chosen during PostgreSQL installation. |
| `Is the server running on host "localhost" and accepting TCP/IP connections?` | PostgreSQL Windows service is stopped | Open Windows Services (`services.msc`), locate **postgresql-x64-16**, and click **Start**. |
| `database "godrej_cricket_db" does not exist` | Database not yet created | Run `CREATE DATABASE godrej_cricket_db;` in pgAdmin or psql before applying migrations. |
| Power BI Desktop DirectQuery prompts for credentials | Power BI requires explicit DB login on first connect | Enter User name `postgres` and your database password. Choose **Database** authentication tab (not Windows). |
