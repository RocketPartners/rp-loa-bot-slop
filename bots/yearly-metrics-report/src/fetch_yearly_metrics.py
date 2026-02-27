#!/usr/bin/env python3
"""
Fetch daily offers and upsells for an entire year, plus current active player count.
Aggregates into monthly, quarterly, highlights, and month-over-month analysis.

Usage:
  python3 fetch_yearly_metrics.py --year 2026
  python3 fetch_yearly_metrics.py --year 2025

Outputs JSON to stdout.
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
import calendar

ET = ZoneInfo('America/New_York')

try:
    import psycopg2
except ImportError:
    print(json.dumps({"success": False, "error": "psycopg2 not installed"}))
    sys.exit(1)

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

# Redshift config
REDSHIFT_HOST = os.environ.get('REDSHIFT_HOST')
REDSHIFT_PORT = os.environ.get('REDSHIFT_PORT', '5439')
REDSHIFT_DATABASE = os.environ.get('REDSHIFT_DATABASE')
REDSHIFT_USER = os.environ.get('REDSHIFT_USER')
REDSHIFT_PASSWORD = os.environ.get('REDSHIFT_PASSWORD')

# MySQL config
MYSQL_HOST = os.environ.get('MYSQL_HOST')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE')
MYSQL_USER = os.environ.get('MYSQL_USER')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')


def quarter_for_month(month):
    """Return quarter number (1-4) for a given month (1-12)."""
    return (month - 1) // 3 + 1


def offer_table_name(year, quarter):
    """Return the quarterly offer table name, e.g. offer_2026_q1."""
    return f"warehouse.public.offer_{year}_q{quarter}"


def get_applicable_quarters(year):
    """Determine which quarters have data for the given year."""
    today_et = datetime.now(ET).date()
    if year < today_et.year:
        return [1, 2, 3, 4]
    elif year == today_et.year:
        current_quarter = quarter_for_month(today_et.month)
        return list(range(1, current_quarter + 1))
    else:
        return []


def parse_args():
    parser = argparse.ArgumentParser(description='Fetch yearly metrics')
    now = datetime.now(ET)
    parser.add_argument('--year', type=int, default=now.year, help='Year (e.g. 2026)')
    args = parser.parse_args()
    return args


def fetch_redshift_daily(year, quarters):
    """Fetch daily offers and upsells from Redshift for the entire year (ET calendar days)."""
    start_time = time.time()

    first_day = date(year, 1, 1)
    last_day = date(year, 12, 31)

    today_et = datetime.now(ET).date()
    if last_day >= today_et:
        last_day = today_et

    # createdat is char(29) with ISO 8601 + offset
    # Use string comparison as rough pre-filter (1-day buffer for timezone edge cases)
    # then CONVERT_TIMEZONE for precise ET calendar day grouping
    buffer_start = (first_day - timedelta(days=1)).isoformat()
    buffer_end = (last_day + timedelta(days=2)).isoformat()
    et_date = "DATE(CONVERT_TIMEZONE('UTC', 'America/New_York', CAST(CAST(createdat AS TIMESTAMPTZ) AS TIMESTAMP)))"

    # Build UNION ALL across firehose_offer9 + all applicable quarterly tables
    select_template = """
        SELECT createdat, liftadded
        FROM {table}
        WHERE createdat >= '{start}'
          AND createdat < '{end}'
          AND cashierkey LIKE '%CashierName%'
    """

    unions = [select_template.format(
        table="warehouse.public.firehose_offer9",
        start=buffer_start,
        end=buffer_end,
    )]

    tables_queried = ["firehose_offer9"]
    for q in quarters:
        table = offer_table_name(year, q)
        unions.append(select_template.format(
            table=table,
            start=buffer_start,
            end=buffer_end,
        ))
        tables_queried.append(f"offer_{year}_q{q}")

    union_sql = "\n        UNION ALL\n".join(unions)

    query = f"""
    SELECT
        {et_date} AS day,
        COUNT(*) AS offers,
        SUM(CASE WHEN liftadded = true THEN 1 ELSE 0 END) AS upsells
    FROM (
        {union_sql}
    ) AS combined
    GROUP BY {et_date}
    ORDER BY day;
    """

    try:
        conn = psycopg2.connect(
            host=REDSHIFT_HOST,
            port=REDSHIFT_PORT,
            database=REDSHIFT_DATABASE,
            user=REDSHIFT_USER,
            password=REDSHIFT_PASSWORD,
            connect_timeout=30
        )
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        elapsed = time.time() - start_time
        daily = []
        for row in rows:
            daily.append({
                "date": row[0].isoformat() if hasattr(row[0], 'isoformat') else str(row[0]),
                "offers": row[1],
                "upsells": row[2],
            })
        return daily, elapsed, tables_queried

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Redshift error: {e}", file=sys.stderr)
        return [], elapsed, tables_queried


def fetch_active_players():
    """Fetch current active player count from MySQL (live snapshot)."""
    if not MYSQL_AVAILABLE or not all([MYSQL_HOST, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD]):
        return None, 0

    start_time = time.time()

    query = """
    SELECT COUNT(DISTINCT playerKey) AS active_players
    FROM lift.Heartbeat
    WHERE macAddress LIKE '70:0A%%'
      AND timestamp >= NOW() - INTERVAL 1 DAY;
    """

    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=int(MYSQL_PORT),
            database=MYSQL_DATABASE,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            connect_timeout=10
        )
        cursor = conn.cursor()
        cursor.execute(query)
        result = cursor.fetchone()
        count = result[0] if result else None
        cursor.close()
        conn.close()

        elapsed = time.time() - start_time
        return count, elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"MySQL error: {e}", file=sys.stderr)
        return None, elapsed


def build_daily(redshift_daily, year):
    """Build daily list from Redshift data, filling missing days with 0."""
    today = datetime.now(ET).date()
    last_day = date(year, 12, 31)
    if last_day > today:
        last_day = today

    rs_map = {r['date']: r for r in redshift_daily}

    merged = []
    current = date(year, 1, 1)
    while current <= last_day:
        day_str = current.isoformat()
        rs = rs_map.get(day_str, {})
        merged.append({
            "date": day_str,
            "day_name": current.strftime('%A'),
            "offers": rs.get('offers', 0),
            "upsells": rs.get('upsells', 0),
        })
        current += timedelta(days=1)
    return merged


def aggregate_monthly(daily):
    """Aggregate daily data into monthly summaries."""
    months = {}
    for d in daily:
        month_num = int(d['date'][5:7])
        if month_num not in months:
            months[month_num] = {"offers": 0, "upsells": 0, "days": 0}
        months[month_num]["offers"] += d["offers"]
        months[month_num]["upsells"] += d["upsells"]
        months[month_num]["days"] += 1

    result = []
    for m in sorted(months.keys()):
        data = months[m]
        avg_offers = round(data["offers"] / data["days"]) if data["days"] > 0 else 0
        avg_upsells = round(data["upsells"] / data["days"]) if data["days"] > 0 else 0
        rate = round(data["upsells"] / data["offers"] * 100, 2) if data["offers"] > 0 else 0
        result.append({
            "month": m,
            "month_name": calendar.month_name[m],
            "offers": data["offers"],
            "upsells": data["upsells"],
            "days": data["days"],
            "avg_daily_offers": avg_offers,
            "avg_daily_upsells": avg_upsells,
            "rate": rate,
        })
    return result


def aggregate_quarterly(monthly, year, quarters):
    """Aggregate monthly data into quarterly summaries."""
    quarter_data = {}
    for m in monthly:
        q = quarter_for_month(m["month"])
        if q not in quarter_data:
            quarter_data[q] = {"offers": 0, "upsells": 0, "tables": []}
        quarter_data[q]["offers"] += m["offers"]
        quarter_data[q]["upsells"] += m["upsells"]

    result = []
    for q in sorted(quarter_data.keys()):
        data = quarter_data[q]
        rate = round(data["upsells"] / data["offers"] * 100, 2) if data["offers"] > 0 else 0
        tables = [offer_table_name(year, q)]
        result.append({
            "quarter": q,
            "offers": data["offers"],
            "upsells": data["upsells"],
            "rate": rate,
            "tables": tables,
        })
    return result


def compute_highlights(daily, monthly):
    """Compute highlights: best/worst months, best day, weekend vs weekday, etc."""
    if not monthly or not daily:
        return {}

    # Best/worst month by offers
    best_month = max(monthly, key=lambda m: m["offers"])
    worst_month = min(monthly, key=lambda m: m["offers"])

    # Best day by offers
    best_day = max(daily, key=lambda d: d["offers"])

    # Best/worst upsell rate month
    months_with_offers = [m for m in monthly if m["offers"] > 0]
    best_rate_month = max(months_with_offers, key=lambda m: m["rate"]) if months_with_offers else None
    worst_rate_month = min(months_with_offers, key=lambda m: m["rate"]) if months_with_offers else None

    # Overall averages
    total_offers = sum(d["offers"] for d in daily)
    total_upsells = sum(d["upsells"] for d in daily)
    total_days = len(daily)
    avg_daily_offers = round(total_offers / total_days) if total_days > 0 else 0
    avg_daily_upsells = round(total_upsells / total_days) if total_days > 0 else 0
    avg_upsell_rate = round(total_upsells / total_offers * 100, 2) if total_offers > 0 else 0

    # Weekend vs weekday
    weekday_days = [d for d in daily if d["day_name"] not in ("Saturday", "Sunday")]
    weekend_days = [d for d in daily if d["day_name"] in ("Saturday", "Sunday")]

    weekday_avg_offers = round(sum(d["offers"] for d in weekday_days) / len(weekday_days)) if weekday_days else 0
    weekend_avg_offers = round(sum(d["offers"] for d in weekend_days) / len(weekend_days)) if weekend_days else 0
    weekday_avg_upsells = round(sum(d["upsells"] for d in weekday_days) / len(weekday_days)) if weekday_days else 0
    weekend_avg_upsells = round(sum(d["upsells"] for d in weekend_days) / len(weekend_days)) if weekend_days else 0

    highlights = {
        "best_month": {"month_name": best_month["month_name"], "offers": best_month["offers"]},
        "worst_month": {"month_name": worst_month["month_name"], "offers": worst_month["offers"]},
        "best_day": {"date": best_day["date"], "offers": best_day["offers"]},
        "avg_daily_offers": avg_daily_offers,
        "avg_daily_upsells": avg_daily_upsells,
        "avg_upsell_rate": avg_upsell_rate,
        "weekday_avg_offers": weekday_avg_offers,
        "weekend_avg_offers": weekend_avg_offers,
        "weekday_avg_upsells": weekday_avg_upsells,
        "weekend_avg_upsells": weekend_avg_upsells,
    }

    if best_rate_month:
        highlights["best_upsell_rate_month"] = {"month_name": best_rate_month["month_name"], "rate": best_rate_month["rate"]}
    if worst_rate_month:
        highlights["worst_upsell_rate_month"] = {"month_name": worst_rate_month["month_name"], "rate": worst_rate_month["rate"]}

    return highlights


def compute_month_over_month(monthly):
    """Compute month-over-month changes."""
    if len(monthly) < 2:
        return []

    result = []
    for i in range(1, len(monthly)):
        prev = monthly[i - 1]
        curr = monthly[i]

        offers_change = round((curr["offers"] - prev["offers"]) / prev["offers"] * 100, 1) if prev["offers"] > 0 else 0
        upsells_change = round((curr["upsells"] - prev["upsells"]) / prev["upsells"] * 100, 1) if prev["upsells"] > 0 else 0
        rate_change = round(curr["rate"] - prev["rate"], 2)

        result.append({
            "month_name": curr["month_name"],
            "offers_change_pct": offers_change,
            "upsells_change_pct": upsells_change,
            "rate_change": rate_change,
        })
    return result


def main():
    args = parse_args()

    if not all([REDSHIFT_HOST, REDSHIFT_DATABASE, REDSHIFT_USER, REDSHIFT_PASSWORD]):
        print(json.dumps({"success": False, "error": "Missing Redshift credentials"}))
        return 1

    quarters = get_applicable_quarters(args.year)
    if not quarters:
        print(json.dumps({"success": False, "error": f"No data available for year {args.year}"}))
        return 1

    print(f"Fetching yearly metrics for {args.year}", file=sys.stderr)
    print(f"Quarters to query: {quarters}", file=sys.stderr)
    for q in quarters:
        print(f"  Table: {offer_table_name(args.year, q)}", file=sys.stderr)

    redshift_daily, rs_time, tables_queried = fetch_redshift_daily(args.year, quarters)
    active_players, my_time = fetch_active_players()

    daily = build_daily(redshift_daily, args.year)
    monthly = aggregate_monthly(daily)
    quarterly = aggregate_quarterly(monthly, args.year, quarters)
    highlights = compute_highlights(daily, monthly)
    month_over_month = compute_month_over_month(monthly)

    totals = {
        "offers": sum(d['offers'] for d in daily),
        "upsells": sum(d['upsells'] for d in daily),
        "days": len(daily),
    }

    result = {
        "success": True,
        "year": args.year,
        "daily": daily,
        "monthly": monthly,
        "quarterly": quarterly,
        "totals": totals,
        "active_players": active_players,
        "highlights": highlights,
        "month_over_month": month_over_month,
        "tables_queried": tables_queried,
        "timing": {
            "redshift_seconds": round(rs_time, 2),
            "mysql_seconds": round(my_time, 2),
        },
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
