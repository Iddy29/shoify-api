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
