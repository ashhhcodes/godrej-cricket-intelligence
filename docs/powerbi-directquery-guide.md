# Power BI Desktop DirectQuery Setup & Operations Guide
## Godrej Cricket Intelligence — Real-Time Cricket Analytics

This guide provides technical instructions for configuring Microsoft Power BI Desktop to connect to the local PostgreSQL database (`godrej_cricket_db`) via **DirectQuery**, setting up the Star Schema semantic model, configuring Automatic Page Refresh (APR), and troubleshooting connectivity.

---

## 1. Prerequisites & Environment Architecture

### 1.1 Local System Requirements
* **Operating System:** Windows 10 / 11 (64-bit).
* **Power BI Desktop:** Microsoft Power BI Desktop (May 2024 or later, x64).
  * *Detected Installation:* Microsoft Store package (`Microsoft.MicrosoftPowerBIDesktop_2.159.883.0_x64`).
* **Database Engine:** PostgreSQL 16+ running locally on port `5432`.
  * *Active Target:* `localhost:5432/godrej_cricket_db`.
* **Database User:** Dedicated project user (`postgres` or configured project user).

### 1.2 Connector & Driver Prerequisites
Power BI Desktop communicates with PostgreSQL via its built-in native connector (`PostgreSQL.Database`).
* In modern Microsoft Store installations of Power BI Desktop, the required 64-bit .NET Data Provider (`Npgsql`) is packaged within the Power BI Mashup runtime.
* **If Power BI prompts:** *"An error happened while reading data from the provider: 'The remote certificate is invalid according to the validation procedure'"* or prompts for Npgsql installation:
  1. Download the official **Npgsql 4.0.10 (x64) MSI** installer from [Npgsql Releases on GitHub](https://github.com/npgsql/npgsql/releases/tag/v4.0.10).
  2. During installation, ensure the feature **"Npgsql GAC Installation"** is selected (`Will be installed on local hard drive`).
  3. Restart Power BI Desktop.

---

## 2. Power BI DirectQuery Connection Procedure

> [!IMPORTANT]
> Always select **DirectQuery** mode. Never choose **Import** mode. DirectQuery offloads aggregations and metric calculations to PostgreSQL and ensures live scorecard updates without manual dataset repopulation.

### Step 1: Open Power BI Desktop & Launch Connector
1. Open Power BI Desktop.
2. In the Home ribbon, click **Get Data** $\to$ **More...**
3. Select **Database** $\to$ **PostgreSQL database** $\to$ Click **Connect**.

### Step 2: Configure Server & Connection Mode
1. In the PostgreSQL database dialog:
   * **Server:** `localhost:5432`
   * **Database:** `godrej_cricket_db`
   * **Data Connectivity mode:** Select **DirectQuery** (Radio button).
   * Expand **Advanced options** (optional): Leave SQL statement blank. We will load the versioned analytical reporting views directly.
2. Click **OK**.

### Step 3: Enter Credentials
1. In the authentication prompt, select the **Database** tab on the left.
2. Enter your credentials (as defined in your `.env` file):
   * **User name:** `postgres` (or your configured user)
   * **Password:** *(Your configured local PostgreSQL password)*
3. **Encryption Support:** If prompted with *"We were unable to connect with the encrypted connection"*, click **OK**, then choose **Unencrypted Connection** (safe and standard for `localhost`).
4. Click **Connect**.

### Step 4: Select Analytical Reporting Views in Navigator
In the Navigator dialog, expand `godrej_cricket_db` $\to$ `public`, and select the **six reporting views**:
* `v_live_match_summary`
* `v_current_batting_scorecard`
* `v_current_bowling_scorecard`
* `v_match_innings_summary`
* `v_worm_comparison`
* `v_api_telemetry`

*(Optional: Select `ball_events` only if building Page 4 deep ball-by-ball commentary drilldowns).*
Click **Load**.

---

## 3. Semantic Model Relationship Configuration

Open the **Model View** (left navigation bar, third icon from top) to inspect and configure table relationships.

### 3.1 Star Schema Topology
The model uses a clean Star Schema anchored by `v_live_match_summary` as the central Conformed Dimension:

```text
       +---------------------------------------------+
       |            v_live_match_summary             |
       |  (Conformed Match Dimension & KPI Header)   |
       |                  [match_id]                 |
       +----------------------+----------------------+
                              |
       +----------------------+----------------------+----------------------+
       | 1:*                  | 1:*                  | 1:*                  | 1:*
       v                      v                      v                      v
+--------------+       +--------------+       +--------------+       +--------------+
|   v_current  |       |   v_current  |       |   v_match    |       |    v_worm    |
|   _batting   |       |   _bowling   |       |   _innings   |       | _comparison  |
|  _scorecard  |       |  _scorecard  |       |   _summary   |       |              |
+--------------+       +--------------+       +--------------+       +--------------+

[Standalone Table]: v_api_telemetry (Zero relationships; operational monitoring)
```

### 3.2 Exact Relationship Settings Matrix

| From (Dimension) | To (Fact) | Join Column | Cardinality | Cross Filter Direction | Assume Referential Integrity |
| :--- | :--- | :--- | :--- | :--- | :---: |
| `v_live_match_summary` | `v_current_batting_scorecard` | `match_id` | **One to Many (1:*)** | **Single** | **Checked (True)** |
| `v_live_match_summary` | `v_current_bowling_scorecard` | `match_id` | **One to Many (1:*)** | **Single** | **Checked (True)** |
| `v_live_match_summary` | `v_match_innings_summary` | `match_id` | **One to Many (1:*)** | **Single** | **Checked (True)** |
| `v_live_match_summary` | `v_worm_comparison` | `match_id` | **One to Many (1:*)** | **Single** | **Checked (True)** |

> [!TIP]
> **Why "Assume Referential Integrity" Matters:**
> In Power BI DirectQuery, enabling *Assume Referential Integrity* instructs the M engine that every foreign key in the fact tables has a matching primary key in `v_live_match_summary`. Consequently, Power BI generates high-performance `INNER JOIN` queries instead of slower `LEFT OUTER JOIN` queries in PostgreSQL.

---

## 4. Refresh Configuration: Automatic Page Refresh (APR)

Power BI Desktop offers two mechanisms for refreshing DirectQuery visuals on a live report page.

### 4.1 The Three-Tier Refresh Cadence (Disconnection Architecture)

```
[Layer 1: Upstream CricAPI] ──(120s–300s Polling)──> [Layer 2: Local PostgreSQL] ──(30s APR DirectQuery)──> [Layer 3: Power BI UI]
   API Freshness: 30–60s                                Ingestion Cadence: 30s Replay / 120s Live         UI Render: 30s Real-Time
   Quota: Max 100 hits/day                              Internal writes: 0 external API hits              DB Queries: 0 external API hits
```

* **No False Promises:** Power BI Desktop refreshing every 30 seconds ensures the visuals display the exact latest state in PostgreSQL without delay. It does **not** make external live cricket data 30-seconds fresh if upstream polling is throttled by the 100-hit daily quota.

### 4.2 Configuring Fixed-Interval APR (Method 1)
1. Select the report page canvas (click on the empty background of Page 1: Live Match Center).
2. Open the **Format Page** pane on the right.
3. Locate **Page refresh**. Toggle the switch to **On**.
4. Set **Refresh type:** `Auto page refresh`.
5. Set **Duration:** `30` or `60` **Seconds**.

### 4.3 Configuring Change Detection APR (Method 2 — Recommended for Performance)
Change Detection issues a single lightweight SQL query periodically rather than refreshing every visual simultaneously:
1. Ensure the DAX measure `[Latest Change Detection Timestamp]` exists in the model:
   ```dax
   Latest Change Detection Timestamp = MAX(v_live_match_summary[state_updated_at_utc])
   ```
2. In the **Format Page** pane $\to$ **Page refresh**:
3. Set **Refresh type:** Select **Change detection**.
4. Click **Add change detection**.
5. Set **Measure:** Choose `Latest Change Detection Timestamp`.
6. Set **Check for change every:** `10` or `15` **Seconds**.
7. Click **Apply**.
8. Power BI will only trigger visual queries when `state_updated_at_utc` advances.

---

## 5. Troubleshooting & Known Limitations

| Symptom / Error | Root Cause | Solution |
| :--- | :--- | :--- |
| **"An error happened while reading data from the provider: A connection attempt failed..."** | PostgreSQL service is stopped or port 5432 is blocked. | Verify PostgreSQL is running via `net start postgresql-x64-16` (or `18`). Verify host is `localhost` and port is `5432`. |
| **"The remote certificate is invalid according to the validation procedure"** | Power BI attempted SSL encryption against local unencrypted PostgreSQL. | Uncheck "Encrypt connections" in Data source settings (`File` $\to$ `Options and settings` $\to$ `Data source settings` $\to$ `Edit Permissions`). |
| **"Npgsql driver missing or GAC registration required"** | Power BI cannot locate Npgsql assembly in GAC. | Run the Npgsql 4.0.10 x64 MSI installer and explicitly enable the **"GAC Installation"** feature. Restart Power BI. |
| **"Function '...' is not supported in DirectQuery mode"** | Attempting to use row-level DAX or time-intelligence functions that cannot fold into SQL. | Use the pre-computed columns from `sql/002_reporting_views.sql` and the approved measures from `docs/dax-measure-dictionary.md`. |
| **APR interval locked to 30 minutes** | Occurs if publishing to Power BI Service (Cloud) under a standard Pro license. | Keep development and presentation inside **Power BI Desktop**, where sub-minute APR has no license restriction. |
| **Credentials popup keeps appearing** | Windows Credential Manager has cached an invalid password. | Go to `File` $\to$ `Options and settings` $\to$ `Data source settings` $\to$ Clear permissions for `localhost:5432`, then re-enter the password. |
