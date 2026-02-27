#!/bin/bash
set -e

echo "=== Monthly Metrics Report ==="
echo "Starting at: $(date)"

# Configure LaunchCode (if available)
if [ -n "$LAUNCHCODE_API_URL" ] && [ -n "$LAUNCHCODE_API_KEY" ]; then
  echo "Configuring LaunchCode..."
  curl -fsSL -H "X-API-Key: $LAUNCHCODE_API_KEY" "$LAUNCHCODE_API_URL/api/claude/setup" | python3
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

# Build args from environment variables (set by LaunchCode job params or CLI)
ARGS=""
[ -n "$REPORT_MONTH" ] && ARGS="$ARGS --month $REPORT_MONTH"
[ -n "$REPORT_YEAR" ] && ARGS="$ARGS --year $REPORT_YEAR"
[ -n "$REPORT_QUARTER" ] && ARGS="$ARGS --quarter $REPORT_QUARTER"

echo "Parameters: month=${REPORT_MONTH:-current} year=${REPORT_YEAR:-current} quarter=${REPORT_QUARTER:-auto}"

# Step 1: Fetch metrics
echo "Step 1: Fetching monthly metrics..."
python3 /app/fetch_monthly_metrics.py $ARGS > /app/monthly_data.json

if [ $? -ne 0 ]; then
  echo "Failed to fetch metrics"
  exit 1
fi

echo "Data fetched"

# Step 2: Post to Slack
echo "Step 2: Posting to Slack..."
cat /app/monthly_data.json | python3 /app/post_to_slack.py

exit_code=$?
if [ $exit_code -eq 0 ]; then
  echo "Job completed at $(date)"
else
  echo "Job failed with exit code $exit_code"
fi

exit $exit_code
