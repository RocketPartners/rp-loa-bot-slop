# Monorepo Migration Guide

## Overview

The automation codebase has been reorganized into a monorepo structure to support multiple LoA player bots.

## New Structure

```
automations/
├── README.md                          # Main monorepo documentation
├── .gitignore                         # Global ignore rules
├── .env                              # Root env (for compatibility)
├── bots/
│   └── app-insights-reporter/
│       ├── README.md                  # Bot-specific documentation
│       ├── .env                       # Bot-specific environment
│       ├── .env.example              # Example configuration
│       ├── Dockerfile                # Container definition
│       ├── test.sh                   # Quick test runner
│       ├── src/                      # Source code
│       │   ├── fetch_insights.py
│       │   ├── fetch_business_metrics.py
│       │   ├── post_to_slack.py
│       │   ├── get_date_range.py
│       │   └── refresh_token.sh
│       ├── scripts/                  # Execution scripts
│       │   ├── run.sh                # LaunchCode runner
│       │   ├── test_local.sh        # Local test runner
│       │   └── debug/               # Debug utilities
│       │       ├── test_metrics_separately.py
│       │       ├── test_parse.py
│       │       ├── explore_custom_events.py
│       │       └── ...
│       ├── docs/                    # Documentation
│       │   ├── AUTOMATION_SUMMARY.md
│       │   ├── BUSINESS_METRICS_SETUP.md
│       │   ├── CHANGELOG.md
│       │   └── ...
│       ├── config/                  # Configuration files
│       │   └── job_config.json
│       └── archive/                 # Deprecated scripts
└── shared/                          # Shared utilities (future)
    └── utils/
```

## Running Tests Locally

### From Bot Directory
```bash
cd bots/app-insights-reporter
./test.sh
```

### From Anywhere
```bash
./bots/app-insights-reporter/scripts/test_local.sh
```

## LaunchCode Deployment

The LaunchCode job configuration maps files to `/app/` in the container. Files are uploaded with the content from the src/ directory.

## Benefits of Monorepo

1. **Centralized Management**: All LoA bots in one repository
2. **Shared Code**: Common utilities in `shared/` directory
3. **Consistent Structure**: Each bot follows the same pattern
4. **Easy Navigation**: Clear separation of concerns
5. **Documentation**: All docs organized by bot

## Adding New Bots

1. Create new bot directory:
   ```bash
   mkdir -p bots/<new-bot-name>/{src,scripts,docs,config}
   ```

2. Follow existing structure:
   - Source code in `src/`
   - Execution scripts in `scripts/`
   - Documentation in `docs/`
   - Configuration in `config/`

3. Create bot-specific README

4. Update main monorepo README with new bot info

## Environment Variables

Each bot has its own `.env` file in its directory. The root `.env` is kept for backward compatibility.

To use a bot's environment:
```bash
cd bots/app-insights-reporter
export $(grep -v '^#' .env | xargs)
```

## Git Workflow

The `.gitignore` prevents committing:
- All `.env` files (except `.env.example`)
- Python cache files
- IDE configs
- Generated JSON output files
- Log files

Always commit:
- Source code changes
- Documentation updates
- Script modifications
- Configuration examples

## Migration Checklist

- [x] Organized files into monorepo structure
- [x] Created bot-specific README
- [x] Updated test scripts with correct paths
- [x] Created wrapper test.sh script
- [x] Documented new structure
- [ ] Test local execution
- [ ] Verify LaunchCode deployment
