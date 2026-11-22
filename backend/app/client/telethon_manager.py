"""Менеджер Telegram-клиентов + сессии (StringSession)."""

from pathlib import Path
from typing import Dict, Optional
import hashlib
import re

from app.config import settings

MOCK = settings.is_mock


class TelethonManager:
    def __init__(self):
        self.sessions_dir = settings.SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.clients: Dict[str, object] = {}
        self.phone_code_hashes: Dict[str, str] = {}
        self.string_sessions: Dict[str, str] = {}  # phone -> StringSession

        self.mock_users: Dict[str, dict] = {}
        self.mock_codes: Dict[str, str] = {}

    def _session_path(self, phone: str) -> Path:
        clean = "".join(c for c in phone if c.isdigit())
        return self.sessions_dir / f"{clean}.session"

    def _phone_key(self, phone: str) -> str:
        return "".join(c for c in phone if c.isdigit()) or phone

    def _ensure_api_keys(self) -> Optional[dict]:
        if not settings.has_api_keys:
            return {
                "status": "error",
                "message": "На сервере не заданы API_ID и API_HASH.",
            }
        return None

    # ==================== MOCK ====================

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
            sess = self.string_sessions.get(phone) or self._mock_make_session(phone)
            self.string_sessions[phone] = sess
            return {
                "status": "success",
                "message": "Уже авторизован",
                "user": self.mock_users[phone],
                "session": sess,
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
        sess = self._mock_make_session(phone)
        self.string_sessions[phone] = sess
        return {
            "status": "success",
            "message": "Успешная регистрация (заглушка)",
            "user": user,
            "session": sess,
        }

    def _mock_make_session(self, phone: str) -> str:
        raw = hashlib.sha256(f"mock-session-{phone}".encode()).hexdigest()
        return "1" + raw + raw[:16]

    async def _mock_logout(self, phone: str) -> dict:
        self.mock_users.pop(phone, None)
        self.mock_codes.pop(phone, None)
        self.phone_code_hashes.pop(phone, None)
        self.string_sessions.pop(phone, None)
        return {"status": "success", "message": "Вышли из аккаунта"}

    async def _mock_get_me(self, phone: str) -> dict:
        user = self.mock_users.get(phone)
        if not user:
            return {
                "status": "error",
                "message": "Сессия не найдена. Загрузите файл сессии вручную.",
            }
        return {"status": "success", "user": user}

    async def _mock_export_session(self, phone: str) -> dict:
        if phone not in self.mock_users:
            return {
                "status": "error",
                "message": "Сессия не найдена. Загрузите файл сессии вручную.",
            }
        sess = self.string_sessions.get(phone) or self._mock_make_session(phone)
        self.string_sessions[phone] = sess
        return {"status": "success", "session": sess, "phone": phone}

    async def _mock_load_session(self, session_str: str, phone: Optional[str] = None) -> dict:
        if not session_str or not session_str.strip():
            return {
                "status": "error",
                "message": "Файл сессии не передан. Отправьте строку или файл сессии.",
            }
        session_str = session_str.strip()
        # ищем phone по известным сессиям или создаём из hash
        found_phone = phone
        for p, s in self.string_sessions.items():
            if s == session_str:
                found_phone = p
                break
        if not found_phone:
            found_phone = phone or ("+session" + session_str[-8:])
        if found_phone not in self.mock_users:
            self.mock_users[found_phone] = {
                "id": int(hashlib.md5(session_str.encode()).hexdigest()[:8], 16)
                % 10_000_000,
                "first_name": "Session",
                "last_name": "User",
                "username": None,
                "phone": found_phone,
            }
        self.string_sessions[found_phone] = session_str
        return {
            "status": "success",
            "message": "Сессия загружена",
            "user": self.mock_users[found_phone],
            "session": session_str,
            "phone": found_phone,
        }

    # ==================== REAL ====================

    async def _real_get_or_create_client(self, phone: str, session_str: Optional[str] = None):
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        key = phone or "unknown"
        if key in self.clients and not session_str:
            client = self.clients[key]
            if not client.is_connected():
                await client.connect()
            return client

        if session_str:
            client = TelegramClient(
                StringSession(session_str),
                int(settings.API_ID),
                settings.API_HASH,
                device_model="TelegramCode",
                system_version="Web",
                app_version="0.1.0",
                lang_code="ru",
                system_lang_code="ru",
            )
        else:
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
        self.clients[key] = client
        return client

    async def _export_string(self, client) -> str:
        from telethon.sessions import StringSession

        return StringSession.save(client.session)

    async def _real_send_code(self, phone: str) -> dict:
        err = self._ensure_api_keys()
        if err:
            return err

        client = await self._real_get_or_create_client(phone)

        if await client.is_user_authorized():
            me = await client.get_me()
            try:
                sess = await self._export_string(client)
                self.string_sessions[phone] = sess
            except Exception:
                sess = None
            return {
                "status": "already_authorized",
                "message": "Уже авторизован",
                "user": self._user_dict(me),
                "session": sess,
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
            sess = await self._export_string(client)
            self.string_sessions[phone] = sess
            return {
                "status": "success",
                "message": "Уже авторизован",
                "user": self._user_dict(me),
                "session": sess,
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
        sess = await self._export_string(client)
        self.string_sessions[phone] = sess
        return {
            "status": "success",
            "message": "Успешный вход",
            "user": self._user_dict(me),
            "session": sess,
        }

    async def _real_export_session(self, phone: str) -> dict:
        err = self._ensure_api_keys()
        if err:
            return err

        if phone in self.string_sessions:
            return {
                "status": "success",
                "session": self.string_sessions[phone],
                "phone": phone,
            }

        client = self.clients.get(phone)
        if not client:
            try:
                client = await self._real_get_or_create_client(phone)
            except Exception:
                return {
                    "status": "error",
                    "message": "Сессия не найдена. Загрузите файл сессии вручную.",
                }

        if not await client.is_user_authorized():
            return {
                "status": "error",
                "message": "Сессия не найдена. Загрузите файл сессии вручную.",
            }

        sess = await self._export_string(client)
        self.string_sessions[phone] = sess
        return {"status": "success", "session": sess, "phone": phone}

    async def _real_load_session(
        self, session_str: str, phone: Optional[str] = None
    ) -> dict:
        err = self._ensure_api_keys()
        if err:
            return err

        if not session_str or not str(session_str).strip():
            return {
                "status": "error",
                "message": "Файл сессии не передан. Отправьте строку или файл сессии.",
            }

        session_str = str(session_str).strip()
        # убрать возможный префикс из файла
        session_str = re.sub(r"^session:\s*", "", session_str, flags=re.I).strip()

        try:
            key = phone or f"str_{session_str[-12:]}"
            client = await self._real_get_or_create_client(key, session_str=session_str)

            if not await client.is_user_authorized():
                return {
                    "status": "error",
                    "message": "Сессия не найдена или недействительна. Загрузите файл сессии вручную.",
                }

            me = await client.get_me()
            user = self._user_dict(me)
            phone_real = user.get("phone") or phone or key
            self.clients[phone_real] = client
            self.string_sessions[phone_real] = session_str
            return {
                "status": "success",
                "message": "Сессия загружена",
                "user": user,
                "session": session_str,
                "phone": phone_real,
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Не удалось загрузить сессию: {e}. Загрузите файл сессии вручную.",
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
        self.string_sessions.pop(phone, None)
        return {"status": "success", "message": "Вышли из аккаунта"}

    async def _real_get_me(self, phone: str) -> dict:
        client = self.clients.get(phone)
        if not client:
            try:
                client = await self._real_get_or_create_client(phone)
            except Exception:
                return {
                    "status": "error",
                    "message": "Сессия не найдена. Загрузите файл сессии вручную.",
                }

        if not await client.is_user_authorized():
            return {
                "status": "error",
                "message": "Сессия не найдена. Загрузите файл сессии вручную.",
            }

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

    # ==================== PUBLIC ====================

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

    async def export_session(self, phone: str) -> dict:
        if MOCK:
            return await self._mock_export_session(phone)
        return await self._real_export_session(phone)

    async def load_session(
        self, session_str: str, phone: Optional[str] = None
    ) -> dict:
        if MOCK:
            return await self._mock_load_session(session_str, phone)
        return await self._real_load_session(session_str, phone)


telethon_manager = TelethonManager()
