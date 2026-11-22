# TelegramCode

Улучшенный веб-клиент Telegram.

**Стек:** React (Vite) + FastAPI + Telethon  
**Деплой:** Render (frontend static + backend Python)

## Что есть сейчас

- Экран **TelegramCode** → «Начать»
- Вход по номеру телефона (реальный Telegram через Telethon)
- Регистрация нового аккаунта (имя / фамилия, если номера ещё нет)
- Поддержка 2FA
- Заготовка входа по QR
- Выезжающее меню ☰ со всеми разделами:
  - Настройки
  - Чаты (тема чатов)
  - Команды
  - ИИ автоответ (вкл/выкл)
  - Настройки Telegram
  - Изменить аккаунт / выход
  - Свои команды (редактор JS / Python / Lua)
  - Скрытность
  - Тема оформления (тёмная / светлая)

## Режимы backend

Управляется переменными окружения на сервере:

| Переменная | Значение |
|------------|----------|
| `API_ID` | api_id приложения Telegram |
| `API_HASH` | api_hash приложения |
| `MOCK` | `false` = реальный вход, `true` = демо-заглушка |

Если `API_ID` и `API_HASH` заданы и `MOCK=false` — работает **реальный** вход в Telegram.  
Ключи брать на https://my.telegram.org/apps (только на сервере, не в git).

Проверка: `GET /health` → `"mock": false`, `"has_api_keys": true`.

## Локальный запуск

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# .env
# API_ID=...
# API_HASH=...
# MOCK=false

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Открой http://localhost:5173  

Для продакшена задай `VITE_API_URL` (URL backend без хвоста `/api`).

## API авторизации

- `POST /api/auth/send-code` — `{ "phone": "+7..." }`
- `POST /api/auth/sign-in` — код, опционально password / first_name / last_name
- `POST /api/auth/logout`
- `POST /api/auth/me`
- `GET /health` — статус и режим

## Структура

```
backend/app/
  api/auth.py
  client/telethon_manager.py
  config.py
  main.py
frontend/src/
  App.jsx
  App.css
render.yaml
```

## В разработке

- Список чатов и сообщения
- Командная строка `| / |` (spam, mute, unmute)
- ИИ (свой API + бесплатные пресеты)
- Реальный stealth / QR login
- Постоянные сессии на диске Render
