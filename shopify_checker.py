shopify_checker.py - Updated with fixes
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
import logging
import traceback

logger = logging.getLogger(__name__)

async def _shopify_check(session, domain, cc, mm, yy, cvv, progress_cb=None):
    """Debug version - logs every step"""
    try:
        logger.info(f"[DEBUG] Starting checkout on {domain}")
        
        # Step 1: Find product
        logger.info(f"[DEBUG] Finding product on {domain}...")
        product = await _fetch_products(session, domain)
        if not product:
            logger.error(f"[DEBUG] ❌ No products on {domain}")
            return None, "No products available", "Shopify Payments", None
        logger.info(f"[DEBUG] ✅ Found product: {product}")
        
        # Step 2: Add to cart
        logger.info(f"[DEBUG] Adding to cart...")
        # ... your existing add to cart code ...
        
        # Step 3: Create checkout
        logger.info(f"[DEBUG] Creating checkout...")
        # ... your existing checkout creation code ...
        
        # Step 4: Get session token
        logger.info(f"[DEBUG] Getting session token...")
        # ... your existing session token code ...
        
        # Step 5: Negotiate
        logger.info(f"[DEBUG] Negotiating...")
        result = await _negotiate(session, graphql_url, headers, variables)
        logger.info(f"[DEBUG] Negotiate result: {result}")
        
        if not result:
            logger.error(f"[DEBUG] ❌ Negotiation failed on {domain}")
            return None, "Negotiate error: no response", "Shopify Payments", None
        
        logger.info(f"[DEBUG] ✅ Checkout complete on {domain}")
        return "1.00", "CCN Live - insufficient_funds", "Shopify Payments", None
        
    except Exception as e:
        logger.error(f"[DEBUG] ❌ Exception on {domain}: {e}")
        logger.error(traceback.format_exc())
        return None, f"Error: {str(e)[:100]}", "Shopify Payments", None
