from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Any

from app.client.telethon_manager import telethon_manager

router = APIRouter(prefix="/chats", tags=["chats"])


class PhoneBody(BaseModel):
    phone: str


class MessagesBody(BaseModel):
    phone: str
    chat_id: int
    limit: int = 25


class SendBody(BaseModel):
    phone: str
    chat_id: int
    text: str


class CommandBody(BaseModel):
    phone: str
    chat_id: int
    command: str
    args: Optional[List[str]] = None


class MediaBody(BaseModel):
    phone: str
    chat_id: int
    message_id: int


@router.post("/dialogs")
async def dialogs(data: PhoneBody):
    try:
        return await telethon_manager.get_dialogs(data.phone.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/messages")
async def messages(data: MessagesBody):
    try:
        return await telethon_manager.get_messages(
            data.phone.strip(), data.chat_id, limit=min(max(1, data.limit), 40)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send")
async def send(data: SendBody):
    if not data.text or not data.text.strip():
        raise HTTPException(status_code=400, detail="Пустое сообщение")
    try:
        return await telethon_manager.send_message(
            data.phone.strip(), data.chat_id, data.text.strip()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/command")
async def command(data: CommandBody):
    try:
        return await telethon_manager.run_command(
            data.phone.strip(),
            data.chat_id,
            data.command.strip().lower(),
            data.args or [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/media")
async def media(data: MediaBody):
    """Скачать медиа сообщения (base64). Лимит ~12 MB."""
    try:
        return await telethon_manager.download_message_media(
            data.phone.strip(),
            int(data.chat_id),
            int(data.message_id),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
