# Changelog

## 2026-01-30 - Timeline Charts & Dependencies Fix

### Added
- **Exception Timeline Chart**: Displays hourly exception counts over 24 hours
  - QuickChart API integration for professional bar charts
  - ASCII fallback chart for when QuickChart is unavailable
  - Chart inserted between metrics grid and top issues section

### Fixed
- **Dependencies Parsing Bug**: Regex patterns now properly handle:
  - Numbers with commas: "2,079 dependencies"
  - Decimal numbers: "2.5M dependencies"
  - K/M/B suffixes: "2500K dependencies"
  - All combinations: "2,500.5K dependencies"
  - **Impact**: Previously "2,079 dependencies (205 failed)" would parse as "079 (205 failed)"

### Changes
- Updated `fetch_insights.py`:
  - Added timeline data query: `bin(timestamp, 1h)` for hourly grouping
  - Returns 4 data types: Summary, Exception, ExceptionGroup, Timeline

- Updated `post_to_slack.py`:
  - Added `generate_chart_url()` function for QuickChart integration
  - Added `create_ascii_chart()` function for fallback ASCII visualization
  - Fixed all metric regex patterns to handle commas and decimals
  - Timeline chart automatically displays when data is available

### Technical Details

**KQL Query Addition:**
```kql
let exceptionTimeline = exceptions
| where timestamp > ago(24h)
| summarize Count = count() by bin(timestamp, 1h)
| order by timestamp asc
| extend DataType = "Timeline";
```

**Fixed Regex Patterns:**
```python
# Before
r'([0-9.]+[KMB]?)\s*dependencies'  # Would fail on "2,079"

# After
r'([0-9,]+(?:\.[0-9]+)?[KMB]?)\s*dependencies'  # Handles "2,079", "2.5M", "2,500.5K"
```

**QuickChart Configuration:**
- Chart type: Bar chart
- Width: 800px, Height: 300px
- Color: Red (#DC2626) with 80% opacity
- X-axis: Time (UTC) in HH:MM format
- Y-axis: Exception count
- Title: "Exception Timeline - Last 24 Hours"

### Testing
- ✅ Local testing: `bash test_local.sh`
- ✅ LaunchCode sync: Both environments use identical code
- ✅ Dependencies parsing: Now shows correct values
- ✅ Timeline chart: Renders successfully in Slack

### Next Steps
1. Monitor Slack messages to verify dependencies display correctly
2. Verify timeline chart renders in production
3. Consider adding more visualizations (trend arrows, comparison to previous day)
