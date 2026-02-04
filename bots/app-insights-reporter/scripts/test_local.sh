#!/bin/bash
set -e

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BOT_DIR="$( cd "$SCRIPT_DIR/.." && pwd )"

echo "=== LoA Application Insights Summary (Local Test) ==="
echo "Starting at: $(date)"
echo "Bot directory: $BOT_DIR"

# Step 0: Refresh Azure Access Token
echo ""
echo "🔄 Step 0: Refreshing Azure Access Token..."
if [ -f "$BOT_DIR/src/refresh_token.sh" ]; then
  cd "$BOT_DIR"
  ./src/refresh_token.sh
  if [ $? -eq 0 ]; then
    echo "✅ Token refreshed successfully"
    # Reload environment variables after token refresh (filter out comments)
    export $(grep -v '^#' .env | xargs)
  else
    echo "⚠️  Token refresh failed, will use existing token"
  fi
else
  echo "⚠️  refresh_token.sh not found, using existing token"
fi

# Check if environment variables are set
if [ -z "$AZURE_APP_INSIGHTS_WORKSPACE_ID" ] || [ -z "$AZURE_ACCESS_TOKEN" ] || [ -z "$SLACK_BOT_TOKEN" ]; then
  echo "❌ Missing required environment variables"
  echo "Please set:"
  echo "  - AZURE_APP_INSIGHTS_WORKSPACE_ID"
  echo "  - AZURE_ACCESS_TOKEN"
  echo "  - SLACK_BOT_TOKEN"
  echo ""
  echo "You can source them from .env:"
  echo "  export \$(grep -v '^#' .env | xargs)"
  exit 1
fi

# Step 1: Fetch Application Insights data
echo "🚀 Step 1: Fetching Application Insights data..."
python3 "$BOT_DIR/src/fetch_insights.py" > "$BOT_DIR/insights_data.json"

if [ $? -ne 0 ]; then
  echo "❌ Failed to fetch Application Insights data"
  cat "$BOT_DIR/insights_data.json"
  exit 1
fi

echo "✅ Data fetched successfully"
cat "$BOT_DIR/insights_data.json"

# Step 1.5: Fetch business metrics from Redshift (optional)
echo ""
if [ -n "$REDSHIFT_HOST" ] && [ -n "$REDSHIFT_USER" ] && [ -n "$REDSHIFT_PASSWORD" ]; then
  echo "📊 Step 1.5: Fetching business metrics from Redshift..."
  python3 "$BOT_DIR/src/fetch_business_metrics.py" > "$BOT_DIR/business_metrics.json" 2>/dev/null

  if [ $? -eq 0 ]; then
    echo "✅ Business metrics fetched successfully"
    cat "$BOT_DIR/business_metrics.json"
  else
    echo "⚠️  Business metrics fetch failed (non-critical, continuing...)"
    echo '{"success": false, "data": {}}' > "$BOT_DIR/business_metrics.json"
  fi
else
  echo "ℹ️  Skipping business metrics (Redshift not configured)"
  echo '{"success": false, "data": {}}' > "$BOT_DIR/business_metrics.json"
fi

# Step 2: Analyze with Claude Code
echo ""
echo "🤖 Step 2: Analyzing data with Claude Code..."
ANALYSIS=$(echo "Analyze Application Insights data for LoA Player and create a daily summary report.

Data: \$(cat $BOT_DIR/insights_data.json)
Business Metrics: \$(cat $BOT_DIR/business_metrics.json)

Contains summary metrics, 50 recent exceptions, and top 20 exception groups.

Create report with EXACTLY this format:

🔴 LoA Player Health Status - [Date]

Metrics: [X] exceptions | [Y] requests | [Z] dependencies ([N] failed) | P95: [Ms]ms

Business Metrics (if available): [N] offers | [M] player heartbeats | [K] upsells

Top 5 Problems:
1. **[count]×** [ProblemId] - [brief description]
2. **[count]×** [ProblemId] - [brief description]
3. **[count]×** [ProblemId] - [brief description]
4. **[count]×** [ProblemId] - [brief description]
5. **[count]×** [ProblemId] - [brief description]

🚨 Action Required: [One sentence with specific action]

IMPORTANT:
- Use EXACTLY format above
- Include '×' symbol after counts
- Use '**' for bold
- Show all 5 issues
- Be specific about error types

Output ONLY the report." | claude -p --dangerously-skip-permissions)

if [ $? -ne 0 ]; then
  echo "❌ Claude Code analysis failed"
  exit 1
fi

echo "✅ Analysis completed"
echo ""
echo "=== ANALYSIS REPORT ==="
echo "$ANALYSIS"
echo "===================="

# Step 3: Post to Slack
echo ""
echo "📤 Step 3: Posting report to Slack..."
echo "$ANALYSIS" | python3 "$BOT_DIR/src/post_to_slack.py"

if [ $? -eq 0 ]; then
  echo "✅ Job completed successfully at $(date)"
else
  echo "❌ Failed to post to Slack at $(date)"
  exit 1
fi
