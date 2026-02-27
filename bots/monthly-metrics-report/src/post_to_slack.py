#!/usr/bin/env python3
"""
Post monthly metrics report to Slack with Block Kit formatting.
Reads JSON from stdin (output of fetch_monthly_metrics.py).
"""
import os
import sys
import json
import requests
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

MONTHLY_METRICS_SLACK_CHANNEL = os.environ.get('MONTHLY_METRICS_SLACK_CHANNEL', '#int-lift-loa-monthly-business-metrics')
SLACK_TOKEN = os.environ.get('SLACK_BOT_TOKEN')


def generate_chart_short_url(chart_config, width=800, height=350):
    """Generate a QuickChart short URL via POST API (avoids URL length limits)."""
    try:
        resp = requests.post(
            'https://quickchart.io/chart/create',
            json={
                'chart': chart_config,
                'width': width,
                'height': height,
                'backgroundColor': '#111827',
                'devicePixelRatio': 2,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get('success'):
            return data['url']
        print(f"QuickChart error: {data}", file=sys.stderr)
    except Exception as e:
        print(f"Chart generation error: {e}", file=sys.stderr)
    return None


def generate_line_chart_url(daily):
    """Generate a QuickChart line chart URL for offers and upsells trends."""
    if not daily:
        return None

    labels = [d['date'][5:] for d in daily]  # MM-DD
    offers = [d['offers'] for d in daily]
    upsells = [d['upsells'] for d in daily]

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Offers",
                    "data": offers,
                    "borderColor": "rgba(251,191,36,1)",
                    "backgroundColor": "rgba(251,191,36,0.1)",
                    "fill": True,
                    "tension": 0.3,
                    "pointRadius": 2,
                },
                {
                    "label": "Upsells",
                    "data": upsells,
                    "borderColor": "rgba(52,211,153,1)",
                    "backgroundColor": "rgba(52,211,153,0.1)",
                    "fill": True,
                    "tension": 0.3,
                    "pointRadius": 2,
                },
            ],
        },
        "options": {
            "responsive": True,
            "legend": {"labels": {"fontColor": "#e5e7eb"}},
            "title": {
                "display": True,
                "text": "Daily Offers & Upsells",
                "fontSize": 16,
                "fontColor": "#e5e7eb",
            },
            "scales": {
                "yAxes": [
                    {
                        "ticks": {"beginAtZero": True, "fontColor": "#9ca3af"},
                        "gridLines": {"color": "rgba(156,163,175,0.2)"},
                    }
                ],
                "xAxes": [
                    {
                        "ticks": {"fontColor": "#9ca3af", "maxTicksLimit": 15},
                        "gridLines": {"color": "rgba(156,163,175,0.2)"},
                    }
                ],
            },
        },
    }

    return generate_chart_short_url(chart_config)


def build_blocks(data):
    """Build Slack Block Kit blocks from metrics data."""
    month_name = data["month_name"]
    year = data["year"]
    quarter = data["quarter"]
    daily = data["daily"]
    totals = data["totals"]
    active_players = data.get("active_players")
    timing = data.get("timing", {})

    # Summary fields
    summary_fields = [
        {"type": "mrkdwn", "text": f"*🎁 Total Offers*\n`{totals['offers']:,}`"},
        {"type": "mrkdwn", "text": f"*💰 Total Upsells*\n`{totals['upsells']:,}`"},
    ]
    if active_players is not None:
        summary_fields.append(
            {"type": "mrkdwn", "text": f"*🎮 Active Players*\n`{active_players:,}`"}
        )

    # Upsell rate
    if totals["offers"] > 0:
        rate = totals["upsells"] / totals["offers"] * 100
        summary_fields.append(
            {"type": "mrkdwn", "text": f"*📈 Upsell Rate*\n`{rate:.2f}%`"}
        )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📅 Monthly Metrics — {month_name} {year} (Q{quarter})",
                "emoji": True,
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p')}_  •  Table: `{data.get('quarterly_table', 'N/A')}`",
                }
            ],
        },
        {"type": "divider"},
        {"type": "section", "fields": summary_fields},
    ]

    # Active players context
    if active_players is not None:
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "🎮 _Active Players = distinct players with a heartbeat in the last 24h (live snapshot from MySQL)_",
                    }
                ],
            }
        )

    blocks.append({"type": "divider"})

    # Line chart
    if daily:
        chart_url = generate_line_chart_url(daily)
        if chart_url:
            blocks.append(
                {
                    "type": "image",
                    "image_url": chart_url,
                    "alt_text": "Daily offers and upsells trend line chart",
                }
            )
            blocks.append({"type": "divider"})

    # Daily breakdown table
    if daily:
        lines = [
            f"{'Date':<12} {'Day':<4} {'Offers':>10} {'Upsells':>10} {'Rate':>7}",
            "─" * 49,
        ]

        for d in daily:
            day_short = d["day_name"][:3]
            weekend = " *" if d["day_name"] in ("Saturday", "Sunday") else ""
            rate = (
                f"{d['upsells'] / d['offers'] * 100:.1f}%"
                if d["offers"] > 0
                else "  -"
            )
            lines.append(
                f"{d['date']:<12} {day_short:<4} {d['offers']:>10,} {d['upsells']:>10,} {rate:>7}{weekend}"
            )

        lines.append("─" * 49)
        total_rate = (
            f"{totals['upsells'] / totals['offers'] * 100:.1f}%"
            if totals["offers"] > 0
            else "  -"
        )
        lines.append(
            f"{'TOTAL':<17} {totals['offers']:>10,} {totals['upsells']:>10,} {total_rate:>7}"
        )
        lines.append("")
        lines.append("* = weekend")

        table_text = "\n".join(lines)

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📊 Daily Breakdown*\n```{table_text}```",
                },
            }
        )

    # Timing footer
    timing_parts = []
    if timing.get("redshift_seconds"):
        timing_parts.append(f"Redshift: {timing['redshift_seconds']}s")
    if timing.get("mysql_seconds"):
        timing_parts.append(f"MySQL: {timing['mysql_seconds']}s")

    if timing_parts:
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⏱️ *Fetch Times:* {' • '.join(timing_parts)}  |  *Sources:* Redshift (Offers, Upsells) • MySQL (Active Players)",
                    }
                ],
            }
        )

    return blocks


def main():
    if not SLACK_TOKEN:
        print("SLACK_BOT_TOKEN is required", file=sys.stderr)
        return 1

    raw = sys.stdin.read().strip()
    if not raw:
        print("No input received on stdin", file=sys.stderr)
        return 1

    data = json.loads(raw)
    if not data.get("success"):
        print(f"Input data indicates failure: {data.get('error')}", file=sys.stderr)
        return 1

    blocks = build_blocks(data)

    client = WebClient(token=SLACK_TOKEN)
    try:
        month_name = data["month_name"]
        year = data["year"]
        client.chat_postMessage(
            channel=MONTHLY_METRICS_SLACK_CHANNEL,
            text=f"Monthly Metrics — {month_name} {year}",
            blocks=blocks,
        )
        print(f"Posted to {MONTHLY_METRICS_SLACK_CHANNEL}", file=sys.stderr)
        return 0
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
