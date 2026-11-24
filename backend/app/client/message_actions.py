"""Avatar download and message actions for TelethonManager."""
from typing import Dict, Optional
from app.client.tg_loop import on_tg_loop
from app.config import settings

MOCK = settings.is_mock


def _save_deleted_disk(self) -> None:
    try:
        import json as _json
        path = self.sessions_dir / "deleted_messages.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = {str(p): (items or [])[-200:] for p, items in (self.deleted_messages or {}).items()}
        path.write_text(_json.dumps(clean, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _save_deleted_settings_disk(self) -> None:
    try:
        import json as _json
        path = self.sessions_dir / "deleted_settings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_json.dumps(self.deleted_settings or {}, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def record_deleted_message(self, phone: str, payload: dict) -> None:
    """Called from MessageDeleted handler. Only stores if setting enabled."""
    cfg = self.deleted_settings.get(phone) or {}
    if not cfg.get("enabled", False):
        return
    items = self.deleted_messages.setdefault(phone, [])
    items.append(payload)
    if len(items) > 200:
        self.deleted_messages[phone] = items[-200:]
    self._save_deleted_disk()


@on_tg_loop
async def get_avatar(self, phone: str, peer_id: int) -> dict:
    if MOCK:
        return {"status": "success", "has_photo": False, "data_base64": None, "mime": None}
    try:
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        import base64
        from io import BytesIO
        entity = await client.get_entity(int(peer_id))
        buf = BytesIO()
        result = await client.download_profile_photo(entity, file=buf)
        if not result:
            return {"status": "success", "has_photo": False, "data_base64": None, "mime": "image/jpeg", "peer_id": int(peer_id)}
        data = buf.getvalue()
        if not data:
            return {"status": "success", "has_photo": False, "data_base64": None, "mime": "image/jpeg", "peer_id": int(peer_id)}
        b64 = base64.b64encode(data).decode("ascii")
        return {
            "status": "success",
            "has_photo": True,
            "data_base64": b64,
            "mime": "image/jpeg",
            "peer_id": int(peer_id),
            "size": len(data),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@on_tg_loop
async def delete_message(self, phone: str, chat_id: int, message_id: int, revoke: bool = False) -> dict:
    if MOCK:
        return {"status": "success", "message": "Удалено (mock)", "revoke": revoke}
    try:
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        await client.delete_messages(int(chat_id), [int(message_id)], revoke=bool(revoke))
        return {"status": "success", "message": "Удалено", "message_id": int(message_id), "revoke": bool(revoke)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@on_tg_loop
async def edit_message(self, phone: str, chat_id: int, message_id: int, text: str) -> dict:
    if MOCK:
        return {"status": "success", "message": {"id": message_id, "text": text, "out": True}}
    try:
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        m = await client.edit_message(int(chat_id), int(message_id), text)
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


@on_tg_loop
async def forward_message(self, phone: str, from_chat_id: int, message_id: int, to_chat_id: int) -> dict:
    if MOCK:
        return {"status": "success", "message": "Переслано (mock)"}
    try:
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        result = await client.forward_messages(int(to_chat_id), [int(message_id)], int(from_chat_id))
        mid = None
        if result:
            first = result[0] if isinstance(result, list) else result
            mid = getattr(first, "id", None)
        return {"status": "success", "message": "Переслано", "message_id": mid, "to_chat_id": int(to_chat_id)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@on_tg_loop
async def pin_message(self, phone: str, chat_id: int, message_id: int, unpin: bool = False) -> dict:
    if MOCK:
        return {"status": "success", "message": "unpinned" if unpin else "pinned"}
    try:
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        if unpin:
            await client.unpin_message(int(chat_id), int(message_id))
            return {"status": "success", "message": "Откреплено", "message_id": int(message_id)}
        await client.pin_message(int(chat_id), int(message_id))
        return {"status": "success", "message": "Закреплено", "message_id": int(message_id)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@on_tg_loop
async def react_message(self, phone: str, chat_id: int, message_id: int, emoticon: str) -> dict:
    if MOCK:
        return {"status": "success", "message": "reaction set" if emoticon else "reaction removed"}
    try:
        from telethon.tl.functions.messages import SendReactionRequest
        from telethon.tl.types import ReactionEmoji
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        if not emoticon:
            await client(SendReactionRequest(peer=int(chat_id), msg_id=int(message_id), reaction=[]))
            return {"status": "success", "message": "Реакция снята", "message_id": int(message_id)}
        await client(SendReactionRequest(
            peer=int(chat_id),
            msg_id=int(message_id),
            reaction=[ReactionEmoji(emoticon=emoticon)],
        ))
        return {"status": "success", "message": "Реакция добавлена", "message_id": int(message_id), "emoticon": emoticon}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@on_tg_loop
async def get_deleted_messages(self, phone: str) -> dict:
    items = list(self.deleted_messages.get(phone) or [])
    cfg = self.deleted_settings.get(phone) or {"enabled": False}
    return {
        "status": "success",
        "messages": items[-100:],
        "enabled": bool(cfg.get("enabled")),
        "count": len(items),
    }


@on_tg_loop
async def clear_deleted_messages(self, phone: str) -> dict:
    self.deleted_messages[phone] = []
    self._save_deleted_disk()
    return {"status": "success", "message": "Сохранённые удалённые сообщения очищены"}


@on_tg_loop
async def set_deleted_settings(self, phone: str, enabled: bool = None) -> dict:
    cfg = dict(self.deleted_settings.get(phone) or {"enabled": False})
    if enabled is not None:
        cfg["enabled"] = bool(enabled)
    self.deleted_settings[phone] = cfg
    self._save_deleted_settings_disk()
    return {"status": "success", "settings": cfg}
