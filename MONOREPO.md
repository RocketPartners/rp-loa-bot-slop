# LoA Player Bots - Monorepo Quick Reference

## Directory Structure ✅

```
automations/                            # Monorepo root
├── README.md                           # Main documentation
├── MONOREPO.md                         # This file
├── .gitignore                          # Global ignore rules
├── bots/                               # All bot projects
│   └── app-insights-reporter/          # Azure App Insights reporter
│       ├── README.md                   # Bot documentation
│       ├── Dockerfile                  # Container definition
│       ├── test.sh                     # Quick test wrapper
│       ├── src/                        # Source code
│       │   ├── fetch_insights.py
│       │   ├── fetch_business_metrics.py
│       │   ├── post_to_slack.py
│       │   ├── get_date_range.py
│       │   └── refresh_token.sh
│       ├── scripts/                    # Execution scripts
│       │   ├── run.sh
│       │   ├── test_local.sh
│       │   └── debug/                  # Debug utilities
│       ├── docs/                       # Documentation
│       ├── config/                     # Configuration files
│       └── archive/                    # Deprecated code
└── shared/                             # Shared utilities
    └── utils/                          # Reusable code
```

## Common Tasks

### Test a Bot Locally

```bash
# Method 1: From bot directory
cd bots/app-insights-reporter
./test.sh

# Method 2: Direct script execution
./bots/app-insights-reporter/scripts/test_local.sh
```

### Add a New Bot

```bash
# Create bot structure
mkdir -p bots/my-new-bot/{src,scripts,scripts/debug,docs,config}

# Copy template files
cp bots/app-insights-reporter/README.md bots/my-new-bot/
cp bots/app-insights-reporter/.env.example bots/my-new-bot/
cp bots/app-insights-reporter/Dockerfile bots/my-new-bot/

# Edit and customize for your bot
```

### Update LaunchCode Job

```bash
cd bots/app-insights-reporter

# Export file contents and update job
# See docs/MONOREPO_MIGRATION.md for details
```

## Environment Setup

Each bot has its own `.env` file:

```bash
cd bots/app-insights-reporter
cp .env.example .env
# Edit .env with your credentials
nano .env
```

Load environment:
```bash
export $(grep -v '^#' bots/app-insights-reporter/.env | xargs)
```

## Git Workflow

### What Gets Committed
- Source code (`.py`, `.sh`, `.js`)
- Documentation (`.md`)
- Configuration examples (`.env.example`)
- Dockerfiles

### What Doesn't Get Committed
- `.env` files (secrets)
- `*.json` output files
- `__pycache__/` directories
- `.idea/`, `.vscode/` IDE configs
- Log files

### Commit Best Practices

```bash
# Stage specific files
git add bots/app-insights-reporter/src/fetch_insights.py

# Commit with clear message
git commit -m "feat(app-insights): add weekend-aware date ranges"

# Convention: <type>(<scope>): <message>
# Types: feat, fix, docs, refactor, test, chore
# Scope: bot name or 'shared'
```

## Documentation

### Bot-Specific Docs
Located in `bots/<bot-name>/docs/`:
- `AUTOMATION_SUMMARY.md` - Overview and features
- `BUSINESS_METRICS_SETUP.md` - Setup guides
- `CHANGELOG.md` - Version history
- `MONOREPO_MIGRATION.md` - Migration notes

### Main Docs
- `/README.md` - Monorepo overview
- `/MONOREPO.md` - This quick reference
- `/shared/README.md` - Shared utilities guide

## File Locations Reference

| File Type | Location | Example |
|-----------|----------|---------|
| Source code | `bots/<bot>/src/` | `fetch_insights.py` |
| Execution scripts | `bots/<bot>/scripts/` | `run.sh`, `test_local.sh` |
| Debug scripts | `bots/<bot>/scripts/debug/` | `explore_mysql.py` |
| Documentation | `bots/<bot>/docs/` | `CHANGELOG.md` |
| Configuration | `bots/<bot>/config/` | `job_config.json` |
| Container | `bots/<bot>/` | `Dockerfile` |
| Environment | `bots/<bot>/` | `.env`, `.env.example` |
| Archived code | `bots/<bot>/archive/` | Old scripts |

## Bot Status

| Bot | Status | Schedule | Description |
|-----|--------|----------|-------------|
| app-insights-reporter | ✅ Active | Mon-Fri 8:30 AM EST | Azure monitoring & Slack reporting |

## Quick Links

- [Main README](README.md)
- [App Insights Reporter](bots/app-insights-reporter/README.md)
- [Shared Utils](shared/README.md)
- [LaunchCode Docs](bots/app-insights-reporter/docs/LAUNCHCODE_SYNC.md)

## Support

For issues or questions:
1. Check bot-specific documentation in `bots/<bot>/docs/`
2. Review main README.md
3. Contact: Circle K Lift team

---

**Last Updated:** February 3, 2026
**Version:** 1.0.0
