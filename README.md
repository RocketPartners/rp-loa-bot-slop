# LoA Player Bots - Monorepo

Centralized repository for all Letter of Authorization (LoA) player monitoring and automation bots.

## Overview

This monorepo contains automated bots and scripts for monitoring, analyzing, and reporting on LoA player activity across multiple data sources including Azure Application Insights, Redshift data warehouse, and MySQL databases.

## Bots

### 📊 [App Insights Reporter](bots/app-insights-reporter/)

Automated daily reporting bot that monitors Azure Application Insights, fetches business metrics from Redshift/MySQL, and posts formatted summaries to Slack.

**Features:**
- Azure Application Insights monitoring (exceptions, requests, dependencies)
- Business metrics (offers, upsells, player heartbeats)
- Weekend-aware date ranges
- Rich Slack formatting with charts

**Schedule:** Monday-Friday at 8:30 AM EST

---

## Repository Structure

```
automations/
├── README.md              # This file
├── .gitignore            # Git ignore rules
├── .env                  # Environment variables (not committed)
├── bots/                 # Individual bot projects
│   └── app-insights-reporter/
│       ├── src/          # Source code
│       ├── scripts/      # Execution scripts
│       ├── docs/         # Documentation
│       ├── config/       # Configuration files
│       └── Dockerfile    # Container definition
└── shared/               # Shared utilities (future)
    └── utils/
```

## Getting Started

Each bot has its own README with specific setup instructions. Generally:

1. Navigate to the bot directory: `cd bots/<bot-name>`
2. Copy `.env.example` to `.env` and configure
3. Follow bot-specific setup instructions

## Development

### Adding a New Bot

1. Create directory: `bots/<new-bot-name>/`
2. Follow the structure of existing bots
3. Include README.md, Dockerfile, and .env.example
4. Update this main README with bot information

### Shared Code

Place reusable utilities in `shared/utils/` for use across multiple bots.

## Deployment

All bots are deployed to LaunchCode platform for scheduled execution. See individual bot documentation for LaunchCode-specific configuration.

## Environment Variables

Each bot manages its own environment variables. See `.env.example` in each bot directory.

Common variables:
- `SLACK_BOT_TOKEN` - Slack bot authentication
- `SLACK_CHANNEL` - Target Slack channel

## Documentation

- Each bot has comprehensive documentation in its `docs/` directory
- See individual bot READMEs for specific features and configuration

## Contributing

When adding or modifying bots:
1. Keep bot code isolated in its own directory
2. Document all environment variables
3. Update relevant README files
4. Test locally before deploying to LaunchCode

## License

Internal use only - Circle K Lift team
