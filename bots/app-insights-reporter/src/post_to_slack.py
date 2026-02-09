#!/usr/bin/env python3
"""
Post analysis report to Slack with Block Kit formatting
Reads report from stdin and parses it for rich formatting
"""
import os
import sys
import re
import json
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configuration
SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', '#int-lift-loa-app-insights')
SLACK_TOKEN = os.environ.get('SLACK_BOT_TOKEN')

def create_bar_chart(count, max_count):
    """Create a simple ASCII bar chart"""
    bar_length = int((count / max_count) * 20) if max_count > 0 else 0
    bar = "█" * bar_length + "░" * (20 - bar_length)
    return bar

def generate_chart_url(timeline_data):
    """Generate QuickChart URL for exception timeline"""
    if not timeline_data:
        return None

    # Sort by timestamp and get only last 24 data points (hours)
    # This prevents URL from being too long when we have multi-day data
    sorted_data = sorted(timeline_data, key=lambda x: x.get('timestamp', ''))
    recent_data = sorted_data[-24:] if len(sorted_data) > 24 else sorted_data

    # Extract hours and counts
    labels = []
    data = []
    for entry in recent_data:
        # Parse timestamp to hour
        timestamp = entry.get('timestamp', '')
        count = entry.get('Count', 0)

        if timestamp:
            # Extract hour from timestamp (e.g., "2026-01-30T08:00:00Z" -> "08:00")
            try:
                hour = timestamp.split('T')[1][:5]  # "08:00:00" -> "08:00"
                labels.append(hour)
                data.append(count)
            except:
                continue

    if not data:
        return None

    # Build Chart.js config matching the style from the image
    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [{
                "label": "Exceptions",
                "data": data,
                "backgroundColor": "rgba(220,38,38,0.9)",
                "borderColor": "rgba(220,38,38,1)",
                "borderWidth": 1
            }]
        },
        "options": {
            "responsive": True,
            "maintainAspectRatio": True,
            "legend": {"display": False},
            "title": {
                "display": True,
                "text": "Exception Timeline - Last 24 Hours",
                "fontSize": 18,
                "fontColor": "#e5e7eb"
            },
            "scales": {
                "yAxes": [{
                    "ticks": {
                        "beginAtZero": True,
                        "fontColor": "#9ca3af"
                    },
                    "scaleLabel": {
                        "display": True,
                        "labelString": "Count",
                        "fontColor": "#9ca3af"
                    },
                    "gridLines": {
                        "color": "rgba(156,163,175,0.2)"
                    }
                }],
                "xAxes": [{
                    "ticks": {
                        "fontColor": "#9ca3af"
                    },
                    "scaleLabel": {
                        "display": True,
                        "labelString": "Time (UTC)",
                        "fontColor": "#9ca3af"
                    },
                    "gridLines": {
                        "color": "rgba(156,163,175,0.2)"
                    }
                }]
            }
        }
    }

    # URL encode the config
    import urllib.parse
    config_json = json.dumps(chart_config, separators=(',', ':'))  # Compact JSON
    encoded = urllib.parse.quote(config_json)

    # Use dark background to match Slack's dark mode
    chart_url = f"https://quickchart.io/chart?c={encoded}&w=800&h=400&bkg=%23111827&devicePixelRatio=2"

    # Check URL length (URLs over 2000 chars often fail)
    if len(chart_url) > 2000:
        print(f"⚠️  Chart URL too long ({len(chart_url)} chars), using ASCII fallback", file=sys.stderr)
        return None

    return chart_url

def create_ascii_chart(timeline_data):
    """Create ASCII bar chart for exception timeline"""
    if not timeline_data or len(timeline_data) == 0:
        return None

    # Sort and get last 12-24 hours for display
    sorted_data = sorted(timeline_data, key=lambda x: x.get('timestamp', ''))
    recent_data = sorted_data[-12:] if len(sorted_data) > 12 else sorted_data

    max_count = max([d.get('Count', 0) for d in recent_data], default=1)

    chart_lines = ["📊 *Exception Timeline (Last 12 Hours)*\n```"]

    for entry in recent_data:
        timestamp = entry.get('timestamp', '')
        count = entry.get('Count', 0)

        if timestamp:
            try:
                # Show time in format "Thu 08:00" or just "08:00"
                from datetime import datetime
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                time_label = dt.strftime('%H:%M')

                bar_length = int((count / max_count) * 20) if max_count > 0 else 0
                bar = "█" * bar_length
                chart_lines.append(f"{time_label} {bar} {count:>5}")
            except:
                continue

    chart_lines.append("```")
    return "\n".join(chart_lines)

