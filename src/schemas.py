from typing import List, Optional, Literal, Union
from pydantic import BaseModel, Field

# --- Normalized Message Schema ---
class NormalizedMessage(BaseModel):
    """
    A unified schema for messages coming from different platforms.
    """
    platform: Literal["whatsapp", "telegram"]
    user_id: str = Field(..., description="Unique identifier for the user on the given platform.")
    type: Literal["text", "audio", "image", "unsupported"] = Field(
        ..., description="Type of the message content."
    )
    text: Optional[str] = Field(None, description="The text content of the message, if type is 'text'.")
    media_id: Optional[str] = Field(
        None, description="The ID of the media, if type is 'audio' or 'image'."
    )
    # Add other common fields if necessary (e.g., timestamp, message_id)

# --- WhatsApp Webhook Schemas ---
class WhatsAppContact(BaseModel):
    wa_id: str
    profile: dict

class WhatsAppMessage(BaseModel):
    from_: str = Field(..., alias="from")
    id: str
    timestamp: str
    type: str
    text: Optional[dict] = None  # {'body': 'hello'}
    image: Optional[dict] = None # {'id': 'media_id', 'mime_type': 'image/jpeg'}
    audio: Optional[dict] = None # {'id': 'media_id', 'mime_type': 'audio/ogg'}

class WhatsAppChangeValue(BaseModel):
    messaging_product: str
    metadata: dict
    contacts: Optional[List[WhatsAppContact]] = None
    messages: Optional[List[WhatsAppMessage]] = None

class WhatsAppChange(BaseModel):
    field: str
    value: WhatsAppChangeValue

class WhatsAppEntry(BaseModel):
    id: str
    changes: List[WhatsAppChange]

class WhatsAppPayload(BaseModel):
    object: str
    entry: List[WhatsAppEntry]

# --- Telegram Webhook Schemas ---
class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    username: Optional[str] = None

class TelegramChat(BaseModel):
    id: int
    first_name: Optional[str] = None
    username: Optional[str] = None
    type: str

class TelegramMessage(BaseModel):
    message_id: int
    from_: TelegramUser = Field(..., alias="from")
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    voice: Optional[dict] = None # {'file_id': '...', 'duration': '...', 'mime_type': '...'}
    photo: Optional[List[dict]] = None # [{'file_id': '...', 'width': '...', 'height': '...'}]

class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None
