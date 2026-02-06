# Slack Message Format Fix

## The Problem

Slack messages were poorly formatted with:
- Missing business metrics section
- Squished text with no spacing
- Raw chart URLs instead of embedded images
- Incomplete metrics (only exceptions, missing requests/dependencies/P95)
- Inconsistent formatting

Example of bad output:
```
LoA Daily ReportFebruary 06, 2026 at 10:05 PM Application Insights - February 05, 2026 Key Metrics
- TotalExceptions: 6,417 Exception Timeline - Last 24 Hourshttps://quickchart.io/chart?c=%7B...
```

## Root Cause

Claude was generating reports in inconsistent formats that the Slack parser couldn't parse reliably. The parser would fail and dump raw text.

## The Solution

### Created `format_report.py`

A Python script that:
1. Reads JSON files directly (`insights_data.json`, `business_metrics.json`)
2. Extracts metrics programmatically (no AI interpretation)
3. Formats output in exact expected format
4. Guarantees consistency every time

### Updated Scripts

**run.sh (LaunchCode):**
```bash
# Before: Ask Claude to format
ANALYSIS=$(echo "Format this data..." | claude)

# After: Use Python formatter
ANALYSIS=$(python3 /app/format_report.py /app/insights_data.json /app/business_metrics.json)
```

**test_local.sh (Local testing):**
```bash
# Same change for local testing
ANALYSIS=$(python3 "$BOT_DIR/src/format_report.py" "$BOT_DIR/insights_data.json" "$BOT_DIR/business_metrics.json")
```

### Enhanced Error Handling

Added debug output to `post_to_slack.py`:
- Shows what was parsed from the report
- Warns if parsing fails
- Falls back to plain text if needed

## Benefits

| Before | After |
|--------|-------|
| ❌ Inconsistent format | ✅ Always formatted correctly |
| ❌ Missing business metrics | ✅ Always includes all sections |
| ❌ Slow (Claude API call) | ✅ Fast (direct Python) |
| ❌ Unpredictable | ✅ Deterministic |
| ❌ Hard to debug | ✅ Clear debug output |

## Expected Output Format

Now every report will have this structure:

```
🔴 LoA Player Health Status - February 6, 2026

Metrics: 6,417 exceptions | 0 requests | 2,313,802 dependencies (202 failed) | P95: 1042ms

Business Metrics: 1,823 offers | 3,768 player heartbeats | 95 upsells

Top 5 Problems:
1. **3,866×** TypeError at BasketAdQueue.handleLineItemEvents - Cannot read 'canDisplay' of undefined
2. **1,827×** TypeError at PromoAdFactory.getProductImage - Cannot read 'contentMappingBlockNeeded' of undefined
3. **316×** TypeError at Offer.void - Cannot read 'id' of undefined
4. **274×** TypeError at PromoAdFactory.buildPriceBubbleDescription - Cannot read 'ngrp_ITTDetailExtension' of null
5. **78×** Error at Mashgin11Renderer.renderBasketAdThankYou - this.currentAd is not defined

🚨 Action Required: Investigate BasketAdQueue.handleLineItemEvents null-safety - accounts for 60% of exceptions
```

Which then gets parsed into a beautiful Block Kit message with:
- Header with status emoji and date
- Business metrics section (first)
- Application Insights section (second)
- Timeline chart (embedded image)
- Top 5 problems with ASCII bars
- Action section
- Performance timing footer

## Testing Locally

```bash
cd bots/app-insights-reporter
./test.sh
```

Should now produce properly formatted Slack messages.

## LaunchCode Deployment

LaunchCode job has been updated with:
- New `format_report.py` file
- Updated `run.sh` script
- Enhanced `post_to_slack.py` with debugging

## Files Changed

1. `src/format_report.py` - NEW file, Python formatter
2. `src/post_to_slack.py` - Added debug output and fallback
3. `scripts/run.sh` - Use Python formatter instead of Claude
4. `scripts/test_local.sh` - Use Python formatter instead of Claude

## Rollback Plan

If issues occur, revert `run.sh` to use Claude formatting:
```bash
ANALYSIS=$(echo "Format report..." | claude -p --dangerously-skip-permissions)
```

But this should not be necessary - Python formatter is more reliable.

## Future Improvements

Consider:
- Add retry logic if JSON parsing fails
- Cache formatted reports for debugging
- Add unit tests for formatter
- Support multiple date ranges in format

## Validation

To verify the fix is working:
1. Check Slack messages have proper structure
2. Business metrics appear at the top
3. All sections are present
4. Numbers are formatted with commas
5. Chart images are embedded (not raw URLs)

---

**Status:** ✅ Fixed and deployed
**Date:** February 6, 2026
**Version:** 2.0.0