def parse_report(report):
    """Parse the text report and extract structured data"""
    lines = report.strip().split('\n')

    # Extract status and title
    status_line = lines[0] if lines else ""
    status_emoji = "🟡"
    if "🔴" in status_line:
        status_emoji = "🔴"
    elif "✅" in status_line or "🟢" in status_line:
        status_emoji = "✅"

    # Extract metrics line - be more flexible
    metrics = ""
    business_metrics = ""
    for line in lines:
        # Look for business metrics line FIRST (before regular metrics)
        if "business" in line.lower() and "metric" in line.lower():
            if re.search(r'\d', line):
                business_metrics = line.replace("**Business Metrics**:", "").replace("Business Metrics:", "").strip()
                # Remove "(if available)" suffix
                business_metrics = re.sub(r'\s*\(if available\):?', '', business_metrics, flags=re.IGNORECASE)
                continue

        # Look for regular metrics line
        if not metrics and ("exception" in line.lower() or "request" in line.lower() or "dependencies" in line.lower() or "P95" in line or "p95" in line.lower()):
            if re.search(r'\d', line):  # Has numbers
                # Clean up the line
                metrics = line.replace("**Metrics**:", "").replace("**Metrics:**", "").replace("Metrics:", "").strip()
                # Don't break - keep looking for business metrics

    # Extract top issues - be more flexible with headers
    issues = []
    in_issues = False
    for i, line in enumerate(lines):
        line_lower = line.lower()
        # More flexible issue section detection
        if any(keyword in line_lower for keyword in ["top issues", "top problems", "top 5", "problems:", "issues:"]):
            in_issues = True
            continue

        if in_issues:
            # Try to match numbered issues with various formats
            # Format 1: "1. **2,190×** Description"
            match1 = re.search(r'^(\d+)\.\s*\*\*([0-9,]+)×?\*\*\s*[-–]?\s*(.+)', line.strip())
            # Format 2: "1. **2,190** - Description"
            match2 = re.search(r'^(\d+)\.\s*\*\*([0-9,]+)\*\*\s*[-–]\s*(.+)', line.strip())
            # Format 3: "1. 2,190× Description" (no bold)
            match3 = re.search(r'^(\d+)\.\s*([0-9,]+)×?\s*[-–]?\s*(.+)', line.strip())

            match = match1 or match2 or match3

            if match:
                count_str = match.group(2).replace(',', '')
                description = match.group(3).strip()
                issues.append({"count": int(count_str), "description": description})
            elif line.strip() and not line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.')):
                # End of issues section
                if issues:
                    break

    # Extract action
    action = ""
    for line in lines:
        if "action required" in line.lower() or "🚨" in line:
            action = re.sub(r'\*\*Action Required:?\*\*|Action Required:?|🚨', '', line, flags=re.IGNORECASE).strip()
            if action:
                break

    return status_emoji, metrics, business_metrics, issues, action

