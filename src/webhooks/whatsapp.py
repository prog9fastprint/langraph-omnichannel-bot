import hmac
import hashlib
from fastapi import Request, HTTPException, Query
from src.config import settings

async def verify_whatsapp_signature(request: Request) -> None:
    """Verify HMAC-SHA256 signature from Meta webhook."""
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")

    body = await request.body()
    app_secret = settings.WHATSAPP_APP_SECRET.encode("utf-8")
    expected = hmac.new(app_secret, body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(signature, f"sha256={expected}"):
        raise HTTPException(status_code=401, detail="Invalid signature")

async def verify_whatsapp_webhook(
    mode: str = Query(...),
    token: str = Query(...),
    challenge: str = Query(...)
) -> int:
    """Handle the GET verification handshake."""
    if mode == "subscribe" and token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        return int(challenge)
    raise HTTPException(status_code=403, detail="Verification failed")