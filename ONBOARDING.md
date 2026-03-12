# Onboarding Guide - LoA Player Bots

Complete guide for understanding, running, and maintaining the LoA monitoring and reporting automations.

---

## Table of Contents

1. [What This Repo Does](#what-this-repo-does)
2. [Repository Structure](#repository-structure)
3. [Prerequisites](#prerequisites)
4. [Environment Setup](#environment-setup)
5. [Bot 1: Daily Report (app-insights-reporter)](#bot-1-daily-report-app-insights-reporter)
6. [Bot 2: Monthly Metrics Report](#bot-2-monthly-metrics-report)
7. [Bot 3: Yearly Metrics Report](#bot-3-yearly-metrics-report)
8. [How the Data Pipeline Works](#how-the-data-pipeline-works)
9. [Date Logic and Quarter Resolution](#date-logic-and-quarter-resolution)
10. [Database Tables and Queries](#database-tables-and-queries)
11. [Slack Output](#slack-output)
12. [Running Locally](#running-locally)
13. [LaunchCode Deployment](#launchcode-deployment)
14. [Azure Token Management](#azure-token-management)
15. [Debugging](#debugging)
16. [Common Issues and Fixes](#common-issues-and-fixes)
17. [File Reference](#file-reference)

---

## What This Repo Does

This monorepo contains three automated bots that monitor the LoA (Letter of Authorization) player system and post reports to Slack:

| Bot | What It Reports | Schedule | Slack Channel |
|-----|----------------|----------|---------------|
| **app-insights-reporter** | Daily health: Azure exceptions, requests, response times, offers, upsells, player heartbeats | Mon-Fri 8:30 AM EST | `#int-lift-loa-app-insights` |
| **monthly-metrics-report** | Month-to-date: daily breakdown of offers and upsells, upsell rate | On demand / scheduled | `MONTHLY_METRICS_SLACK_CHANNEL` |
| **yearly-metrics-report** | Year-to-date: monthly and quarterly rollups, highlights, trends | On demand / scheduled | `YEARLY_METRICS_SLACK_CHANNEL` |

All three bots share the same root `.env` file for credentials and follow the same Fetch -> Format -> Post pattern.

---

## Repository Structure

```
automations/
├── .env                              # Shared credentials (not committed)
├── .gitignore
├── README.md                         # Repo overview
├── ONBOARDING.md                     # This file
│
├── bots/
│   ├── app-insights-reporter/        # DAILY report
│   │   ├── src/
│   │   │   ├── fetch_insights.py         # Queries Azure App Insights REST API (KQL)
│   │   │   ├── fetch_business_metrics.py # Queries Redshift (offers/upsells) + MySQL (heartbeats)
│   │   │   ├── format_report.py          # Turns raw JSON into a text report
│   │   │   ├── post_to_slack.py          # Converts text report to Slack Block Kit and posts
│   │   │   ├── get_date_range.py         # Weekend-aware date range calculator
│   │   │   ├── refresh_token.sh          # Refreshes Azure access token via `az` CLI
│   │   │   └── az_login_playwright.py    # Automated Azure login via headless browser
│   │   ├── scripts/
│   │   │   ├── test_local.sh             # Run the full pipeline locally
│   │   │   ├── run.sh                    # LaunchCode production entrypoint
│   │   │   ├── deploy_to_launchcode.js   # Deploy files to LaunchCode job
│   │   │   ├── update_launchcode.js      # Update LaunchCode job config
│   │   │   └── debug/                    # Debug/test utilities (see Debugging section)
│   │   ├── docs/                         # Additional documentation
│   │   ├── config/job_config.json        # LaunchCode job definition
│   │   ├── archive/                      # Deprecated scripts (reference only)
│   │   ├── .env.example                  # Template for bot-level .env
│   │   ├── test.sh                       # Quick wrapper: loads .env + runs test_local.sh
│   │   └── Dockerfile                    # Container for LaunchCode
│   │
│   ├── monthly-metrics-report/       # MONTHLY report
│   │   ├── src/
│   │   │   ├── fetch_monthly_metrics.py  # Daily offers/upsells for a month from Redshift
│   │   │   └── post_to_slack.py          # Posts monthly summary to Slack
│   │   └── scripts/
│   │       ├── test_local.sh             # Local test (supports REPORT_MONTH, REPORT_YEAR)
│   │       └── run.sh                    # LaunchCode production entrypoint
│   │
│   └── yearly-metrics-report/        # YEARLY report
│       ├── src/
│       │   ├── fetch_yearly_metrics.py   # All quarters for a year from Redshift
│       │   └── post_yearly_to_slack.py   # Posts yearly summary to Slack
│       └── scripts/
│           ├── test_yearly_local.sh      # Local test (supports REPORT_YEAR)
│           └── run.sh                    # LaunchCode production entrypoint
│
└── shared/                           # Shared utilities (future)
    └── utils/
```

---

## Prerequisites

**Tools you need installed:**

- Python 3.11+
- Azure CLI (`az`) -- for token refresh
- pip packages: `slack-sdk requests python-dateutil psycopg2-binary mysql-connector-python`

Install Python dependencies:

```bash
pip3 install slack-sdk requests python-dateutil psycopg2-binary mysql-connector-python
```

**Access you need:**

- Azure portal access (for App Insights token)
- Redshift read access (`liftreadyonly` user on `redshift.circleklift.com`)
- MySQL read access (cirk-prod cluster, `lift.Heartbeat` table)
- Slack bot token with `chat:write` permission
- VPN access (required when connecting to Redshift/MySQL from non-corp network)

---

## Environment Setup

All three bots load credentials from the root `.env` file at `automations/.env`.

Create it by copying the example and filling in real values:

```bash
cp bots/app-insights-reporter/.env.example .env
```

**Required variables:**

```bash
# ── Azure Application Insights ──
AZURE_APP_INSIGHTS_WORKSPACE_ID=68702a23-e965-43e5-81b6-9df7b4fec2b6
AZURE_ACCESS_TOKEN=<get from: az account get-access-token --resource=https://api.applicationinsights.io>

# ── Slack ──
SLACK_BOT_TOKEN=xoxb-...
SLACK_CHANNEL=#int-lift-loa-app-insights
MONTHLY_METRICS_SLACK_CHANNEL=#your-monthly-channel
YEARLY_METRICS_SLACK_CHANNEL=#your-yearly-channel

# ── Redshift (LIFT US REDSHIFT PROD) ──
REDSHIFT_HOST=redshift.circleklift.com
REDSHIFT_PORT=5439
REDSHIFT_DATABASE=warehouse
REDSHIFT_USER=liftreadyonly
REDSHIFT_PASSWORD=<ask team lead>

# ── MySQL (cirk-prod, player heartbeats) ──
MYSQL_HOST=<cirk-prod cluster endpoint>
MYSQL_PORT=3306
MYSQL_DATABASE=lift
MYSQL_USER=<ask team lead>
MYSQL_PASSWORD=<ask team lead>

# ── VPN (LaunchCode production only) ──
OPENVPN_USER=<your vpn user>
OPENVPN_PASS=<your vpn pass>
```

The Azure access token expires every ~1 hour. See [Azure Token Management](#azure-token-management) for how to refresh it.

---

## Bot 1: Daily Report (app-insights-reporter)

### What it does

Every weekday at 8:30 AM EST, this bot:

1. Fetches Azure Application Insights data (exceptions, requests, dependencies, response times)
2. Fetches business metrics from Redshift (offers, upsells) and MySQL (player heartbeats)
3. Formats everything into a structured text report
4. Posts to Slack as a rich Block Kit message with charts

### Pipeline steps

```
Step 0: Refresh Azure token (refresh_token.sh)
           ↓
Step 1: Fetch Azure App Insights → insights_data.json
           ↓
Step 1.5: Fetch Redshift + MySQL → business_metrics.json
           ↓
Step 2: Format report (format_report.py reads both JSON files)
           ↓
Step 3: Post to Slack (post_to_slack.py builds Block Kit and sends)
```

### Run it locally

```bash
cd bots/app-insights-reporter

# Option A: Quick wrapper (loads .env automatically)
bash test.sh

# Option B: Manual (if .env is at the root)
export $(grep -v '^#' ../../.env | xargs)
bash scripts/test_local.sh
```

### Key source files

| File | Responsibility |
|------|---------------|
| `src/fetch_insights.py` | Calls Azure App Insights REST API with KQL queries. Returns summary metrics (requests, exceptions, dependencies, P95), last 50 individual exceptions, top 20 exception groups, and hourly exception timeline. Uses `get_date_range()` to dynamically set the lookback window. |
| `src/fetch_business_metrics.py` | Connects to Redshift for offers/upsells and MySQL for player heartbeats. Dynamically resolves the quarterly table based on the current date (e.g., `offer_2026_q1` in Q1, `offer_2026_q2` in Q2). |
| `src/format_report.py` | Parses the two JSON files and produces a text report with status emoji, metrics line, business metrics line, top 5 exception problems, and action required section. |
| `src/post_to_slack.py` | Parses the text report with regex, builds Slack Block Kit JSON (2-column grids, QuickChart bar charts with ASCII fallback, code blocks for exceptions), and posts via `slack-sdk`. |
| `src/get_date_range.py` | Returns ET calendar day boundaries. Monday = 3 days (Fri-Sun), other days = 1 day (yesterday). Also returns buffer dates for Redshift string pre-filtering. |
| `src/refresh_token.sh` | Runs `az account get-access-token` and updates `.env` in-place. |

---

## Bot 2: Monthly Metrics Report

### What it does

Fetches daily offers and upsells for a given month from Redshift, plus current active player count from MySQL. Posts a day-by-day breakdown to Slack.

### Run it locally

```bash
cd bots/monthly-metrics-report

# Current month (auto-detected from today's date)
bash scripts/test_local.sh

# Specific month
REPORT_MONTH=1 REPORT_YEAR=2026 bash scripts/test_local.sh

# Explicit quarter override
REPORT_MONTH=3 REPORT_QUARTER=1 REPORT_YEAR=2026 bash scripts/test_local.sh
```

### How it picks the table

The script derives the quarter from the month: `quarter = (month - 1) // 3 + 1`

- Months 1-3 -> Q1 -> `warehouse.public.offer_YYYY_q1`
- Months 4-6 -> Q2 -> `warehouse.public.offer_YYYY_q2`
- Months 7-9 -> Q3 -> `warehouse.public.offer_YYYY_q3`
- Months 10-12 -> Q4 -> `warehouse.public.offer_YYYY_q4`

---

## Bot 3: Yearly Metrics Report

### What it does

Fetches all available quarterly tables for a given year, aggregates into monthly and quarterly rollups, identifies best/worst months and peak days. Posts to Slack.

### Run it locally

```bash
cd bots/yearly-metrics-report

# Current year
bash scripts/test_yearly_local.sh

# Specific year
REPORT_YEAR=2026 bash scripts/test_yearly_local.sh
```

---

## How the Data Pipeline Works

All three bots follow the same architecture:

```
┌──────────────┐     ┌──────────────┐     ┌────────────────┐     ┌─────────┐
│ Data Sources │ ──> │ Fetch Script  │ ──> │ Format / Parse │ ──> │  Slack  │
│              │     │ (Python)      │     │ (Python)       │     │         │
│ - Azure API  │     │ outputs JSON  │     │ reads JSON     │     │ Block   │
│ - Redshift   │     │ to stdout     │     │ builds text    │     │ Kit     │
│ - MySQL      │     │               │     │ or JSON        │     │ message │
└──────────────┘     └──────────────┘     └────────────────┘     └─────────┘
```

**Data flows through files, not in-memory.** Each step writes to a JSON file on disk so you can inspect intermediate output:

- `insights_data.json` -- raw Azure App Insights response
- `business_metrics.json` -- raw Redshift + MySQL response
- `monthly_data.json` -- monthly aggregation
- `yearly_data.json` -- yearly aggregation

---

## Date Logic and Quarter Resolution

### Weekend-aware date ranges (daily bot)

Defined in `src/get_date_range.py`:

| Day of Week | Reports On | Days Back | Example |
|-------------|-----------|-----------|---------|
| Monday | Friday + Saturday + Sunday | 3 | Report date range: "March 06 - March 08, 2026" |
| Tuesday | Monday | 1 | Report date: "March 09, 2026" |
| Wednesday | Tuesday | 1 | ... |
| Thursday | Wednesday | 1 | ... |
| Friday | Thursday | 1 | ... |
| Saturday | Friday | 1 | ... |
| Sunday | Saturday | 1 | ... |

All dates are in **Eastern Time** (`America/New_York`).

### Automatic quarterly table resolution (all bots)

The Redshift warehouse stores offer data in quarterly partition tables:

```
warehouse.public.offer_2026_q1   (Jan 1 - Mar 31)
warehouse.public.offer_2026_q2   (Apr 1 - Jun 30)
warehouse.public.offer_2026_q3   (Jul 1 - Sep 30)
warehouse.public.offer_2026_q4   (Oct 1 - Dec 31)
```

Every bot resolves which table to query based on the date it's reporting on:

```python
def quarter_for_month(month):
    return (month - 1) // 3 + 1

def offer_table_name(year, quarter):
    return f"warehouse.public.offer_{year}_q{quarter}"
```

The daily bot uses the `report_date` (the date being reported, not today) to determine the quarter. This means on April 1 (reporting on March 31), it still queries Q1.

There is also a permanent archive table `warehouse.public.firehose_offer9` that is always queried in a `UNION ALL` alongside the quarterly table. This ensures no data is missed.

---

## Database Tables and Queries

### Redshift

**Connection:**
- Host: `redshift.circleklift.com`
- Port: `5439`
- Database: `warehouse`
- User: `liftreadyonly`

**Tables queried:**

| Table | Purpose |
|-------|---------|
| `warehouse.public.firehose_offer9` | Permanent archive of all offers |
| `warehouse.public.offer_YYYY_qN` | Quarterly partition table (e.g., `offer_2026_q1`) |

**Key columns:**
- `createdat` -- char(29), ISO 8601 with timezone offset (e.g., `2026-02-19T23:57:05.741-07:00`)
- `cashierkey` -- filtered by `LIKE '%CashierName%'`
- `liftadded` -- boolean, `true` means the offer was an upsell
- `playercode` -- player identifier

**Timezone conversion:**
```sql
DATE(CONVERT_TIMEZONE('UTC', 'America/New_York', CAST(CAST(createdat AS TIMESTAMPTZ) AS TIMESTAMP)))
```

Since `createdat` is a char column, queries use a 1-day string buffer as a rough pre-filter before applying the precise timezone conversion:

```sql
WHERE createdat >= '2026-03-07'   -- buffer_start (1 day before report date)
  AND createdat < '2026-03-10'    -- buffer_end (1 day after end date)
  AND <ET_DATE> >= '2026-03-08'   -- precise ET boundary
  AND <ET_DATE> < '2026-03-09'
```

### MySQL

**Connection:**
- Host: cirk-prod cluster (us-east-1)
- Port: `3306`
- Database: `lift`

**Table queried:**

| Table | Purpose |
|-------|---------|
| `lift.Heartbeat` | Current state of player heartbeats |

**Key columns:**
- `playerKey` -- unique player identifier
- `macAddress` -- filtered by `LIKE '70:0A%'` (LoA hardware)
- `timestamp` -- last heartbeat time

**Query pattern:**
```sql
SELECT COUNT(DISTINCT playerKey) AS unique_players
FROM lift.Heartbeat
WHERE macAddress LIKE '70:0A%'
  AND timestamp >= NOW() - INTERVAL N DAY;
```

`N` is 1 for normal days, 3 for Monday (matches the weekend lookback).

---

## Slack Output

The daily bot posts a rich Block Kit message with these sections:

1. **Header** -- "LoA Daily Report" with timestamp
2. **Business Metrics** -- 2-column grid: Offers, Player Heartbeats, Upsells
3. **Application Insights** -- 2-column grid: Exceptions, Requests, Dependencies, P95 Response, Success Rate
4. **Exception Timeline** -- QuickChart bar chart (falls back to ASCII if URL too long)
5. **Top 5 Exception Problems** -- ASCII bar chart + code block with error details
6. **Action Required** -- Recommendation based on top exception
7. **Footer** -- Fetch timing (Azure, Redshift, MySQL) + Azure Portal link

Status emoji thresholds:
- `>5000` exceptions: red
- `>2000` exceptions: yellow
- `<=2000` exceptions: green

---

## Running Locally

### Daily report

```bash
cd bots/app-insights-reporter

# 1. Make sure you have a valid Azure token
az login
az account get-access-token --resource=https://api.applicationinsights.io --query accessToken -o tsv
# Copy the token into .env as AZURE_ACCESS_TOKEN

# 2. Make sure you're on VPN (for Redshift/MySQL access)

# 3. Run
bash test.sh
```

### Monthly report

```bash
cd bots/monthly-metrics-report
bash scripts/test_local.sh                                    # current month
REPORT_MONTH=2 REPORT_YEAR=2026 bash scripts/test_local.sh   # Feb 2026
```

### Yearly report

```bash
cd bots/yearly-metrics-report
bash scripts/test_yearly_local.sh                             # current year
REPORT_YEAR=2026 bash scripts/test_yearly_local.sh            # 2026
```

### Run just one step at a time (daily bot)

```bash
cd bots/app-insights-reporter
export $(grep -v '^#' ../../.env | xargs)

# Step 1: Fetch insights only
python3 src/fetch_insights.py > insights_data.json
cat insights_data.json | python3 -m json.tool

# Step 1.5: Fetch business metrics only
python3 src/fetch_business_metrics.py > business_metrics.json
cat business_metrics.json | python3 -m json.tool

# Step 2: Format report
python3 src/format_report.py insights_data.json business_metrics.json

# Step 3: Post to Slack
python3 src/format_report.py insights_data.json business_metrics.json | python3 src/post_to_slack.py
```

---

## LaunchCode Deployment

The daily bot runs as a LaunchCode job inside a Docker container.

### Dockerfile

Based on `python:3.11-slim` with:
- Azure CLI (for token refresh)
- Node.js + Claude Code CLI
- Python packages: `slack-sdk`, `requests`, `python-dateutil`, `psycopg2-binary`, `mysql-connector-python`

### Production flow differences from local

| Aspect | Local (`test_local.sh`) | Production (`run.sh`) |
|--------|------------------------|-----------------------|
| Token refresh | `az account get-access-token` via CLI | Pre-set token or Service Principal |
| VPN | Must be connected manually | OpenVPN client started in-container |
| File paths | Relative to bot directory | `/app/*` (Docker working dir) |
| .env loading | Sources from root `.env` | Environment injected by LaunchCode |

### Cron schedule

```
30 8 * * 1-5    # Monday-Friday at 8:30 AM EST
```

### Deploying updates

```bash
cd bots/app-insights-reporter
node scripts/deploy_to_launchcode.js    # Upload files to LaunchCode
node scripts/update_launchcode.js       # Update job configuration
```

---

## Azure Token Management

The Azure access token (`AZURE_ACCESS_TOKEN`) is needed to call the Application Insights REST API. It expires after ~1 hour.

### Manual refresh

```bash
# 1. Make sure you're logged in
az login

# 2. Get a fresh token
az account get-access-token --resource=https://api.applicationinsights.io --query accessToken -o tsv
```

### Automatic refresh (local)

`test_local.sh` calls `src/refresh_token.sh` at the start of every run, which:
1. Runs `az account get-access-token`
2. Writes the new token into `.env` using `sed`
3. Re-exports the updated `.env`

This requires `az login` to have been run at least once in the current session.

### Automated login (headless)

`src/az_login_playwright.py` can fully automate `az login` using Playwright:
1. Starts `az login --use-device-code`
2. Captures the device code
3. Opens headless Chromium, navigates to Microsoft device login
4. Fills in credentials and handles Okta federation + TOTP MFA

Requires: `AZURE_EMAIL`, `AZURE_PASSWORD`, and optionally `OKTA_TOTP_CODE`.

---

## Debugging

Debug scripts are in `bots/app-insights-reporter/scripts/debug/`:

| Script | What it tests |
|--------|--------------|
| `debug_azure.py` | Azure App Insights API connectivity and basic query |
| `send_slack_message.py` | Send a test message to your Slack channel |
| `test_slack.sh` | Bash wrapper for Slack testing |
| `test_parse.py` | Test the report parsing logic in isolation |
| `test_metrics_separately.py` | Test each data source (Azure, Redshift, MySQL) independently |
| `explore_custom_events.py` | Explore available Azure custom events |
| `explore_mysql.py` | Test MySQL connection and queries |
| `announce_to_team.py` | Send a team announcement to Slack |

### Example debug session

```bash
cd bots/app-insights-reporter
export $(grep -v '^#' ../../.env | xargs)

# Test Azure connection
python3 scripts/debug/debug_azure.py

# Test each data source separately
python3 scripts/debug/test_metrics_separately.py

# Send a test Slack message
python3 scripts/debug/send_slack_message.py "Hello from debug"
```

### Checking date range logic

```bash
cd bots/app-insights-reporter/src
python3 get_date_range.py
```

This prints the current date range as JSON so you can verify what dates and tables would be queried.

---

## Common Issues and Fixes

### "Authentication failed - token may be expired or invalid"

The Azure token expired. Refresh it:

```bash
az login
./src/refresh_token.sh
```

### Redshift/MySQL connection timeout

You need to be on VPN. Connect to the corporate VPN and retry.

### "psycopg2 not installed"

```bash
pip3 install psycopg2-binary
```

### "mysql.connector not installed"

```bash
pip3 install mysql-connector-python
```

Business metrics are optional -- if MySQL is not configured, the bot continues and posts the report without heartbeat data.

### Slack message shows "Parser found no structured data"

The format of the text report changed in a way that `post_to_slack.py`'s regex can't parse. Check the raw output:

```bash
python3 src/format_report.py insights_data.json business_metrics.json
```

Compare the output against the regex patterns in `post_to_slack.py`'s `parse_report()` function.

### QuickChart image not showing in Slack

If the chart URL exceeds 2000 characters, the script automatically falls back to an ASCII chart. This is logged to stderr:

```
Chart URL too long (2345 chars), using ASCII fallback
```

### Wrong quarterly table being queried

All bots now dynamically resolve the quarterly table from the report date. Run the date range check to verify:

```bash
cd bots/app-insights-reporter/src
python3 -c "
from get_date_range import get_date_range
from datetime import date
info = get_date_range()
report_date = date.fromisoformat(info['report_date'])
quarter = (report_date.month - 1) // 3 + 1
print(f'Report date: {report_date}')
print(f'Quarter: Q{quarter}')
print(f'Table: warehouse.public.offer_{report_date.year}_q{quarter}')
"
```

---

## File Reference

### app-insights-reporter/src/

| File | Lines | Description |
|------|-------|-------------|
| `fetch_insights.py` | 167 | Azure App Insights REST API with KQL (Summary, Exceptions, ExceptionGroups, Timeline) |
| `fetch_business_metrics.py` | 278 | Redshift offers/upsells + MySQL heartbeats, dynamic quarterly table resolution |
| `format_report.py` | 138 | JSON -> text report with status emoji, metrics, top 5 issues, action items |
| `post_to_slack.py` | 621 | Text -> Slack Block Kit (2-col grids, QuickChart/ASCII charts, code blocks) |
| `get_date_range.py` | 59 | Weekend-aware ET date range calculator |
| `refresh_token.sh` | ~15 | `az account get-access-token` -> updates .env |
| `az_login_playwright.py` | ~100 | Headless browser automation for `az login` |

### monthly-metrics-report/src/

| File | Description |
|------|-------------|
| `fetch_monthly_metrics.py` | Fetches daily offers/upsells for a month, active players snapshot |
| `post_to_slack.py` | Posts monthly summary to Slack |

### yearly-metrics-report/src/

| File | Description |
|------|-------------|
| `fetch_yearly_metrics.py` | Fetches all quarters for a year, builds monthly/quarterly rollups and highlights |
| `post_yearly_to_slack.py` | Posts yearly summary with analytics to Slack |

---

## Quick Reference Card

```bash
# ── Daily report ──
cd bots/app-insights-reporter && bash test.sh

# ── Monthly report (current month) ──
cd bots/monthly-metrics-report && bash scripts/test_local.sh

# ── Monthly report (specific month) ──
REPORT_MONTH=1 REPORT_YEAR=2026 bash scripts/test_local.sh

# ── Yearly report (current year) ──
cd bots/yearly-metrics-report && bash scripts/test_yearly_local.sh

# ── Yearly report (specific year) ──
REPORT_YEAR=2026 bash scripts/test_yearly_local.sh

# ── Refresh Azure token ──
cd bots/app-insights-reporter && ./src/refresh_token.sh

# ── Check what dates/tables would be queried today ──
cd bots/app-insights-reporter/src && python3 get_date_range.py

# ── Debug individual data sources ──
cd bots/app-insights-reporter
python3 scripts/debug/test_metrics_separately.py
```
