#!/bin/bash
# Test locally — loads root .env and runs the pipeline
# Usage:
#   cd bots/monthly-metrics-report
#   bash scripts/test_local.sh                         # current month
#   REPORT_MONTH=1 REPORT_YEAR=2026 bash scripts/test_local.sh   # Jan 2026

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$(dirname "$BOT_DIR")")"

# Load root .env
if [ -f "$ROOT_DIR/.env" ]; then
  echo "Loading $ROOT_DIR/.env"
  set -a
  source "$ROOT_DIR/.env"
  set +a
fi

# Build args
ARGS=""
[ -n "$REPORT_MONTH" ] && ARGS="$ARGS --month $REPORT_MONTH"
[ -n "$REPORT_YEAR" ] && ARGS="$ARGS --year $REPORT_YEAR"
[ -n "$REPORT_QUARTER" ] && ARGS="$ARGS --quarter $REPORT_QUARTER"

echo "=== Monthly Metrics Report (Local Test) ==="
echo "Parameters: month=${REPORT_MONTH:-current} year=${REPORT_YEAR:-current} quarter=${REPORT_QUARTER:-auto}"

echo ""
echo "Step 1: Fetching metrics..."
python3 "$BOT_DIR/src/fetch_monthly_metrics.py" $ARGS > "$BOT_DIR/monthly_data.json"

echo ""
echo "Data saved to monthly_data.json"
echo ""

# Show summary
python3 -c "
import json
with open('$BOT_DIR/monthly_data.json') as f:
    d = json.load(f)
t = d['totals']
print(f\"{d['month_name']} {d['year']} (Q{d['quarter']})\")
print(f\"  Table: {d['quarterly_table']}\")
print(f\"  Days:  {len(d['daily'])}\")
print(f\"  Offers:     {t['offers']:,}\")
print(f\"  Upsells:    {t['upsells']:,}\")
ap = d.get('active_players')
if ap is not None:
    print(f\"  Active Players: {ap:,}\")
else:
    print(f\"  Active Players: N/A\")
rate = t['upsells'] / t['offers'] * 100 if t['offers'] > 0 else 0
print(f\"  Upsell Rate: {rate:.2f}%\")
print(f\"  Redshift:   {d['timing']['redshift_seconds']}s\")
print(f\"  MySQL:      {d['timing']['mysql_seconds']}s\")
"

echo ""
echo "Step 2: Posting to Slack..."
cat "$BOT_DIR/monthly_data.json" | python3 "$BOT_DIR/src/post_to_slack.py"

echo ""
echo "Done."
