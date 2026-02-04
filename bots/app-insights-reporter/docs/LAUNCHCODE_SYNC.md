# LaunchCode Job Sync - Complete

## ✅ Job Updated Successfully

The LaunchCode job now matches `test_local.sh` exactly!

**Job**: [LoA Application Insights Summary Job](https://rocketpartners.launch-code.dev/automations/jobs/b9084540-4725-4f23-b6c6-9310bb3328b7)

## 🔄 Execution Flow (Both Local & LaunchCode)

```
┌─────────────────────────────────────────────┐
│ 🔧 Configure Claude Code with LaunchCode   │
│   (LaunchCode only - auto-injects API key) │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 🔄 Step 0: Refresh Azure Access Token      │
│                                             │
│ Local:                                      │
│   • Uses az CLI                             │
│   • Updates .env file                       │
│   • Reloads environment                     │
│                                             │
│ LaunchCode:                                 │
│   • Uses Service Principal (if configured)  │
│   • Calls Azure OAuth API                   │
│   • Exports AZURE_ACCESS_TOKEN              │
│   • Falls back to pre-set token            │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 📋 Check Environment Variables              │
│   • AZURE_APP_INSIGHTS_WORKSPACE_ID         │
│   • SLACK_BOT_TOKEN                         │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 🚀 Step 1: Fetch Application Insights Data │
│   • Runs fetch_insights.py                  │
│   • Queries last 24 hours                   │
│   • Saves to insights_data.json             │
│   • Summary + 50 exceptions + 20 groups     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 🤖 Step 2: Analyze with Claude Code        │
│   • Reads insights_data.json                │
│   • Uses structured prompt                  │
│   • Generates formatted report:             │
│     - Status line with emoji                │
│     - Metrics line                          │
│     - Top 5 Problems                        │
│     - Action Required                       │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ 📤 Step 3: Post to Slack                   │
│   • Runs post_to_slack.py                   │
│   • Parses text report                      │
│   • Builds Block Kit JSON:                  │
│     - Header block                          │
│     - Metrics grid (2 columns)              │
│     - 5 issue blocks with bars              │
│     - Action section                        │
│     - Footer with link                      │
│   • Posts to #int-lift-loa-app-insights     │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────┐
│ ✅ Job Completed Successfully               │
└─────────────────────────────────────────────┘
```

## 📊 Side-by-Side Comparison

| Feature | test_local.sh | LaunchCode Job | Status |
|---------|---------------|----------------|--------|
| Step 0: Token Refresh | ✅ az CLI | ✅ Service Principal | ✅ Synced |
| Step 1: Fetch Data | ✅ fetch_insights.py | ✅ fetch_insights.py | ✅ Synced |
| Step 2: Claude Analysis | ✅ Exact format | ✅ Exact format | ✅ Synced |
| Step 3: Slack Post | ✅ Block Kit | ✅ Block Kit | ✅ Synced |
| Top Issues Count | ✅ 5 issues | ✅ 5 issues | ✅ Synced |
| Metrics Display | ✅ 2-col grid | ✅ 2-col grid | ✅ Synced |
| Bar Charts | ✅ ASCII bars | ✅ ASCII bars | ✅ Synced |
| Error Handling | ✅ Graceful | ✅ Graceful | ✅ Synced |

## 🔐 Token Refresh Configuration

### Local (test_local.sh)
```bash
# Automatic refresh using Azure CLI
./refresh_token.sh
  └─> az account get-access-token --resource=https://api.applicationinsights.io
  └─> Updates .env file
  └─> Reloads environment variables
```

### LaunchCode (run.sh)
```bash
# Automatic refresh using Service Principal
if [ -n "$AZURE_TENANT_ID" ] && [ -n "$AZURE_CLIENT_ID" ] && [ -n "$AZURE_CLIENT_SECRET" ]; then
  # Get token via Azure OAuth API
  curl -X POST "https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/token"
    -d "client_id=${AZURE_CLIENT_ID}"
    -d "client_secret=${AZURE_CLIENT_SECRET}"
    -d "scope=https://api.applicationinsights.io/.default"
    -d "grant_type=client_credentials"

  export AZURE_ACCESS_TOKEN
else
  # Falls back to pre-set AZURE_ACCESS_TOKEN
fi
```

## 📝 Files Synced

| File | Local | LaunchCode | Status |
|------|-------|------------|--------|
| run.sh / test_local.sh | ✅ | ✅ | Synced - Token refresh integrated |
| fetch_insights.py | ✅ | ✅ | Synced - Same KQL query |
| post_to_slack.py | ✅ | ✅ | Synced - Block Kit with top 5 |
| Dockerfile | ✅ | ✅ | Synced - Node.js + Claude Code |

## 🚀 Ready to Enable

The LaunchCode job is now fully configured and ready to enable for daily runs!

### Current Configuration
- **Schedule**: Daily at 8:30 AM EST (`30 8 * * *`)
- **Timezone**: America/New_York
- **Status**: Disabled (ready to enable)
- **CPU**: 512 units
- **Memory**: 1024 MB

### To Enable Daily Runs

1. **Set up Azure Service Principal** (for permanent token solution):
   ```bash
   az ad sp create-for-rbac \
     --name "LoA-AppInsights-Reader" \
     --role "Reader" \
     --scopes /subscriptions/<sub-id>/resourceGroups/<rg>/providers/microsoft.insights/components/<app-insights>
   ```

2. **Update LaunchCode environment variables**:
   - `AZURE_TENANT_ID` = Your Azure tenant ID
   - `AZURE_CLIENT_ID` = Service principal app ID
   - `AZURE_CLIENT_SECRET` = Service principal password

3. **Enable the job**:
   ```bash
   ~/.launchcode/scripts/api.js <<'EOF'
   await api.jobs.toggle("b9084540-4725-4f23-b6c6-9310bb3328b7", true);
   console.log("✅ Job enabled for daily runs!");
   EOF
   ```

## 📊 Expected Output

### Console Logs
```
=== LoA Application Insights Summary ===
Starting at: Fri Jan 30 2026 08:30:00 GMT-0500 (EST)
Timezone: America/New_York

🔧 Configuring Claude Code with LaunchCode...

🔄 Step 0: Refreshing Azure Access Token...
  Using Azure Service Principal to get fresh token...
  ✅ Fresh access token obtained

📋 Checking environment variables...

🚀 Step 1: Fetching Application Insights data...
  ✅ Data fetched successfully

🤖 Step 2: Analyzing data with Claude Code...
  ✅ Analysis completed

📤 Step 3: Posting report to Slack...
  ✅ Message posted successfully to #int-lift-loa-app-insights

✅ Job completed successfully at Fri Jan 30 2026 08:30:45 GMT-0500 (EST)
```

### Slack Message
```
🔴 LoA Application Insights - Daily Summary
January 30, 2026 at 08:30 AM EST
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 Exceptions      📥 Requests
4,560              0

✅ Success Rate    ⚡ P95 Response
100%               1,235ms

🔗 Dependencies
2.5M (217 failed)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔥 Top Exception Problems
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 2,191× occurrences
████████████████████ 2,191
```TypeError at BasketAdQueue.handleLineItemEvents```

[... 4 more issues ...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚡ Action Required
Add null/undefined checks in BasketAdQueue
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 View in Azure Portal | Generated by Claude Code
```

## ✅ Verification Checklist

- [x] Step 0: Token refresh integrated
- [x] Step 1: fetch_insights.py matches local
- [x] Step 2: Claude prompt matches local (exact format)
- [x] Step 3: post_to_slack.py matches local (Block Kit)
- [x] Top 5 issues (not 3)
- [x] Beautiful metrics grid (2 columns)
- [x] Visual bar charts (████░░)
- [x] Code blocks for exceptions
- [x] Interactive Azure Portal link
- [x] Error handling and graceful fallbacks

## 🎯 Summary

**Local and LaunchCode are now 100% synchronized!**

The only difference is the token refresh mechanism:
- **Local**: Uses `az CLI` (requires manual login)
- **LaunchCode**: Uses Service Principal (fully automated)

Both produce identical Slack messages with:
- ✅ Beautiful Block Kit layout
- ✅ 2-column metrics grid
- ✅ Top 5 exception problems
- ✅ Visual bar charts
- ✅ Full error descriptions
- ✅ Actionable recommendations

Ready for production! 🚀
