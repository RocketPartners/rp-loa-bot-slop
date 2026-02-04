#!/bin/bash
set -e

echo "🧪 Testing Slack Integration..."
echo ""

# Check if environment variables are set
if [ -z "$SLACK_BOT_TOKEN" ]; then
  echo "⚠️  Environment variables not loaded"
  echo "Loading from .env file..."
  export $(cat .env | xargs)
fi

# Send a test message
TEST_MESSAGE="*🧪 Test Message*
This is a test message from the LoA Application Insights automation.

Sent at: $(date)
From: $(hostname)

✅ If you can see this, Slack integration is working!"

python3 send_slack_message.py "$TEST_MESSAGE"
