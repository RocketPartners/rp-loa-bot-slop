#!/usr/bin/env python3
"""
Explore MySQL database to find heartbeat and other business metrics
"""
import os
import sys
import mysql.connector

# MySQL Configuration
MYSQL_HOST = os.environ.get('MYSQL_HOST')
MYSQL_PORT = os.environ.get('MYSQL_PORT', '3306')
MYSQL_DATABASE = os.environ.get('MYSQL_DATABASE')
MYSQL_USER = os.environ.get('MYSQL_USER')
MYSQL_PASSWORD = os.environ.get('MYSQL_PASSWORD')

def explore_mysql():
    """Explore MySQL database structure"""

    try:
        print("🔍 Connecting to MySQL...")
        conn = mysql.connector.connect(
            host=MYSQL_HOST,
            port=int(MYSQL_PORT),
            database=MYSQL_DATABASE,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            connect_timeout=10
        )

        cursor = conn.cursor()

        print(f"✅ Connected to {MYSQL_DATABASE} database")
        print("=" * 80)

        # List all tables
        print("\n📋 Available Tables:")
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        for table in tables:
            table_name = table[0]

            # Get row count
            try:
                cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                count = cursor.fetchone()[0]

                # Highlight tables that might contain heartbeat data
                emoji = "💓" if "heartbeat" in table_name.lower() or "ping" in table_name.lower() else "📊"
                print(f"  {emoji} {table_name}: {count:,} rows")

            except Exception as e:
                print(f"  ⚠️  {table_name}: (error counting)")

        # Look for heartbeat-related tables
        print("\n" + "=" * 80)
        print("🔍 Searching for heartbeat/ping tables...")
        heartbeat_tables = [t[0] for t in tables if 'heartbeat' in t[0].lower() or 'ping' in t[0].lower() or 'health' in t[0].lower()]

        if heartbeat_tables:
            print(f"✅ Found {len(heartbeat_tables)} potential heartbeat table(s):")
            for table in heartbeat_tables:
                print(f"\n📋 Table: {table}")

                # Show table structure
                cursor.execute(f"DESCRIBE `{table}`")
                columns = cursor.fetchall()
                print("  Columns:")
                for col in columns:
                    print(f"    - {col[0]} ({col[1]})")

                # Show sample data
                print("  Sample data (last 5 rows):")
                cursor.execute(f"SELECT * FROM `{table}` ORDER BY id DESC LIMIT 5")
                samples = cursor.fetchall()
                for sample in samples:
                    print(f"    {sample[:5]}...")  # Show first 5 columns
        else:
            print("⚠️  No obvious heartbeat tables found")
            print("\n💡 Common table naming patterns:")
            print("   - player_heartbeats")
            print("   - heartbeat_log")
            print("   - player_ping")
            print("   - health_checks")

        cursor.close()
        conn.close()

        return 0

    except mysql.connector.Error as e:
        print(f"❌ MySQL Error: {e}")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == '__main__':
    if not all([MYSQL_HOST, MYSQL_DATABASE, MYSQL_USER, MYSQL_PASSWORD]):
        print("❌ Missing MySQL configuration in .env")
        sys.exit(1)

    sys.exit(explore_mysql())
