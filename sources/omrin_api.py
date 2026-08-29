# omrin_api.py
import base64
import json
import uuid
from datetime import datetime
import requests
from rsa import pkcs1
from Crypto.PublicKey import RSA

BASE_URL = "https://api-omrin.freed.nl/Account"
DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def get_omrin_token(app_id: str) -> dict:
    resp = requests.post(
        f"{BASE_URL}/GetToken/",
        json={"AppId": app_id, "AppVersion": "", "OsVersion": "", "Platform": "iCal"},
        timeout=30,
    ).json()
    if not resp.get("PublicKey"):
        raise ValueError("Failed to retrieve public key from Omrin API.")
    return resp


def encrypt_request(public_key_b64: str, request_body: dict) -> str:
    rsa_public_key = RSA.importKey(base64.b64decode(public_key_b64))
    encrypted = pkcs1.encrypt(json.dumps(request_body).encode(), rsa_public_key)
    return base64.b64encode(encrypted).decode("utf-8")


def fetch_calendar_data(app_id: str, encrypted_request: str) -> list:
    resp = requests.post(
        f"{BASE_URL}/FetchAccount/{app_id}",
        '"' + encrypted_request + '"',
        timeout=60,
    ).json()
    if not resp.get("Success"):
        raise ValueError(f"Omrin API returned an unsuccessful response: {resp}")
    return resp.get("CalendarV2") or []


def fetch_omrin_calendar(postal_code: str, house_number: int) -> list:
    app_id = str(uuid.uuid1())
    token = get_omrin_token(app_id)
    request_body = {
        "a": False,
        "Email": None,
        "Password": None,
        "PostalCode": postal_code,
        "HouseNumber": house_number,
    }
    encrypted_request = encrypt_request(token["PublicKey"], request_body)
    return fetch_calendar_data(app_id, encrypted_request)
