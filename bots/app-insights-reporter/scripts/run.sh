#!/bin/bash
set -e

echo "=== LoA Application Insights Summary ==="
echo "Starting at: $(date)"
echo "Timezone: America/New_York"
echo "Authentication: Azure Access Token"

# Configure Claude Code with LaunchCode (if API credentials provided)
if [ -n "$LAUNCHCODE_API_URL" ] && [ -n "$LAUNCHCODE_API_KEY" ]; then
  echo "🔧 Configuring Claude Code with LaunchCode..."
  curl -fsSL -H "X-API-Key: $LAUNCHCODE_API_KEY" "$LAUNCHCODE_API_URL/api/claude/setup" | python3
fi

# Verify environment variables
echo "📋 Checking environment variables..."
[ -z "$AZURE_APP_INSIGHTS_WORKSPACE_ID" ] && echo "⚠️  AZURE_APP_INSIGHTS_WORKSPACE_ID not set"
[ -z "$AZURE_ACCESS_TOKEN" ] && echo "❌ AZURE_ACCESS_TOKEN not set - REQUIRED"
[ -z "$SLACK_BOT_TOKEN" ] && echo "❌ SLACK_BOT_TOKEN not set - REQUIRED"

# Verify Redshift credentials (optional - for business metrics)
if [ -n "$REDSHIFT_HOST" ]; then
  echo "✅ Redshift configuration detected"
  [ -z "$REDSHIFT_USER" ] && echo "⚠️  REDSHIFT_USER not set"
  [ -z "$REDSHIFT_PASSWORD" ] && echo "⚠️  REDSHIFT_PASSWORD not set"
  [ -z "$REDSHIFT_DATABASE" ] && echo "⚠️  REDSHIFT_DATABASE not set"
fi

if [ -n "$AZURE_ACCESS_TOKEN" ]; then
  echo "✅ Azure access token configured"
  echo "ℹ️  Note: Access tokens expire after 1 hour. Refresh before scheduled runs."
else
  echo "❌ No Azure access token found"
  exit 1
fi

# Step 1: Fetch Application Insights data
echo "🚀 Step 1: Fetching Application Insights data..."
python3 /app/fetch_insights.py > /app/insights_data.json

if [ $? -ne 0 ]; then
  echo "❌ Failed to fetch Application Insights data"
  exit 1
fi

echo "✅ Data fetched successfully"

# Step 1.5: Fetch business metrics from Redshift (optional)
if [ -n "$REDSHIFT_HOST" ] && [ -n "$REDSHIFT_USER" ] && [ -n "$REDSHIFT_PASSWORD" ]; then
  echo "📊 Step 1.5: Fetching business metrics from Redshift..."
  python3 /app/fetch_business_metrics.py > /app/business_metrics.json 2>/dev/null

  if [ $? -eq 0 ]; then
    echo "✅ Business metrics fetched successfully"
  else
    echo "⚠️  Business metrics fetch failed (non-critical, continuing...)"
    echo '{"success": false, "data": {}}' > /app/business_metrics.json
  fi
else
  echo "ℹ️  Skipping business metrics (Redshift not configured)"
  echo '{"success": false, "data": {}}' > /app/business_metrics.json
fi

# Step 2: Analyze with Claude Code
echo "🤖 Step 2: Analyzing data with Claude Code..."
ANALYSIS=$(echo "Analyze Application Insights data for LoA Player and create a daily summary report.

Data in /app/insights_data.json contains summary metrics, 50 recent exceptions, and top 20 exception groups.
Business metrics in /app/business_metrics.json contains offers, player heartbeats, and upsells (if available).

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

# Step 3: Post to Slack
echo "📤 Step 3: Posting report to Slack..."
echo "$ANALYSIS" | python3 /app/post_to_slack.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
  echo "✅ Job completed successfully at $(date)"
else
  echo "❌ Job failed with exit code $exit_code at $(date)"
fi

exit $exit_code
