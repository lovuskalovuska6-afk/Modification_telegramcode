"""Mute-delete, AI auto-reply, extra commands helpers for TelethonManager."""
from typing import Optional, Dict, Any, List
import asyncio

AI_PRESETS = {
    "groq": {
        "base": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
    },
    "openrouter": {
        "base": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
    },
    "openai": {
        "base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
}


def default_ai() -> dict:
    return {
        "enabled": False,
        "provider": "groq",
        "api_key": "",
        "model": "llama-3.3-70b-versatile",
        "api_base": "https://api.groq.com/openai/v1",
    }


async def attach_handlers(manager, phone: str, client) -> None:
    if not hasattr(manager, "_handlers_ready"):
        manager._handlers_ready = set()
    if phone in manager._handlers_ready:
        return
    from telethon import events

    @client.on(events.NewMessage(incoming=True))
    async def _on_incoming(event, _phone=phone):
        try:
            await handle_incoming(manager, _phone, event)
        except Exception:
            pass

    manager._handlers_ready.add(phone)


async def handle_incoming(manager, phone: str, event) -> None:
    chat_id = event.chat_id
    muted = getattr(manager, "muted", {}).get(phone) or set()
    if chat_id in muted:
        try:
            await event.delete()
        except Exception:
            try:
                await event.client.delete_messages(chat_id, [event.id], revoke=True)
            except Exception:
                pass
        return

    ai = getattr(manager, "ai_settings", {}).get(phone) or {}
    if not ai.get("enabled"):
        return
    if not event.is_private:
        return
    if event.out:
        return
    text = (event.raw_text or "").strip()
    if not text:
        return
    reply = await ai_generate(manager, phone, text)
    if reply:
        try:
            await event.respond(reply)
        except Exception:
            pass


async def ai_generate(manager, phone: str, user_text: str) -> Optional[str]:
    ai = getattr(manager, "ai_settings", {}).get(phone) or {}
    api_key = (ai.get("api_key") or "").strip()
    if not api_key:
        return None
    provider = (ai.get("provider") or "groq").lower()
    model = (ai.get("model") or "").strip()
    api_base = (ai.get("api_base") or "").strip().rstrip("/")
    preset = AI_PRESETS.get(provider, AI_PRESETS["openai"])
    base = api_base or preset["base"]
    model = model or preset["model"]
    try:
        import httpx
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://telegramcode-web-76rb.onrender.com"
            headers["X-Title"] = "TelegramCode"
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты помощник владельца аккаунта Telegram. Отвечай кратко и по-русски от его имени, как живой человек.",
                },
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.7,
            "max_tokens": 500,
        }
        async with httpx.AsyncClient(timeout=45.0) as http:
            r = await http.post(f"{base}/chat/completions", headers=headers, json=payload)
            if r.status_code >= 400:
                return None
            data = r.json()
            return (data.get("choices") or [{}])[0].get("message", {}).get("content") or None
    except Exception:
        return None


async def run_extra_command(manager, phone, chat_id, cmd, args, MOCK, send_message, get_me):
    if cmd in ("help", "commands", "cmds"):
        text = (
            "Команды:\n"
            "help — список\n"
            "spam слово N — повторить (макс 20)\n"
            "mute — удалять все входящие в этом чате\n"
            "unmute — снять mute\n"
            "status — mute и ИИ\n"
            "id — id чата\n"
            "ping — проверка\n"
            "me — кто я\n"
            "ai on|off — автоответ ИИ\n"
            "reply текст — ответить от себя"
        )
        return {"status": "success", "message": text}

    if cmd == "mute":
        manager.muted.setdefault(phone, set()).add(chat_id)
        return {"status": "success", "message": "Mute включён: все входящие в этом чате будут удаляться"}

    if cmd == "unmute":
        manager.muted.setdefault(phone, set()).discard(chat_id)
        return {"status": "success", "message": f"Mute выключен для чата {chat_id}"}

    if cmd == "status":
        is_muted = chat_id in (manager.muted.get(phone) or set())
        ai = getattr(manager, "ai_settings", {}).get(phone) or {}
        return {
            "status": "success",
            "message": f"mute={'да' if is_muted else 'нет'}; ИИ={'вкл' if ai.get('enabled') else 'выкл'}; provider={ai.get('provider') or '-'}",
        }

    if cmd == "id":
        return {"status": "success", "message": f"chat_id={chat_id}"}

    if cmd == "ping":
        return {"status": "success", "message": "pong"}

    if cmd == "me":
        me = await get_me(phone)
        if me.get("status") != "success":
            return me
        u = me.get("user") or {}
        return {"status": "success", "message": f"{u.get('first_name') or ''} @{u.get('username') or '—'} id={u.get('id')}"}

    if cmd == "ai":
        mode = (args[0] if args else "").lower()
        if not hasattr(manager, "ai_settings"):
            manager.ai_settings = {}
        cfg = default_ai()
        cfg.update(manager.ai_settings.get(phone) or {})
        if mode in ("on", "1", "true", "вкл"):
            cfg["enabled"] = True
            manager.ai_settings[phone] = cfg
            return {"status": "success", "message": "ИИ автоответ включён"}
        if mode in ("off", "0", "false", "выкл"):
            cfg["enabled"] = False
            manager.ai_settings[phone] = cfg
            return {"status": "success", "message": "ИИ автоответ выключен"}
        return {"status": "success", "message": f"ИИ сейчас: {'вкл' if cfg.get('enabled') else 'выкл'}. Используй: ai on | ai off"}

    if cmd == "reply":
        text = " ".join(args).strip()
        if not text:
            return {"status": "error", "message": "Укажи текст: reply привет"}
        return await send_message(phone, chat_id, text)

    return None
