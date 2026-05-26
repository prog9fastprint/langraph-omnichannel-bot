import httpx
import logging
from src.config import settings

logger = logging.getLogger(__name__)

class WhatsAppClient:
    def __init__(self):
        self.base_url = f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{settings.WHATSAPP_PHONE_NUMBER_ID}"
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(base_url=self.base_url, headers=self.headers)

    async def send_text_message(self, to: str, text: str):
        """
        Sends a text message to a WhatsApp user.
        """
        endpoint = "/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": text}
        }
        try:
            response = await self.client.post(endpoint, json=payload)
            response.raise_for_status()
            logger.info(f"WhatsApp message sent to {to}: {response.json()}")
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error sending WhatsApp message to {to}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Network error sending WhatsApp message to {to}: {e}")
            raise

whatsapp_client = WhatsAppClient()
