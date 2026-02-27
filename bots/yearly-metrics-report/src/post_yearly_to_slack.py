#!/usr/bin/env python3
"""
Post yearly metrics report to Slack with Block Kit formatting.
Reads JSON from stdin (output of fetch_yearly_metrics.py).

Includes 3 charts, monthly/quarterly tables, highlights, and weekend vs weekday analysis.
"""
import os
import sys
import json
import requests
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

YEARLY_METRICS_SLACK_CHANNEL = os.environ.get('YEARLY_METRICS_SLACK_CHANNEL', '#int-lift-loa-yearly-business-metrics')
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
        print("QuickChart error: {}".format(data), file=sys.stderr)
    except Exception as e:
        print("Chart generation error: {}".format(e), file=sys.stderr)
    return None


def generate_monthly_line_chart_url(monthly):
    """Chart 1: Monthly Offers & Upsells line chart (amber/emerald, dark theme)."""
    if not monthly:
        return None

    labels = [m['month_name'][:3] for m in monthly]
    offers = [m['offers'] for m in monthly]
    upsells = [m['upsells'] for m in monthly]

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
                    "pointRadius": 3,
                },
                {
                    "label": "Upsells",
                    "data": upsells,
                    "borderColor": "rgba(52,211,153,1)",
                    "backgroundColor": "rgba(52,211,153,0.1)",
                    "fill": True,
                    "tension": 0.3,
                    "pointRadius": 3,
                },
            ],
        },
        "options": {
            "responsive": True,
            "legend": {"labels": {"fontColor": "#e5e7eb"}},
            "title": {
                "display": True,
                "text": "Monthly Offers & Upsells",
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
                        "ticks": {"fontColor": "#9ca3af"},
                        "gridLines": {"color": "rgba(156,163,175,0.2)"},
                    }
                ],
            },
        },
    }

    return generate_chart_short_url(chart_config)


def generate_upsell_rate_chart_url(monthly):
    """Chart 2: Monthly Upsell Rate Trend line chart (blue/purple)."""
    if not monthly:
        return None

    labels = [m['month_name'][:3] for m in monthly]
    rates = [m['rate'] for m in monthly]

    chart_config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Upsell Rate (%)",
                    "data": rates,
                    "borderColor": "rgba(96,165,250,1)",
                    "backgroundColor": "rgba(96,165,250,0.1)",
                    "fill": True,
                    "tension": 0.3,
                    "pointRadius": 4,
                    "pointBackgroundColor": "rgba(167,139,250,1)",
                    "datalabels": {
                        "display": True,
                        "color": "#e5e7eb",
                        "anchor": "end",
                        "align": "top",
                        "formatter": "__FUNC__",
                    },
                },
            ],
        },
        "options": {
            "responsive": True,
            "legend": {"labels": {"fontColor": "#e5e7eb"}},
            "title": {
                "display": True,
                "text": "Monthly Upsell Rate Trend",
                "fontSize": 16,
                "fontColor": "#e5e7eb",
            },
            "plugins": {
                "datalabels": {
                    "display": True,
                    "color": "#e5e7eb",
                    "font": {"size": 11},
                },
            },
            "scales": {
                "yAxes": [
                    {
                        "ticks": {
                            "fontColor": "#9ca3af",
                            "callback": "__FUNC_PCT__",
                        },
                        "gridLines": {"color": "rgba(156,163,175,0.2)"},
                    }
                ],
                "xAxes": [
                    {
                        "ticks": {"fontColor": "#9ca3af"},
                        "gridLines": {"color": "rgba(156,163,175,0.2)"},
                    }
                ],
            },
        },
    }

    # QuickChart supports inline JS functions in the config
    config_str = json.dumps(chart_config, separators=(",", ":"))
    # Replace formatter placeholders with JS functions
    config_str = config_str.replace('"__FUNC__"', "(val) => val.toFixed(1) + '%'")
    config_str = config_str.replace('"__FUNC_PCT__"', "(val) => val.toFixed(1) + '%'")

    # Use POST API with the raw config string (supports JS functions)
    try:
        resp = requests.post(
            'https://quickchart.io/chart/create',
            json={
                'chart': config_str,
                'width': 800,
                'height': 350,
                'backgroundColor': '#111827',
                'devicePixelRatio': 2,
            },
            timeout=15,
        )
        data = resp.json()
        if data.get('success'):
            return data['url']
        print("QuickChart upsell rate error: {}".format(data), file=sys.stderr)
    except Exception as e:
        print("Upsell rate chart error: {}".format(e), file=sys.stderr)
    return None


