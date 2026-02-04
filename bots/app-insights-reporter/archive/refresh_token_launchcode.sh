#!/bin/bash

echo "  🔄 Refreshing Azure Application Insights API token..."

# Check if Service Principal credentials are available
if [ -z "$AZURE_TENANT_ID" ] || [ -z "$AZURE_CLIENT_ID" ] || [ -z "$AZURE_CLIENT_SECRET" ]; then
  echo "  ⚠️  Service Principal credentials not configured"
  echo "  Using existing AZURE_ACCESS_TOKEN (if set)"

  if [ -z "$AZURE_ACCESS_TOKEN" ]; then
    echo "  ❌ No access token available"
    exit 1
  fi

  exit 0
fi

echo "  Using Azure Service Principal to get fresh token..."

# Get token using Azure REST API
TOKEN_RESPONSE=$(curl -s -X POST "https://login.microsoftonline.com/${AZURE_TENANT_ID}/oauth2/v2.0/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=${AZURE_CLIENT_ID}" \
  -d "client_secret=${AZURE_CLIENT_SECRET}" \
  -d "scope=https://api.applicationinsights.io/.default" \
  -d "grant_type=client_credentials")

# Extract access token from response
AZURE_ACCESS_TOKEN=$(echo $TOKEN_RESPONSE | python3 -c "import sys, json; print(json.load(sys.stdin).get('access_token', ''))" 2>/dev/null)

if [ -z "$AZURE_ACCESS_TOKEN" ]; then
  echo "  ❌ Failed to get access token"
  echo "  Response: $TOKEN_RESPONSE"
  exit 1
fi

# Export for use in the same shell session
export AZURE_ACCESS_TOKEN

echo "  ✅ Fresh access token obtained (expires in ~1 hour)"
