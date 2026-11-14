# TelegramCode

Улучшенный клиент Telegram.

## Возможности

- Вход по номеру / QR
- Регистрация нового аккаунта через сайт
- Левое меню настроек
- ИИ автоответ
- Редактор команд (JS / Python / Lua)
- Режим скрытности
- Тёмная и светлая тема

## Запуск

### 1. API ключи Telegram

Зайди на https://my.telegram.org/apps и создай приложение.
Скопируй `api_id` и `api_hash`.

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Впиши API_ID и API_HASH в .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Открой http://localhost:5173

## Поток авторизации

1. Экран «TelegramCode» → Начать
2. Выбор: войти по номеру / QR / зарегистрироваться
3. Номер → код → (если новый номер) имя + фамилия
4. Готово

## API

- `POST /api/auth/send-code`
- `POST /api/auth/sign-in`
- `POST /api/auth/logout`
- `POST /api/auth/me`
