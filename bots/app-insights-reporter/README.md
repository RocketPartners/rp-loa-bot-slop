# LoA Application Insights Reporter Bot

Automated daily reporting bot that fetches Azure Application Insights metrics, business metrics from Redshift/MySQL, and posts formatted summaries to Slack.

## Features

- 📊 Azure Application Insights monitoring (exceptions, requests, dependencies, response times)
- 💼 Business metrics from Redshift (offers, upsells) and MySQL (player heartbeats)
- 📅 Weekend-aware date ranges (Monday fetches 3 days, other days fetch 1 day)
- 📱 Rich Slack Block Kit formatting with charts and visualizations
- ⏱️ Performance timing metrics for all data sources
- 🔄 Automatic Azure token refresh

## Directory Structure

```
app-insights-reporter/
├── src/                          # Core application code
│   ├── fetch_insights.py         # Fetch Azure App Insights data
│   ├── fetch_business_metrics.py # Fetch Redshift + MySQL metrics
│   ├── post_to_slack.py          # Format and post to Slack
│   ├── get_date_range.py         # Weekend-aware date calculations
│   └── refresh_token.sh          # Azure token refresh script
├── scripts/                      # Execution scripts
│   ├── run.sh                    # Main LaunchCode runner
│   ├── test_local.sh             # Local testing script
│   └── debug/                    # Debug and exploration scripts
├── docs/                         # Documentation
├── config/                       # Configuration files
├── Dockerfile                    # Container definition
└── README.md                     # This file
```

## Setup

1. Copy `.env.example` to `.env` and fill in credentials
2. Run locally: `./scripts/test_local.sh`
3. Deploy to LaunchCode (see docs/LAUNCHCODE_SYNC.md)

## Schedule

Runs Monday-Friday at 8:30 AM EST via LaunchCode cron: `30 8 * * 1-5`

## Data Sources

- **Azure Application Insights**: Exception tracking, request metrics, dependencies
- **Redshift**: Offers and upsells from warehouse.public.firehose_offer9 and quarterly table (auto-resolved, e.g. offer_2026_q1)
- **MySQL**: Player heartbeats from cirk-prod.cluster (us-east-1)

## Documentation

- [Automation Summary](docs/AUTOMATION_SUMMARY.md)
- [Business Metrics Setup](docs/BUSINESS_METRICS_SETUP.md)
- [LaunchCode Sync Guide](docs/LAUNCHCODE_SYNC.md)
- [Changelog](docs/CHANGELOG.md)
