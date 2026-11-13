"""
Менеджер Telethon-клиентов.
Хранит активные клиенты в памяти и на диске (sessions/).
"""

import os
from pathlib import Path
from typing import Dict, Optional

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.sessions import StringSession

from app.config import settings


class TelethonManager:
    def __init__(self):
        self.sessions_dir = settings.SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        # phone -> TelegramClient
        self.clients: Dict[str, TelegramClient] = {}

        # phone -> phone_code_hash (нужен для sign_in)
        self.phone_code_hashes: Dict[str, str] = {}

    def _session_path(self, phone: str) -> Path:
        # Убираем всё кроме цифр, чтобы имя файла было безопасным
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
            device_model="Modified Telegram",
            system_version="1.0",
            app_version="0.1.0",
        )

        await client.connect()
        self.clients[phone] = client
        return client

    async def send_code(self, phone: str) -> dict:
        """Отправляет код подтверждения на номер."""
        client = await self.get_or_create_client(phone)

        if await client.is_user_authorized():
            return {"status": "already_authorized", "message": "Уже авторизован"}

        result = await client.send_code_request(phone)
        self.phone_code_hashes[phone] = result.phone_code_hash

        return {
            "status": "code_sent",
            "message": "Код отправлен",
            "phone_code_hash": result.phone_code_hash,
        }

    async def sign_in(self, phone: str, code: str, password: Optional[str] = None) -> dict:
        """Вход по коду + опционально 2FA пароль."""
        client = await self.get_or_create_client(phone)

        if await client.is_user_authorized():
            me = await client.get_me()
            return {
                "status": "success",
                "message": "Уже авторизован",
                "user": {
                    "id": me.id,
                    "first_name": me.first_name,
                    "last_name": me.last_name,
                    "username": me.username,
                    "phone": me.phone,
                },
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

        me = await client.get_me()
        return {
            "status": "success",
            "message": "Успешный вход",
            "user": {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
            },
        }

    async def logout(self, phone: str) -> dict:
        client = self.clients.get(phone)
        if client:
            await client.log_out()
            await client.disconnect()
            del self.clients[phone]

        session_file = self._session_path(phone)
        if session_file.exists():
            session_file.unlink()

        self.phone_code_hashes.pop(phone, None)
        return {"status": "success", "message": "Вышли из аккаунта"}

    async def get_me(self, phone: str) -> dict:
        client = self.clients.get(phone)
        if not client or not await client.is_user_authorized():
            return {"status": "error", "message": "Не авторизован"}

        me = await client.get_me()
        return {
            "status": "success",
            "user": {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
            },
        }


# Глобальный экземпляр
telethon_manager = TelethonManager()
