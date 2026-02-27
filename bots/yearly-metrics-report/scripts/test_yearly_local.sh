#!/bin/bash
# Test yearly report locally — loads root .env and runs the pipeline
# Usage:
#   cd bots/yearly-metrics-report
#   bash scripts/test_yearly_local.sh                    # current year
#   REPORT_YEAR=2026 bash scripts/test_yearly_local.sh   # specific year

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
[ -n "$REPORT_YEAR" ] && ARGS="$ARGS --year $REPORT_YEAR"

echo "=== Yearly Metrics Report (Local Test) ==="
echo "Parameters: year=${REPORT_YEAR:-current}"

echo ""
echo "Step 1: Fetching yearly metrics..."
python3 "$BOT_DIR/src/fetch_yearly_metrics.py" $ARGS > "$BOT_DIR/yearly_data.json"

echo ""
echo "Data saved to yearly_data.json"
echo ""

# Show summary
python3 -c "
import json
with open('$BOT_DIR/yearly_data.json') as f:
    d = json.load(f)
t = d['totals']
print(f\"Year: {d['year']}\")
print(f\"  Tables: {', '.join(d.get('tables_queried', []))}\")
print(f\"  Days:       {t['days']}\")
print(f\"  Offers:     {t['offers']:,}\")
print(f\"  Upsells:    {t['upsells']:,}\")
rate = t['upsells'] / t['offers'] * 100 if t['offers'] > 0 else 0
print(f\"  Upsell Rate: {rate:.2f}%\")
ap = d.get('active_players')
if ap is not None:
    print(f\"  Active Players: {ap:,}\")
else:
    print(f\"  Active Players: N/A\")
print()
print('Monthly:')
for m in d.get('monthly', []):
    print(f\"  {m['month_name']:<12} {m['offers']:>12,} offers  {m['upsells']:>10,} upsells  {m['rate']:.1f}%\")
print()
print('Quarterly:')
for q in d.get('quarterly', []):
    print(f\"  Q{q['quarter']}  {q['offers']:>12,} offers  {q['upsells']:>10,} upsells  {q['rate']:.1f}%\")
print()
h = d.get('highlights', {})
if h:
    bm = h.get('best_month', {})
    wm = h.get('worst_month', {})
    bd = h.get('best_day', {})
    if bm:
        print(f\"  Best Month:  {bm['month_name']} ({bm['offers']:,} offers)\")
    if wm:
        print(f\"  Worst Month: {wm['month_name']} ({wm['offers']:,} offers)\")
    if bd:
        print(f\"  Peak Day:    {bd['date']} ({bd['offers']:,} offers)\")
print(f\"  Redshift:   {d['timing']['redshift_seconds']}s\")
print(f\"  MySQL:      {d['timing']['mysql_seconds']}s\")
"

echo ""
echo "Step 2: Posting to Slack..."
cat "$BOT_DIR/yearly_data.json" | python3 "$BOT_DIR/src/post_yearly_to_slack.py"

echo ""
echo "Done."
