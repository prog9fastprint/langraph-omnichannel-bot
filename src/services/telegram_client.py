import httpx
import logging
from typing import Union
from src.config import settings

logger = logging.getLogger(__name__)

class TelegramClient:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"
        self.client = httpx.AsyncClient(base_url=self.base_url)

    async def send_text_message(self, chat_id: Union[int, str], text: str):
        """
        Sends a text message to a Telegram user or chat.
        """
        endpoint = "/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text
        }
        try:
            response = await self.client.post(endpoint, json=payload)
            response.raise_for_status()
            logger.info(f"Telegram message sent to {chat_id}: {response.json()}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error sending Telegram message to {chat_id}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Network error sending Telegram message to {chat_id}: {e}")
            raise

telegram_client = TelegramClient()
