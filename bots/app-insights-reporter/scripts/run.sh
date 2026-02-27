#!/bin/bash
set -e

echo "=== LoA Application Insights Summary ==="
echo "Starting at: $(date)"
echo "Timezone: America/New_York"
echo "Authentication: Azure Access Token"

# Configure Claude Code with LaunchCode (if API credentials provided)
if [ -n "$LAUNCHCODE_API_URL" ] && [ -n "$LAUNCHCODE_API_KEY" ]; then
  echo "🔧 Configuring Claude Code with LaunchCode..."
  curl -fsSL -H "X-API-Key: $LAUNCHCODE_API_KEY" "$LAUNCHCODE_API_URL/api/claude/setup" | python3
fi

# Azure CLI login (one-time, token cached in ~/.azure)
# If OKTA_TOTP_CODE is set, automates the full Okta device-code flow via Playwright.
# Once logged in, subsequent runs skip this step.
if command -v az &> /dev/null; then
  if az account show &> /dev/null; then
    echo "Azure CLI: logged in"
  elif [ -n "$AZURE_EMAIL" ] && [ -n "$AZURE_PASSWORD" ] && [ -n "$OKTA_TOTP_CODE" ]; then
    echo "Azure CLI: not logged in — running automated login via Playwright..."
    python3 /app/az_login_playwright.py
    if [ $? -ne 0 ]; then
      echo "Azure CLI login failed (non-blocking, continuing...)"
    fi
  else
    echo "Azure CLI: not logged in (set AZURE_EMAIL, AZURE_PASSWORD, OKTA_TOTP_CODE to auto-login)"
  fi
fi

# OpenVPN connection (required for Redshift/MySQL access)
if [ -n "$OPENVPN_USER" ] && [ -n "$OPENVPN_PASS" ] && [ -f /app/vpn.ovpn ]; then
  echo "Connecting to VPN (using .ovpn config)..."

  # Write auth credentials file
  echo -e "${OPENVPN_USER}\n${OPENVPN_PASS}" > /tmp/vpn_auth.txt
  chmod 600 /tmp/vpn_auth.txt

  # Start OpenVPN using the full .ovpn profile
  openvpn --config /app/vpn.ovpn \
    --auth-user-pass /tmp/vpn_auth.txt \
    --auth-nocache \
    --script-security 2 \
    --route-delay 2 \
    --daemon \
    --log /tmp/openvpn.log

  # Wait for tunnel to come up
  echo "Waiting for VPN tunnel..."
  for i in $(seq 1 60); do
    if ip addr show tun0 > /dev/null 2>&1; then
      echo "VPN tunnel interface up"
      # Wait extra time for routes to be pushed and applied
      sleep 5
      echo "VPN routes:"
      ip route | grep tun || echo "  (no tun routes found)"
      echo "VPN connected"
      break
    fi
    if [ "$i" -eq 60 ]; then
      echo "VPN connection timed out"
      cat /tmp/openvpn.log 2>/dev/null || true
      exit 1
    fi
    sleep 1
  done

  rm -f /tmp/vpn_auth.txt
fi

# Verify environment variables
echo "📋 Checking environment variables..."
[ -z "$AZURE_APP_INSIGHTS_WORKSPACE_ID" ] && echo "⚠️  AZURE_APP_INSIGHTS_WORKSPACE_ID not set"
[ -z "$AZURE_ACCESS_TOKEN" ] && echo "❌ AZURE_ACCESS_TOKEN not set - REQUIRED"
[ -z "$SLACK_BOT_TOKEN" ] && echo "❌ SLACK_BOT_TOKEN not set - REQUIRED"

# Verify Redshift credentials (optional - for business metrics)
if [ -n "$REDSHIFT_HOST" ]; then
  echo "✅ Redshift configuration detected"
  [ -z "$REDSHIFT_USER" ] && echo "⚠️  REDSHIFT_USER not set"
  [ -z "$REDSHIFT_PASSWORD" ] && echo "⚠️  REDSHIFT_PASSWORD not set"
  [ -z "$REDSHIFT_DATABASE" ] && echo "⚠️  REDSHIFT_DATABASE not set"
fi

if [ -n "$AZURE_ACCESS_TOKEN" ]; then
  echo "✅ Azure access token configured"
  echo "ℹ️  Note: Access tokens expire after 1 hour. Refresh before scheduled runs."
else
  echo "❌ No Azure access token found"
  exit 1
fi

# Step 1: Fetch Application Insights data
echo "🚀 Step 1: Fetching Application Insights data..."
python3 /app/fetch_insights.py > /app/insights_data.json

if [ $? -ne 0 ]; then
  echo "❌ Failed to fetch Application Insights data"
  exit 1
fi

echo "✅ Data fetched successfully"

# Step 1.5: Fetch business metrics from Redshift (optional)
if [ -n "$REDSHIFT_HOST" ] && [ -n "$REDSHIFT_USER" ] && [ -n "$REDSHIFT_PASSWORD" ]; then
  echo "📊 Step 1.5: Fetching business metrics from Redshift..."
  python3 /app/fetch_business_metrics.py > /app/business_metrics.json 2>/dev/null

  if [ $? -eq 0 ]; then
    echo "✅ Business metrics fetched successfully"
  else
    echo "⚠️  Business metrics fetch failed (non-critical, continuing...)"
    echo '{"success": false, "data": {}}' > /app/business_metrics.json
  fi
else
  echo "ℹ️  Skipping business metrics (Redshift not configured)"
  echo '{"success": false, "data": {}}' > /app/business_metrics.json
fi

# Step 2: Format report from JSON data
echo "📊 Step 2: Formatting report from data..."
ANALYSIS=$(python3 /app/format_report.py /app/insights_data.json /app/business_metrics.json)

if [ $? -ne 0 ]; then
  echo "❌ Claude Code analysis failed"
  exit 1
fi

echo "✅ Analysis completed"

# Step 3: Post to Slack
echo "📤 Step 3: Posting report to Slack..."
echo "$ANALYSIS" | python3 /app/post_to_slack.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
  echo "✅ Job completed successfully at $(date)"
else
  echo "❌ Job failed with exit code $exit_code at $(date)"
fi

exit $exit_code
