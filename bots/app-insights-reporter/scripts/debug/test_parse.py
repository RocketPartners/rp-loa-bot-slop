#!/usr/bin/env python3
"""
Debug script to test report parsing
"""
import sys
sys.path.insert(0, '/Users/lep143/IdeaProjects/work/automations')

from post_to_slack import parse_report

report = """🔴 LoA Player Health Status - February 2, 2026

Metrics: 2352 exceptions | 0 requests | 2313802 dependencies (202 failed) | P95: 1042ms

Business Metrics: 1410 offers | 3768 player heartbeats | 63 upsells

Top 5 Problems:
1. **1394×** TypeError at PromoAdFactory.getProductImage - Cannot read 'contentMappingBlockNeeded' of undefined
2. **500×** TypeError at BasketAdQueue.handleLineItemEvents - Cannot read 'canDisplay' of undefined
3. **195×** TypeError at PromoAdFactory.buildPriceBubbleDescription - Cannot read 'ngrp_ITTDetailExtension' of null
4. **180×** TypeError at Offer.void - Cannot read 'id' of undefined
5. **42×** Error at Mashgin11Renderer.renderBasketAdThankYou - this.currentAd is not defined

🚨 Action Required: Fix null/undefined reference handling in PromoAdFactory.getProductImage (1394 occurrences) and BasketAdQueue.handleLineItemEvents (500 occurrences)."""

status_emoji, metrics, business_metrics, issues, action = parse_report(report)

print("=" * 60)
print("PARSED REPORT:")
print("=" * 60)
print(f"Status Emoji: {status_emoji}")
print(f"Metrics: {metrics}")
print(f"Business Metrics: '{business_metrics}'")
print(f"Number of Issues: {len(issues)}")
print(f"Action: {action}")
print("=" * 60)

if business_metrics:
    print("✅ Business metrics parsed successfully!")
else:
    print("❌ Business metrics NOT parsed - empty string!")
