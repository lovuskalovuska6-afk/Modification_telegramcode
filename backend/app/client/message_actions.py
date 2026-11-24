"""Avatar download and message actions for TelethonManager (bound as methods)."""
from pathlib import Path
from typing import Optional

from app.client.tg_loop import on_tg_loop
from app.config import settings

MOCK = settings.is_mock


def _phone_digits(phone: str) -> str:
    return "".join(c for c in str(phone) if c.isdigit()) or "unknown"


async def _peer(client, chat_id):
    """Resolve Telegram peer; raw int often fails for channels/supergroups."""
    return await client.get_input_entity(int(chat_id))


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
    """Only from MessageDeleted events. Merges text from msg cache if available.

    Limits (Telegram / Telethon):
    - In some private chats MessageDeleted may omit chat_id.
    - Without chat_id we only attach cache text if a single cache entry matches msg id
      (avoid cross-chat ambiguity).
    - We never invent deletions from missing history rows.
    """
    cfg = (self.deleted_settings or {}).get(phone) or {}
    if not cfg.get("enabled", False):
        return
    cache = getattr(self, "msg_text_cache", {}).get(phone) or {}
    mid = payload.get("id")
    cid = payload.get("chat_id")
    prev = None
    if cid is not None and mid is not None:
        prev = cache.get(f"{cid}:{mid}") or {}
    elif mid is not None:
        # ambiguous without chat_id — only use cache if unique id match
        matches = [v for k, v in cache.items() if k.endswith(f":{mid}")]
        if len(matches) == 1:
            prev = matches[0]
            # do not invent chat_id from cache key unless clearly unique
        else:
            prev = {}
    if prev:
        payload = {
            **payload,
            "text": prev.get("text") or payload.get("text"),
            "sender": prev.get("sender") or payload.get("sender"),
            "date": prev.get("date") or payload.get("date"),
            "out": prev.get("out"),
            "chat_id_uncertain": cid is None,
        }
    elif cid is None:
        payload = {**payload, "chat_id_uncertain": True}
    items = self.deleted_messages.setdefault(phone, [])
    def _same(x):
        if x.get("id") != payload.get("id"):
            return False
        # if both lack chat_id, treat as same; if one has it, require equal
        xc, pc = x.get("chat_id"), payload.get("chat_id")
        if xc is None and pc is None:
            return True
        return xc == pc
    items = [x for x in items if not _same(x)]
    items.append(payload)
    self.deleted_messages[phone] = items[-200:]
    self._save_deleted_disk()


def cache_messages_for_deleted(self, phone: str, chat_id: int, messages: list) -> None:
    """Keep recent message text so MessageDeleted can store author/text."""
    if not hasattr(self, "msg_text_cache"):
        self.msg_text_cache = {}
    bucket = self.msg_text_cache.setdefault(phone, {})
    for m in messages or []:
        mid = m.get("id")
        if mid is None:
            continue
        bucket[f"{chat_id}:{mid}"] = {
            "text": (m.get("text") or "")[:2000],
            "sender": m.get("sender"),
            "date": m.get("date"),
            "out": m.get("out"),
        }
    # cap cache size
    if len(bucket) > 2000:
        keys = list(bucket.keys())[:-1500]
        for k in keys:
            bucket.pop(k, None)


