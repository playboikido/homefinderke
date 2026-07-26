import base64
import logging
import requests
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15  # seconds — prevents a hung Safaricom request from freezing a web worker


def get_base_url():
    return "https://sandbox.safaricom.co.ke" if settings.MPESA_ENV == 'sandbox' else "https://api.safaricom.co.ke"


def get_access_token():
    url = f"{get_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(
        url,
        auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET),
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()['access_token']


def normalize_phone(phone):
    phone = phone.strip().replace(' ', '').replace('+', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    return phone


def initiate_stk_push(
    phone_number,
    amount,
    callback_url=None,
    account_reference="HomeFinderKE",
    transaction_desc="Support HomeFinder Kenya",
):
    """
    Initiates an M-Pesa STK Push. Returns Safaricom's JSON response on success.
    On any network/auth failure, returns a dict shaped like Safaricom's own
    error responses (ResponseCode != '0') so callers can handle both cases
    the same way without needing a separate try/except at every call site.
    """
    try:
        access_token = get_access_token()
    except requests.exceptions.RequestException as e:
        logger.error("M-Pesa auth failed: %s", e)
        return {'ResponseCode': '1', 'errorMessage': 'Payment service is temporarily unavailable. Please try again shortly.'}

    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(
        f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode()
    ).decode()

    phone = normalize_phone(phone_number)

    payload = {
        "BusinessShortCode": settings.MPESA_SHORTCODE,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": int(amount),
        "PartyA": phone,
        "PartyB": settings.MPESA_SHORTCODE,
        "PhoneNumber": phone,
        "CallBackURL": callback_url or settings.MPESA_CALLBACK_URL,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_desc,
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{get_base_url()}/mpesa/stkpush/v1/processrequest"

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        body = getattr(e.response, 'text', '')[:500] if getattr(e, 'response', None) is not None else ''
        logger.error("M-Pesa STK push failed: %s | response body: %s", e, body)
        return {'ResponseCode': '1', 'errorMessage': 'Could not reach M-Pesa right now. Please try again shortly.'}