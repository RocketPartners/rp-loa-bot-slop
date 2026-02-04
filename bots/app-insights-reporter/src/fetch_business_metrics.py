#!/usr/bin/env python3
"""
Fetch business metrics from Redshift warehouse and MySQL database
Outputs JSON to stdout
"""
import os
import json
import sys
import time
from datetime import datetime, timedelta
from get_date_range import get_date_range

# Try to import database libraries
try:
    import psycopg2
except ImportError:
    print(json.dumps({
        "success": False,
        "error": "psycopg2 not installed. Run: pip install psycopg2-binary"
    }))
    sys.exit(1)

try:
    import mysql.connector
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

# Redshift Configuration
REDSHIFT_HOST = os.environ.get('REDSHIFT_HOST')
REDSHIFT_PORT = os.environ.get('REDSHIFT_PORT', '5439')
REDSHIFT_DATABASE = os.environ.get('REDSHIFT_DATABASE')
REDSHIFT_USER = os.environ.get('REDSHIFT_USER')
REDSHIFT_PASSWORD = os.environ.get('REDSHIFT_PASSWORD')

# MySQL Configuration
MYSQL_HOST = os.environ.get('MYSQL_HOST')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE')
MYSQL_USER = os.environ.get('MYSQL_USER')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')

def fetch_redshift_metrics(interval_sql):
    """Fetch offers and upsells from Redshift"""
    offers_count = None
    upsells_count = None

    start_time = time.time()

    try:
        # Connect to Redshift
        conn = psycopg2.connect(
            host=REDSHIFT_HOST,
            port=REDSHIFT_PORT,
            database=REDSHIFT_DATABASE,
            user=REDSHIFT_USER,
            password=REDSHIFT_PASSWORD,
            connect_timeout=10
        )

        cursor = conn.cursor()

        # Query for Offers (dynamic interval based on day of week)
        offers_query = f"""
        SELECT COUNT(*) AS offers_last_24h
        FROM (
            SELECT playercode
            FROM warehouse.public.firehose_offer9
            WHERE createdat >= GETDATE() - {interval_sql}
              AND cashierkey LIKE '%CashierName%'

            UNION ALL

            SELECT playercode
            FROM warehouse.public.offer_2025_q4
            WHERE createdat >= GETDATE() - {interval_sql}
              AND cashierkey LIKE '%CashierName%'
        ) AS combined;
        """

        cursor.execute(offers_query)
        offers_count = cursor.fetchone()[0]

        # Query for Upsells (dynamic interval) - offers where liftadded = true
        upsells_query = f"""
        SELECT COUNT(*) AS upsell_last_24h
        FROM (
            SELECT playercode
            FROM warehouse.public.firehose_offer9
            WHERE createdat >= GETDATE() - {interval_sql}
              AND cashierkey LIKE '%CashierName%'
              AND liftadded = true

            UNION ALL

            SELECT playercode
            FROM warehouse.public.offer_2025_q4
            WHERE createdat >= GETDATE() - {interval_sql}
              AND cashierkey LIKE '%CashierName%'
              AND liftadded = true
        ) AS combined;
        """

        cursor.execute(upsells_query)
        upsells_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        elapsed_time = time.time() - start_time
        return offers_count, upsells_count, elapsed_time

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"⚠️  Redshift error: {str(e)}", file=sys.stderr)
        return offers_count, upsells_count, elapsed_time

def fetch_mysql_heartbeats(interval_sql):
    """Fetch player heartbeats from MySQL"""
    if not MYSQL_AVAILABLE:
        return None, 0

    if not all([MYSQL_HOST, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD]):
        return None, 0

    start_time = time.time()

    try:
        # Connect to MySQL
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=int(MYSQL_PORT),
            database=MYSQL_DATABASE,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            connect_timeout=10
        )

        cursor = conn.cursor()

        # Query for Player Heartbeats (dynamic interval based on day of week)
        heartbeats_query = f"""
        SELECT COUNT(DISTINCT playerKey) AS unique_players_last_24h
        FROM lift.Heartbeat
        WHERE macAddress LIKE '70:0A%'
          AND timestamp >= NOW() - {interval_sql};
        """

        cursor.execute(heartbeats_query)
        result = cursor.fetchone()
        heartbeats_count = result[0] if result else None

        cursor.close()
        conn.close()

        elapsed_time = time.time() - start_time
        return heartbeats_count, elapsed_time

    except Exception as e:
        elapsed_time = time.time() - start_time
        print(f"⚠️  MySQL error: {str(e)}", file=sys.stderr)
        return None, elapsed_time

def fetch_business_metrics():
    """Fetch business metrics from Redshift and MySQL with dynamic date ranges"""

    try:
        # Get date range based on day of week
        date_info = get_date_range()

        # Fetch from Redshift (offers and upsells)
        offers_count, upsells_count, redshift_time = fetch_redshift_metrics(
            date_info['interval_sql_redshift']
        )

        # Fetch from MySQL (player heartbeats)
        heartbeats_count, mysql_time = fetch_mysql_heartbeats(
            date_info['interval_sql_mysql']
        )

        return {
            "success": True,
            "data": {
                "offers_last_24h": offers_count,
                "player_heartbeats": heartbeats_count,
                "upsells": upsells_count
            },
            "date_range": {
                "date_range": date_info['date_range'],
                "days_text": date_info['days_text'],
                "days_back": date_info['days_back']
            },
            "timing": {
                "redshift_seconds": round(redshift_time, 2),
                "mysql_seconds": round(mysql_time, 2),
                "total_seconds": round(redshift_time + mysql_time, 2)
            }
        }

    except psycopg2.OperationalError as e:
        return {
            "success": False,
            "error": f"Connection failed: {str(e)}"
        }
    except psycopg2.Error as e:
        return {
            "success": False,
            "error": f"Database error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }

def main():
    """Main execution function"""

    # Validate required environment variables
    if not all([REDSHIFT_HOST, REDSHIFT_DATABASE, REDSHIFT_USER, REDSHIFT_PASSWORD]):
        missing = []
        if not REDSHIFT_HOST: missing.append("REDSHIFT_HOST")
        if not REDSHIFT_DATABASE: missing.append("REDSHIFT_DATABASE")
        if not REDSHIFT_USER: missing.append("REDSHIFT_USER")
        if not REDSHIFT_PASSWORD: missing.append("REDSHIFT_PASSWORD")

        print(json.dumps({
            "success": False,
            "error": f"Missing required environment variables: {', '.join(missing)}"
        }), file=sys.stderr)
        return 1

    # Fetch metrics
    result = fetch_business_metrics()

    # Output JSON to stdout
    print(json.dumps(result, indent=2))

    # Return appropriate exit code
    return 0 if result.get("success") else 1

if __name__ == '__main__':
    sys.exit(main())
