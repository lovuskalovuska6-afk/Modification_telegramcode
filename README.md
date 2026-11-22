# TelegramCode

Улучшенный клиент Telegram.

## Сейчас включена ЗАГЛУШКА (demo-режим)

Вход и регистрация работают **без** API_ID / API_HASH.

### Как тестировать

1. Запусти backend и frontend
2. Нажми «Начать»
3. Выбери «Я не имею аккаунта» или «Войти по номеру»
4. Введи любой номер (например `+79991234567`)
5. Код: **`12345`** (или любой)
6. Если регистрация — укажи имя
7. Попадёшь внутрь клиента

### Запуск

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (в другом терминале)
cd frontend
npm install
npm run dev
```

Открой http://localhost:5173

### Переключение на реальный Telegram

В файле `backend/app/client/telethon_manager.py`:

```python
MOCK = False
```

И добавь в `backend/.env`:

```
API_ID=твой_id
API_HASH=твой_hash
```

Ключи берутся на https://my.telegram.org/apps (только для сервера, пользователи их не видят).

## Возможности

- Экран TelegramCode → Начать
- Вход по номеру / QR
- Регистрация нового аккаунта
- Левое меню
- ИИ автоответ, команды, скрытность, темы
