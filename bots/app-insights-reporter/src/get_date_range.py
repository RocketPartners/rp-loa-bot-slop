#!/usr/bin/env python3
"""
Calculate date range based on day of week
"""
from datetime import datetime, timedelta

def get_date_range():
    """
    Returns the number of days to look back and a human-readable date range

    Monday: Look back 3 days (Friday, Saturday, Sunday)
    Tuesday-Sunday: Look back 1 day (previous day)
    """
    today = datetime.now()
    day_of_week = today.weekday()  # Monday=0, Sunday=6

    if day_of_week == 0:  # Monday
        days_back = 3
        start_date = today - timedelta(days=3)  # Friday
        date_range = f"{start_date.strftime('%B %d')} - {today.strftime('%B %d, %Y')}"
        days_text = "Friday, Saturday, Sunday"
    else:
        days_back = 1
        start_date = today - timedelta(days=1)
        date_range = start_date.strftime('%B %d, %Y')
        days_text = start_date.strftime('%A')

    return {
        'days_back': days_back,
        'date_range': date_range,
        'days_text': days_text,
        'interval_sql_mysql': f"INTERVAL {days_back} DAY",
        'interval_sql_redshift': f"INTERVAL '{days_back} day'"
    }

if __name__ == '__main__':
    import json
    result = get_date_range()
    print(json.dumps(result, indent=2))