def generate_quarterly_bar_chart_url(quarterly):
    """Chart 3: Quarterly Comparison bar chart (grouped bars)."""
    if not quarterly:
        return None

    labels = [f"Q{q['quarter']}" for q in quarterly]
    offers = [q['offers'] for q in quarterly]
    upsells = [q['upsells'] for q in quarterly]

    chart_config = {
        "type": "bar",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Offers",
                    "data": offers,
                    "backgroundColor": "rgba(251,191,36,0.8)",
                    "borderColor": "rgba(251,191,36,1)",
                    "borderWidth": 1,
                },
                {
                    "label": "Upsells",
                    "data": upsells,
                    "backgroundColor": "rgba(52,211,153,0.8)",
                    "borderColor": "rgba(52,211,153,1)",
                    "borderWidth": 1,
                },
            ],
        },
        "options": {
            "responsive": True,
            "legend": {"labels": {"fontColor": "#e5e7eb"}},
            "title": {
                "display": True,
                "text": "Quarterly Comparison",
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
                        "ticks": {"fontColor": "#9ca3af"},
                        "gridLines": {"color": "rgba(156,163,175,0.2)"},
                    }
                ],
            },
        },
    }

    return generate_chart_short_url(chart_config)


def fmt_num(n):
    """Format number with commas."""
    return f"{n:,}"


