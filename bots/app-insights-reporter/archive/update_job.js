#!/usr/bin/env node

const fetchInsights = `#!/usr/bin/env python3
"""
Fetch Application Insights data from Azure
Outputs JSON to stdout
"""
import os
import json
import requests
import sys

# Configuration
WORKSPACE_ID = os.environ.get('AZURE_APP_INSIGHTS_WORKSPACE_ID')
ACCESS_TOKEN = os.environ.get('AZURE_ACCESS_TOKEN')

def fetch_app_insights():
    """Fetch Application Insights data for the last 24 hours using REST API"""

    # KQL query to get summary metrics and detailed exceptions
    query = """
    let summary = union requests, exceptions, dependencies, traces
    | where timestamp > ago(24h)
    | summarize
        TotalRequests = countif(itemType == 'request'),
        FailedRequests = countif(itemType == 'request' and success == false),
        TotalExceptions = countif(itemType == 'exception'),
        AvgResponseTime = avgif(duration, itemType == 'request'),
        P95ResponseTime = percentile(duration, 95),
        TotalDependencies = countif(itemType == 'dependency'),
        FailedDependencies = countif(itemType == 'dependency' and success == false)
    | extend SuccessRate = iff(TotalRequests > 0, round(100.0 * (TotalRequests - FailedRequests) / TotalRequests, 2), 100.0)
    | extend DataType = "Summary";
    let exceptionDetails = exceptions
    | where timestamp > ago(24h)
    | project
        DataType = "Exception",
        timestamp,
        type,
        outerMessage,
        problemId,
        operation_Name,
        cloud_RoleName,
        severityLevel
    | order by timestamp desc
    | take 50;
    let exceptionGroups = exceptions
    | where timestamp > ago(24h)
    | summarize
        Count = count(),
        LatestOccurrence = max(timestamp),
        SampleMessage = any(outerMessage)
        by problemId, type, operation_Name
    | order by Count desc
    | take 20
    | extend DataType = "ExceptionGroup";
    union summary, exceptionDetails, exceptionGroups
    """

    try:
        # Call Azure Application Insights REST API
        url = f'https://api.applicationinsights.io/v1/apps/{WORKSPACE_ID}/query'
        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'query': query
        }

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()

        # Parse results
        if 'tables' in result and len(result['tables']) > 0:
            table = result['tables'][0]
            columns = [col['name'] for col in table['columns']]
            rows = [dict(zip(columns, row)) for row in table['rows']]
            return {"success": True, "data": rows}
        else:
            return {"success": True, "data": [], "message": "No data returned from query"}

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            error_msg = "Authentication failed - token may be expired or invalid"
        elif e.response.status_code == 403:
            error_msg = "Access denied - insufficient permissions for Application Insights"
        else:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        return {"success": False, "error": error_msg}
    except Exception as e:
        return {"success": False, "error": str(e)}

def main():
    """Main execution function"""

    # Validate required environment variables
    if not ACCESS_TOKEN:
        print(json.dumps({"success": False, "error": "AZURE_ACCESS_TOKEN is required"}), file=sys.stderr)
        return 1

    if not WORKSPACE_ID:
        print(json.dumps({"success": False, "error": "AZURE_APP_INSIGHTS_WORKSPACE_ID is required"}), file=sys.stderr)
        return 1

    # Fetch data
    result = fetch_app_insights()

    # Output JSON to stdout
    print(json.dumps(result, indent=2))

    # Return appropriate exit code
    return 0 if result.get("success") else 1

if __name__ == '__main__':
    sys.exit(main())
`;

const postToSlack = `#!/usr/bin/env python3
"""
Post analysis report to Slack
Reads report from stdin
"""
import os
import sys
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configuration
SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', '#int-lift-loa-app-insights')
SLACK_TOKEN = os.environ.get('SLACK_BOT_TOKEN')

def post_to_slack(report):
    """Post the analysis report to Slack"""

    if not SLACK_TOKEN:
        print("❌ SLACK_BOT_TOKEN is required", file=sys.stderr)
        return 1

    client = WebClient(token=SLACK_TOKEN)

    try:
        # Create a formatted message
        message_text = f"*LoA Application Insights - Daily Summary*\\n_{datetime.now().strftime('%Y-%m-%d %H:%M %Z')}_\\n\\n{report}"

        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message_text,
            mrkdwn=True
        )

        print(f"✅ Message posted successfully to {SLACK_CHANNEL}")
        return 0

    except SlackApiError as e:
        print(f"❌ Error posting to Slack: {e.response['error']}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}", file=sys.stderr)
        return 1

def main():
    """Main execution function"""

    # Read report from stdin
    report = sys.stdin.read().strip()

    if not report:
        print("❌ No report content received from stdin", file=sys.stderr)
        return 1

    return post_to_slack(report)

if __name__ == '__main__':
    sys.exit(main())
`;

const runSh = `#!/bin/bash
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
`;

const dockerfile = `# Use Amazon ECR to avoid Docker Hub rate limits
FROM public.ecr.aws/docker/library/python:3.11-slim

# Install system dependencies including Node.js for Claude Code
RUN apt-get update && apt-get install -y --no-install-recommends \\
    bash \\
    curl \\
    ca-certificates \\
    nodejs \\
    npm \\
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI
RUN npm install -g @anthropics/claude-code

# Install Python dependencies (no longer need anthropic SDK)
RUN pip install --no-cache-dir \\
    slack-sdk \\
    requests \\
    python-dateutil

# Set working directory
WORKDIR /app

# Set shell to bash
SHELL ["/bin/bash", "-c"]

CMD ["bash", "/app/run.sh"]
`;

const config = {
  files: [
    { mode: "755", path: "/app/run.sh", content: runSh },
    { mode: "755", path: "/app/fetch_insights.py", content: fetchInsights },
    { mode: "755", path: "/app/post_to_slack.py", content: postToSlack }
  ],
  dockerfile: dockerfile
};

console.log(JSON.stringify(config, null, 2));
