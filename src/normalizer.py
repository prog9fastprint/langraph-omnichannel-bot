from typing import Optional, Union
from src.schemas import WhatsAppPayload, TelegramUpdate, NormalizedMessage, WhatsAppMessage, TelegramMessage

def normalize_whatsapp_message(wa_message: WhatsAppMessage, user_id: str) -> NormalizedMessage:
    """Normalizes a WhatsApp message into a NormalizedMessage."""
    if wa_message.type == "text" and wa_message.text:
        return NormalizedMessage(
            platform="whatsapp",
            user_id=user_id,
            type="text",
            text=wa_message.text.get("body")
        )
    elif wa_message.type == "image" and wa_message.image:
        return NormalizedMessage(
            platform="whatsapp",
            user_id=user_id,
            type="image",
            media_id=wa_message.image.get("id")
        )
    elif wa_message.type == "audio" and wa_message.audio:
        return NormalizedMessage(
            platform="whatsapp",
            user_id=user_id,
            type="audio",
            media_id=wa_message.audio.get("id")
        )
    return NormalizedMessage(
        platform="whatsapp",
        user_id=user_id,
        type="unsupported"
    )

def normalize_telegram_message(tg_message: TelegramMessage) -> NormalizedMessage:
    """Normalizes a Telegram message into a NormalizedMessage."""
    user_id = str(tg_message.from_.id) # Telegram user ID is an int

    if tg_message.text:
        return NormalizedMessage(
            platform="telegram",
            user_id=user_id,
            type="text",
            text=tg_message.text
        )
    elif tg_message.photo:
        # Telegram sends multiple photo sizes, pick the last one (largest)
        largest_photo = tg_message.photo[-1]
        return NormalizedMessage(
            platform="telegram",
            user_id=user_id,
            type="image",
            media_id=largest_photo.get("file_id")
        )
    elif tg_message.voice:
        return NormalizedMessage(
            platform="telegram",
            user_id=user_id,
            type="audio",
            media_id=tg_message.voice.get("file_id")
        )
    return NormalizedMessage(
        platform="telegram",
        user_id=user_id,
        type="unsupported"
    )

async def normalize_payload(
    payload: Union[WhatsAppPayload, TelegramUpdate]
) -> list[NormalizedMessage]:
    """
    Parses an incoming webhook payload (WhatsApp or Telegram)
    and returns a list of NormalizedMessages.
    """
    normalized_messages = []
    if isinstance(payload, WhatsAppPayload):
        for entry in payload.entry:
            for change in entry.changes:
                if change.field == "messages" and change.value.messages:
                    for wa_message in change.value.messages:
                        # Assuming the first contact is the sender
                        user_id = change.value.contacts[0].wa_id if change.value.contacts else wa_message.from_
                        normalized = normalize_whatsapp_message(wa_message, user_id)
                        normalized_messages.append(normalized)
    elif isinstance(payload, TelegramUpdate):
        if payload.message:
            normalized = normalize_telegram_message(payload.message)
            normalized_messages.append(normalized)
    
    return normalized_messages
