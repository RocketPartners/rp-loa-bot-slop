#!/usr/bin/env python3
"""
Debug Azure Application Insights access
"""
import os
import json
import requests

WORKSPACE_ID = os.environ.get('AZURE_APP_INSIGHTS_WORKSPACE_ID')
ACCESS_TOKEN = os.environ.get('AZURE_ACCESS_TOKEN')

print("=== Azure Application Insights Debug ===\n")

# Check environment variables
print("Environment Variables:")
print(f"  WORKSPACE_ID: {WORKSPACE_ID}")
print(f"  ACCESS_TOKEN: {'***' + ACCESS_TOKEN[-4:] if ACCESS_TOKEN and len(ACCESS_TOKEN) > 4 else 'NOT SET'}")
print()

if not ACCESS_TOKEN or not WORKSPACE_ID:
    print("❌ Missing required environment variables")
    exit(1)

# Test 1: Try to access the workspace metadata
print("Test 1: Checking workspace access...")
url = f'https://api.applicationinsights.io/v1/apps/{WORKSPACE_ID}'
headers = {
    'Authorization': f'Bearer {ACCESS_TOKEN}',
    'Content-Type': 'application/json'
}

try:
    response = requests.get(url, headers=headers, timeout=10)
    print(f"  Status Code: {response.status_code}")

    if response.status_code == 200:
        print("  ✅ Workspace found!")
        data = response.json()
        print(f"  App Name: {data.get('name', 'N/A')}")
        print(f"  App ID: {data.get('appId', 'N/A')}")
    else:
        print(f"  ❌ Failed: {response.text}")
except Exception as e:
    print(f"  ❌ Error: {str(e)}")

print()

# Test 2: Try a simple query
print("Test 2: Testing simple query...")
query_url = f'https://api.applicationinsights.io/v1/apps/{WORKSPACE_ID}/query'
simple_query = {
    'query': 'requests | take 1'
}

try:
    response = requests.post(query_url, headers=headers, json=simple_query, timeout=10)
    print(f"  Status Code: {response.status_code}")

    if response.status_code == 200:
        print("  ✅ Query successful!")
        result = response.json()
        print(f"  Tables returned: {len(result.get('tables', []))}")
    else:
        print(f"  ❌ Failed: {response.text}")
except Exception as e:
    print(f"  ❌ Error: {str(e)}")

print()
print("=== Troubleshooting Tips ===")
print("1. Make sure you're using the Application ID, not the Workspace ID")
print("2. Verify your access token hasn't expired (they last ~1 hour)")
print("3. Check that the token has 'Reader' permissions for Application Insights")
print("4. You can find the Application ID in Azure Portal:")
print("   - Go to Application Insights resource")
print("   - Look for 'API Access' in the left menu")
print("   - Copy the 'Application ID' (not Instrumentation Key)")
