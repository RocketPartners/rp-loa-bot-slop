#!/bin/bash

echo "  🔄 Refreshing Azure Application Insights API token..."

# Get token for Application Insights API
TOKEN=$(az account get-access-token --resource=https://api.applicationinsights.io --query accessToken -o tsv 2>/dev/null)

if [ -z "$TOKEN" ]; then
  echo "  ❌ Failed to get token. Make sure you're logged in with 'az login'"
  exit 1
fi

# Update .env file
if [[ "$OSTYPE" == "darwin"* ]]; then
  # macOS
  sed -i '' "s|AZURE_ACCESS_TOKEN=.*|AZURE_ACCESS_TOKEN=$TOKEN|" .env
else
  # Linux
  sed -i "s|AZURE_ACCESS_TOKEN=.*|AZURE_ACCESS_TOKEN=$TOKEN|" .env
fi

echo "  ✅ Token updated in .env file (expires in ~1 hour)"
