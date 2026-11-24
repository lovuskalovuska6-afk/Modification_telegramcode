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
    reply_to: Optional[int] = None


class CommandBody(BaseModel):
    phone: str
    chat_id: int
    command: str
    args: Optional[List[str]] = None


class MediaBody(BaseModel):
    phone: str
    chat_id: int
    message_id: int


class AvatarBody(BaseModel):
    phone: str
    peer_id: int


class DeleteMsgBody(BaseModel):
    phone: str
    chat_id: int
    message_id: int
    revoke: bool = False  # True = delete for everyone when allowed


class EditMsgBody(BaseModel):
    phone: str
    chat_id: int
    message_id: int
    text: str


class ForwardBody(BaseModel):
    phone: str
    from_chat_id: int
    message_id: int
    to_chat_id: int


class PinBody(BaseModel):
    phone: str
    chat_id: int
    message_id: int
    unpin: bool = False


class ReactBody(BaseModel):
    phone: str
    chat_id: int
    message_id: int
    emoticon: str  # empty string = remove own reaction


class DeletedSettingsBody(BaseModel):
    phone: str
    enabled: Optional[bool] = None


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
            data.phone.strip(),
            data.chat_id,
            data.text.strip(),
            reply_to=data.reply_to,
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


@router.post("/avatar")
async def avatar(data: AvatarBody):
    """Аватар peer (user/chat/channel) как base64 JPEG. Кеш на клиенте по phone+peer_id."""
    try:
        return await telethon_manager.get_avatar(
            data.phone.strip(), int(data.peer_id)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/delete")
async def message_delete(data: DeleteMsgBody):
    try:
        return await telethon_manager.delete_message(
            data.phone.strip(),
            int(data.chat_id),
            int(data.message_id),
            revoke=bool(data.revoke),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/edit")
async def message_edit(data: EditMsgBody):
    if not data.text or not data.text.strip():
        raise HTTPException(status_code=400, detail="Пустой текст")
    try:
        return await telethon_manager.edit_message(
            data.phone.strip(),
            int(data.chat_id),
            int(data.message_id),
            data.text.strip(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/forward")
async def message_forward(data: ForwardBody):
    try:
        return await telethon_manager.forward_message(
            data.phone.strip(),
            int(data.from_chat_id),
            int(data.message_id),
            int(data.to_chat_id),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/pin")
async def message_pin(data: PinBody):
    try:
        return await telethon_manager.pin_message(
            data.phone.strip(),
            int(data.chat_id),
            int(data.message_id),
            unpin=bool(data.unpin),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/message/react")
async def message_react(data: ReactBody):
    try:
        return await telethon_manager.react_message(
            data.phone.strip(),
            int(data.chat_id),
            int(data.message_id),
            (data.emoticon or "").strip(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deleted/get")
async def deleted_get(data: PhoneBody):
    try:
        return await telethon_manager.get_deleted_messages(data.phone.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deleted/clear")
async def deleted_clear(data: PhoneBody):
    try:
        return await telethon_manager.clear_deleted_messages(data.phone.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/deleted/settings")
async def deleted_settings(data: DeletedSettingsBody):
    try:
        return await telethon_manager.set_deleted_settings(
            data.phone.strip(), enabled=data.enabled
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
