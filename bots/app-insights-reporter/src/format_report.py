#!/usr/bin/env python3
"""
Format Application Insights and business metrics into a report
More reliable than asking Claude to format
"""
import json
import sys
from datetime import datetime

def format_report(insights_path='insights_data.json', business_path='business_metrics.json'):
    """Format the report from JSON files"""

    try:
        # Read insights data
        with open(insights_path, 'r') as f:
            insights = json.load(f)

        # Read business metrics
        with open(business_path, 'r') as f:
            business = json.load(f)

        # Extract summary metrics
        summary = next((d for d in insights.get('data', []) if d.get('DataType') == 'Summary'), {})

        total_exceptions = summary.get('TotalExceptions') or 0
        total_requests = summary.get('TotalRequests') or 0
        total_dependencies = summary.get('TotalDependencies') or 0
        failed_dependencies = summary.get('FailedDependencies') or 0
        p95_response = summary.get('P95ResponseTime')
        if p95_response:
            p95_response = int(p95_response)
        else:
            p95_response = 0

        # Extract business metrics
        biz_data = business.get('data', {})
        offers = biz_data.get('offers_last_24h') or 0
        heartbeats = biz_data.get('player_heartbeats') or 0
        upsells = biz_data.get('upsells') or 0

        # Extract exception groups (top 5)
        exception_groups = [d for d in insights.get('data', []) if d.get('DataType') == 'ExceptionGroup']
        exception_groups.sort(key=lambda x: x.get('Count', 0), reverse=True)
        top_issues = exception_groups[:5]

        # Determine status emoji
        if total_exceptions > 5000:
            status_emoji = "🔴"
        elif total_exceptions > 2000:
            status_emoji = "🟡"
        else:
            status_emoji = "✅"

        # Format date
        today = datetime.now().strftime("%B %d, %Y")

        # Build report
        report = f"""{status_emoji} LoA Player Health Status - {today}

Metrics: {total_exceptions:,} exceptions | {total_requests:,} requests | {total_dependencies:,} dependencies ({failed_dependencies:,} failed) | P95: {p95_response}ms

Business Metrics: {offers:,} offers | {heartbeats:,} player heartbeats | {upsells:,} upsells

Top 5 Problems:
"""

        # Add top issues
        for i, issue in enumerate(top_issues, 1):
            count = issue.get('Count', 0)
            error_type = issue.get('type', 'Unknown')
            operation = issue.get('operation_Name', 'Unknown')
            message = issue.get('SampleMessage', '')

            # Shorten message
            if len(message) > 80:
                message = message[:77] + '...'

            # Extract just the error description
            if ' - ' in message:
                message = message.split(' - ', 1)[1]
            elif ': ' in message:
                message = message.split(': ', 1)[1]

            report += f"{i}. **{count:,}×** {error_type} at {operation} - {message}\n"

        # Add action (simple heuristic based on top issue)
        if top_issues:
            top_issue = top_issues[0]
            top_operation = top_issue.get('operation_Name', 'Unknown')
            top_count = top_issue.get('Count', 0)
            percentage = int((top_count / total_exceptions * 100)) if total_exceptions > 0 else 0

            report += f"\n🚨 Action Required: Investigate {top_operation} null-safety - accounts for {percentage}% of exceptions\n"
        else:
            report += "\n✅ No major issues detected\n"

        return report

    except Exception as e:
        print(f"❌ Error formatting report: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None

if __name__ == '__main__':
    insights_file = sys.argv[1] if len(sys.argv) > 1 else 'insights_data.json'
    business_file = sys.argv[2] if len(sys.argv) > 2 else 'business_metrics.json'

    report = format_report(insights_file, business_file)
    if report:
        print(report)
    else:
        sys.exit(1)
