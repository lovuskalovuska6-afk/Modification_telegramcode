"""Менеджер Telegram-клиентов (Telethon)."""

from pathlib import Path
from typing import Dict, Optional
import hashlib

from app.config import settings

MOCK = settings.is_mock


class TelethonManager:
    def __init__(self):
        self.sessions_dir = settings.SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.clients: Dict[str, object] = {}
        self.phone_code_hashes: Dict[str, str] = {}

        self.mock_users: Dict[str, dict] = {}
        self.mock_codes: Dict[str, str] = {}

    def _session_path(self, phone: str) -> Path:
        clean = "".join(c for c in phone if c.isdigit())
        return self.sessions_dir / f"{clean}.session"

    def _ensure_api_keys(self) -> Optional[dict]:
        if not settings.has_api_keys:
            return {
                "status": "error",
                "message": "На сервере не заданы API_ID и API_HASH. "
                "Добавь их в Environment Variables на Render.",
            }
        return None

    async def _mock_send_code(self, phone: str) -> dict:
        if phone in self.mock_users:
            return {
                "status": "already_authorized",
                "message": "Уже авторизован",
                "user": self.mock_users[phone],
            }
        self.mock_codes[phone] = "12345"
        self.phone_code_hashes[phone] = "mock_hash_" + phone
        return {
            "status": "code_sent",
            "message": "Код отправлен (заглушка). Используй код: 12345",
        }

    async def _mock_sign_in(
        self,
        phone: str,
        code: str,
        password: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> dict:
        if phone in self.mock_users:
            return {
                "status": "success",
                "message": "Уже авторизован",
                "user": self.mock_users[phone],
            }
        if phone not in self.phone_code_hashes:
            return {"status": "error", "message": "Сначала запросите код"}
        if not first_name:
            return {
                "status": "need_signup",
                "message": "Аккаунт не найден. Нужна регистрация",
            }
        user_id = int(hashlib.md5(phone.encode()).hexdigest()[:8], 16) % 10_000_000
        user = {
            "id": user_id,
            "first_name": first_name,
            "last_name": last_name or "",
            "username": None,
            "phone": phone,
        }
        self.mock_users[phone] = user
        return {
            "status": "success",
            "message": "Успешная регистрация (заглушка)",
            "user": user,
        }

    async def _mock_logout(self, phone: str) -> dict:
        self.mock_users.pop(phone, None)
        self.mock_codes.pop(phone, None)
        self.phone_code_hashes.pop(phone, None)
        return {"status": "success", "message": "Вышли из аккаунта"}

    async def _mock_get_me(self, phone: str) -> dict:
        user = self.mock_users.get(phone)
        if not user:
            return {"status": "error", "message": "Не авторизован"}
        return {"status": "success", "user": user}

    async def _real_get_or_create_client(self, phone: str):
        from telethon import TelegramClient

        if phone in self.clients:
            client = self.clients[phone]
            if not client.is_connected():
                await client.connect()
            return client

        session_file = str(self._session_path(phone))
        client = TelegramClient(
            session_file,
            int(settings.API_ID),
            settings.API_HASH,
            device_model="TelegramCode",
            system_version="Web",
            app_version="0.1.0",
            lang_code="ru",
            system_lang_code="ru",
        )
        await client.connect()
        self.clients[phone] = client
        return client

    async def _real_send_code(self, phone: str) -> dict:
        err = self._ensure_api_keys()
        if err:
            return err

        client = await self._real_get_or_create_client(phone)

        if await client.is_user_authorized():
            me = await client.get_me()
            return {
                "status": "already_authorized",
                "message": "Уже авторизован",
                "user": self._user_dict(me),
            }

        result = await client.send_code_request(phone)
        self.phone_code_hashes[phone] = result.phone_code_hash
        return {"status": "code_sent", "message": "Код отправлен в Telegram"}

    async def _real_sign_in(
        self,
        phone: str,
        code: str,
        password: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> dict:
        from telethon.errors import (
            SessionPasswordNeededError,
            PhoneNumberUnoccupiedError,
            PhoneCodeInvalidError,
            PhoneCodeExpiredError,
            FloodWaitError,
        )

        err = self._ensure_api_keys()
        if err:
            return err

        client = await self._real_get_or_create_client(phone)

        if await client.is_user_authorized():
            me = await client.get_me()
            return {
                "status": "success",
                "message": "Уже авторизован",
                "user": self._user_dict(me),
            }

        phone_code_hash = self.phone_code_hashes.get(phone)
        if not phone_code_hash:
            return {
                "status": "error",
                "message": "Сначала запросите код (или сервер перезапустился — запросите код снова)",
            }

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
            if not first_name or not first_name.strip():
                return {
                    "status": "need_signup",
                    "message": "Аккаунт не найден. Нужна регистрация",
                }
            await client.sign_up(
                code=code,
                first_name=first_name.strip(),
                last_name=(last_name or "").strip(),
                phone=phone,
                phone_code_hash=phone_code_hash,
            )
        except PhoneCodeInvalidError:
            return {"status": "error", "message": "Неверный код"}
        except PhoneCodeExpiredError:
            return {"status": "error", "message": "Код истёк. Запросите новый"}
        except FloodWaitError as e:
            return {
                "status": "error",
                "message": f"Слишком много попыток. Подождите {e.seconds} сек.",
            }

        me = await client.get_me()
        return {
            "status": "success",
            "message": "Успешный вход",
            "user": self._user_dict(me),
        }

    async def _real_logout(self, phone: str) -> dict:
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
            self.clients.pop(phone, None)

        session_file = self._session_path(phone)
        if session_file.exists():
            session_file.unlink(missing_ok=True)

        self.phone_code_hashes.pop(phone, None)
        return {"status": "success", "message": "Вышли из аккаунта"}

    async def _real_get_me(self, phone: str) -> dict:
        client = self.clients.get(phone)
        if not client:
            try:
                client = await self._real_get_or_create_client(phone)
            except Exception:
                return {"status": "error", "message": "Не авторизован"}

        if not await client.is_user_authorized():
            return {"status": "error", "message": "Не авторизован"}

        me = await client.get_me()
        return {"status": "success", "user": self._user_dict(me)}

    @staticmethod
    def _user_dict(me) -> dict:
        return {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone,
        }

    async def send_code(self, phone: str) -> dict:
        if MOCK:
            return await self._mock_send_code(phone)
        return await self._real_send_code(phone)

    async def sign_in(
        self,
        phone: str,
        code: str,
        password: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> dict:
        if MOCK:
            return await self._mock_sign_in(
                phone, code, password, first_name, last_name
            )
        return await self._real_sign_in(
            phone, code, password, first_name, last_name
        )

    async def logout(self, phone: str) -> dict:
        if MOCK:
            return await self._mock_logout(phone)
        return await self._real_logout(phone)

    async def get_me(self, phone: str) -> dict:
        if MOCK:
            return await self._mock_get_me(phone)
        return await self._real_get_me(phone)


telethon_manager = TelethonManager()
