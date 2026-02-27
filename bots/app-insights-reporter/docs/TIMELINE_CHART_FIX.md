# Timeline Chart Fix - ASCII vs QuickChart

## The Problem

The exception timeline chart was showing as a download link "(95 kB)" instead of displaying inline in Slack.

### Why QuickChart Images Failed

QuickChart generates PNG images from chart configs, but they often fail in Slack due to:

1. **Workspace Security Settings** - Some Slack workspaces block external images
2. **Image Proxy Timeouts** - Slack's image proxy may timeout fetching from QuickChart
3. **Rate Limiting** - QuickChart may rate-limit requests
4. **URL Complexity** - Long URLs (multi-day data) can fail

## The Solution

**Switched to ASCII charts** - Always display, no external dependencies, reliable.

### ASCII Chart Example

```
📊 Exception Timeline (Last 12 Hours)
```
08:00 ██████████ 145
09:00 ████████████ 167
10:00 ███████ 103
11:00 ██████████████ 189
12:00 ████████████████████ 215
13:00 ██████ 89
14:00 ████████ 112
```
```

### Benefits

✅ Always displays - No external image loading
✅ Fast - Renders instantly in Slack
✅ Reliable - No dependencies on QuickChart
✅ Works everywhere - No workspace security issues
✅ Copy-paste friendly - Can copy data from chart

## Comparison

| Feature | QuickChart (PNG) | ASCII Chart |
|---------|------------------|-------------|
| Display | ❌ Often fails | ✅ Always works |
| Load time | ⏱️ 2-5 seconds | ⚡ Instant |
| Dependencies | ❌ External service | ✅ None |
| Data visibility | Good | Excellent |
| Professional look | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## Re-enabling QuickChart (Optional)

If you want to try QuickChart images again (e.g., if workspace settings change):

### In `post_to_slack.py`, replace the ASCII section with:

```python
# Try QuickChart first, fallback to ASCII
chart_url = generate_chart_url(timeline_data)
if chart_url:
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": "*📈 Exception Timeline - Last 24 Hours*"
        }
    })
    blocks.append({
        "type": "image",
        "image_url": chart_url,
        "alt_text": "Exception timeline chart"
    })
else:
    # Fallback to ASCII
    ascii_chart = create_ascii_chart(timeline_data)
    if ascii_chart:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ascii_chart
            }
        })
```

### Test QuickChart URL

```bash
python3 << 'EOF'
import requests

# Your QuickChart URL here
url = "https://quickchart.io/chart?..."

try:
    response = requests.head(url, timeout=5)
    print(f"Status: {response.status_code}")
    print(f"Content-Type: {response.headers.get('Content-Type')}")
    print(f"Size: {response.headers.get('Content-Length')} bytes")
except Exception as e:
    print(f"Error: {e}")
EOF
```

## Troubleshooting

### "Image shows as download link"

**Cause:** Slack workspace blocks external images

**Fix:**
1. Ask Slack admin to allow images from `quickchart.io`
2. Or use ASCII charts (current solution)

### "Chart shows old data"

**Cause:** QuickChart may cache responses

**Fix:** Add cache-busting parameter:
```python
chart_url = f"{base_url}&t={int(time.time())}"
```

### "URL too long error"

**Cause:** Too many data points (multi-day ranges)

**Fix:** Already handled - limits to last 24 hours

## Current Implementation

- ✅ ASCII charts enabled by default
- ✅ Reliable display in all Slack workspaces
- ✅ Shows last 12 hours of data
- ✅ Proper time formatting (HH:MM)
- ✅ Right-aligned numbers for readability

## Future Improvements

Consider:
- Add date labels (Mon, Tue) for multi-day views
- Color-code bars (red for high, green for low)
- Show percentage change vs previous period
- Add min/max indicators

---

**Status:** ✅ Fixed
**Solution:** ASCII charts (reliable)
**Date:** February 9, 2026
