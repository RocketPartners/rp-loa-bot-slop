#!/usr/bin/env python3
"""
LoA Application Insights Summary
Fetches App Insights data using Azure REST API, analyzes it, and posts to Slack
"""
import os
import json
import requests
from datetime import datetime, timedelta
from anthropic import Anthropic
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configuration
WORKSPACE_ID = os.environ.get('AZURE_APP_INSIGHTS_WORKSPACE_ID')
ACCESS_TOKEN = os.environ.get('AZURE_ACCESS_TOKEN')
SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', '#int-lift-loa-app-insights')
SLACK_TOKEN = os.environ['SLACK_BOT_TOKEN']

def fetch_app_insights():
    """Fetch Application Insights data for the last 24 hours using REST API"""
    print("Fetching Application Insights data via REST API...")

    # KQL query to get key metrics
    query = """
    union requests, exceptions, dependencies, traces
    | where timestamp > ago(24h)
    | summarize
        TotalRequests = countif(itemType == 'request'),
        FailedRequests = countif(itemType == 'request' and success == false),
        TotalExceptions = countif(itemType == 'exception'),
        AvgResponseTime = avgif(duration, itemType == 'request'),
        P95ResponseTime = percentileif(duration, 95, itemType == 'request'),
        TotalDependencies = countif(itemType == 'dependency'),
        FailedDependencies = countif(itemType == 'dependency' and success == false)
    | extend SuccessRate = round(100.0 * (TotalRequests - FailedRequests) / TotalRequests, 2)
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

        print(f"Querying Application Insights workspace: {WORKSPACE_ID}")
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()

        # Parse results
        if 'tables' in result and len(result['tables']) > 0:
            table = result['tables'][0]
            columns = [col['name'] for col in table['columns']]
            rows = [dict(zip(columns, row)) for row in table['rows']]
            print(f"✅ Retrieved {len(rows)} rows of data")
            return rows
        else:
            print("⚠️  No data returned from query")
            return []

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            error_msg = "Authentication failed - token may be expired or invalid"
        elif e.response.status_code == 403:
            error_msg = "Access denied - insufficient permissions for Application Insights"
        else:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}
    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}

def analyze_insights(data):
    """Use Claude to analyze the insights and generate a report"""
    print("Analyzing insights with Claude...")

    # ANTHROPIC_API_KEY is auto-injected by LaunchCode platform
    client = Anthropic()

    prompt = f"""
    You are analyzing Application Insights data for the LoA (Letter of Authorization) application.

    Here is the data from the last 24 hours:
    {json.dumps(data, indent=2)}

    Please provide a concise daily summary report that includes:
    1. Overall health status (Healthy, Warning, Critical)
    2. Key metrics summary (requests, success rate, response times, errors)
    3. Notable observations or anomalies
    4. Recommendations if any issues are detected

    Format the response in a clear, readable manner suitable for Slack posting.
    Use emojis appropriately to highlight status (✅ 🟡 🔴).
    """

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}]
    )

    return message.content[0].text

def post_to_slack(report):
    """Post the analysis report to Slack"""
    print(f"Posting report to Slack channel {SLACK_CHANNEL}...")

    client = WebClient(token=SLACK_TOKEN)

    try:
        # Create a formatted message
        message_text = f"*LoA Application Insights - Daily Summary*\n_{datetime.now().strftime('%Y-%m-%d %H:%M %Z')}_\n\n{report}"

        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message_text,
            mrkdwn=True
        )

        print(f"✅ Message posted successfully: {response['ts']}")
        return response

    except SlackApiError as e:
        print(f"❌ Error posting to Slack: {e.response['error']}")
        raise

def main():
    """Main execution function"""
    print("=" * 60)
    print("Starting LoA Application Insights Summary job...")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print("=" * 60)

    # Validate required environment variables
    if not ACCESS_TOKEN:
        print("❌ AZURE_ACCESS_TOKEN is required")
        return 1

    if not WORKSPACE_ID:
        print("❌ AZURE_APP_INSIGHTS_WORKSPACE_ID is required")
        return 1

    try:
        # Fetch data from Application Insights
        insights_data = fetch_app_insights()

        if isinstance(insights_data, dict) and 'error' in insights_data:
            error_msg = f"❌ Failed to fetch Application Insights data: {insights_data['error']}"
            print(error_msg)
            post_to_slack(error_msg)
            return 1

        if not insights_data:
            warning_msg = "⚠️  No data available from Application Insights for the last 24 hours"
            print(warning_msg)
            post_to_slack(warning_msg)
            return 0

        # Analyze the data
        analysis_report = analyze_insights(insights_data)

        # Post to Slack
        post_to_slack(analysis_report)

        print("=" * 60)
        print("✅ Job completed successfully")
        print("=" * 60)
        return 0

    except Exception as e:
        error_msg = f"❌ Error in LoA Application Insights job: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        try:
            post_to_slack(error_msg)
        except:
            pass
        return 1

if __name__ == '__main__':
    exit(main())
