from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, List

from app.client.telethon_manager import telethon_manager

router = APIRouter(prefix="/settings", tags=["settings"])


class PhoneBody(BaseModel):
    phone: str


class AISettingsBody(BaseModel):
    phone: str
    enabled: Optional[bool] = None
    provider: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    api_base: Optional[str] = None


class TriggersBody(BaseModel):
    phone: str
    triggers: List[dict] = []


class LocalAIChatBody(BaseModel):
    phone: str
    message: str
    history: Optional[List[dict]] = None


@router.post("/ai/get")
async def ai_get(data: PhoneBody):
    try:
        return await telethon_manager.get_ai_settings(data.phone.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/set")
async def ai_set(data: AISettingsBody):
    try:
        payload = data.model_dump(exclude={"phone"}, exclude_none=False)
        return await telethon_manager.set_ai_settings(data.phone.strip(), payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/triggers/get")
async def triggers_get(data: PhoneBody):
    try:
        return await telethon_manager.get_triggers(data.phone.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/triggers/set")
async def triggers_set(data: TriggersBody):
    try:
        return await telethon_manager.set_triggers(data.phone.strip(), data.triggers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ai/chat")
async def ai_chat(data: LocalAIChatBody):
    try:
        return await telethon_manager.local_ai_chat(
            data.phone.strip(),
            data.message.strip(),
            data.history or [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
