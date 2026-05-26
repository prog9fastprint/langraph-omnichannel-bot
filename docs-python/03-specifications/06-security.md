# 06 — Security Requirements (Python / Omnichannel)

## Security Checklist

| Requirement | Implementation |
|-------------|---------------|
| WA Webhook Security | HMAC-SHA256 (`X-Hub-Signature-256`) |
| TG Webhook Security | `X-Telegram-Bot-Api-Secret-Token` |
| Rate limiting | Redis-based rate limiting per `platform:user_id` |
| SQL injection prevention | N/A (Bot uses ERP APIs) |
| Input validation | Pydantic schemas for both webhooks |

---

## 1. Webhook Signature Verification (WhatsApp)

```python
import hmac
import hashlib
import os
from fastapi import Request, HTTPException

async def verify_whatsapp_signature(request: Request):
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(status_code=401, detail="Missing signature")

    body = await request.body()
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "").encode('utf-8')
    expected_signature = hmac.new(app_secret, body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(signature, f"sha256={expected_signature}"):
        raise HTTPException(status_code=401, detail="Invalid signature")
```

---

## 2. Webhook Signature Verification (Telegram)

```python
from fastapi import Header, HTTPException
import os

TELEGRAM_SECRET_TOKEN = os.getenv("TELEGRAM_SECRET_TOKEN")

async def verify_telegram_secret(x_telegram_bot_api_secret_token: str = Header(None)):
    if x_telegram_bot_api_secret_token != TELEGRAM_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid secret token")
```

---

## 3. Rate Limiting (Cross-Platform)

Apply rate limiting using the normalized `user_id` and `platform`.

```python
import redis.asyncio as redis
from fastapi import HTTPException

redis_client = redis.from_url("redis://localhost:6379/0")

async def check_user_rate_limit(platform: str, user_id: str):
    key = f"rate:{platform}:{user_id}"
    
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, 60) # 1 minute window
        
    if count > 30:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
```

---

## 4. Input Validation with Pydantic

Instead of trusting raw JSON, use Pydantic to validate Meta and Telegram payloads.

**Telegram Example:**
```python
class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[dict] = None
```

**WhatsApp Example:**
```python
class WhatsAppPayload(BaseModel):
    object: str
    entry: list
```

---

## 5. Error Handling (Silencing Errors to Avoid Retries)

Both Meta and Telegram will retry webhooks infinitely if your server returns a `5xx` error. You must catch AI errors internally and always return `200 OK` to the webhook provider.

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {str(exc)}")
    # Always return 200 OK so Meta/Telegram stop retrying
    return JSONResponse(status_code=200, content={"status": "error_handled_silently"})
```
