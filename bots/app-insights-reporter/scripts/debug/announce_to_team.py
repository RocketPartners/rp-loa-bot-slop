#!/usr/bin/env python3
"""
Post announcement about the new LoA Application Insights automation
"""
import os
import sys
from datetime import datetime
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# Configuration
SLACK_CHANNEL = os.environ.get('SLACK_CHANNEL', '#int-lift-loa-app-insights')
SLACK_TOKEN = os.environ.get('SLACK_BOT_TOKEN')

def post_announcement():
    """Post the announcement to Slack"""

    if not SLACK_TOKEN:
        print("❌ SLACK_BOT_TOKEN is required", file=sys.stderr)
        return 1

    client = WebClient(token=SLACK_TOKEN)

    try:
        # Build the announcement message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🚀 New Automation: Daily LoA Application Insights Reports",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Hey team! 👋 We've just launched an automated daily health monitoring system for our LoA application. Every morning at 8:30 AM EST, you'll receive a comprehensive insights report right here in this channel."
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*✨ What You'll Get Daily:*"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": "*🎯 Health Status*\nAt-a-glance system health with visual indicators"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*📊 Key Metrics*\nExceptions, requests, success rate, P95 response time"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*📈 Timeline Charts*\nHourly exception trends over 24 hours"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*🔥 Top 5 Issues*\nMost frequent problems with visual bar charts"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*⚡ Action Items*\nAI-powered recommendations for each issue"
                    },
                    {
                        "type": "mrkdwn",
                        "text": "*🔗 Dependencies*\nExternal API health and failure rates"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🎨 Features We're Proud Of:*\n\n• *Smart Analysis* - Claude AI analyzes 24 hours of data and identifies patterns\n• *Beautiful Visualizations* - Professional charts and ASCII bar graphs\n• *Proactive Alerts* - Get notified before users complain\n• *Zero Manual Work* - Fully automated with LaunchCode + Azure CLI\n• *Mobile Friendly* - Optimized Block Kit layout for on-the-go viewing\n• *Direct Portal Links* - One click to Azure for deep dives"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🛠️ Tech Stack:*"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "🐳 Docker • 🐍 Python • ☁️ Azure Application Insights • 🤖 Claude Code AI • 💬 Slack Block Kit • ⚙️ LaunchCode Automations"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📅 Schedule:*\nDaily at *8:30 AM EST* (Mon-Sun)\n\n*🎯 What This Means for You:*\n✅ Start your day knowing exactly what needs attention\n✅ Catch issues before they escalate\n✅ Track trends and improvements over time\n✅ Spend less time digging through logs"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*💡 Example Use Cases:*\n\n*Scenario 1:* You see 2,000+ TypeError exceptions from `BasketAdQueue`\n→ The report tells you: _\"Add null/undefined checks in BasketAdQueue.handleLineItemEvents\"_\n\n*Scenario 2:* P95 response time jumps to 3000ms\n→ Timeline chart shows it spiked at 2 AM\n→ Check if a deployment or batch job coincided\n\n*Scenario 3:* Dependencies show 500+ failures\n→ Know immediately if external APIs are degraded"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🙋 Questions or Feedback?*\nThis automation is continuously improving. If you have ideas for additional metrics, visualizations, or alerts, let's chat!"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "🚀 Built with ❤️ by the team • Powered by LaunchCode Platform • First report drops tomorrow at 8:30 AM EST"
                    }
                ]
            }
        ]

        # Post the announcement
        response = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text="🚀 New Automation: Daily LoA Application Insights Reports",
            blocks=blocks,
            unfurl_links=False,
            unfurl_media=False
        )

        print(f"✅ Announcement posted successfully to {SLACK_CHANNEL}")
        print(f"📊 Message timestamp: {response['ts']}")
        return 0

    except SlackApiError as e:
        print(f"❌ Error posting to Slack: {e.response['error']}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(post_announcement())
