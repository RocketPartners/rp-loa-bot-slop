#!/usr/bin/env python3
"""
Explore custom events and metrics in Application Insights
to see what business metrics are available
"""
import os
import json
import requests
import sys

# Configuration
WORKSPACE_ID = os.environ.get('AZURE_APP_INSIGHTS_WORKSPACE_ID')
ACCESS_TOKEN = os.environ.get('AZURE_ACCESS_TOKEN')

def explore_custom_data():
    """Explore what custom events and metrics are available"""

    # Query to discover custom events
    query = """
    // Get all custom event names from last 24 hours
    let customEvents = customEvents
    | where timestamp > ago(24h)
    | summarize Count = count() by name
    | order by Count desc
    | take 50;

    // Get all custom metric names
    let customMetrics = customMetrics
    | where timestamp > ago(24h)
    | summarize Count = count() by name
    | order by Count desc
    | take 50;

    // Get sample traces that might contain business metrics
    let sampleTraces = traces
    | where timestamp > ago(24h)
    | where message contains "player" or message contains "offer" or message contains "upsell" or message contains "heartbeat"
    | project timestamp, message, severityLevel
    | take 20;

    // Check for pageViews or custom dimensions
    let pageViews = pageViews
    | where timestamp > ago(24h)
    | summarize Count = count() by name
    | order by Count desc
    | take 20;

    union
        (customEvents | extend Type = "CustomEvent"),
        (customMetrics | extend Type = "CustomMetric"),
        (pageViews | extend Type = "PageView"),
        (sampleTraces | extend Type = "SampleTrace", Count = 1, name = substring(message, 0, 100))
    """

    try:
        url = f'https://api.applicationinsights.io/v1/apps/{WORKSPACE_ID}/query'
        headers = {
            'Authorization': f'Bearer {ACCESS_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {'query': query}

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        result = response.json()

        if 'tables' in result and len(result['tables']) > 0:
            table = result['tables'][0]
            columns = [col['name'] for col in table['columns']]
            rows = [dict(zip(columns, row)) for row in table['rows']]

            print("=" * 80)
            print("CUSTOM EVENTS & METRICS AVAILABLE IN APPLICATION INSIGHTS")
            print("=" * 80)

            # Group by type
            events = [r for r in rows if r.get('Type') == 'CustomEvent']
            metrics = [r for r in rows if r.get('Type') == 'CustomMetric']
            pages = [r for r in rows if r.get('Type') == 'PageView']
            traces = [r for r in rows if r.get('Type') == 'SampleTrace']

            if events:
                print("\n📊 CUSTOM EVENTS (last 24h):")
                for event in events:
                    print(f"  - {event.get('name')}: {event.get('Count')} occurrences")

            if metrics:
                print("\n📈 CUSTOM METRICS (last 24h):")
                for metric in metrics:
                    print(f"  - {metric.get('name')}: {metric.get('Count')} data points")

            if pages:
                print("\n📄 PAGE VIEWS (last 24h):")
                for page in pages:
                    print(f"  - {page.get('name')}: {page.get('Count')} views")

            if traces:
                print("\n🔍 SAMPLE TRACES (mentioning players/offers/upsells):")
                for trace in traces[:10]:
                    print(f"  - {trace.get('name')[:100]}")

            print("\n" + "=" * 80)
            print("💡 TIP: Look for event names like:")
            print("  - PlayerHeartbeat, PlayerConnected, PlayerActive")
            print("  - OfferDisplayed, OfferShown, OfferAccepted")
            print("  - UpsellShown, UpsellAccepted, UpsellDeclined")
            print("=" * 80)

            return {"success": True, "data": rows}
        else:
            return {"success": True, "data": [], "message": "No data returned"}

    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == '__main__':
    if not ACCESS_TOKEN or not WORKSPACE_ID:
        print("❌ Please set AZURE_ACCESS_TOKEN and AZURE_APP_INSIGHTS_WORKSPACE_ID")
        sys.exit(1)

    result = explore_custom_data()

    if not result.get("success"):
        print(f"❌ Error: {result.get('error')}")
        sys.exit(1)
