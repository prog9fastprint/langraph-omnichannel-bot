import httpx
import logging
from src.config import settings

logger = logging.getLogger(__name__)

class MediaDownloader:
    def __init__(self):
        self.whatsapp_client = httpx.AsyncClient(
            base_url=f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/",
            headers={"Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}"}
        )
        self.telegram_client = httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/"
        )

    async def download_media(self, platform: str, media_id: str, file_name: str = None) -> bytes:
        """
        Downloads media (audio, image) from the specified platform.
        Returns the binary content of the media.
        """
        if platform == "whatsapp":
            return await self._download_whatsapp_media(media_id)
        elif platform == "telegram":
            return await self._download_telegram_media(media_id)
        else:
            raise ValueError(f"Unsupported platform: {platform}")

    async def _download_whatsapp_media(self, media_id: str) -> bytes:
        """Downloads media from WhatsApp (Meta Graph API)."""
        try:
            # First, get the media URL
            media_info_response = await self.whatsapp_client.get(f"{media_id}")
            media_info_response.raise_for_status()
            media_url = media_info_response.json().get("url")

            if not media_url:
                raise ValueError(f"WhatsApp media URL not found for media_id: {media_id}")

            # Then, download the media content
            media_content_response = await self.whatsapp_client.get(media_url)
            media_content_response.raise_for_status()
            logger.info(f"Downloaded WhatsApp media: {media_id}")
            return media_content_response.content
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading WhatsApp media {media_id}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Network error downloading WhatsApp media {media_id}: {e}")
            raise

    async def _download_telegram_media(self, file_id: str) -> bytes:
        """Downloads media from Telegram Bot API."""
        try:
            # First, get the file path
            file_info_response = await self.telegram_client.get(f"getFile?file_id={file_id}")
            file_info_response.raise_for_status()
            file_path = file_info_response.json()["result"]["file_path"]
            
            # Then, download the media content
            # The actual file download URL is api.telegram.org/file/bot<token>/<file_path>
            media_url = f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
            media_content_response = await httpx.AsyncClient().get(media_url) # Use a new client for raw file download
            media_content_response.raise_for_status()
            logger.info(f"Downloaded Telegram media: {file_id}")
            return media_content_response.content
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error downloading Telegram media {file_id}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Network error downloading Telegram media {file_id}: {e}")
            raise

media_downloader = MediaDownloader()
