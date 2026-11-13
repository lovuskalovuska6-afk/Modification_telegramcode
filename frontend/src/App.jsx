import React, { useState } from 'react'
import './App.css'

const API_URL = 'http://localhost:8000/api'

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [loginStep, setLoginStep] = useState('phone') // phone | code | 2fa | qr
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password2fa, setPassword2fa] = useState('')
  const [user, setUser] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

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
          setIsLoggedIn(true)
        } else {
          setLoginStep('code')
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
      const res = await fetch(`${API_URL}/auth/sign-in`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone,
          code,
          password: password2fa || null,
        }),
      })
      const data = await res.json()

      if (data.status === 'success') {
        setUser(data.user)
        setIsLoggedIn(true)
      } else if (data.status === '2fa_required') {
        setLoginStep('2fa')
      } else {
        setError(data.message || data.detail || 'Ошибка входа')
      }
    } catch (e) {
      setError('Ошибка соединения с сервером')
    }
    setLoading(false)
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
              <p>Вы вошли как: <b>{user.first_name} {user.last_name || ''}</b> (@{user.username || 'нет'})</p>
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
                <p>Username: @{user.username || 'нет'}</p>
                <p>Телефон: {user.phone}</p>
              </div>
            )}
            <button
              style={{ marginTop: 16 }}
              onClick={() => {
                setIsLoggedIn(false)
                setUser(null)
                setLoginStep('phone')
                setCode('')
                setPassword2fa('')
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

  return (
    <div className={`app theme-${theme}`}>
      {!isLoggedIn ? (
        <div className="login-screen">
          <div className="login-box">
            <h1>Modified Telegram</h1>

            {error && <div className="error">{error}</div>}

            {loginStep === 'phone' && (
              <>
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
                <button className="secondary" onClick={() => setLoginStep('qr')}>
                  Войти по QR-коду
                </button>
              </>
            )}

            {loginStep === 'code' && (
              <>
                <p>Код отправлен на {phone}</p>
                <input
                  type="text"
                  placeholder="Код из Telegram / SMS"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  className="login-input"
                />
                <button onClick={handleSignIn} disabled={loading}>
                  {loading ? 'Проверка...' : 'Войти'}
                </button>
                <button className="secondary" onClick={() => setLoginStep('phone')}>
                  Назад
                </button>
              </>
            )}

            {loginStep === '2fa' && (
              <>
                <p>Введите пароль двухфакторной аутентификации</p>
                <input
                  type="password"
                  placeholder="Пароль 2FA"
                  value={password2fa}
                  onChange={(e) => setPassword2fa(e.target.value)}
                  className="login-input"
                />
                <button onClick={handleSignIn} disabled={loading}>
                  {loading ? 'Проверка...' : 'Подтвердить'}
                </button>
              </>
            )}

            {loginStep === 'qr' && (
              <>
                <p>Отсканируйте QR-код в официальном приложении Telegram</p>
                <div className="qr-placeholder">[ QR-код появится здесь ]</div>
                <button className="secondary" onClick={() => setLoginStep('phone')}>
                  Войти по номеру
                </button>
              </>
            )}
          </div>
          <div className="login-footer">
            | модифицированный телеграмм /code |
          </div>
        </div>
      ) : (
        <div className="main-layout">
          <aside className="sidebar">
            <div className="sidebar-header">☰ Modified TG</div>
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
      )}
    </div>
  )
}

export default App
