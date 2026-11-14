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
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class PhoneRequest(BaseModel):
    phone: str


@router.post("/send-code")
async def send_code(data: SendCodeRequest):
    if not data.phone or len(data.phone.strip()) < 8:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")

    try:
        result = await telethon_manager.send_code(data.phone.strip())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sign-in")
async def sign_in(data: SignInRequest):
    try:
        result = await telethon_manager.sign_in(
            phone=data.phone.strip(),
            code=data.code.strip(),
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout(data: PhoneRequest):
    try:
        result = await telethon_manager.logout(data.phone.strip())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/me")
async def get_me(data: PhoneRequest):
    try:
        result = await telethon_manager.get_me(data.phone.strip())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
