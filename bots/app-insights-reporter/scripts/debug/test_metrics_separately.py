#!/usr/bin/env python3
"""
Test each business metric separately to identify performance issues
"""
import os
import time
import mysql.connector
import psycopg2

# Configuration
REDSHIFT_HOST = os.environ.get('REDSHIFT_HOST')
REDSHIFT_PORT = os.environ.get('REDSHIFT_PORT', '5439')
REDSHIFT_DATABASE = os.environ.get('REDSHIFT_DATABASE')
REDSHIFT_USER = os.environ.get('REDSHIFT_USER')
REDSHIFT_PASSWORD = os.environ.get('REDSHIFT_PASSWORD')

MYSQL_HOST = os.environ.get('MYSQL_HOST')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE')
MYSQL_USER = os.environ.get('MYSQL_USER')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')

def test_redshift_offers():
    """Test Redshift offers query"""
    print("🎁 Testing Offers query...")
    start = time.time()

    try:
        conn = psycopg2.connect(
            host=REDSHIFT_HOST, port=REDSHIFT_PORT,
            database=REDSHIFT_DATABASE, user=REDSHIFT_USER,
            password=REDSHIFT_PASSWORD, connect_timeout=10
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) AS offers_last_24h
            FROM (
                SELECT playercode FROM warehouse.public.firehose_offer9
                WHERE createdat >= GETDATE() - INTERVAL '1 day'
                  AND cashierkey LIKE '%CashierName%'
                UNION ALL
                SELECT playercode FROM warehouse.public.offer_2025_q4
                WHERE createdat >= GETDATE() - INTERVAL '1 day'
                  AND cashierkey LIKE '%CashierName%'
            ) AS combined;
        """)

        count = cursor.fetchone()[0]
        elapsed = time.time() - start

        cursor.close()
        conn.close()

        print(f"   ✅ Offers: {count:,} (took {elapsed:.2f}s)")
        return count
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def test_redshift_upsells():
    """Test Redshift upsells query"""
    print("💰 Testing Upsells query...")
    start = time.time()

    try:
        conn = psycopg2.connect(
            host=REDSHIFT_HOST, port=REDSHIFT_PORT,
            database=REDSHIFT_DATABASE, user=REDSHIFT_USER,
            password=REDSHIFT_PASSWORD, connect_timeout=10
        )
        cursor = conn.cursor()

        cursor.execute("""
            SELECT COUNT(*) AS upsell_last_24h
            FROM (
                SELECT playercode FROM warehouse.public.firehose_offer9
                WHERE createdat >= GETDATE() - INTERVAL '1 day'
                  AND cashierkey LIKE '%CashierName%'
                  AND liftadded = true
                UNION ALL
                SELECT playercode FROM warehouse.public.offer_2025_q4
                WHERE createdat >= GETDATE() - INTERVAL '1 day'
                  AND cashierkey LIKE '%CashierName%'
                  AND liftadded = true
            ) AS combined;
        """)

        count = cursor.fetchone()[0]
        elapsed = time.time() - start

        cursor.close()
        conn.close()

        print(f"   ✅ Upsells: {count:,} (took {elapsed:.2f}s)")
        return count
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def test_mysql_heartbeats():
    """Test MySQL heartbeats query"""
    print("🎮 Testing Player Heartbeats query...")
    start = time.time()

    try:
        conn = mysql.connector.connect(
            host=MYSQL_HOST, port=int(MYSQL_PORT),
            database=MYSQL_DATABASE, user=MYSQL_USER,
            password=MYSQL_PASSWORD, connect_timeout=10
        )
        cursor = conn.cursor()

        print("   📊 Executing query (may take a while if table is large)...")
        cursor.execute("""
            SELECT COUNT(DISTINCT playerKey) AS unique_players_last_24h
            FROM lift.Heartbeat
            WHERE macAddress LIKE '70:0A%'
              AND timestamp >= NOW() - INTERVAL 1 DAY;
        """)

        count = cursor.fetchone()[0]
        elapsed = time.time() - start

        cursor.close()
        conn.close()

        print(f"   ✅ Player Heartbeats: {count:,} (took {elapsed:.2f}s)")

        if elapsed > 10:
            print(f"   ⚠️  Query took {elapsed:.2f}s - consider adding indexes:")
            print("      CREATE INDEX idx_heartbeat_timestamp ON lift.Heartbeat(timestamp);")
            print("      CREATE INDEX idx_heartbeat_macaddress ON lift.Heartbeat(macAddress);")

        return count
    except Exception as e:
        elapsed = time.time() - start
        print(f"   ❌ Error after {elapsed:.2f}s: {e}")
        return None

if __name__ == '__main__':
    print("=" * 60)
    print("Testing Business Metrics Separately")
    print("=" * 60)
    print()

    offers = test_redshift_offers()
    print()

    upsells = test_redshift_upsells()
    print()

    heartbeats = test_mysql_heartbeats()
    print()

    print("=" * 60)
    print("Summary:")
    print(f"  🎁 Offers: {offers:,}" if offers else "  🎁 Offers: Failed")
    print(f"  💰 Upsells: {upsells:,}" if upsells else "  💰 Upsells: Failed")
    print(f"  🎮 Heartbeats: {heartbeats:,}" if heartbeats else "  🎮 Heartbeats: Failed")
    print("=" * 60)
