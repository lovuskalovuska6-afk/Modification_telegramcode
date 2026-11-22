from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from app.client.telethon_manager import telethon_manager, MOCK

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


class LoadSessionRequest(BaseModel):
    session: Optional[str] = None
    phone: Optional[str] = None


@router.get("/mode")
async def auth_mode():
    return {
        "mock": MOCK,
        "message": "Заглушка (demo)" if MOCK else "Реальный Telegram",
    }


@router.post("/send-code")
async def send_code(data: SendCodeRequest):
    if not data.phone or len(data.phone.strip()) < 8:
        raise HTTPException(status_code=400, detail="Некорректный номер телефона")
    try:
        return await telethon_manager.send_code(data.phone.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sign-in")
async def sign_in(data: SignInRequest):
    try:
        return await telethon_manager.sign_in(
            phone=data.phone.strip(),
            code=data.code.strip(),
            password=data.password,
            first_name=data.first_name,
            last_name=data.last_name,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/logout")
async def logout(data: PhoneRequest):
    try:
        return await telethon_manager.logout(data.phone.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/me")
async def get_me(data: PhoneRequest):
    try:
        return await telethon_manager.get_me(data.phone.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export-session")
async def export_session(data: PhoneRequest):
    """Скачать/получить строку сессии после входа."""
    if not data.phone:
        raise HTTPException(
            status_code=400,
            detail="Сессия не найдена. Загрузите файл сессии вручную.",
        )
    try:
        result = await telethon_manager.export_session(data.phone.strip())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load-session")
async def load_session(data: LoadSessionRequest):
    """Вход по строке сессии."""
    if not data.session or not data.session.strip():
        return {
            "status": "error",
            "message": "Файл сессии не передан. Отправьте строку или файл сессии.",
        }
    try:
        return await telethon_manager.load_session(
            data.session.strip(),
            phone=data.phone.strip() if data.phone else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load-session-file")
async def load_session_file(
    file: Optional[UploadFile] = File(None),
    session: Optional[str] = Form(None),
    phone: Optional[str] = Form(None),
):
    """Загрузка сессии из файла или form-поля."""
    content = None
    if file is not None:
        raw = await file.read()
        try:
            content = raw.decode("utf-8").strip()
        except Exception:
            # бинарный .session — не StringSession; просим текстовую сессию
            return {
                "status": "error",
                "message": "Нужна текстовая StringSession (не бинарный .session). "
                "Скачайте сессию кнопкой на сайте после входа и загрузите её.",
            }
    elif session:
        content = session.strip()

    if not content:
        return {
            "status": "error",
            "message": "Файл сессии не передан. Отправьте строку или файл сессии.",
        }

    try:
        return await telethon_manager.load_session(
            content, phone=phone.strip() if phone else None
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
