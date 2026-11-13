from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.client.telethon_manager import telethon_manager

router = APIRouter(prefix="/auth", tags=["auth"])


class SendCodeRequest(BaseModel):
    phone: str


class SignInRequest(BaseModel):
    phone: str
    code: str
    password: Optional[str] = None


class PhoneRequest(BaseModel):
    phone: str


@router.post("/send-code")
async def send_code(data: SendCodeRequest):
    """Отправить код подтверждения на номер."""
    if not data.phone or len(data.phone) < 8:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")

    try:
        result = await telethon_manager.send_code(data.phone)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sign-in")
async def sign_in(data: SignInRequest):
    """Войти по коду (и паролю 2FA если нужно)."""
    try:
        result = await telethon_manager.sign_in(data.phone, data.code, data.password)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout(data: PhoneRequest):
    """Выйти из аккаунта."""
    try:
        result = await telethon_manager.logout(data.phone)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/me")
async def get_me(data: PhoneRequest):
    """Получить информацию о текущем пользователе."""
    try:
        result = await telethon_manager.get_me(data.phone)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
