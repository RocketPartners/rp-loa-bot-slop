#!/usr/bin/env python3
"""
Calculate date range based on day of week using US Eastern (Atlanta) timezone.
Returns calendar day boundaries for consistent SQL queries.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ET = ZoneInfo('America/New_York')


def get_date_range():
    """
    Returns calendar day boundaries for the reporting period in Eastern Time.

    Monday: Reports on Friday, Saturday, Sunday
    Tuesday-Sunday: Reports on the previous day

    Returns ET date boundaries plus a 1-day string buffer for Redshift
    WHERE clauses (createdat is a char column with ISO 8601 + offset).
    """
    now = datetime.now(ET)
    today = now.date()
    day_of_week = today.weekday()  # Monday=0, Sunday=6

    if day_of_week == 0:  # Monday
        days_back = 3
        start_date = today - timedelta(days=3)  # Friday
        end_date = today  # Monday (exclusive)
        date_range = f"{start_date.strftime('%B %d')} - {(end_date - timedelta(days=1)).strftime('%B %d, %Y')}"
        days_text = "Friday, Saturday, Sunday"
    else:
        days_back = 1
        start_date = today - timedelta(days=1)
        end_date = today
        date_range = start_date.strftime('%B %d, %Y')
        days_text = start_date.strftime('%A')

    return {
        'days_back': days_back,
        'date_range': date_range,
        'days_text': days_text,
        # ET calendar day boundaries (inclusive start, exclusive end)
        'start_date': start_date.isoformat(),
        'end_date': end_date.isoformat(),
        # 1-day buffer for string-based pre-filter on createdat (char column)
        'buffer_start': (start_date - timedelta(days=1)).isoformat(),
        'buffer_end': (end_date + timedelta(days=1)).isoformat(),
        'report_date': start_date.isoformat(),
        # Keep interval for heartbeats (rolling window, table stores current state only)
        'interval_sql_mysql': f"INTERVAL {days_back} DAY",
    }


if __name__ == '__main__':
    import json
    result = get_date_range()
    print(json.dumps(result, indent=2))
