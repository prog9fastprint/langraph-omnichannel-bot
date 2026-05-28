import logging
from typing import Annotated
from fastapi import FastAPI, Request, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from src.config import settings
from src.security import verify_whatsapp_signature, verify_telegram_secret
from src.schemas import WhatsAppPayload, TelegramUpdate, NormalizedMessage
from src.normalizer import normalize_payload
import httpx
from langchain_core.messages import HumanMessage
from src.agent.graph import init_graph
app_graph = None
checkpointer = None
from src.agent.models import AgentState
from src.services.media_downloader import media_downloader

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Omnichannel AI Chatbot",
    description="FastAPI microservice for WhatsApp and Telegram AI chatbot.",
    version="0.1.0",
)

@app.get("/health", summary="Health check endpoint")
async def health_check():
    """
    Responds with a simple status to indicate the service is running.
    """
    return {"status": "ok"}

@app.get("/webhook/whatsapp", summary="WhatsApp Webhook Verification")
async def whatsapp_webhook_verification(
    hub_mode: str = "",
    hub_challenge: str = "",
    hub_verify_token: str = ""
):
    """
    Handles WhatsApp webhook verification requests.
    """
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_WEBHOOK_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verification successful.")
        return int(hub_challenge)
    logger.error("WhatsApp webhook verification failed.")
    raise HTTPException(status_code=403, detail="Verification failed")

async def _process_normalized_message(normalized_message: NormalizedMessage):
    """
    Processes a normalized message using the LangGraph agent, handling media if present.
    """
    logger.info(f"Processing normalized message: {normalized_message.model_dump_json(indent=2)}")

    input_content = []
    if normalized_message.text:
        input_content.append({"type": "text", "text": normalized_message.text})
    
    if normalized_message.media_id and (normalized_message.type == "image" or normalized_message.type == "audio"):
        try:
            media_bytes = await media_downloader.download_media(
                platform=normalized_message.platform,
                media_id=normalized_message.media_id
            )
            # Gemini 2.5 Flash expects image/audio as {"image": bytes} or {"audio": bytes}
            input_content.append({"type": normalized_message.type, "mime_type": "application/octet-stream", "data": media_bytes})
            logger.info(f"Downloaded and prepared media for LLM: {normalized_message.type} from {normalized_message.platform}")
        except Exception as e:
            logger.error(f"Failed to download media {normalized_message.media_id}: {e}")
            # Continue without media if download fails
    
    if not input_content:
        logger.warning(f"No processable content in normalized message from {normalized_message.platform}:{normalized_message.user_id}. Skipping LangGraph invocation.")
        return

    thread_id = f"{normalized_message.platform}:{normalized_message.user_id}"
    input_message = HumanMessage(content=input_content) # HumanMessage can take list of dict for multimodal

    try:
        # Invoke the LangGraph agent
        await app_graph.ainvoke(
            input=AgentState(
                messages=[input_message],
                platform=normalized_message.platform,
                user_id=normalized_message.user_id
            ),
            config={"configurable": {"thread_id": thread_id}}
        )
        logger.info(f"LangGraph agent invoked for thread_id: {thread_id}")
    except Exception as e:
        logger.error(f"Error invoking LangGraph agent for {thread_id}: {e}", exc_info=True)

@app.post("/webhook/whatsapp", summary="WhatsApp Webhook Endpoint")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    payload: WhatsAppPayload,
    signature_verified: Annotated[bool, Depends(verify_whatsapp_signature)]
):
    """
    Receives and processes incoming WhatsApp messages.
    """
    # This check is redundant due to Depends, but kept for clarity if security changes
    if not signature_verified:
        raise HTTPException(status_code=403, detail="Signature verification failed")
    
    logger.info(f"Received raw WhatsApp payload: {payload.model_dump_json(indent=2)}")
    normalized_messages = await normalize_payload(payload)
    
    if normalized_messages:
        for normalized_message in normalized_messages:
            background_tasks.add_task(_process_normalized_message, normalized_message)
        logger.info(f"{len(normalized_messages)} WhatsApp messages received and passed to background tasks.")
    else:
        logger.warning("Could not normalize WhatsApp payload.")
        
    return JSONResponse(status_code=200, content={"message": "Event received"})

@app.post("/webhook/telegram", summary="Telegram Webhook Endpoint")
async def telegram_webhook(
    background_tasks: BackgroundTasks,
    payload: TelegramUpdate,
    secret_token_verified: Annotated[bool, Depends(verify_telegram_secret)]
):
    """
    Receives and processes incoming Telegram messages.
    """
    if not secret_token_verified: # Should not happen due to Depends
        raise HTTPException(status_code=403, detail="Secret token verification failed")

    logger.info(f"Received raw Telegram payload: {payload.model_dump_json(indent=2)}")
    normalized_messages = await normalize_payload(payload)

    if normalized_messages:
        for normalized_message in normalized_messages:
            background_tasks.add_task(_process_normalized_message, normalized_message)
        logger.info(f"{len(normalized_messages)} Telegram messages received and passed to background tasks.")
    else:
        logger.warning("Could not normalize Telegram payload.")

    return JSONResponse(status_code=200, content={"message": "Event received"})

@app.post("/admin/register-telegram-webhook", summary="Register Telegram Webhook")
async def register_telegram_webhook():
    """
    Registers the Telegram webhook dynamically using the NGROK_URL from settings.
    """
    if not settings.NGROK_URL:
        raise HTTPException(status_code=400, detail="NGROK_URL is not set in configuration")
    
    webhook_url = f"{settings.NGROK_URL.rstrip('/')}/webhook/telegram"
    api_url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook"
    
    payload = {
        "url": webhook_url,
        "secret_token": settings.TELEGRAM_SECRET_TOKEN
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(api_url, json=payload)
        data = response.json()
        if data.get("ok"):
            logger.info(f"Webhook registered successfully: {webhook_url}")
            return {"status": "success", "description": data.get("description")}
        else:
            logger.error(f"Failed to register webhook: {data}")
            raise HTTPException(status_code=500, detail=data.get("description"))

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Global exception handler to catch all unhandled exceptions.
    Always returns 200 OK to prevent webhook providers from retrying indefinitely.
    """
    logger.error(f"Unhandled error during request to {request.url}: {exc}", exc_info=True)
    # Always return 200 OK so Meta/Telegram stop retrying
    return JSONResponse(
        status_code=200,
        content={
            "status": "error_handled_silently",
            "message": "An internal error occurred and was handled silently."
        }
    )

@app.on_event("startup")
async def startup_event():
    global checkpointer, app_graph
    logger.info("Application startup event triggered.")
    logger.info(f"Loaded ERP Base URL: {settings.ERP_BASE_URL}")
    checkpointer, app_graph = await init_graph()
    await checkpointer.setup()
    logger.info("Postgres checkpointer tables initialized.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")
    await checkpointer.aclose()
