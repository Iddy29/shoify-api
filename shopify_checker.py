# shopify_checker.py - Updated with fixes
import logging
import json
import asyncio
import random
import aiohttp
import traceback

logger = logging.getLogger(__name__)

# ============================================================
# UPDATED: Working Sites List
# ============================================================
SHOPIFY_SITES = [
    "www.rarebeauty.com",
    "www.olehenriksen.com",
    "www.fentybeauty.com",
    "shopmissa.com",
    "www.anastasiabeverlyhills.com",
    "www.glowrecipe.com",
    "www.skims.com",
    "www.kyliecosmetics.com",
]

# ============================================================
# UPDATED: Better Headers
# ============================================================
def _checkout_graphql_headers(domain, checkout_url):
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json',
        'Origin': f'https://{domain}',
        'Referer': checkout_url,
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="130", "Google Chrome";v="130"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
    }

# ============================================================
# MAIN FUNCTION
# ============================================================
async def shopify_native_check_rich(cc, mm, yy, cvv, site=None, progress_cb=None):
    logger.info(f"[MAIN] Checking card: {cc[:6]}xxxx{cc[-4:]}")
    
    if site:
        logger.info(f"[MAIN] Using provided site: {site}")
        try:
            result = await _shopify_check(None, site, cc, mm, yy, cvv, progress_cb)
            if result and result[1] and "error" not in result[1].lower():
                return result
        except Exception as e:
            logger.warning(f"[MAIN] Site {site} failed: {e}")
    
    for s in SHOPIFY_SITES[:5]:
        try:
            logger.info(f"[MAIN] Trying site: {s}")
            result = await _shopify_check(None, s, cc, mm, yy, cvv, progress_cb)
            if result and result[1] and "error" not in result[1].lower():
                return result
        except Exception as e:
            logger.warning(f"[MAIN] Site {s} failed: {e}")
            continue
    
    logger.error("[MAIN] All sites failed")
    return None, "All sites failed - Negotiate error", "Shopify Payments", None

# ============================================================
# IMPORTANT: Replace this with your actual _shopify_check
# ============================================================
async def _shopify_check(session, domain, cc, mm, yy, cvv, progress_cb=None):
    """Placeholder - replace with your actual Shopify checkout logic"""
    logger.info(f"[SHOPIFY] Testing on {domain}")
    
    # This is a simplified version for testing
    # Replace this with your real Shopify checkout logic
    if domain in ["www.rarebeauty.com", "www.olehenriksen.com", "www.fentybeauty.com"]:
        return "1.00", "CCN Live - insufficient_funds", "Shopify Payments", None
    else:
        return None, "No products available", "Shopify Payments", None

# Your existing functions (negotiate, etc.) go here
# ... keep the rest of your original code below this line ...
