# Modified Telegram

Улучшенный клиент Telegram с дополнительными возможностями.

## Возможности (в разработке)

- Вход по номеру телефона или QR-коду
- Левое меню настроек
- Система команд
- ИИ автоответ
- Редактор пользовательских команд (JS / Python / Lua)
- Режим скрытности
- Темы оформления

## Быстрый старт

### 1. Получи API_ID и API_HASH

Зайди на [https://my.telegram.org/apps](https://my.telegram.org/apps) и создай приложение.

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Отредактируй .env — вставь свой API_ID и API_HASH

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Открой http://localhost:5173

## API авторизации

- `POST /api/auth/send-code` — отправить код
- `POST /api/auth/sign-in` — войти по коду (+ 2FA)
- `POST /api/auth/logout` — выйти
- `POST /api/auth/me` — информация о пользователе

## Структура

```
backend/app/
  api/auth.py              # эндпоинты авторизации
  client/telethon_manager.py  # работа с Telethon
  features/                # будущие фичи
frontend/src/              # React интерфейс
```
