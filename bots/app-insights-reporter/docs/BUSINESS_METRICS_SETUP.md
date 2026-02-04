# Business Metrics Setup Guide

## Current Status

✅ **Offers (Redshift)** - Working! Fetches from `firehose_offer9` and `offer_2025_q4`
⏳ **Player Heartbeats (MySQL)** - Needs configuration
⏳ **Upsells (Redshift)** - Needs query

## What's Needed

### 1. MySQL Configuration (Player Heartbeats)

Update `.env` with MySQL connection details:

```bash
MYSQL_HOST=your_mysql_host_here
MYSQL_PORT=3306
MYSQL_DATABASE=your_database_name
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
```

**Questions:**
- What's the MySQL host/endpoint?
- Which database contains player heartbeat data?
- What are the read-only credentials?
- Which table/columns contain heartbeat data?

**Example Query Needed:**
```sql
-- Count unique players with heartbeats in last 24 hours
SELECT COUNT(DISTINCT player_id)
FROM heartbeats_table
WHERE timestamp >= NOW() - INTERVAL 1 DAY;
```

### 2. Redshift Upsells Query

Update `fetch_business_metrics.py` line 71 with the actual upsells query:

```python
upsells_query = """
-- Replace this with actual upsells query
SELECT COUNT(*) FROM warehouse.public.upsells_table
WHERE created_at >= GETDATE() - INTERVAL '1 day';
"""
```

**Questions:**
- Which table(s) contain upsell data in Redshift?
- What columns identify an upsell?
- What's the timestamp column name?
- Any filters needed (like cashierkey for offers)?

**Example Tables to Check:**
- `warehouse.public.firehose_upsell*`
- `warehouse.public.upsell_*`
- Or is it in the same offer tables with a flag?

## Installation

### Local Development

```bash
# Install MySQL connector
pip3 install mysql-connector-python

# Test the script
export $(grep -v '^#' .env | xargs)
python3 fetch_business_metrics.py
```

### LaunchCode

The Dockerfile already includes `mysql-connector-python`, so it will work automatically once the environment variables are set.

## Testing

Once you provide the details above, you can test with:

```bash
# Test Redshift only (offers + upsells)
export $(grep -v '^#' .env | xargs)
python3 fetch_business_metrics.py

# Expected output:
# {
#   "success": true,
#   "data": {
#     "offers_last_24h": 209603,
#     "player_heartbeats": 3776,
#     "upsells": 17959
#   }
# }
```

## Files Modified

- ✅ `fetch_business_metrics.py` - Added MySQL support and upsells placeholder
- ✅ `.env` - Added MySQL configuration section
- ✅ `Dockerfile` - Added `mysql-connector-python`
- ✅ Script handles graceful failures (if MySQL not configured, continues with Redshift only)

## Next Steps

1. **Provide MySQL Details** - Connection info and heartbeats query
2. **Provide Upsells Query** - Redshift table/query for upsells
3. **Test Locally** - Run `python3 fetch_business_metrics.py`
4. **Update LaunchCode** - Sync all changes to production
5. **Enjoy Complete Metrics** - All 3 metrics in daily Slack reports! 🎉