def post_to_slack(report, insights_data_path='/app/insights_data.json', business_metrics_path='/app/business_metrics.json'):
    """Post the analysis report to Slack with Block Kit formatting"""

    if not SLACK_TOKEN:
        print("❌ SLACK_BOT_TOKEN is required", file=sys.stderr)
        return 1

    client = WebClient(token=SLACK_TOKEN)

    try:
        # Parse the report
        status_emoji, metrics, business_metrics, issues, action = parse_report(report)

        # Debug output
        print(f"📊 Parsed report:")
        print(f"  Status: {status_emoji}")
        print(f"  Metrics: {metrics[:100] if metrics else 'NONE'}")
        print(f"  Business Metrics: {business_metrics[:100] if business_metrics else 'NONE'}")
        print(f"  Issues found: {len(issues)}")
        print(f"  Action: {action[:100] if action else 'NONE'}")

        # Validate we got something
        if not metrics and not business_metrics and not issues:
            print("⚠️  Parser found no structured data. Check Claude's output format.")
            print("📝 Raw report:")
            print(report[:500])
            print("\n⚠️  Posting as plain text fallback...")

            # Fallback: post as simple formatted text
            client.chat_postMessage(
                channel=SLACK_CHANNEL,
                text=f"⚠️ LoA Application Insights Report\n\n{report}"
            )
            return 1

        # Load insights data for timeline chart and date range
        timeline_data = []
        app_insights_time = None
        insights_date_range = None
        try:
            with open(insights_data_path, 'r') as f:
                insights = json.load(f)
                if insights.get('success') and insights.get('data'):
                    timeline_data = [d for d in insights['data'] if d.get('DataType') == 'Timeline']
                # Get timing information
                if insights.get('timing'):
                    app_insights_time = insights['timing'].get('app_insights_seconds')
                # Get date range information
                if insights.get('date_range'):
                    insights_date_range = insights['date_range'].get('date_range')
        except:
            pass

        # Load business metrics timing and date range
        redshift_time = None
        mysql_time = None
        business_date_range = None
        try:
            with open(business_metrics_path, 'r') as f:
                business_data = json.load(f)
                if business_data.get('timing'):
                    redshift_time = business_data['timing'].get('redshift_seconds')
                    mysql_time = business_data['timing'].get('mysql_seconds')
                # Get date range information
                if business_data.get('date_range'):
                    business_date_range = business_data['date_range'].get('date_range')
        except:
            pass

        # Calculate max count for bar charts
        max_count = max([i['count'] for i in issues], default=1)

        # Build Block Kit message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📊 LoA Daily Report"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_{datetime.now().strftime('%B %d, %Y at %I:%M %p %Z')}_"
                    }
                ]
            },
            {
                "type": "divider"
            }
        ]

        # Add business metrics section FIRST (different data sources: Redshift + MySQL)
        if business_metrics:
            # Parse business metrics
            offers_match = re.search(r'([0-9,]+(?:\.[0-9]+)?[KMB]?)\s*offers?', business_metrics, re.IGNORECASE)
            heartbeats_match = re.search(r'([0-9,]+(?:\.[0-9]+)?[KMB]?)\s*player\s*heartbeats?', business_metrics, re.IGNORECASE)
            upsells_match = re.search(r'([0-9,]+(?:\.[0-9]+)?[KMB]?)\s*upsells?', business_metrics, re.IGNORECASE)

            business_fields = []

            if offers_match:
                business_fields.append({
                    "type": "mrkdwn",
                    "text": f"*🎁 Offers*\n`{offers_match.group(1)}`"
                })

            if heartbeats_match:
                business_fields.append({
                    "type": "mrkdwn",
                    "text": f"*🎮 Player Heartbeats*\n`{heartbeats_match.group(1)}`"
                })

            if upsells_match:
                business_fields.append({
                    "type": "mrkdwn",
                    "text": f"*💰 Upsells*\n`{upsells_match.group(1)}`"
                })

            if business_fields:
                # Build header with date range if available
                header_text = "📊 LoA Business Metrics – Daily"
                if business_date_range:
                    header_text = f"📊 LoA Business Metrics – {business_date_range}"

                blocks.append({
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": header_text,
                        "emoji": True
                    }
                })
                blocks.append({
                    "type": "section",
                    "fields": business_fields
                })

                # Build context with date range info if available
                context_text = "*Data Sources:* Redshift (Offers, Upsells) • MySQL (Player Heartbeats)"
                if business_date_range:
                    context_text += f" • Data from: {business_date_range}"
                else:
                    context_text += " • Last 24 hours"

                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": context_text
                        }
                    ]
                })
                blocks.append({
                    "type": "divider"
                })

        # Add technical metrics section (Azure Application Insights)
        if metrics:
            # Build header with date range if available
            insights_header = f"{status_emoji} Application Insights - Health Summary"
            if insights_date_range:
                insights_header = f"{status_emoji} Application Insights - {insights_date_range}"

            blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": insights_header,
                    "emoji": True
                }
            })
            # Parse metrics from the string
            metrics_clean = metrics.replace('**Metrics:**', '').strip()

            # Try to extract individual metrics (handle commas and K/M/B suffixes)
            exceptions_match = re.search(r'([0-9,]+(?:\.[0-9]+)?[KMB]?)\s*exceptions?', metrics_clean, re.IGNORECASE)
            dependencies_match = re.search(r'([0-9,]+(?:\.[0-9]+)?[KMB]?)\s*dependencies', metrics_clean, re.IGNORECASE)
            failed_deps_match = re.search(r'\(([0-9,]+(?:\.[0-9]+)?[KMB]?)\s*failed\)', metrics_clean, re.IGNORECASE)
            p95_match = re.search(r'P95:\s*([0-9,]+(?:\.[0-9]+)?)ms', metrics_clean, re.IGNORECASE)
            requests_match = re.search(r'([0-9,]+(?:\.[0-9]+)?[KMB]?)\s*requests?', metrics_clean, re.IGNORECASE)
            success_match = re.search(r'([0-9,]+(?:\.[0-9]+)?)%\s*success', metrics_clean, re.IGNORECASE)

            metrics_fields = []

            if exceptions_match:
                metrics_fields.append({
                    "type": "mrkdwn",
                    "text": f"*🚨 Exceptions*\n`{exceptions_match.group(1)}`"
                })

            if requests_match:
                metrics_fields.append({
                    "type": "mrkdwn",
                    "text": f"*📥 Requests*\n`{requests_match.group(1)}`"
                })

            if success_match:
                metrics_fields.append({
                    "type": "mrkdwn",
                    "text": f"*✅ Success Rate*\n`{success_match.group(1)}%`"
                })

            if dependencies_match:
                deps_text = dependencies_match.group(1)
                if failed_deps_match:
                    deps_text += f" ({failed_deps_match.group(1)} failed)"
                metrics_fields.append({
                    "type": "mrkdwn",
                    "text": f"*🔗 Dependencies*\n`{deps_text}`"
                })

            if p95_match:
                metrics_fields.append({
                    "type": "mrkdwn",
                    "text": f"*⚡ P95 Response*\n`{p95_match.group(1)}ms`"
                })

            if metrics_fields:
                blocks.append({
                    "type": "section",
                    "fields": metrics_fields
                })
            else:
                # Fallback if parsing fails
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*📊 Key Metrics*\n`{metrics}`"
                    }
                })

        # Add exception timeline chart
        if timeline_data:
            blocks.append({
                "type": "divider"
            })

            # Try to add QuickChart image first, fallback to ASCII
            chart_url = generate_chart_url(timeline_data)
            if chart_url:
                print(f"📊 Chart URL generated: {chart_url[:100]}...", file=sys.stderr)
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*📈 Exception Timeline - Last 24 Hours*"
                    }
                })
                blocks.append({
                    "type": "image",
                    "image_url": chart_url,
                    "alt_text": "Exception timeline showing hourly exception counts"
                })
            else:
                # Fallback to ASCII chart if URL generation fails
                print("⚠️  Chart URL generation failed, using ASCII fallback", file=sys.stderr)
                ascii_chart = create_ascii_chart(timeline_data)
                if ascii_chart:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": ascii_chart
                        }
                    })

        # Add top issues with visualization
        if issues:
            blocks.append({
                "type": "divider"
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🔥 Top Exception Problems*"
                }
            })

            # Create issue visualization - show top 5
            for i, issue in enumerate(issues[:5], 1):
                bar = create_bar_chart(issue['count'], max_count)

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{i}. {issue['count']:,}× occurrences*\n`{bar}` _{issue['count']:,}_\n```{issue['description']}```"
                    }
                })

        # Add action section
        if action:
            blocks.append({
                "type": "divider"
            })
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*⚡ Action Required*\n{action}"
                }
            })

        # Add performance metrics
        if app_insights_time or redshift_time or mysql_time:
            blocks.append({
                "type": "divider"
            })

            timing_parts = []
            if app_insights_time:
                timing_parts.append(f"Azure App Insights: {app_insights_time}s")
            if redshift_time:
                timing_parts.append(f"Redshift: {redshift_time}s")
            if mysql_time:
                timing_parts.append(f"MySQL: {mysql_time}s")

            if timing_parts:
                blocks.append({
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"⏱️ *Fetch Times:* {' • '.join(timing_parts)}"
                        }
                    ]
                })

        # Add footer
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "📈 <https://portal.azure.com|View in Azure Portal> | Generated by Claude Code Automation"
                }
            ]
        })

        # Post message with blocks
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=f"{status_emoji} LoA Application Insights - Daily Summary",  # Fallback text
            blocks=blocks
        )

        print(f"✅ Message posted successfully to {SLACK_CHANNEL}")
        return 0

    except SlackApiError as e:
        print(f"❌ Error posting to Slack: {e.response['error']}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

def main():
    """Main execution function"""

    # Read report from stdin
    report = sys.stdin.read().strip()

    if not report:
        print("❌ No report content received from stdin", file=sys.stderr)
        return 1

    # Try to find insights_data.json in various locations
    insights_path = '/app/insights_data.json'  # LaunchCode
    if not os.path.exists(insights_path):
        insights_path = 'insights_data.json'  # Local
    if not os.path.exists(insights_path):
        insights_path = os.path.join(os.path.dirname(__file__), 'insights_data.json')

    # Try to find business_metrics.json
    business_path = '/app/business_metrics.json'  # LaunchCode
    if not os.path.exists(business_path):
        business_path = 'business_metrics.json'  # Local
    if not os.path.exists(business_path):
        business_path = os.path.join(os.path.dirname(__file__), 'business_metrics.json')

    return post_to_slack(report, insights_path, business_path)

if __name__ == '__main__':
    sys.exit(main())
