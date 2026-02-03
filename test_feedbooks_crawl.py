#!/usr/bin/env python3
"""Test Feedbooks ODL crawler with credentials."""

import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

from opds_tools.util.odl_inventory_generator import crawl_odl_feed_for_inventory

# TODO: Replace these with your EXACT credentials from the browser
# Copy/paste the exact username and password that works in browser
feed_url = "https://market.feedbooks.com/api/libraries/harvest.json"
username = "262"  # REPLACE WITH EXACT VALUE FROM BROWSER
password = "abcde123456"  # REPLACE WITH EXACT VALUE FROM BROWSER

print(f"\nTesting ODL inventory crawler with:")
print(f"  URL: {feed_url}")
print(f"  Username: {username}")
print(f"  Password: {password[:3]}*** (first 3 chars)")
print(f"  Auth: HTTP Basic Auth\n")

result = crawl_odl_feed_for_inventory(
    feed_url,
    max_pages=2,
    username=username,
    password=password
)

print(f"\n✅ Crawl completed!")
print(f"   Total publications: {len(result['inventory'])}")
print(f"   Pages crawled: {result['stats']['pages_crawled']}")
print(f"   Errors: {len(result['errors'])}")

if result['errors']:
    print(f"\n⚠️  Errors encountered:")
    for err in result['errors'][:3]:
        print(f"   - {err}")
