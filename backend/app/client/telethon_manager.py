"""Менеджер Telegram-клиентов + сессии + чаты + mute + ИИ автоответ."""

from pathlib import Path
from typing import Dict, Optional, List, Any
import hashlib
import re
import asyncio

from app.config import settings
from app.client.tg_loop import on_tg_loop

MOCK = settings.is_mock

try:
    from app.client.live_features import (
        attach_handlers,
        run_extra_command,
        default_ai,
        AI_PRESETS,
        load_ai_from_disk,
        save_ai_to_disk,
        load_mute_from_disk,
        save_mute_to_disk,
        load_triggers_from_disk,
        save_triggers_to_disk,
        ai_generate,
        FREE_MODELS,
    )
except Exception:  # pragma: no cover
    attach_handlers = None
    run_extra_command = None
    load_ai_from_disk = None
    save_ai_to_disk = None
    load_mute_from_disk = None
    save_mute_to_disk = None
    load_triggers_from_disk = None
    save_triggers_to_disk = None
    ai_generate = None
    FREE_MODELS = {
        "groq": ["openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b", "allam-2-7b"],
        "openrouter": [
            "meta-llama/llama-3.2-3b-instruct:free",
            "google/gemma-2-9b-it:free",
            "microsoft/phi-3-mini-128k-instruct:free",
            "qwen/qwen-2-7b-instruct:free",
        ],
        "openai": ["gpt-4o-mini", "gpt-3.5-turbo"],
    }

    def default_ai() -> dict:
        return {
            "enabled": False,
            "provider": "groq",
            "api_key": "",
            "model": "openai/gpt-oss-20b",
            "api_base": "https://api.groq.com/openai/v1",
            "last_error": "",
        }

    AI_PRESETS = {
        "groq": {"base": "https://api.groq.com/openai/v1", "model": "openai/gpt-oss-20b"},
        "openrouter": {"base": "https://openrouter.ai/api/v1", "model": "meta-llama/llama-3.2-3b-instruct:free"},
        "openai": {"base": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    }


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

        # chat_id set per phone — any incoming message is deleted
        self.muted: Dict[str, set] = {}
        if load_mute_from_disk is not None:
            try:
                self.muted = load_mute_from_disk(self.sessions_dir) or {}
            except Exception:
                self.muted = {}
        # AI auto-reply settings per phone (загружаем с диска после рестарта)
        self.ai_settings: Dict[str, dict] = {}
        if load_ai_from_disk is not None:
            try:
                self.ai_settings = load_ai_from_disk(self.sessions_dir) or {}
            except Exception:
                self.ai_settings = {}
        self.triggers: Dict[str, list] = {}
        if load_triggers_from_disk is not None:
            try:
                self.triggers = load_triggers_from_disk(self.sessions_dir) or {}
            except Exception:
                self.triggers = {}
        self._handlers_ready: set = set()
        # deleted-messages store (only via MessageDeleted events)
        self.deleted_messages: Dict[str, list] = {}
        self.deleted_settings: Dict[str, dict] = {}
        self.msg_text_cache: Dict[str, dict] = {}
        try:
            import json as _json
            dp = self.sessions_dir / "deleted_messages.json"
            if dp.exists():
                self.deleted_messages = _json.loads(dp.read_text(encoding="utf-8")) or {}
            sp = self.sessions_dir / "deleted_settings.json"
            if sp.exists():
                self.deleted_settings = _json.loads(sp.read_text(encoding="utf-8")) or {}
        except Exception:
            pass

    def _session_path(self, phone: str) -> Path:
        clean = "".join(c for c in phone if c.isdigit())
        return self.sessions_dir / f"{clean}.session"

    def _ensure_api_keys(self) -> Optional[dict]:
        if not settings.has_api_keys:
            return {"status": "error", "message": "На сервере не заданы API_ID и API_HASH."}
        return None

    async def _attach_live(self, phone: str, client) -> None:
        """Подключает NewMessage-хендлеры (mute-delete + ИИ)."""
        if MOCK or client is None or attach_handlers is None:
            return
        try:
            await attach_handlers(self, phone, client)
        except Exception:
            pass

    async def _ensure_client(self, phone: str):
        client = self.clients.get(phone)
        if client is not None:
            if not MOCK and hasattr(client, "is_connected") and not client.is_connected():
                await client.connect()
            await self._attach_live(phone, client)
            return client
        sess = self.string_sessions.get(phone)
        if sess and not MOCK:
            client = await self._real_get_or_create_client(phone, session_str=sess)
            await self._attach_live(phone, client)
            return client
        if not MOCK and self._session_path(phone).exists():
            client = await self._real_get_or_create_client(phone)
            await self._attach_live(phone, client)
            return client
        raise RuntimeError("Нет активной сессии. Войдите или загрузите сессию.")

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
        self.muted.pop(phone, None)
        self.ai_settings.pop(phone, None)
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
                device_model="TelegramCode", system_version="Web", app_version="0.3.0",
                lang_code="ru", system_lang_code="ru",
            )
        else:
            client = TelegramClient(
                str(self._session_path(phone)), int(settings.API_ID), settings.API_HASH,
                device_model="TelegramCode", system_version="Web", app_version="0.3.0",
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
            await self._attach_live(phone, client)
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
            await self._attach_live(phone, client)
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
        await self._attach_live(phone, client)
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
            await self._attach_live(phone_real, client)
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
        self.muted.pop(phone, None)
        self.ai_settings.pop(phone, None)
        self._handlers_ready.discard(phone)
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
        return {
            "id": me.id,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "username": me.username,
            "phone": me.phone,
        }

    # ==================== CHATS ====================

    @on_tg_loop
    async def get_dialogs(self, phone: str) -> dict:
        if MOCK:
            self._init_mock_chats(phone)
            return {"status": "success", "dialogs": self.mock_dialogs.get(phone, [])}
        try:
            client = await self._ensure_client(phone)
            if not await client.is_user_authorized():
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
            # собираем mute по всем вариантам ключа телефона (+7 / 7 / digits)
            muted_ids = set()
            phone_digits = "".join(c for c in str(phone) if c.isdigit())
            for k, s in (self.muted or {}).items():
                kd = "".join(c for c in str(k) if c.isdigit())
                if k == phone or kd == phone_digits:
                    for x in s:
                        try:
                            muted_ids.add(int(x))
                        except Exception:
                            pass
            ai_on = bool((self.ai_settings.get(phone) or {}).get("enabled"))
            if not ai_on:
                for k, cfg in (self.ai_settings or {}).items():
                    kd = "".join(c for c in str(k) if c.isdigit())
                    if k == phone or kd == phone_digits:
                        if (cfg or {}).get("enabled"):
                            ai_on = True
                            break

            def _dialog_row(d, force_archived=False):
                entity = d.entity
                title = d.name or "Без имени"
                username = getattr(entity, "username", None)
                last = ""
                if d.message:
                    last = d.message.message or ("[медиа]" if d.message.media else "")
                    if last and len(last) > 80:
                        last = last[:80] + "…"
                did = int(d.id)
                archived = force_archived or bool(getattr(d, "archived", False))
                return {
                    "id": did,
                    "title": title,
                    "username": username,
                    "unread": d.unread_count or 0,
                    "last_message": last,
                    "is_group": d.is_group,
                    "is_channel": d.is_channel,
                    "muted": did in muted_ids,
                    "ai_enabled": ai_on,
                    "archived": archived,
                }

            # folder=0 — основной список; folder=1 — архив (как в Telegram)
            dialogs = []
            async for d in client.iter_dialogs(limit=50, folder=0):
                if getattr(d, "archived", False):
                    continue
                dialogs.append(_dialog_row(d, force_archived=False))

            archived = []
            try:
                async for d in client.iter_dialogs(limit=50, folder=1):
                    archived.append(_dialog_row(d, force_archived=True))
            except Exception:
                archived = []

            return {
                "status": "success",
                "dialogs": dialogs,
                "archived": archived,
                "ai_enabled": ai_on,
                "muted_ids": list(muted_ids),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @on_tg_loop
    async def get_messages(self, phone: str, chat_id: int, limit: int = 25) -> dict:
        if MOCK:
            self._init_mock_chats(phone)
            msgs = list(reversed(self.mock_messages.get(phone, {}).get(chat_id, [])))
            return {"status": "success", "messages": msgs}
        try:
            client = await self._ensure_client(phone)
            if not await client.is_user_authorized():
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
            me = await client.get_me()
            result = []
            messages = await client.get_messages(chat_id, limit=limit)
            for m in reversed(list(messages)):
                text = m.message or ""
                media_info = None
                if m.media:
                    media_info = await self._describe_media(client, m)
                    if not text:
                        text = (media_info or {}).get("label") or "[медиа]"
                sender_name = ""
                sender_username = None
                try:
                    if m.sender:
                        sender_name = getattr(m.sender, "first_name", None) or getattr(m.sender, "title", None) or ""
                        sender_username = getattr(m.sender, "username", None) or None
                except Exception:
                    pass
                reactions = []
                try:
                    if getattr(m, "reactions", None) and getattr(m.reactions, "results", None):
                        for r in m.reactions.results:
                            emo = getattr(getattr(r, "reaction", None), "emoticon", None) or "👍"
                            reactions.append({"emoji": emo, "count": int(getattr(r, "count", 1) or 1)})
                except Exception:
                    pass
                reply_to = None
                try:
                    rto = getattr(m, "reply_to", None)
                    rid = getattr(rto, "reply_to_msg_id", None) if rto else None
                    if rid:
                        reply_to = {"id": int(rid)}
                except Exception:
                    reply_to = None
                row = {
                    "id": m.id,
                    "text": text,
                    "out": bool(m.out),
                    "date": m.date.strftime("%H:%M") if m.date else "",
                    "sender": sender_name or ("Вы" if m.out else ""),
                    "sender_username": sender_username,
                    "media": media_info,
                    "reactions": reactions,
                    "reply_to": reply_to,
                }
                result.append(row)
            # fill reply quote text/sender from messages in this page when possible
            by_id = {row["id"]: row for row in result if row.get("id") is not None}
            for row in result:
                rto = row.get("reply_to")
                if not rto or not rto.get("id"):
                    continue
                src = by_id.get(rto["id"])
                if src:
                    rto["text"] = (src.get("text") or "")[:120]
                    rto["sender"] = src.get("sender") or ""
            try:
                self.cache_messages_for_deleted(phone, int(chat_id), result)
            except Exception:
                pass
            return {"status": "success", "messages": result, "me_id": me.id}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    async def _describe_media(self, client, m) -> dict:
        """Только метаданные медиа (без скачивания файла). Превью — через /chats/media по запросу."""
        from telethon.tl.types import (
            MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage,
        )
        info = {"type": "unknown", "label": "[медиа]", "thumb": None, "name": None, "mime": None, "size": None}
        try:
            media = m.media
            if isinstance(media, MessageMediaPhoto) or (getattr(m, "photo", None)):
                info["type"] = "photo"
                info["label"] = "📷 Фото"
                info["mime"] = "image/jpeg"
                # не качаем здесь — иначе список сообщений тормозит на каждой фотке
                return info
            if isinstance(media, MessageMediaDocument) or getattr(m, "document", None):
                doc = getattr(m, "document", None) or getattr(media, "document", None)
                mime = getattr(doc, "mime_type", "") or ""
                name = None
                duration = None
                for attr in getattr(doc, "attributes", []) or []:
                    n = getattr(attr, "file_name", None)
                    if n:
                        name = n
                    # DocumentAttributeAudio: voice=True для голосовых
                    if getattr(attr, "voice", False):
                        duration = getattr(attr, "duration", None)
                        info["type"] = "voice"
                        info["label"] = "🎤 Голосовое"
                    elif getattr(attr, "duration", None) is not None and "audio" in mime and info["type"] == "unknown":
                        duration = attr.duration
                        info["type"] = "audio"
                        info["label"] = "🎵 Аудио"
                    elif getattr(attr, "duration", None) is not None and "video" in mime:
                        duration = attr.duration
                        info["type"] = "video"
                        info["label"] = "🎬 Видео"
                if info["type"] == "unknown":
                    if "image" in mime:
                        info["type"] = "photo"
                        info["label"] = "📷 Изображение"
                    elif "audio" in mime:
                        info["type"] = "audio"
                        info["label"] = "🎵 Аудио"
                    elif "video" in mime:
                        info["type"] = "video"
                        info["label"] = "🎬 Видео"
                    else:
                        info["type"] = "file"
                        info["label"] = "📎 Файл"
                info["name"] = name
                info["mime"] = mime
                info["size"] = getattr(doc, "size", None)
                info["duration"] = duration
                if name:
                    info["label"] = f"{info['label']}: {name}"
                return info
            if isinstance(media, MessageMediaWebPage):
                info["type"] = "webpage"
                info["label"] = "🔗 Ссылка"
                return info
        except Exception:
            pass
        return info

    MEDIA_DOWNLOAD_MAX = 12 * 1024 * 1024  # 12 MB — лимит free-хостинга

    @on_tg_loop
    async def download_message_media(self, phone: str, chat_id: int, message_id: int) -> dict:
        """Скачать медиа сообщения (base64). Фото/аудио/видео/файл в пределах лимита."""
        import base64
        if MOCK:
            return {"status": "error", "message": "В mock-режиме медиа недоступно"}
        try:
            client = await self._ensure_client(phone)
            if not await client.is_user_authorized():
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
            msgs = await client.get_messages(chat_id, ids=int(message_id))
            m = msgs if not isinstance(msgs, list) else (msgs[0] if msgs else None)
            if not m:
                return {"status": "error", "message": "Сообщение не найдено"}
            if not getattr(m, "media", None):
                return {"status": "error", "message": "В сообщении нет медиа"}

            size_hint = None
            mime = "application/octet-stream"
            name = f"file_{message_id}"
            media_type = "file"
            try:
                desc = await self._describe_media(client, m)
                media_type = desc.get("type") or "file"
                mime = desc.get("mime") or mime
                if desc.get("name"):
                    name = desc["name"]
                size_hint = desc.get("size")
                if media_type == "photo":
                    mime = "image/jpeg"
                    if not str(name).lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                        name = f"photo_{message_id}.jpg"
                elif media_type == "voice":
                    mime = mime if "audio" in (mime or "") else "audio/ogg"
                    if "." not in str(name):
                        name = f"voice_{message_id}.ogg"
                elif media_type == "audio":
                    mime = mime or "audio/mpeg"
                    if "." not in str(name):
                        name = f"audio_{message_id}.mp3"
                elif media_type == "video":
                    mime = mime or "video/mp4"
                    if "." not in str(name):
                        name = f"video_{message_id}.mp4"
            except Exception:
                pass

            if size_hint and int(size_hint) > self.MEDIA_DOWNLOAD_MAX:
                mb = int(size_hint) // (1024 * 1024)
                return {
                    "status": "error",
                    "message": f"Файл слишком большой ({mb} MB). Лимит {self.MEDIA_DOWNLOAD_MAX // (1024 * 1024)} MB.",
                    "too_large": True,
                    "size": int(size_hint),
                }

            data = await client.download_media(m, file=bytes)
            if not data:
                return {"status": "error", "message": "Не удалось скачать медиа"}
            if len(data) > self.MEDIA_DOWNLOAD_MAX:
                return {
                    "status": "error",
                    "message": f"Файл слишком большой ({len(data) // (1024 * 1024)} MB). Лимит {self.MEDIA_DOWNLOAD_MAX // (1024 * 1024)} MB.",
                    "too_large": True,
                    "size": len(data),
                }
            return {
                "status": "success",
                "type": media_type,
                "mime": mime,
                "name": name,
                "size": len(data),
                "data_base64": base64.b64encode(data).decode("ascii"),
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @on_tg_loop
    async def send_message(self, phone: str, chat_id: int, text: str, reply_to: int = None) -> dict:
        if MOCK:
            self._init_mock_chats(phone)
            msgs = self.mock_messages.setdefault(phone, {}).setdefault(chat_id, [])
            msg = {"id": len(msgs) + 1, "text": text, "out": True, "date": "сейчас", "sender": "You"}
            if reply_to:
                msg["reply_to"] = {"id": int(reply_to), "text": "", "sender": ""}
            msgs.append(msg)
            for d in self.mock_dialogs.get(phone, []):
                if d["id"] == chat_id:
                    d["last_message"] = text[:80]
            return {"status": "success", "message": msg}
        try:
            client = await self._ensure_client(phone)
            if not await client.is_user_authorized():
                return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
            kwargs = {}
            if reply_to:
                kwargs["reply_to"] = int(reply_to)
            m = await client.send_message(chat_id, text, **kwargs)
            out = {
                "id": m.id,
                "text": m.message or text,
                "out": True,
                "date": m.date.strftime("%H:%M") if m.date else "",
                "sender": "Вы",
            }
            if reply_to:
                out["reply_to"] = {"id": int(reply_to)}
            return {"status": "success", "message": out}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # ==================== COMMANDS ====================

    @on_tg_loop
    async def run_command(self, phone: str, chat_id: int, command: str, args: List[str]) -> dict:
        cmd = (command or "").lower().strip()
        args = args or []

        # Extra commands from live_features (help, mute, unmute, status, id, ping, me, ai, reply)
        if run_extra_command is not None:
            extra = await run_extra_command(
                self, phone, chat_id, cmd, args, MOCK, self.send_message, self.get_me
            )
            if extra is not None:
                # Ensure handlers are attached after mute so delete works immediately
                if cmd in ("mute", "unmute") and not MOCK:
                    try:
                        client = await self._ensure_client(phone)
                        await self._attach_live(phone, client)
                    except Exception:
                        pass
                return extra

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
            try:
                cid = int(chat_id)
            except Exception:
                cid = chat_id
            self.muted.setdefault(phone, set()).add(cid)
            if save_mute_to_disk is not None:
                try:
                    save_mute_to_disk(self.sessions_dir, self.muted)
                except Exception:
                    pass
            if not MOCK:
                try:
                    client = await self._ensure_client(phone)
                    await self._attach_live(phone, client)
                except Exception:
                    pass
            return {
                "status": "success",
                "message": f"Mute включён для чата {cid}: все входящие будут удаляться",
                "muted": True,
                "chat_id": cid,
            }

        if cmd == "unmute":
            try:
                cid = int(chat_id)
            except Exception:
                cid = chat_id
            self.muted.setdefault(phone, set()).discard(cid)
            if save_mute_to_disk is not None:
                try:
                    save_mute_to_disk(self.sessions_dir, self.muted)
                except Exception:
                    pass
            return {
                "status": "success",
                "message": f"Mute выключен для чата {cid}",
                "muted": False,
                "chat_id": cid,
            }

        if cmd in ("help", "commands", "cmds"):
            text = (
                "Команды TelegramCode:\n"
                "help — этот список\n"
                "spam слово N — повторить (макс 20)\n"
                "mute — удалять ВСЕ входящие в этом чате (текст/фото/видео/стикеры)\n"
                "unmute — снять mute\n"
                "status — mute и ИИ\n"
                "id — id чата\n"
                "ping — проверка\n"
                "me / whoami — кто я\n"
                "ai on|off — автоответ ИИ в личках\n"
                "reply текст — отправить от себя\n"
                "info — краткая инфа о чате\n"
                "clear N — удалить свои последние N сообщений (макс 30)"
            )
            return {"status": "success", "message": text}

        if cmd == "status":
            is_muted = chat_id in (self.muted.get(phone) or set())
            ai = self.ai_settings.get(phone) or {}
            return {
                "status": "success",
                "message": f"mute={'да' if is_muted else 'нет'}; ИИ={'вкл' if ai.get('enabled') else 'выкл'}; provider={ai.get('provider') or '-'}",
            }

        if cmd == "id":
            return {"status": "success", "message": f"chat_id={chat_id}"}

        if cmd == "ping":
            return {"status": "success", "message": "pong ✓"}

        if cmd in ("me", "whoami"):
            me = await self.get_me(phone)
            if me.get("status") != "success":
                return me
            u = me.get("user") or {}
            return {
                "status": "success",
                "message": f"{u.get('first_name') or ''} @{u.get('username') or '—'} id={u.get('id')} phone={u.get('phone') or '—'}",
            }

        if cmd == "ai":
            mode = (args[0] if args else "").lower()
            cfg = default_ai()
            cfg.update(self.ai_settings.get(phone) or {})
            if mode in ("on", "1", "true", "вкл"):
                cfg["enabled"] = True
                self.ai_settings[phone] = cfg
                return {"status": "success", "message": "ИИ автоответ включён (только личные сообщения)"}
            if mode in ("off", "0", "false", "выкл"):
                cfg["enabled"] = False
                self.ai_settings[phone] = cfg
                return {"status": "success", "message": "ИИ автоответ выключен"}
            return {
                "status": "success",
                "message": f"ИИ сейчас: {'вкл' if cfg.get('enabled') else 'выкл'}. Используй: ai on | ai off",
            }

        if cmd == "reply":
            text = " ".join(args).strip()
            if not text:
                return {"status": "error", "message": "Укажи текст: reply привет"}
            return await self.send_message(phone, chat_id, text)

        if cmd == "info":
            return {
                "status": "success",
                "message": f"chat_id={chat_id}; muted={chat_id in (self.muted.get(phone) or set())}",
            }

        if cmd == "clear":
            try:
                n = int(args[0]) if args else 5
            except ValueError:
                n = 5
            n = max(1, min(n, 30))
            if MOCK:
                return {"status": "success", "message": f"(mock) clear {n}"}
            try:
                client = await self._ensure_client(phone)
                msgs = await client.get_messages(chat_id, limit=n * 2)
                own_ids = [m.id for m in msgs if m.out][:n]
                if own_ids:
                    await client.delete_messages(chat_id, own_ids, revoke=True)
                return {"status": "success", "message": f"Удалено своих сообщений: {len(own_ids)}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        return {
            "status": "error",
            "message": f"Неизвестная команда: {cmd}. Напиши help",
        }

    # ==================== AI SETTINGS ====================

    @on_tg_loop
    async def get_ai_settings(self, phone: str) -> dict:
        cfg = default_ai()
        cfg.update(self.ai_settings.get(phone) or {})
        key = cfg.get("api_key") or ""
        masked = (key[:4] + "…" + key[-4:]) if len(key) > 8 else (key[:2] + "…" if key else "")
        return {
            "status": "success",
            "settings": {
                "enabled": bool(cfg.get("enabled")),
                "provider": cfg.get("provider") or "groq",
                "api_key": key,
                "api_key_masked": masked,
                "model": cfg.get("model") or "",
                "api_base": cfg.get("api_base") or "",
                "last_error": cfg.get("last_error") or "",
                "presets": {k: v for k, v in AI_PRESETS.items()},
                "free_models": FREE_MODELS if FREE_MODELS else {},
            },
        }

    @on_tg_loop
    async def set_ai_settings(self, phone: str, payload: dict) -> dict:
        cfg = default_ai()
        cfg.update(self.ai_settings.get(phone) or {})
        if "enabled" in payload and payload["enabled"] is not None:
            cfg["enabled"] = bool(payload["enabled"])
        if payload.get("provider"):
            p = str(payload["provider"]).lower().strip()
            if p in AI_PRESETS:
                cfg["provider"] = p
                preset = AI_PRESETS[p]
                if not payload.get("api_base"):
                    cfg["api_base"] = preset["base"]
                if not payload.get("model"):
                    cfg["model"] = preset["model"]
        if "api_key" in payload and payload["api_key"] is not None:
            cfg["api_key"] = str(payload["api_key"]).strip()
        if payload.get("model"):
            cfg["model"] = str(payload["model"]).strip()
        if payload.get("api_base"):
            cfg["api_base"] = str(payload["api_base"]).strip().rstrip("/")
        # clear error on successful save of new key
        if payload.get("api_key"):
            cfg["last_error"] = ""
        self.ai_settings[phone] = cfg
        if save_ai_to_disk is not None:
            try:
                save_ai_to_disk(self.sessions_dir, self.ai_settings)
            except Exception:
                pass
        if not MOCK and phone in self.clients:
            try:
                await self._attach_live(phone, self.clients[phone])
            except Exception:
                pass
        return {
            "status": "success",
            "message": "Настройки ИИ сохранены (диск + память)",
            "settings": {
                "enabled": cfg["enabled"],
                "provider": cfg["provider"],
                "model": cfg["model"],
                "api_base": cfg["api_base"],
                "last_error": cfg.get("last_error") or "",
            },
        }

    # ==================== PUBLIC ====================

    @on_tg_loop
    async def send_code(self, phone: str) -> dict:
        return await self._mock_send_code(phone) if MOCK else await self._real_send_code(phone)

    @on_tg_loop
    async def sign_in(self, phone, code, password=None, first_name=None, last_name=None) -> dict:
        if MOCK:
            return await self._mock_sign_in(phone, code, password, first_name, last_name)
        return await self._real_sign_in(phone, code, password, first_name, last_name)

    @on_tg_loop
    async def logout(self, phone: str) -> dict:
        return await self._mock_logout(phone) if MOCK else await self._real_logout(phone)

    @on_tg_loop
    async def get_me(self, phone: str) -> dict:
        return await self._mock_get_me(phone) if MOCK else await self._real_get_me(phone)

    @on_tg_loop
    async def export_session(self, phone: str) -> dict:
        return await self._mock_export_session(phone) if MOCK else await self._real_export_session(phone)

    @on_tg_loop
    async def load_session(self, session_str: str, phone: Optional[str] = None) -> dict:
        if MOCK:
            return await self._mock_load_session(session_str, phone)
        return await self._real_load_session(session_str, phone)

    @on_tg_loop
    async def get_triggers(self, phone: str) -> dict:
        items = list(self.triggers.get(phone) or [])
        return {"status": "success", "triggers": items}

    @on_tg_loop
    async def set_triggers(self, phone: str, triggers: list) -> dict:
        clean = []
        for t in (triggers or [])[:50]:
            if not isinstance(t, dict):
                continue
            pat = str(t.get("pattern") or "").strip()
            if not pat:
                continue
            clean.append({
                "id": str(t.get("id") or f"t{len(clean)+1}"),
                "pattern": pat[:200],
                "reply": str(t.get("reply") or "")[:2000],
                "mode": str(t.get("mode") or "contains")[:20],
                "enabled": bool(t.get("enabled", True)),
            })
        self.triggers[phone] = clean
        if save_triggers_to_disk is not None:
            try:
                save_triggers_to_disk(self.sessions_dir, self.triggers)
            except Exception:
                pass
        return {"status": "success", "triggers": clean, "message": f"Сохранено триггеров: {len(clean)}"}

    @on_tg_loop
    async def local_ai_chat(self, phone: str, message: str, history: list = None) -> dict:
        """Локальный ИИ-чат только на сайте (не Telegram)."""
        if ai_generate is None:
            return {"status": "error", "message": "AI недоступен"}
        hist = []
        for h in (history or [])[-12]:
            if isinstance(h, dict) and h.get("content"):
                hist.append({"role": h.get("role") or "user", "content": str(h["content"])[:800]})
        me_info = None
        try:
            if phone in self.clients and not MOCK:
                me = await self.clients[phone].get_me()
                me_info = {
                    "first_name": getattr(me, "first_name", "") or "",
                    "last_name": getattr(me, "last_name", "") or "",
                    "username": getattr(me, "username", "") or "",
                }
        except Exception:
            pass
        reply, err = await ai_generate(self, phone, message, history=hist, me_info=me_info)
        if err:
            return {"status": "error", "message": err}
        return {"status": "success", "reply": reply}




# Bind message actions (avatar, delete, edit, forward, pin, react, deleted store)
try:
    from app.client import message_actions as _ma
    TelethonManager._save_deleted_disk = _ma._save_deleted_disk
    TelethonManager._save_deleted_settings_disk = _ma._save_deleted_settings_disk
    TelethonManager.record_deleted_message = _ma.record_deleted_message
    TelethonManager.cache_messages_for_deleted = _ma.cache_messages_for_deleted
    TelethonManager.get_avatar = _ma.get_avatar
    TelethonManager.delete_message = _ma.delete_message
    TelethonManager.edit_message = _ma.edit_message
    TelethonManager.forward_message = _ma.forward_message
    TelethonManager.pin_message = _ma.pin_message
    TelethonManager.react_message = _ma.react_message
    TelethonManager.get_deleted_messages = _ma.get_deleted_messages
    TelethonManager.clear_deleted_messages = _ma.clear_deleted_messages
    TelethonManager.set_deleted_settings = _ma.set_deleted_settings
except Exception:
    pass



telethon_manager = TelethonManager()
