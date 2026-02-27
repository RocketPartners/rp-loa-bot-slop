#!/usr/bin/env python3
"""
Fetch daily offers, upsells for a given month, plus current active player count.

Usage:
  python3 fetch_monthly_metrics.py                          # current month
  python3 fetch_monthly_metrics.py --month 2 --year 2026    # Feb 2026
  python3 fetch_monthly_metrics.py --month 1 --quarter 1 --year 2026

Outputs JSON to stdout.
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime, date, time as dt_time, timedelta, timezone
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


def parse_args():
    parser = argparse.ArgumentParser(description='Fetch daily metrics for a month')
    now = datetime.now(ET)
    parser.add_argument('--month', type=int, default=now.month, help='Month (1-12)')
    parser.add_argument('--year', type=int, default=now.year, help='Year (e.g. 2026)')
    parser.add_argument('--quarter', type=int, default=None,
                        help='Quarter (1-4). Defaults to the quarter of the given month.')
    args = parser.parse_args()

    if args.quarter is None:
        args.quarter = quarter_for_month(args.month)

    if not (1 <= args.month <= 12):
        print(f"Invalid month: {args.month}", file=sys.stderr)
        sys.exit(1)
    if not (1 <= args.quarter <= 4):
        print(f"Invalid quarter: {args.quarter}", file=sys.stderr)
        sys.exit(1)

    return args


def fetch_redshift_daily(year, month, quarter):
    """Fetch daily offers and upsells from Redshift for the given month (ET calendar days)."""
    start_time = time.time()

    first_day = date(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date(year, month, last_day_num)

    today_et = datetime.now(ET).date()
    if last_day >= today_et:
        last_day = today_et

    quarterly_table = offer_table_name(year, quarter)

    # createdat is char(29) with ISO 8601 + offset (e.g. '2026-02-19T23:57:05.741-07:00')
    # Use string comparison as rough pre-filter (1-day buffer for timezone edge cases)
    # then CONVERT_TIMEZONE for precise ET calendar day grouping
    buffer_start = (first_day - timedelta(days=1)).isoformat()
    buffer_end = (last_day + timedelta(days=2)).isoformat()
    et_date = "DATE(CONVERT_TIMEZONE('UTC', 'America/New_York', CAST(CAST(createdat AS TIMESTAMPTZ) AS TIMESTAMP)))"

    query = f"""
    SELECT
        {et_date} AS day,
        COUNT(*) AS offers,
        SUM(CASE WHEN liftadded = true THEN 1 ELSE 0 END) AS upsells
    FROM (
        SELECT createdat, liftadded
        FROM warehouse.public.firehose_offer9
        WHERE createdat >= '{buffer_start}'
          AND createdat < '{buffer_end}'
          AND cashierkey LIKE '%CashierName%'

        UNION ALL

        SELECT createdat, liftadded
        FROM {quarterly_table}
        WHERE createdat >= '{buffer_start}'
          AND createdat < '{buffer_end}'
          AND cashierkey LIKE '%CashierName%'
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
            connect_timeout=10
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
        return daily, elapsed

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"Redshift error: {e}", file=sys.stderr)
        return [], elapsed


def fetch_active_players():
    """
    Fetch current active player count from MySQL.

    The lift.Heartbeat table stores current state only (latest heartbeat per player),
    so historical daily counts are not meaningful. We query a snapshot of distinct
    active players whose last heartbeat was within the last 24 hours.
    """
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


def build_daily(redshift_daily, year, month):
    """Build daily list from Redshift data, filling missing days with 0."""
    last_day_num = calendar.monthrange(year, month)[1]
    today = datetime.now(ET).date()

    rs_map = {r['date']: r for r in redshift_daily}

    merged = []
    for d in range(1, last_day_num + 1):
        day = date(year, month, d)
        if day > today:
            break
        day_str = day.isoformat()
        rs = rs_map.get(day_str, {})
        merged.append({
            "date": day_str,
            "day_name": day.strftime('%A'),
            "offers": rs.get('offers', 0),
            "upsells": rs.get('upsells', 0),
        })
    return merged


def main():
    args = parse_args()

    if not all([REDSHIFT_HOST, REDSHIFT_DATABASE, REDSHIFT_USER, REDSHIFT_PASSWORD]):
        print(json.dumps({"success": False, "error": "Missing Redshift credentials"}))
        return 1

    month_name = calendar.month_name[args.month]
    quarterly_table = offer_table_name(args.year, args.quarter)

    print(f"Fetching daily metrics for {month_name} {args.year} (Q{args.quarter})", file=sys.stderr)
    print(f"Redshift table: {quarterly_table}", file=sys.stderr)

    redshift_daily, rs_time = fetch_redshift_daily(args.year, args.month, args.quarter)
    active_players, my_time = fetch_active_players()

    daily = build_daily(redshift_daily, args.year, args.month)

    totals = {
        "offers": sum(d['offers'] for d in daily),
        "upsells": sum(d['upsells'] for d in daily),
    }

    result = {
        "success": True,
        "month": args.month,
        "month_name": month_name,
        "year": args.year,
        "quarter": args.quarter,
        "quarterly_table": quarterly_table,
        "daily": daily,
        "totals": totals,
        "active_players": active_players,
        "timing": {
            "redshift_seconds": round(rs_time, 2),
            "mysql_seconds": round(my_time, 2),
        },
    }

    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