@on_tg_loop
async def get_avatar(self, phone: str, peer_id: int) -> dict:
    """Avatar with disk cache: sessions/avatars/{phone_digits}/{peer_id}.jpg"""
    if MOCK:
        return {"status": "success", "has_photo": False, "data_base64": None, "mime": None}
    try:
        import base64
        from io import BytesIO

        peer_id = int(peer_id)
        digits = _phone_digits(phone)
        cache_dir = Path(self.sessions_dir) / "avatars" / digits
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"{peer_id}.jpg"

        if cache_file.exists() and cache_file.stat().st_size > 0:
            data = cache_file.read_bytes()
            return {
                "status": "success",
                "has_photo": True,
                "data_base64": base64.b64encode(data).decode("ascii"),
                "mime": "image/jpeg",
                "peer_id": peer_id,
                "cached": True,
            }

        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}

        entity = await client.get_entity(peer_id)
        buf = BytesIO()
        result = await client.download_profile_photo(entity, file=buf)
        data = buf.getvalue() if result else b""
        if not data:
            return {
                "status": "success",
                "has_photo": False,
                "data_base64": None,
                "mime": "image/jpeg",
                "peer_id": peer_id,
            }
        # Safe resize (never truncate JPEG bytes — that corrupts the file)
        try:
            from PIL import Image
            from io import BytesIO as _B
            im = Image.open(_B(data))
            im.thumbnail((160, 160), Image.Resampling.LANCZOS)
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            out = _B()
            im.save(out, format="JPEG", quality=85, optimize=True)
            data = out.getvalue()
        except Exception:
            # if Pillow missing/broken, keep original only if reasonably small
            if len(data) > 400_000:
                return {
                    "status": "success",
                    "has_photo": False,
                    "data_base64": None,
                    "mime": "image/jpeg",
                    "peer_id": peer_id,
                    "message": "avatar too large and resize unavailable",
                }
        try:
            cache_file.write_bytes(data)
        except Exception:
            pass
        return {
            "status": "success",
            "has_photo": True,
            "data_base64": base64.b64encode(data).decode("ascii"),
            "mime": "image/jpeg",
            "peer_id": peer_id,
            "cached": False,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@on_tg_loop
async def delete_message(self, phone: str, chat_id: int, message_id: int, revoke: bool = False) -> dict:
    if MOCK:
        return {"status": "success", "message": "deleted", "revoke": revoke}
    try:
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        peer = await _peer(client, chat_id)
        await client.delete_messages(peer, [int(message_id)], revoke=bool(revoke))
        return {
            "status": "success",
            "message": "Удалено у всех" if revoke else "Удалено у меня",
            "message_id": int(message_id),
            "revoke": bool(revoke),
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@on_tg_loop
async def edit_message(self, phone: str, chat_id: int, message_id: int, text: str) -> dict:
    if MOCK:
        return {"status": "success", "message": {"id": message_id, "text": text}}
    try:
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        peer = await _peer(client, chat_id)
        m = await client.edit_message(peer, int(message_id), text)
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
        return {"status": "success", "message": "forwarded"}
    try:
        client = await self._ensure_client(phone)
        if not await client.is_user_authorized():
            return {"status": "error", "message": "Сессия не найдена. Загрузите файл сессии вручную."}
        to_peer = await _peer(client, to_chat_id)
        from_peer = await _peer(client, from_chat_id)
        result = await client.forward_messages(
            entity=to_peer,
            messages=int(message_id),
            from_peer=from_peer,
        )
        return {"status": "success", "message": "Переслано", "result_ids": [getattr(r, "id", None) for r in (result if isinstance(result, list) else [result])]}
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
        peer = await _peer(client, chat_id)
        if unpin:
            await client.unpin_message(peer, int(message_id))
            return {"status": "success", "message": "Откреплено", "message_id": int(message_id)}
        await client.pin_message(peer, int(message_id))
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
        peer = await _peer(client, chat_id)
        if not emoticon:
            await client(SendReactionRequest(peer=peer, msg_id=int(message_id), reaction=[]))
            return {"status": "success", "message": "Реакция снята", "message_id": int(message_id)}
        await client(
            SendReactionRequest(
                peer=peer,
                msg_id=int(message_id),
                reaction=[ReactionEmoji(emoticon=emoticon)],
            )
        )
        return {
            "status": "success",
            "message": "Реакция добавлена",
            "message_id": int(message_id),
            "emoticon": emoticon,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@on_tg_loop
async def get_deleted_messages(self, phone: str) -> dict:
    items = list((self.deleted_messages or {}).get(phone) or [])
    cfg = (self.deleted_settings or {}).get(phone) or {"enabled": False}
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
    cfg = dict((self.deleted_settings or {}).get(phone) or {"enabled": False})
    if enabled is not None:
        cfg["enabled"] = bool(enabled)
    self.deleted_settings[phone] = cfg
    self._save_deleted_settings_disk()
    return {"status": "success", "settings": cfg}
