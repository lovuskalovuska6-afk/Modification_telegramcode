"""Менеджер Telegram-клиентов + сессии + чаты."""

from pathlib import Path
from typing import Dict, Optional, List, Any
import hashlib
import re
import asyncio

from app.config import settings

MOCK = settings.is_mock


class TelethonManager:
    def __init__(self):
        self.sessions_dir = settings.SESSIONS_DIR
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.clients: Dict[str, object] = {}
        self.phone_code_hashes: Dict[str, str] = {}
        self.string_sessions: Dict[str, str] = {}

        self.mock_users: Dict[str, dict] = {}
        self.mock_codes: Dict[str, str] = {}
        self.mock_dialogs: Dict[str, list] = {}
        self.mock_messages: Dict[str, Dict[int, list]] = {}
        self.muted: Dict[str, set] = {}

    def _session_path(self, phone: str) -> Path:
        clean = "".join(c for c in phone if c.isdigit())
        return self.sessions_dir / f"{clean}.session"

    def _ensure_api_keys(self) -> Optional[dict]:
        if not settings.has_api_keys:
            return {"status": "error", "message": "На сервере не заданы API_ID и API_HASH."}
        return None

    def _ensure_client(self, phone: str):
        client = self.clients.get(phone)
        if not client:
            raise RuntimeError("Нет активной сессии. Войдите или загрузите сессию.")
        return client

    # ==================== MOCK AUTH ====================

    async def _mock_send_code(self, phone: str) -> dict:
        if phone in self.mock_users:
            return {"status": "already_authorized", "message": "Уже авторизован", "user": self.mock_users[phone]}
        self.mock_codes[phone] = "12345"
        self.phone_code_hashes[phone] = "mock_hash_" + phone
        return {"status": "code_sent", "message": "Код отправлен (заглушка). Используй код: 12345"}

    async def _mock_sign_in(self, phone, code, password=None, first_name=None, last_name=None) -> dict:
        if phone in self.mock_users:
            sess = self.string_sessions.get(phone) or self._mock_make_session(phone)
            self.string_sessions[phone] = sess
            self._init_mock_chats(phone)
            return {"status": "success", "message": "Уже авторизован", "user": self.mock_users[phone], "session": sess}
        if phone not in self.phone_code_hashes:
            return {"status": "error", "message": "Сначала запросите код"}
        if not first_name:
            return {"status": "need_signup", "message": "Аккаунт не найден. Нужна регистрация"}
        user_id = int(hashlib.md5(phone.encode()).hexdigest()[:8], 16) % 10_000_000
        user = {"id": user_id, "first_name": first_name, "last_name": last_name or "", "username": None, "phone": phone}
        self.mock_users[phone] = user
        sess = self._mock_make_session(phone)
        self.string_sessions[phone] = sess
        self._init_mock_chats(phone)
        return {"status": "success", "message": "Успешная регистрация (заглушка)", "user": user, "session": sess}

    def _mock_make_session(self, phone: str) -> str:
        raw = hashlib.sha256(f"mock-session-{phone}".encode()).hexdigest()
        return "1" + raw + raw[:16]

    def _init_mock_chats(self, phone: str):
        if phone in self.mock_dialogs:
            return
        self.mock_dialogs[phone] = [
            {"id": 1001, "title": "Избранное", "username": None, "unread": 0, "last_message": "Заметки", "is_group": False, "is_channel": False},
            {"id": 1002, "title": "Друг", "username": "friend", "unread": 2, "last_message": "Привет!", "is_group": False, "is_channel": False},
            {"id": 1003, "title": "Чат разработки", "username": None, "unread": 5, "last_message": "Код готов", "is_group": True, "is_channel": False},
        ]
        self.mock_messages[phone] = {
            1001: [
                {"id": 1, "text": "Добро пожаловать в TelegramCode", "out": False, "date": "12:00", "sender": "System"},
                {"id": 2, "text": "Это избранное (демо)", "out": True, "date": "12:01", "sender": "You"},
            ],
            1002: [
                {"id": 1, "text": "Привет!", "out": False, "date": "11:30", "sender": "Друг"},
                {"id": 2, "text": "Как дела?", "out": False, "date": "11:31", "sender": "Друг"},
            ],
            1003: [
                {"id": 1, "text": "Код готов", "out": False, "date": "10:00", "sender": "Dev"},
            ],
        }

    async def _mock_logout(self, phone: str) -> dict:
        self.mock_users.pop(phone, None)
        self.mock_codes.pop(phone, None)
        self.phone_code_hashes.pop(phone, None)
        self.string_sessions.pop(phone, None)
        self.mock_dialogs.pop(phone, None)
        self.mock_messages.pop(phone, None)
        return {"status": "success", "message": "Вышли из аккаунта"}

    async def _mock_get_me(self, phone: str) -> dict:
        user = self.mock_users.get(phone)
        if not user:
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        return {"status": "success", "user": user}

    async def _mock_export_session(self, phone: str) -> dict:
        if phone not in self.mock_users:
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        sess = self.string_sessions.get(phone) or self._mock_make_session(phone)
        self.string_sessions[phone] = sess
        return {"status": "success", "session": sess, "phone": phone}

    async def _mock_load_session(self, session_str: str, phone: Optional[str] = None) -> dict:
        if not session_str or not session_str.strip():
            return {"status": "error", "message": "Файл сессии не передан. Отправьте строку или файл сессии."}
        session_str = session_str.strip()
        found_phone = phone
        for p, s in self.string_sessions.items():
            if s == session_str:
                found_phone = p
                break
        if not found_phone:
            found_phone = phone or ("+session" + session_str[-8:])
        if found_phone not in self.mock_users:
            self.mock_users[found_phone] = {
                "id": int(hashlib.md5(session_str.encode()).hexdigest()[:8], 16) % 10_000_000,
                "first_name": "Session", "last_name": "User", "username": None, "phone": found_phone,
            }
        self.string_sessions[found_phone] = session_str
        self._init_mock_chats(found_phone)
        return {"status": "success", "message": "Сессия загружена", "user": self.mock_users[found_phone], "session": session_str, "phone": found_phone}

    # ==================== REAL AUTH ====================

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
                StringSession(session_str), int(settings.API_ID), settings.API_HASH,
                device_model="TelegramCode", system_version="Web", app_version="0.2.0",
                lang_code="ru", system_lang_code="ru",
            )
        else:
            client = TelegramClient(
                str(self._session_path(phone)), int(settings.API_ID), settings.API_HASH,
                device_model="TelegramCode", system_version="Web", app_version="0.2.0",
                lang_code="ru", system_lang_code="ru",
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
            return {"status": "already_authorized", "message": "Уже авторизован", "user": self._user_dict(me), "session": sess}
        result = await client.send_code_request(phone)
        self.phone_code_hashes[phone] = result.phone_code_hash
        return {"status": "code_sent", "message": "Код отправлен в Telegram"}

    async def _real_sign_in(self, phone, code, password=None, first_name=None, last_name=None) -> dict:
        from telethon.errors import (
            SessionPasswordNeededError, PhoneNumberUnoccupiedError,
            PhoneCodeInvalidError, PhoneCodeExpiredError, FloodWaitError,
        )
        err = self._ensure_api_keys()
        if err:
            return err
        client = await self._real_get_or_create_client(phone)
        if await client.is_user_authorized():
            me = await client.get_me()
            sess = await self._export_string(client)
            self.string_sessions[phone] = sess
            return {"status": "success", "message": "Уже авторизован", "user": self._user_dict(me), "session": sess}
        phone_code_hash = self.phone_code_hashes.get(phone)
        if not phone_code_hash:
            return {"status": "error", "message": "Сначала запросите код (или сервер перезапустился — запросите код снова)"}
        try:
            await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except SessionPasswordNeededError:
            if not password:
                return {"status": "2fa_required", "message": "Требуется пароль двухфакторной аутентификации"}
            await client.sign_in(password=password)
        except PhoneNumberUnoccupiedError:
            if not first_name or not first_name.strip():
                return {"status": "need_signup", "message": "Аккаунт не найден. Нужна регистрация"}
            await client.sign_up(code=code, first_name=first_name.strip(), last_name=(last_name or "").strip(), phone=phone, phone_code_hash=phone_code_hash)
        except PhoneCodeInvalidError:
            return {"status": "error", "message": "Неверный код"}
        except PhoneCodeExpiredError:
            return {"status": "error", "message": "Код истёк. Запросите новый"}
        except FloodWaitError as e:
            return {"status": "error", "message": f"Слишком много попыток. Подождите {e.seconds} сек."}
        me = await client.get_me()
        sess = await self._export_string(client)
        self.string_sessions[phone] = sess
        return {"status": "success", "message": "Успешный вход", "user": self._user_dict(me), "session": sess}

    async def _real_export_session(self, phone: str) -> dict:
        err = self._ensure_api_keys()
        if err:
            return err
        if phone in self.string_sessions:
            return {"status": "success", "session": self.string_sessions[phone], "phone": phone}
        client = self.clients.get(phone)
        if not client:
            try:
                client = await self._real_get_or_create_client(phone)
            except Exception:
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        sess = await self._export_string(client)
        self.string_sessions[phone] = sess
        return {"status": "success", "session": sess, "phone": phone}

    async def _real_load_session(self, session_str: str, phone: Optional[str] = None) -> dict:
        err = self._ensure_api_keys()
        if err:
            return err
        if not session_str or not str(session_str).strip():
            return {"status": "error", "message": "Файл сессии не передан. Отправьте строку или файл сессии."}
        session_str = re.sub(r"^session:\s*", "", str(session_str).strip(), flags=re.I).strip()
        try:
            key = phone or f"str_{session_str[-12:]}"
            client = await self._real_get_or_create_client(key, session_str=session_str)
            if not await client.is_user_authorized():
                return {"status": "error", "message": "Сессия не найдена или недействительна. Загрузите файл сессии вручную."}
            me = await client.get_me()
            user = self._user_dict(me)
            phone_real = user.get("phone") or phone or key
            self.clients[phone_real] = client
            self.string_sessions[phone_real] = session_str
            return {"status": "success", "message": "Сессия загружена", "user": user, "session": session_str, "phone": phone_real}
        except Exception as e:
            return {"status": "error", "message": f"Не удалось загрузить сессию: {e}. Загрузите файл сессии вручную."}

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
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        me = await client.get_me()
        return {"status": "success", "user": self._user_dict(me)}

    @staticmethod
    def _user_dict(me) -> dict:
        return {"id": me.id, "first_name": me.first_name, "last_name": me.last_name, "username": me.username, "phone": me.phone}

    # ==================== CHATS ====================

    async def get_dialogs(self, phone: str) -> dict:
        if MOCK:
            self._init_mock_chats(phone)
            return {"status": "success", "dialogs": self.mock_dialogs.get(phone, [])}
        try:
            client = self._ensure_client(phone)
            if not await client.is_user_authorized():
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
            dialogs = []
            async for d in client.iter_dialogs(limit=50):
                entity = d.entity
                title = d.name or "Без имени"
                username = getattr(entity, "username", None)
                last = ""
                if d.message:
                    last = d.message.message or ("[медиа]" if d.message.media else "")
                    if last and len(last) > 80:
                        last = last[:80] + "…"
                dialogs.append({
                    "id": d.id,
                    "title": title,
                    "username": username,
                    "unread": d.unread_count or 0,
                    "last_message": last,
                    "is_group": d.is_group,
                    "is_channel": d.is_channel,
                })
            return {"status": "success", "dialogs": dialogs}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def get_messages(self, phone: str, chat_id: int, limit: int = 40) -> dict:
        if MOCK:
            self._init_mock_chats(phone)
            msgs = list(reversed(self.mock_messages.get(phone, {}).get(chat_id, [])))
            return {"status": "success", "messages": msgs}
        try:
            client = self._ensure_client(phone)
            if not await client.is_user_authorized():
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
            me = await client.get_me()
            result = []
            messages = await client.get_messages(chat_id, limit=limit)
            for m in reversed(list(messages)):
                text = m.message or ""
                if not text and m.media:
                    text = "[медиа]"
                sender_name = ""
                try:
                    if m.sender:
                        sender_name = getattr(m.sender, "first_name", None) or getattr(m.sender, "title", None) or ""
                except Exception:
                    pass
                result.append({
                    "id": m.id,
                    "text": text,
                    "out": bool(m.out),
                    "date": m.date.strftime("%H:%M") if m.date else "",
                    "sender": sender_name or ("Вы" if m.out else ""),
                })
            return {"status": "success", "messages": result, "me_id": me.id}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def send_message(self, phone: str, chat_id: int, text: str) -> dict:
        if MOCK:
            self._init_mock_chats(phone)
            msgs = self.mock_messages.setdefault(phone, {}).setdefault(chat_id, [])
            msg = {"id": len(msgs) + 1, "text": text, "out": True, "date": "сейчас", "sender": "You"}
            msgs.append(msg)
            for d in self.mock_dialogs.get(phone, []):
                if d["id"] == chat_id:
                    d["last_message"] = text[:80]
            return {"status": "success", "message": msg}
        try:
            client = self._ensure_client(phone)
            if not await client.is_user_authorized():
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
            m = await client.send_message(chat_id, text)
            return {
                "status": "success",
                "message": {
                    "id": m.id,
                    "text": m.message or text,
                    "out": True,
                    "date": m.date.strftime("%H:%M") if m.date else "",
                    "sender": "Вы",
                },
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def run_command(self, phone: str, chat_id: int, command: str, args: List[str]) -> dict:
        cmd = (command or "").lower().strip()
        if cmd == "spam":
            word = args[0] if args else "spam"
            try:
                count = int(args[1]) if len(args) > 1 else 3
            except ValueError:
                count = 3
            count = max(1, min(count, 20))
            sent = []
            for i in range(count):
                r = await self.send_message(phone, chat_id, word)
                if r.get("status") == "success":
                    sent.append(r.get("message"))
                if not MOCK:
                    await asyncio.sleep(0.35)
            return {"status": "success", "message": f"Отправлено {len(sent)} раз", "sent": sent}

        if cmd == "mute":
            self.muted.setdefault(phone, set()).add(chat_id)
            return {"status": "success", "message": f"Mute для чата {chat_id} (локально)"}

        if cmd == "unmute":
            self.muted.setdefault(phone, set()).discard(chat_id)
            return {"status": "success", "message": f"Unmute для чата {chat_id}"}

        return {"status": "error", "message": f"Неизвестная команда: {cmd}. Доступны: spam, mute, unmute"}

    # ==================== PUBLIC ====================

    async def send_code(self, phone: str) -> dict:
        return await self._mock_send_code(phone) if MOCK else await self._real_send_code(phone)

    async def sign_in(self, phone, code, password=None, first_name=None, last_name=None) -> dict:
        if MOCK:
            return await self._mock_sign_in(phone, code, password, first_name, last_name)
        return await self._real_sign_in(phone, code, password, first_name, last_name)

    async def logout(self, phone: str) -> dict:
        return await self._mock_logout(phone) if MOCK else await self._real_logout(phone)

    async def get_me(self, phone: str) -> dict:
        return await self._mock_get_me(phone) if MOCK else await self._real_get_me(phone)

    async def export_session(self, phone: str) -> dict:
        return await self._mock_export_session(phone) if MOCK else await self._real_export_session(phone)

    async def load_session(self, session_str: str, phone: Optional[str] = None) -> dict:
        return await self._mock_load_session(session_str, phone) if MOCK else await self._real_load_session(session_str, phone)


telethon_manager = TelethonManager()
