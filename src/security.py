import hmac
import hashlib
import os
from fastapi import Request, HTTPException, Header
from src.config import settings

async def verify_whatsapp_signature(request: Request):
    """
    Verifies the HMAC-SHA256 signature for WhatsApp webhook requests.
    Raises HTTPException 401 if signature is missing or invalid.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Hub-Signature-256 header")

    body = await request.body()
    app_secret = settings.WHATSAPP_APP_SECRET.encode('utf-8')

    # Calculate expected signature
    calculated_signature = hmac.new(app_secret, body, hashlib.sha256).hexdigest()
    expected_signature = f"sha256={calculated_signature}"

    if not hmac.compare_digest(signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp signature")
    return True # Signature is valid

async def verify_telegram_secret(x_telegram_bot_api_secret_token: str = Header(None)):
    """
    Verifies the X-Telegram-Bot-Api-Secret-Token for Telegram webhook requests.
    Raises HTTPException 401 if token is missing or invalid.
    """
    if not x_telegram_bot_api_secret_token:
        raise HTTPException(status_code=401, detail="Missing X-Telegram-Bot-Api-Secret-Token header")

    if x_telegram_bot_api_secret_token != settings.TELEGRAM_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid Telegram secret token")
    return True # Token is valid
