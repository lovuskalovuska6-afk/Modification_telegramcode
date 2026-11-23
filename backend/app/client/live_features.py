"""Mute-delete, AI auto-reply, extra commands helpers for TelethonManager."""
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import asyncio
import json
import os

AI_PRESETS = {
    "groq": {
        "base": "https://api.groq.com/openai/v1",
        # llama-3.3-70b-versatile больше не бесплатная (с ~авг 2026)
        "model": "openai/gpt-oss-20b",
        "key_url": "https://console.groq.com/keys",
        "label": "Groq (бесплатно)",
    },
    "openrouter": {
        "base": "https://openrouter.ai/api/v1",
        "model": "meta-llama/llama-3.2-3b-instruct:free",
        "key_url": "https://openrouter.ai/keys",
        "label": "OpenRouter (есть :free)",
    },
    "openai": {
        "base": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_url": "https://platform.openai.com/api-keys",
        "label": "OpenAI",
    },
}

# Актуальные бесплатные модели (ноябрь 2026)
FREE_MODELS = {
    "groq": [
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "qwen/qwen3.8-27b",
        "allam-2-7b",
    ],
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


def _ai_disk_path(sessions_dir: Path) -> Path:
    return Path(sessions_dir) / "ai_settings.json"


def load_ai_from_disk(sessions_dir: Path) -> Dict[str, dict]:
    """Загружает все AI-настройки с диска (после рестарта Render)."""
    path = _ai_disk_path(sessions_dir)
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # нормализуем
                out = {}
                for phone, cfg in data.items():
                    if isinstance(cfg, dict):
                        base = default_ai()
                        base.update(cfg)
                        out[str(phone)] = base
                return out
    except Exception:
        pass
    return {}


def save_ai_to_disk(sessions_dir: Path, ai_settings: Dict[str, dict]) -> None:
    """Сохраняет AI-настройки на диск (переживает рестарт)."""
    path = _ai_disk_path(sessions_dir)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # не храним last_error на диске как постоянное — но можно
        clean = {}
        for phone, cfg in (ai_settings or {}).items():
            if not isinstance(cfg, dict):
                continue
            c = {
                "enabled": bool(cfg.get("enabled")),
                "provider": cfg.get("provider") or "groq",
                "api_key": cfg.get("api_key") or "",
                "model": cfg.get("model") or "",
                "api_base": cfg.get("api_base") or "",
            }
            clean[str(phone)] = c
        path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def set_last_error(manager, phone: str, err: str) -> None:
    if not hasattr(manager, "ai_settings"):
        manager.ai_settings = {}
    cfg = default_ai()
    cfg.update(manager.ai_settings.get(phone) or {})
    cfg["last_error"] = (err or "")[:500]
    manager.ai_settings[phone] = cfg


def _norm_chat_id(cid) -> int:
    try:
        return int(cid)
    except Exception:
        return cid


def _muted_set(manager, phone: str) -> set:
    s = getattr(manager, "muted", {}).get(phone) or set()
    return {_norm_chat_id(x) for x in s}


def _is_muted(manager, phone: str, chat_id) -> bool:
    return _norm_chat_id(chat_id) in _muted_set(manager, phone)


def save_mute_to_disk(sessions_dir: Path, muted: Dict[str, set]) -> None:
    path = Path(sessions_dir) / "muted.json"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = {str(p): [int(x) for x in s] for p, s in (muted or {}).items()}
        path.write_text(json.dumps(clean, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def load_mute_from_disk(sessions_dir: Path) -> Dict[str, set]:
    path = Path(sessions_dir) / "muted.json"
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            out = {}
            for p, ids in (data or {}).items():
                out[str(p)] = {int(x) for x in ids}
            return out
    except Exception:
        pass
    return {}


async def attach_handlers(manager, phone: str, client) -> None:
    """Вешаем хендлер на client. После reconnect клиент новый — флаг на объекте сбросится."""
    if client is None:
        return
    if getattr(client, "_tc_incoming_handler", False):
        return
    from telethon import events

    @client.on(events.NewMessage(incoming=True))
    async def _on_incoming(event, _phone=phone):
        try:
            await handle_incoming(manager, _phone, event)
        except Exception as e:
            try:
                set_last_error(manager, _phone, f"handler: {type(e).__name__}: {e}")
            except Exception:
                pass

    client._tc_incoming_handler = True
    if not hasattr(manager, "_handlers_ready"):
        manager._handlers_ready = set()
    manager._handlers_ready.add(phone)


async def handle_incoming(manager, phone: str, event) -> None:
    """Mute: удаляет любое входящее. AI: отвечает на текст в ЛС с историей и стилем аккаунта."""
    chat_id = _norm_chat_id(event.chat_id)

    # --- MUTE ---
    if _is_muted(manager, phone, chat_id):
        try:
            await event.delete()
        except Exception:
            pass
        try:
            await event.client.delete_messages(event.chat_id, [event.id], revoke=True)
        except Exception:
            pass
        return

    # --- AI (только личка, входящий текст) ---
    ai = getattr(manager, "ai_settings", {}).get(phone) or {}
    if not ai.get("enabled"):
        return

    is_private = False
    try:
        is_private = bool(event.is_private)
    except Exception:
        is_private = False
    if not is_private and chat_id > 0:
        # user peer id положительный — считаем личкой
        is_private = True
    if not is_private:
        return
    if getattr(event, "out", False):
        return
    text = (event.raw_text or "").strip()
    if not text:
        return

    history = []
    me_info = None
    try:
        client = event.client
        try:
            me = await client.get_me()
            me_info = {
                "first_name": getattr(me, "first_name", "") or "",
                "last_name": getattr(me, "last_name", "") or "",
                "username": getattr(me, "username", "") or "",
                "phone": getattr(me, "phone", "") or "",
                "id": getattr(me, "id", None),
            }
        except Exception:
            me_info = None
        msgs = await client.get_messages(event.chat_id, limit=12)
        for m in reversed(list(msgs)[1:] if msgs else []):
            t = (m.raw_text or "").strip()
            if not t:
                continue
            role = "assistant" if m.out else "user"
            history.append({"role": role, "content": t[:500]})
        history = history[-10:]
    except Exception:
        history = []

    reply, err = await ai_generate(manager, phone, text, history=history, me_info=me_info)
    if err:
        set_last_error(manager, phone, err)
    if reply:
        try:
            await event.respond(reply)
            set_last_error(manager, phone, "")
        except Exception as e:
            set_last_error(manager, phone, f"Не удалось отправить ответ: {e}")


# Устаревшие модели → актуальная замена (Groq 2026)
DEPRECATED_MODELS = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-20b",
    "llama3-70b-8192": "openai/gpt-oss-20b",
    "llama-3.1-70b-versatile": "openai/gpt-oss-20b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "gemma2-9b-it": "openai/gpt-oss-20b",
    "mixtral-8x7b-32768": "openai/gpt-oss-20b",
    "llama3-8b-8192": "openai/gpt-oss-20b",
}


def normalize_model(provider: str, model: str) -> str:
    m = (model or "").strip()
    if not m:
        preset = AI_PRESETS.get(provider, AI_PRESETS["groq"])
        return preset["model"]
    if m in DEPRECATED_MODELS:
        return DEPRECATED_MODELS[m]
    return m


async def ai_generate(
    manager,
    phone: str,
    user_text: str,
    history: Optional[List[dict]] = None,
    me_info: Optional[dict] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Возвращает (текст_ответа, ошибка). Учитывает историю и личность аккаунта."""
    ai = getattr(manager, "ai_settings", {}).get(phone) or {}
    api_key = (ai.get("api_key") or "").strip()
    if not api_key:
        return None, "Нет API-ключа. Вставь ключ в разделе «ИИ автоответ» и сохрани."

    provider = (ai.get("provider") or "groq").lower()
    model = (ai.get("model") or "").strip()
    api_base = (ai.get("api_base") or "").strip().rstrip("/")
    preset = AI_PRESETS.get(provider, AI_PRESETS["openai"])
    base = api_base or preset["base"]
    old_model = model
    model = normalize_model(provider, model or preset["model"])
    if old_model != model and old_model in DEPRECATED_MODELS:
        try:
            cfg = dict(ai)
            cfg["model"] = model
            manager.ai_settings[phone] = cfg
            sd = getattr(manager, "sessions_dir", None)
            if sd:
                save_ai_to_disk(sd, manager.ai_settings)
        except Exception:
            pass

    # личность аккаунта
    me = me_info or {}
    name_parts = [me.get("first_name") or "", me.get("last_name") or ""]
    display_name = " ".join(p for p in name_parts if p).strip() or "владелец аккаунта"
    uname = me.get("username") or ""
    system_content = (
        f"Ты пишешь от лица человека: {display_name}"
        + (f" (@{uname})" if uname else "")
        + ". Это его личный Telegram-аккаунт.\n"
        "Пиши точь-в-точь как он: коротко, по-человечески, на русском, "
        "в том же тоне, что и в истории переписки ниже.\n"
        "Не упоминай, что ты ИИ, бот или автоответчик. "
        "Не извиняйся за задержку без причины. Не используй канцелярит."
    )

    messages = [{"role": "system", "content": system_content}]
    if history:
        for h in history:
            role = h.get("role") or "user"
            content = (h.get("content") or "").strip()
            if content and role in ("user", "assistant", "system"):
                messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_text})

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
            "messages": messages,
            "temperature": 0.75,
            "max_tokens": 500,
        }
        async with httpx.AsyncClient(timeout=45.0) as http:
            r = await http.post(f"{base}/chat/completions", headers=headers, json=payload)
            body_text = r.text[:800] if r.text else ""
            if r.status_code == 401:
                return None, "401: Неверный API-ключ. Проверь ключ на сайте провайдера и сохрани заново."
            if r.status_code == 402:
                return None, "402: Нет средств / лимит оплаты. Для бесплатного: Groq или OpenRouter модели с :free."
            if r.status_code == 429:
                return None, (
                    "429: Лимит запросов. Подожди 1–2 мин или смени модель. "
                    "Groq: console.groq.com — смотри rate limits. "
                    "OpenRouter: используй модели с суффиксом :free."
                )
            if r.status_code == 404:
                return None, (
                    f"404: модель «{model}» недоступна на {provider}. "
                    "В разделе ИИ выбери бесплатную модель из списка "
                    "(например openai/gpt-oss-20b для Groq) и нажми Сохранить."
                )
            if r.status_code >= 400:
                hint = ""
                try:
                    j = r.json()
                    hint = (j.get("error") or {}).get("message") or j.get("message") or body_text
                except Exception:
                    hint = body_text
                return None, f"Ошибка API {r.status_code}: {hint[:300]}"
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content")
            if not content:
                return None, "Пустой ответ от модели. Попробуй другую модель."
            return content.strip(), None
    except Exception as e:
        return None, f"Сеть/ошибка запроса: {type(e).__name__}: {e}"


async def run_extra_command(manager, phone, chat_id, cmd, args, MOCK, send_message, get_me):
    if cmd in ("help", "commands", "cmds"):
        text = (
            "Команды TelegramCode:\n"
            "help — этот список\n"
            "spam слово N — повторить (макс 20)\n"
            "mute — удалять ВСЕ входящие в этом чате\n"
            "unmute — снять mute\n"
            "status — mute, ИИ и последняя ошибка\n"
            "id — id чата\n"
            "ping — проверка\n"
            "me — кто я\n"
            "ai on|off — автоответ ИИ\n"
            "ai test — проверить ИИ (отправит тестовый запрос)\n"
            "reply текст — ответить от себя\n"
            "info — инфа о чате\n"
            "clear N — удалить свои последние N сообщений"
        )
        return {"status": "success", "message": text}

    if cmd == "mute":
        cid = _norm_chat_id(chat_id)
        if not cid:
            return {"status": "error", "message": "Mute только в реальном чате (открой чат и напиши mute там)"}
        manager.muted.setdefault(phone, set()).add(cid)
        try:
            sd = getattr(manager, "sessions_dir", None)
            if sd:
                save_mute_to_disk(sd, manager.muted)
        except Exception:
            pass
        return {
            "status": "success",
            "message": f"Mute включён для чата {cid}: все входящие будут удаляться",
            "muted": True,
            "chat_id": cid,
        }

    if cmd == "unmute":
        cid = _norm_chat_id(chat_id)
        manager.muted.setdefault(phone, set()).discard(cid)
        try:
            sd = getattr(manager, "sessions_dir", None)
            if sd:
                save_mute_to_disk(sd, manager.muted)
        except Exception:
            pass
        return {
            "status": "success",
            "message": f"Mute выключен для чата {cid}",
            "muted": False,
            "chat_id": cid,
        }

    if cmd == "status":
        is_muted = _is_muted(manager, phone, chat_id)
        ai = getattr(manager, "ai_settings", {}).get(phone) or {}
        err = (ai.get("last_error") or "").strip()
        key = (ai.get("api_key") or "").strip()
        key_ok = "да" if key else "нет"
        msg = (
            f"mute={'да' if is_muted else 'нет'}\n"
            f"ИИ={'вкл' if ai.get('enabled') else 'выкл'}\n"
            f"provider={ai.get('provider') or '-'}\n"
            f"model={ai.get('model') or '-'}\n"
            f"ключ={'есть' if key else 'НЕТ'}"
        )
        if err:
            msg += f"\n\n⚠ Последняя ошибка ИИ:\n{err}"
        return {"status": "success", "message": msg}

    if cmd == "id":
        return {"status": "success", "message": f"chat_id={chat_id}"}

    if cmd == "ping":
        return {"status": "success", "message": "pong ✓"}

    if cmd in ("me", "whoami"):
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

        # ai test — реальный запрос к модели, результат в чат
        if mode == "test":
            prompt = " ".join(args[1:]).strip() or "Скажи коротко: привет, я работаю"
            reply, err = await ai_generate(manager, phone, prompt)
            if err:
                set_last_error(manager, phone, err)
                return {"status": "error", "message": f"ИИ ошибка:\n{err}"}
            set_last_error(manager, phone, "")
            return {
                "status": "success",
                "message": f"ИИ ответ:\n{reply}",
            }

        if mode in ("on", "1", "true", "вкл"):
            cfg["enabled"] = True
            manager.ai_settings[phone] = cfg
            try:
                sd = getattr(manager, "sessions_dir", None)
                if sd:
                    save_ai_to_disk(sd, manager.ai_settings)
            except Exception:
                pass
            return {"status": "success", "message": "ИИ автоответ включён (только личные сообщения)"}
        if mode in ("off", "0", "false", "выкл"):
            cfg["enabled"] = False
            manager.ai_settings[phone] = cfg
            try:
                sd = getattr(manager, "sessions_dir", None)
                if sd:
                    save_ai_to_disk(sd, manager.ai_settings)
            except Exception:
                pass
            return {"status": "success", "message": "ИИ автоответ выключен"}
        return {
            "status": "success",
            "message": (
                f"ИИ сейчас: {'вкл' if cfg.get('enabled') else 'выкл'}\n"
                f"provider={cfg.get('provider')} model={cfg.get('model')}\n"
                "Команды: ai on | ai off | ai test"
            ),
        }

    if cmd == "reply":
        text = " ".join(args).strip()
        if not text:
            return {"status": "error", "message": "Укажи текст: reply привет"}
        return await send_message(phone, chat_id, text)

    if cmd == "info":
        is_muted = chat_id in (manager.muted.get(phone) or set())
        return {"status": "success", "message": f"chat_id={chat_id}; muted={'да' if is_muted else 'нет'}"}

    return None
