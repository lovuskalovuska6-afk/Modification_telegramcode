import React, { useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/api'

function App() {
  // screen: landing | auth-choice | phone | code | register | 2fa | qr | app
  const [screen, setScreen] = useState('landing')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password2fa, setPassword2fa] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [user, setUser] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isRegister, setIsRegister] = useState(false)

  const [activeMenu, setActiveMenu] = useState('chats')
  const [theme, setTheme] = useState('dark')

  const handleSendCode = async () => {
    if (phone.trim().length < 8) {
      setError('Введите корректный номер')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_URL}/auth/send-code`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      })
      const data = await res.json()
      if (data.status === 'code_sent' || data.status === 'already_authorized') {
        if (data.status === 'already_authorized') {
          setUser(data.user || null)
          setScreen('app')
        } else {
          setScreen('code')
        }
      } else {
        setError(data.message || data.detail || 'Ошибка отправки кода')
      }
    } catch (e) {
      setError('Не удалось связаться с сервером. Запущен ли backend?')
    }
    setLoading(false)
  }

  const handleSignIn = async () => {
    setLoading(true)
    setError('')
    try {
      const body = {
        phone,
        code,
        password: password2fa || null,
      }
      if (isRegister) {
        body.first_name = firstName
        body.last_name = lastName || null
      }

      const res = await fetch(`${API_URL}/auth/sign-in`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const data = await res.json()

      if (data.status === 'success') {
        setUser(data.user)
        setScreen('app')
      } else if (data.status === '2fa_required') {
        setScreen('2fa')
      } else if (data.status === 'need_signup') {
        // Аккаунт новый — показываем форму регистрации
        setIsRegister(true)
        setScreen('register')
      } else {
        setError(data.message || data.detail || 'Ошибка')
      }
    } catch (e) {
      setError('Ошибка соединения с сервером')
    }
    setLoading(false)
  }

  const handleRegister = async () => {
    if (!firstName.trim()) {
      setError('Введите имя')
      return
    }
    setIsRegister(true)
    await handleSignIn()
  }

  const menuItems = [
    { id: 'settings', label: 'Настройки' },
    { id: 'chats', label: 'Чаты' },
    { id: 'commands', label: 'Команды' },
    { id: 'ai', label: 'ИИ автоответ' },
    { id: 'tg-settings', label: 'Настройки Telegram' },
    { id: 'account', label: 'Изменить аккаунт' },
    { id: 'custom-command', label: 'Добавить свою команду' },
    { id: 'stealth', label: 'Скрытность' },
    { id: 'theme', label: 'Тема оформления' },
  ]

  const renderContent = () => {
    switch (activeMenu) {
      case 'settings':
        return <div className="panel"><h2>Настройки</h2><p>Общие настройки клиента</p></div>
      case 'chats':
        return (
          <div className="panel">
            <h2>Чаты</h2>
            {user && (
              <p>Вы вошли как: <b>{user.first_name} {user.last_name || ''}</b> {user.username ? `(@${user.username})` : ''}</p>
            )}
            <p>Здесь будет список чатов</p>
          </div>
        )
      case 'commands':
        return <div className="panel"><h2>Команды</h2><p>Управление командами и настройка ИИ</p></div>
      case 'ai':
        return (
          <div className="panel">
            <h2>ИИ автоответ</h2>
            <label className="toggle">
              <input type="checkbox" />
              <span>Включить автоответ</span>
            </label>
          </div>
        )
      case 'tg-settings':
        return <div className="panel"><h2>Настройки Telegram</h2><p>Настройки самого Telegram</p></div>
      case 'account':
        return (
          <div className="panel">
            <h2>Аккаунт</h2>
            {user && (
              <div>
                <p>ID: {user.id}</p>
                <p>Имя: {user.first_name} {user.last_name || ''}</p>
                <p>Username: {user.username ? `@${user.username}` : 'нет'}</p>
                <p>Телефон: {user.phone}</p>
              </div>
            )}
            <button
              className="danger-btn"
              onClick={() => {
                setScreen('landing')
                setUser(null)
                setPhone('')
                setCode('')
                setPassword2fa('')
                setFirstName('')
                setLastName('')
                setIsRegister(false)
              }}
            >
              Выйти
            </button>
          </div>
        )
      case 'custom-command':
        return (
          <div className="panel">
            <h2>Добавить свою команду</h2>
            <p>Редактор скриптов (JavaScript / Python / Lua)</p>
            <select defaultValue="python">
              <option value="javascript">JavaScript</option>
              <option value="python">Python</option>
              <option value="lua">Lua</option>
            </select>
            <textarea placeholder="// Ваш код здесь..." rows={12}></textarea>
          </div>
        )
      case 'stealth':
        return (
          <div className="panel">
            <h2>Скрытность</h2>
            <label className="toggle">
              <input type="checkbox" />
              <span>Скрывать онлайн-статус</span>
            </label>
          </div>
        )
      case 'theme':
        return (
          <div className="panel">
            <h2>Тема оформления</h2>
            <div className="theme-buttons">
              <button className={theme === 'dark' ? 'active' : ''} onClick={() => setTheme('dark')}>Тёмная</button>
              <button className={theme === 'light' ? 'active' : ''} onClick={() => setTheme('light')}>Светлая</button>
            </div>
          </div>
        )
      default:
        return <div className="panel"><p>Выберите раздел</p></div>
    }
  }

  // ========== LANDING ==========
  if (screen === 'landing') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="landing">
          <div className="landing-content">
            <h1 className="logo">TelegramCode</h1>
            <button className="start-btn" onClick={() => setScreen('auth-choice')}>
              Начать
            </button>
          </div>
          <div className="login-footer">
            | модифицированный телеграмм /code |
          </div>
        </div>
      </div>
    )
  }

  // ========== AUTH CHOICE ==========
  if (screen === 'auth-choice') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>TelegramCode</h1>
            <p>Выберите способ входа</p>

            <button onClick={() => { setIsRegister(false); setScreen('phone'); }}>
              Войти по номеру телефона
            </button>

            <button className="secondary" onClick={() => setScreen('qr')}>
              Войти по QR-коду
            </button>

            <button
              className="register-link"
              onClick={() => { setIsRegister(true); setScreen('phone'); }}
            >
              Я не имею аккаунта (зарегистрироваться)
            </button>
          </div>
          <div className="login-footer">
            | модифицированный телеграмм /code |
          </div>
        </div>
      </div>
    )
  }

  // ========== PHONE ==========
  if (screen === 'phone') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>{isRegister ? 'Регистрация' : 'Вход'}</h1>
            {error && <div className="error">{error}</div>}
            <p>Введите номер телефона</p>
            <input
              type="tel"
              placeholder="+7 999 123-45-67"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="login-input"
            />
            <button onClick={handleSendCode} disabled={loading}>
              {loading ? 'Отправка...' : 'Получить код'}
            </button>
            <button className="secondary" onClick={() => setScreen('auth-choice')}>
              Назад
            </button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  // ========== CODE ==========
  if (screen === 'code') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Код подтверждения</h1>
            {error && <div className="error">{error}</div>}
            <p>Код отправлен на {phone}</p>
            <input
              type="text"
              placeholder="Код из Telegram / SMS"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              className="login-input"
            />
            <button onClick={handleSignIn} disabled={loading}>
              {loading ? 'Проверка...' : (isRegister ? 'Далее' : 'Войти')}
            </button>
            <button className="secondary" onClick={() => setScreen('phone')}>
              Назад
            </button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  // ========== REGISTER (имя) ==========
  if (screen === 'register') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Создание аккаунта</h1>
            {error && <div className="error">{error}</div>}
            <p>Как вас зовут?</p>
            <input
              type="text"
              placeholder="Имя"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              className="login-input"
            />
            <input
              type="text"
              placeholder="Фамилия (необязательно)"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              className="login-input"
            />
            <button onClick={handleRegister} disabled={loading}>
              {loading ? 'Создание...' : 'Зарегистрироваться'}
            </button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  // ========== 2FA ==========
  if (screen === '2fa') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Двухфакторная аутентификация</h1>
            {error && <div className="error">{error}</div>}
            <p>Введите пароль 2FA</p>
            <input
              type="password"
              placeholder="Пароль"
              value={password2fa}
              onChange={(e) => setPassword2fa(e.target.value)}
              className="login-input"
            />
            <button onClick={handleSignIn} disabled={loading}>
              {loading ? 'Проверка...' : 'Подтвердить'}
            </button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  // ========== QR ==========
  if (screen === 'qr') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Вход по QR</h1>
            <p>Отсканируйте QR-код в официальном приложении Telegram</p>
            <div className="qr-placeholder">[ QR-код появится здесь ]</div>
            <button className="secondary" onClick={() => setScreen('auth-choice')}>
              Назад
            </button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  // ========== MAIN APP ==========
  return (
    <div className={`app theme-${theme}`}>
      <div className="main-layout">
        <aside className="sidebar">
          <div className="sidebar-header">☰ TelegramCode</div>
          <nav className="sidebar-menu">
            {menuItems.map((item) => (
              <div
                key={item.id}
                className={`menu-item ${activeMenu === item.id ? 'active' : ''}`}
                onClick={() => setActiveMenu(item.id)}
              >
                {item.label}
              </div>
            ))}
          </nav>
        </aside>
        <main className="content-area">
          {renderContent()}
        </main>
      </div>
    </div>
  )
}

export default App
