import base64
import requests
from datetime import datetime
from django.conf import settings

def get_base_url():
    return "https://sandbox.safaricom.co.ke" if settings.MPESA_ENV == 'sandbox' else "https://api.safaricom.co.ke"

def get_access_token():
    url = f"{get_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    response = requests.get(url, auth=(settings.MPESA_CONSUMER_KEY, settings.MPESA_CONSUMER_SECRET))
    response.raise_for_status()
    return response.json()['access_token']

def normalize_phone(phone):
    phone = phone.strip().replace(' ', '').replace('+', '')
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    return phone

def initiate_stk_push(phone_number, amount):
    access_token = get_access_token()
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
        "CallBackURL": settings.MPESA_CALLBACK_URL,
        "AccountReference": "HomeFinderKE",
        "TransactionDesc": "Support HomeFinder Kenya",
    }
    headers = {"Authorization": f"Bearer {access_token}"}
    url = f"{get_base_url()}/mpesa/stkpush/v1/processrequest"
    response = requests.post(url, json=payload, headers=headers)
    return response.json()