#!/usr/bin/env python3
"""
Fetch Application Insights data from Azure
Outputs JSON to stdout
"""
import os
import json
import requests
import sys
import time
from get_date_range import get_date_range

# Configuration
WORKSPACE_ID = os.environ.get('AZURE_APP_INSIGHTS_WORKSPACE_ID')
ACCESS_TOKEN = os.environ.get('AZURE_ACCESS_TOKEN')

def fetch_app_insights():
    """Fetch Application Insights data with dynamic date range using REST API"""

    start_time = time.time()

    # Get date range based on day of week
    date_info = get_date_range()
    days_back = date_info['days_back']

    # KQL query to get summary metrics, detailed exceptions, and hourly timeline
    query = f"""
    let summary = union requests, exceptions, dependencies, traces
    | where timestamp > ago({days_back}d)
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
    | where timestamp > ago({days_back}d)
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
    | where timestamp > ago({days_back}d)
    | summarize
        Count = count(),
        LatestOccurrence = max(timestamp),
        SampleMessage = any(outerMessage)
        by problemId, type, operation_Name
    | order by Count desc
    | take 20
    | extend DataType = "ExceptionGroup";
    let exceptionTimeline = exceptions
    | where timestamp > ago({days_back}d)
    | summarize
        Count = count()
        by bin(timestamp, 1h)
    | order by timestamp asc
    | extend DataType = "Timeline";
    union summary, exceptionDetails, exceptionGroups, exceptionTimeline
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
        elapsed_time = time.time() - start_time

        if 'tables' in result and len(result['tables']) > 0:
            table = result['tables'][0]
            columns = [col['name'] for col in table['columns']]
            rows = [dict(zip(columns, row)) for row in table['rows']]
            return {
                "success": True,
                "data": rows,
                "date_range": {
                    "date_range": date_info['date_range'],
                    "days_text": date_info['days_text'],
                    "days_back": date_info['days_back']
                },
                "timing": {
                    "app_insights_seconds": round(elapsed_time, 2)
                }
            }
        else:
            return {
                "success": True,
                "data": [],
                "message": "No data returned from query",
                "date_range": {
                    "date_range": date_info['date_range'],
                    "days_text": date_info['days_text'],
                    "days_back": date_info['days_back']
                },
                "timing": {
                    "app_insights_seconds": round(elapsed_time, 2)
                }
            }

    except requests.exceptions.HTTPError as e:
        elapsed_time = time.time() - start_time
        if e.response.status_code == 401:
            error_msg = "Authentication failed - token may be expired or invalid"
        elif e.response.status_code == 403:
            error_msg = "Access denied - insufficient permissions for Application Insights"
        else:
            error_msg = f"HTTP error {e.response.status_code}: {e.response.text}"
        return {
            "success": False,
            "error": error_msg,
            "timing": {"app_insights_seconds": round(elapsed_time, 2)}
        }
    except Exception as e:
        elapsed_time = time.time() - start_time
        return {
            "success": False,
            "error": str(e),
            "timing": {"app_insights_seconds": round(elapsed_time, 2)}
        }

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
