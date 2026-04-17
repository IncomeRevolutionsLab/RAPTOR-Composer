import requests
import logging
from backend.config import settings

logger = logging.getLogger(__name__)

def send_telegram_message(message: str):
    """지정된 텔레그램 채팅으로 메시지를 전송합니다."""
    token = getattr(settings, "telegram_bot_token", None)
    chat_id = getattr(settings, "telegram_chat_id", None)
    
    if not token or not chat_id:
        logger.warning("[Notifier] Telegram token or chat_id is missing. Skipping notification.")
        return False
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"[Notifier] Failed to send telegram message: {e}")
        return False