def build_blocks(data):
    """Build Slack Block Kit blocks from yearly metrics data."""
    year = data["year"]
    daily = data["daily"]
    monthly = data["monthly"]
    quarterly = data["quarterly"]
    totals = data["totals"]
    active_players = data.get("active_players")
    highlights = data.get("highlights", {})
    mom = data.get("month_over_month", [])
    timing = data.get("timing", {})
    tables_queried = data.get("tables_queried", [])

    total_rate = round(totals["upsells"] / totals["offers"] * 100, 2) if totals["offers"] > 0 else 0

    blocks = []

    # 1. Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": f"\ud83d\udcc5 Yearly Summary \u2014 {year}",
            "emoji": True,
        },
    })

    # 2. Context: generated timestamp, timezone, tables
    tables_str = ", ".join(f"`{t}`" for t in tables_queried)
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"_Generated {datetime.now().strftime('%B %d, %Y at %I:%M %p ET')}_  \u2022  Tables: {tables_str}",
            }
        ],
    })

    # 3. Divider
    blocks.append({"type": "divider"})

    # 4. Summary section (4 fields)
    summary_fields = [
        {"type": "mrkdwn", "text": f"*\ud83c\udf81 Total Offers*\n`{fmt_num(totals['offers'])}`"},
        {"type": "mrkdwn", "text": f"*\ud83d\udcb0 Total Upsells*\n`{fmt_num(totals['upsells'])}`"},
        {"type": "mrkdwn", "text": f"*\ud83d\udcc8 Upsell Rate*\n`{total_rate:.2f}%`"},
    ]
    if active_players is not None:
        summary_fields.append(
            {"type": "mrkdwn", "text": f"*\ud83c\udfae Active Players*\n`{fmt_num(active_players)}`"}
        )
    blocks.append({"type": "section", "fields": summary_fields})

    # 5. Context: days covered, avg daily
    avg_offers = highlights.get("avg_daily_offers", 0)
    blocks.append({
        "type": "context",
        "elements": [
            {
                "type": "mrkdwn",
                "text": f"_Days covered: {totals['days']}  \u2022  Avg daily offers: {fmt_num(avg_offers)}_",
            }
        ],
    })

    # 6. Divider
    blocks.append({"type": "divider"})

    # 7. Chart 1 — Monthly Offers & Upsells
    chart1_url = generate_monthly_line_chart_url(monthly)
    if chart1_url:
        blocks.append({
            "type": "image",
            "image_url": chart1_url,
            "alt_text": "Monthly offers and upsells trend line chart",
        })

    # 8. Divider
    blocks.append({"type": "divider"})

    # 9. Chart 2 — Monthly Upsell Rate Trend
    chart2_url = generate_upsell_rate_chart_url(monthly)
    if chart2_url:
        blocks.append({
            "type": "image",
            "image_url": chart2_url,
            "alt_text": "Monthly upsell rate trend line chart",
        })

    # 10. Divider
    blocks.append({"type": "divider"})

    # 11. Monthly breakdown table
    if monthly:
        # Build MoM lookup
        mom_map = {m["month_name"]: m for m in mom}

        lines = [
            f"{'Month':<12} {'Offers':>12} {'Upsells':>10} {'Rate':>6} {'MoM%':>7}",
            "\u2500" * 51,
        ]

        for m in monthly:
            mom_entry = mom_map.get(m["month_name"])
            mom_str = f"{mom_entry['offers_change_pct']:>+6.1f}%" if mom_entry else "     -"
            lines.append(
                f"{m['month_name']:<12} {m['offers']:>12,} {m['upsells']:>10,} {m['rate']:>6.2f}% {mom_str}"
            )

        lines.append("\u2500" * 51)
        lines.append(
            f"{'TOTAL':<12} {totals['offers']:>12,} {totals['upsells']:>10,} {total_rate:>6.2f}%"
        )

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*\ud83d\udcca Monthly Breakdown*\n```\n{}\n```".format("\n".join(lines)),
            },
        })

    # 12. Divider
    blocks.append({"type": "divider"})

    # 13. Chart 3 — Quarterly Comparison
    chart3_url = generate_quarterly_bar_chart_url(quarterly)
    if chart3_url:
        blocks.append({
            "type": "image",
            "image_url": chart3_url,
            "alt_text": "Quarterly comparison bar chart",
        })

    # 14. Divider
    blocks.append({"type": "divider"})

    # 15. Quarterly summary table
    if quarterly:
        total_offers = totals["offers"]
        lines = [
            f"{'Quarter':<10} {'Offers':>12} {'Upsells':>10} {'Rate':>6} {'Share':>7}",
            "\u2500" * 49,
        ]

        for q in quarterly:
            share = round(q["offers"] / total_offers * 100, 1) if total_offers > 0 else 0
            lines.append(
                f"Q{q['quarter']:<9} {q['offers']:>12,} {q['upsells']:>10,} {q['rate']:>6.2f}% {share:>5.1f}%"
            )

        lines.append("\u2500" * 49)
        lines.append(
            f"{'TOTAL':<10} {totals['offers']:>12,} {totals['upsells']:>10,} {total_rate:>6.2f}%"
        )

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*\ud83d\udcca Quarterly Summary*\n```\n{}\n```".format("\n".join(lines)),
            },
        })

    # 16. Divider
    blocks.append({"type": "divider"})

    # 17. Highlights section
    if highlights:
        highlight_lines = []

        best_month = highlights.get("best_month", {})
        worst_month = highlights.get("worst_month", {})
        best_day = highlights.get("best_day", {})
        best_rate = highlights.get("best_upsell_rate_month", {})
        worst_rate = highlights.get("worst_upsell_rate_month", {})

        if best_month:
            highlight_lines.append(f"\ud83c\udfc6 *Best Month:* {best_month['month_name']} ({fmt_num(best_month['offers'])} offers)")
        if worst_month:
            highlight_lines.append(f"\ud83d\udcc9 *Worst Month:* {worst_month['month_name']} ({fmt_num(worst_month['offers'])} offers)")
        if best_day:
            highlight_lines.append(f"\u2b50 *Peak Day:* {best_day['date']} ({fmt_num(best_day['offers'])} offers)")
        if best_rate:
            highlight_lines.append(f"\ud83d\ude80 *Best Upsell Rate:* {best_rate['month_name']} ({best_rate['rate']:.2f}%)")
        if worst_rate:
            highlight_lines.append(f"\ud83d\udca4 *Worst Upsell Rate:* {worst_rate['month_name']} ({worst_rate['rate']:.2f}%)")

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*\ud83d\udd25 Highlights*\n" + "\n".join(highlight_lines),
            },
        })

    # 18. Divider
    blocks.append({"type": "divider"})

    # 19. Weekend vs Weekday analysis
    if highlights:
        wd_offers = highlights.get("weekday_avg_offers", 0)
        we_offers = highlights.get("weekend_avg_offers", 0)
        wd_upsells = highlights.get("weekday_avg_upsells", 0)
        we_upsells = highlights.get("weekend_avg_upsells", 0)
        wd_rate = round(wd_upsells / wd_offers * 100, 1) if wd_offers > 0 else 0
        we_rate = round(we_upsells / we_offers * 100, 1) if we_offers > 0 else 0

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*\ud83d\udcc5 Weekend vs Weekday*\n"
                    f"```\n"
                    f"Weekday avg: {fmt_num(wd_offers)} offers / {fmt_num(wd_upsells)} upsells ({wd_rate:.2f}% rate)\n"
                    f"Weekend avg: {fmt_num(we_offers)} offers / {fmt_num(we_upsells)} upsells ({we_rate:.2f}% rate)\n"
                    f"```"
                ),
            },
        })

    # 20. Divider
    blocks.append({"type": "divider"})

    # 21. Timing footer
    timing_parts = []
    if timing.get("redshift_seconds"):
        timing_parts.append(f"Redshift: {timing['redshift_seconds']}s")
    if timing.get("mysql_seconds"):
        timing_parts.append(f"MySQL: {timing['mysql_seconds']}s")

    if timing_parts:
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "\u23f1\ufe0f *Fetch Times:* {}  |  *Sources:* Redshift (Offers, Upsells) \u2022 MySQL (Active Players)".format(" \u2022 ".join(timing_parts)),
                }
            ],
        })

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

    print(f"Block count: {len(blocks)} (limit: 50)", file=sys.stderr)

    client = WebClient(token=SLACK_TOKEN)
    try:
        year = data["year"]
        client.chat_postMessage(
            channel=YEARLY_METRICS_SLACK_CHANNEL,
            text=f"Yearly Summary \u2014 {year}",
            blocks=blocks,
        )
        print(f"Posted to {YEARLY_METRICS_SLACK_CHANNEL}", file=sys.stderr)
        return 0
    except SlackApiError as e:
        print(f"Slack error: {e.response['error']}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
