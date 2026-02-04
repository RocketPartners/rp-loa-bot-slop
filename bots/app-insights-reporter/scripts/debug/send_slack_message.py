#!/usr/bin/env python3
"""
Send a test message to Slack
Usage:
  python3 send_slack_message.py "Your message here"
  or pipe message:
  echo "Your message" | python3 send_slack_message.py
"""
import os
import sys
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configuration
SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', '#int-lift-loa-app-insights')
SLACK_TOKEN = os.environ.get('SLACK_BOT_TOKEN')

def send_message(message):
    """Send a message to Slack"""

    if not SLACK_TOKEN:
        print("❌ SLACK_BOT_TOKEN environment variable is required", file=sys.stderr)
        print("Run: export $(cat .env | xargs)", file=sys.stderr)
        return 1

    client = WebClient(token=SLACK_TOKEN)

    try:
        print(f"📤 Sending message to {SLACK_CHANNEL}...")

        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message,
            mrkdwn=True
        )

        print(f"✅ Message sent successfully!")
        print(f"   Channel: {SLACK_CHANNEL}")
        print(f"   Timestamp: {response['ts']}")
        return 0

    except SlackApiError as e:
        print(f"❌ Slack API Error: {e.response['error']}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}", file=sys.stderr)
        return 1

def main():
    """Main function"""

    # Check if message is provided as argument
    if len(sys.argv) > 1:
        message = ' '.join(sys.argv[1:])
    # Otherwise read from stdin
    elif not sys.stdin.isatty():
        message = sys.stdin.read().strip()
    else:
        print("Usage:")
        print("  python3 send_slack_message.py \"Your message here\"")
        print("  echo \"Your message\" | python3 send_slack_message.py")
        return 1

    if not message:
        print("❌ No message provided", file=sys.stderr)
        return 1

    return send_message(message)

if __name__ == '__main__':
    sys.exit(main())
