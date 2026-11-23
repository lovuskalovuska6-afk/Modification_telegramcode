"""Mute-delete, AI auto-reply, extra commands helpers for TelethonManager."""
from typing import Optional, Dict, Any, List
import asyncio
import json
from pathlib import Path

AI_PRESETS = {
    "groq": {
        "base": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_url": "https://console.groq.com/keys",
        "label": "Groq (бесплатно)",
    },
    "openrouter": {
        "base": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.2-3b-instruct:free",
        "key_url": "https://openrouter.ai/keys",
        "label": "OpenRouter (есть бесплатные модели)",
    },
    "openai": {
        "base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_url": "https://platform.openai.com/api-keys",
        "label": "OpenAI",
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


def _ai_disk_path(manager) -> Path:
    base = getattr(manager, "sessions_dir", None) or Path("sessions")
    return Path(base) / "ai_settings.json"


def load_ai_from_disk(manager) -> None:
    path = _ai_disk_path(manager)
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return
        if not hasattr(manager, "ai_settings"):
            manager.ai_settings = {}
        for phone, cfg in data.items():
            if isinstance(cfg, dict):
                base = default_ai()
                base.update(cfg)
                manager.ai_settings[phone] = base
    except Exception:
        pass


def save_ai_to_disk(manager) -> None:
    path = _ai_disk_path(manager)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = getattr(manager, "ai_settings", {}) or {}
        clean = {}
        for phone, cfg in data.items():
            if not isinstance(cfg, dict):
                continue
            clean[phone] = {
                k: v for k, v in cfg.items()
                if k not in ("last_error", "last_error_at")
            }
        path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def set_last_error(manager, phone: str, msg: str) -> None:
    if not hasattr(manager, "ai_settings"):
        manager.ai_settings = {}
    cfg = default_ai()
    cfg.update(manager.ai_settings.get(phone) or {})
    cfg["last_error"] = msg
    manager.ai_settings[phone] = cfg


def clear_last_error(manager, phone: str) -> None:
    ai = getattr(manager, "ai_settings", {}).get(phone)
    if ai and "last_error" in ai:
        ai["last_error"] = ""


async def attach_handlers(manager, phone: str, client) -> None:
    if not hasattr(manager, "_handlers_ready"):
        manager._handlers_ready = set()
    if not getattr(manager, "_ai_disk_loaded", False):
        load_ai_from_disk(manager)
        manager._ai_disk_loaded = True
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

    reply, err = await ai_generate(manager, phone, text)
    if err:
        set_last_error(manager, phone, err)
        return
    if reply:
        clear_last_error(manager, phone)
        try:
            await event.respond(reply)
        except Exception as e:
            set_last_error(manager, phone, f"Не удалось отправить ответ в Telegram: {e}")


async def ai_generate(manager, phone: str, user_text: str):
    ai = getattr(manager, "ai_settings", {}).get(phone) or {}
    api_key = (ai.get("api_key") or "").strip()
    if not api_key:
        return None, (
            "Нет API-ключа. Открой «ИИ автоответ» → вставь ключ → Сохранить. "
            "Бесплатно: Groq → https://console.groq.com/keys"
        )

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
                    "content": (
                        "Ты помощник владельца аккаунта Telegram. "
                        "Отвечай кратко и по-русски от его имени, как живой человек. "
                        "Не пиши, что ты ИИ, если тебя об этом не спросили."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
            "temperature": 0.7,
            "max_tokens": 500,
        }

        async with httpx.AsyncClient(timeout=45.0) as http:
            r = await http.post(f"{base}/chat/completions", headers=headers, json=payload)
            body_text = r.text or ""
            if r.status_code == 401:
                return None, (
                    "Неверный API-ключ (401). Проверь ключ в настройках ИИ. "
                    f"Ключ для {preset.get('label', provider)}: {preset.get('key_url', '')}"
                )
            if r.status_code == 429:
                return None, (
                    "Лимит запросов / квота исчерпана (429). "
                    "Подожди несколько минут или смени ключ/провайдера. "
                    "Groq бесплатный, но с дневным лимитом — https://console.groq.com/keys"
                )
            if r.status_code == 402:
                return None, (
                    "Недостаточно средств / платный лимит (402). "
                    "Для бесплатного: выбери Groq или модель OpenRouter с :free"
                )
            if r.status_code >= 400:
                detail = body_text[:300].replace("\n", " ")
                return None, f"Ошибка API {r.status_code}: {detail}"

            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
            if not content:
                return None, "API вернул пустой ответ. Проверь модель."
            return content.strip(), None
    except Exception as e:
        return None, f"Сбой запроса к ИИ: {type(e).__name__}: {e}"


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
            "ai status — ошибка ИИ / ключ\n"
            "reply текст — ответить от себя\n"
            "info — инфа о чате\n"
            "clear N — удалить свои последние N сообщений"
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
        err = ai.get("last_error") or "нет"
        return {
            "status": "success",
            "message": (
                f"mute={'да' if is_muted else 'нет'}; "
                f"ИИ={'вкл' if ai.get('enabled') else 'выкл'}; "
                f"provider={ai.get('provider') or '-'}; "
                f"ключ={'есть' if (ai.get('api_key') or '').strip() else 'НЕТ'}; "
                f"ошибка={err}"
            ),
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
        return {
            "status": "success",
            "message": f"{u.get('first_name') or ''} @{u.get('username') or '—'} id={u.get('id')}",
        }

    if cmd == "ai":
        mode = (args[0] if args else "").lower()
        if not hasattr(manager, "ai_settings"):
            manager.ai_settings = {}
        cfg = default_ai()
        cfg.update(manager.ai_settings.get(phone) or {})
        if mode in ("on", "1", "true", "вкл"):
            cfg["enabled"] = True
            manager.ai_settings[phone] = cfg
            save_ai_to_disk(manager)
            has_key = bool((cfg.get("api_key") or "").strip())
            msg = "ИИ автоответ включён"
            if not has_key:
                msg += ". ВНИМАНИЕ: нет API-ключа — ответы не будут работать. Добавь ключ в настройках."
            return {"status": "success", "message": msg}
        if mode in ("off", "0", "false", "выкл"):
            cfg["enabled"] = False
            manager.ai_settings[phone] = cfg
            save_ai_to_disk(manager)
            return {"status": "success", "message": "ИИ автоответ выключен"}
        if mode in ("status", "err", "error"):
            err = cfg.get("last_error") or "ошибок нет"
            return {
                "status": "success",
                "message": (
                    f"ИИ={'вкл' if cfg.get('enabled') else 'выкл'}; "
                    f"provider={cfg.get('provider')}; "
                    f"model={cfg.get('model')}; "
                    f"ключ={'есть' if (cfg.get('api_key') or '').strip() else 'НЕТ'}; "
                    f"ошибка={err}"
                ),
            }
        return {
            "status": "success",
            "message": f"ИИ сейчас: {'вкл' if cfg.get('enabled') else 'выкл'}. Используй: ai on | ai off | ai status",
        }

    if cmd == "reply":
        text = " ".join(args).strip()
        if not text:
            return {"status": "error", "message": "Укажи текст: reply привет"}
        return await send_message(phone, chat_id, text)

    if cmd == "info":
        is_muted = chat_id in (manager.muted.get(phone) or set())
        return {"status": "success", "message": f"chat_id={chat_id}; muted={'да' if is_muted else 'нет'}"}

    if cmd == "clear":
        try:
            n = int(args[0]) if args else 5
        except ValueError:
            n = 5
        n = max(1, min(n, 50))
        return {"status": "success", "message": f"clear {n}: используй в реальном клиенте (заглушка лимита)"}

    return None
