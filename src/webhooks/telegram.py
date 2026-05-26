from fastapi import Header, HTTPException
from src.config import settings

async def verify_telegram_secret(
    x_telegram_bot_api_secret_token: str = Header(None)
) -> None:
    if x_telegram_bot_api_secret_token != settings.TELEGRAM_SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid secret token")