"""
Менеджер Telethon-клиентов.
Поддержка входа и регистрации новых аккаунтов.
"""

from pathlib import Path
from typing import Dict, Optional

from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneNumberUnoccupiedError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
)

from app.config import settings


class TelethonManager:
    def __init__(self):
        self.sessions_dir = settings.SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.clients: Dict[str, TelegramClient] = {}
        self.phone_code_hashes: Dict[str, str] = {}

    def _session_path(self, phone: str) -> Path:
        clean = "".join(c for c in phone if c.isdigit())
        return self.sessions_dir / f"{clean}.session"

    async def get_or_create_client(self, phone: str) -> TelegramClient:
        if phone in self.clients:
            return self.clients[phone]

        session_file = str(self._session_path(phone))
        client = TelegramClient(
            session_file,
            settings.API_ID,
            settings.API_HASH,
            device_model="TelegramCode",
            system_version="1.0",
            app_version="0.1.0",
        )

        await client.connect()
        self.clients[phone] = client
        return client

    async def send_code(self, phone: str) -> dict:
        client = await self.get_or_create_client(phone)

        if await client.is_user_authorized():
            me = await client.get_me()
            return {
                "status": "already_authorized",
                "message": "Уже авторизован",
                "user": self._user_dict(me),
            }

        result = await client.send_code_request(phone)
        self.phone_code_hashes[phone] = result.phone_code_hash

        return {
            "status": "code_sent",
            "message": "Код отправлен",
        }

    async def sign_in(
        self,
        phone: str,
        code: str,
        password: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> dict:
        client = await self.get_or_create_client(phone)

        if await client.is_user_authorized():
            me = await client.get_me()
            return {
                "status": "success",
                "message": "Уже авторизован",
                "user": self._user_dict(me),
            }

        phone_code_hash = self.phone_code_hashes.get(phone)
        if not phone_code_hash:
            return {"status": "error", "message": "Сначала запросите код"}

        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                return {
                    "status": "2fa_required",
                    "message": "Требуется пароль двухфакторной аутентификации",
                }
            await client.sign_in(password=password)
        except PhoneNumberUnoccupiedError:
            # Номер свободен — нужна регистрация
            if not first_name:
                return {
                    "status": "need_signup",
                    "message": "Аккаунт не найден. Нужна регистрация",
                }
            await client.sign_up(
                code=code,
                first_name=first_name,
                last_name=last_name or "",
                phone=phone,
                phone_code_hash=phone_code_hash,
            )
        except PhoneCodeInvalidError:
            return {"status": "error", "message": "Неверный код"}
        except PhoneCodeExpiredError:
            return {"status": "error", "message": "Код истёк. Запросите новый"}

        me = await client.get_me()
        return {
            "status": "success",
            "message": "Успешный вход",
            "user": self._user_dict(me),
        }

    async def logout(self, phone: str) -> dict:
        client = self.clients.get(phone)
        if client:
            try:
                await client.log_out()
            except Exception:
                pass
            try:
                await client.disconnect()
            except Exception:
                pass
            del self.clients[phone]

        session_file = self._session_path(phone)
        if session_file.exists():
            session_file.unlink(missing_ok=True)

        self.phone_code_hashes.pop(phone, None)
        return {"status": "success", "message": "Вышли из аккаунта"}

    async def get_me(self, phone: str) -> dict:
        client = self.clients.get(phone)
        if not client or not await client.is_user_authorized():
            return {"status": "error", "message": "Не авторизован"}

        me = await client.get_me()
        return {
            "status": "success",
            "user": self._user_dict(me),
        }

    @staticmethod
    def _user_dict(me) -> dict:
        return {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone,
        }


telethon_manager = TelethonManager()
