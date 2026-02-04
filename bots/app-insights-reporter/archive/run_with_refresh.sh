#!/bin/bash
set -e

echo "=== LoA Application Insights Summary ==="
echo "Starting at: $(date)"
echo "Timezone: America/New_York"

# Configure Claude Code with LaunchCode (if API credentials provided)
if [ -n "$LAUNCHCODE_API_URL" ] && [ -n "$LAUNCHCODE_API_KEY" ]; then
  echo "🔧 Configuring Claude Code with LaunchCode..."
  curl -fsSL -H "X-API-Key: $LAUNCHCODE_API_KEY" "$LAUNCHCODE_API_URL/api/claude/setup" | python3
fi

# Verify environment variables
echo "📋 Checking environment variables..."
[ -z "$AZURE_APP_INSIGHTS_WORKSPACE_ID" ] && echo "⚠️  AZURE_APP_INSIGHTS_WORKSPACE_ID not set"
[ -z "$SLACK_BOT_TOKEN" ] && echo "❌ SLACK_BOT_TOKEN not set - REQUIRED"

# Step 0: Refresh Azure Access Token
echo "🔄 Step 0: Refreshing Azure Access Token..."
if [ -n "$AZURE_TENANT_ID" ] && [ -n "$AZURE_CLIENT_ID" ] && [ -n "$AZURE_CLIENT_SECRET" ]; then
  echo "Using Azure Service Principal to get fresh token..."

  # Get token using Azure REST API
  TOKEN_RESPONSE=$(curl -s -X POST "https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "client_id=${AZURE_CLIENT_ID}" \
    -d "client_secret=${AZURE_CLIENT_SECRET}" \
    -d "scope=https://api.applicationinsights.io/.default" \
    -d "grant_type=client_credentials")

  AZURE_ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))")

  if [ -z "$AZURE_ACCESS_TOKEN" ]; then
    echo "❌ Failed to get access token"
    echo "Response: $TOKEN_RESPONSE"
    exit 1
  fi

  export AZURE_ACCESS_TOKEN
  echo "✅ Fresh access token obtained"
elif [ -n "$AZURE_ACCESS_TOKEN" ]; then
  echo "⚠️  Using pre-set AZURE_ACCESS_TOKEN (will expire after 1 hour)"
  echo "💡 Tip: Set AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET for automatic token refresh"
else
  echo "❌ No Azure credentials found"
  echo "Please set either:"
  echo "  - AZURE_ACCESS_TOKEN (expires in 1 hour), or"
  echo "  - AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET (for automatic refresh)"
  exit 1
fi

# Step 1: Fetch Application Insights data
echo "🚀 Step 1: Fetching Application Insights data..."
python3 /app/fetch_insights.py > /app/insights_data.json

if [ $? -ne 0 ]; then
  echo "❌ Failed to fetch Application Insights data"
  cat /app/insights_data.json
  exit 1
fi

echo "✅ Data fetched successfully"

# Step 2: Analyze with Claude Code
echo "🤖 Step 2: Analyzing data with Claude Code..."
ANALYSIS=$(echo "You are analyzing Application Insights data for the LoA (Letter of Authorization) application.

Here is the data from the last 24 hours in /app/insights_data.json

Please provide a concise daily summary report that includes:
1. Overall health status (Healthy, Warning, Critical)
2. Key metrics summary (requests, success rate, response times, errors)
3. Top exception problems with counts and specific error messages
4. Notable observations or anomalies
5. Actionable recommendations for each major issue

Format the response in a clear, readable manner suitable for Slack posting.
Use emojis appropriately to highlight status (✅ 🟡 🔴).

Important: Output ONLY the report text, no preamble or explanation." | claude -p --dangerously-skip-permissions)

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
