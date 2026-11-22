import React, { useState } from 'react'
import './App.css'

const API_URL = (() => {
  let base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  base = String(base).trim().replace(/\/$/, '')
  if (!base.startsWith('http://') && !base.startsWith('https://')) {
    base = `https://${base}`
  }
  if (base.endsWith('/api')) return base
  return `${base}/api`
})()

function App() {
  const [screen, setScreen] = useState('landing')
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [password2fa, setPassword2fa] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [user, setUser] = useState(null)
  const [sessionStr, setSessionStr] = useState('')
  const [sessionInput, setSessionInput] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isRegister, setIsRegister] = useState(false)

  const [activeMenu, setActiveMenu] = useState('chats')
  const [theme, setTheme] = useState('dark')
  const [menuOpen, setMenuOpen] = useState(false)

  const [aiEnabled, setAiEnabled] = useState(false)
  const [stealthOn, setStealthOn] = useState(false)
  const [chatTheme, setChatTheme] = useState('default')

  const saveLocalSession = (phoneVal, sess, userObj) => {
    try {
      if (sess) localStorage.setItem('tg_session', sess)
      if (phoneVal) localStorage.setItem('tg_phone', phoneVal)
      if (userObj) localStorage.setItem('tg_user', JSON.stringify(userObj))
    } catch (e) {}
  }

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
      if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`)
      const data = await res.json()
      if (data.status === 'code_sent' || data.status === 'already_authorized') {
        if (data.status === 'already_authorized') {
          setUser(data.user || null)
          if (data.session) {
            setSessionStr(data.session)
            saveLocalSession(phone, data.session, data.user)
          }
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
      if (!res.ok) throw new Error(await res.text() || `HTTP ${res.status}`)
      const data = await res.json()

      if (data.status === 'success') {
        setUser(data.user)
        if (data.session) {
          setSessionStr(data.session)
          saveLocalSession(phone, data.session, data.user)
        }
        setScreen('app')
      } else if (data.status === '2fa_required') {
        setScreen('2fa')
      } else if (data.status === 'need_signup') {
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

  const handleLoadSession = async () => {
    const value = sessionInput.trim()
    if (!value) {
      setError('Файл сессии не передан. Отправьте строку или файл сессии.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await fetch(`${API_URL}/auth/load-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session: value, phone: phone || null }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setUser(data.user)
        setSessionStr(data.session || value)
        if (data.phone) setPhone(data.phone)
        saveLocalSession(data.phone || phone, data.session || value, data.user)
        setScreen('app')
      } else {
        setError(
          data.message ||
            'Сессия не найдена. Загрузите файл сессии вручную.'
        )
      }
    } catch (e) {
      setError('Не удалось загрузить сессию. Проверьте файл и сервер.')
    }
    setLoading(false)
  }

  const handleSessionFile = async (e) => {
    const file = e.target.files && e.target.files[0]
    if (!file) {
      setError('Файл сессии не передан. Отправьте строку или файл сессии.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const text = await file.text()
      if (!text.trim()) {
        setError('Файл сессии не передан или пустой.')
        setLoading(false)
        return
      }
      setSessionInput(text.trim())
      const res = await fetch(`${API_URL}/auth/load-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session: text.trim(), phone: phone || null }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setUser(data.user)
        setSessionStr(data.session || text.trim())
        if (data.phone) setPhone(data.phone)
        saveLocalSession(data.phone || phone, data.session || text.trim(), data.user)
        setScreen('app')
      } else {
        setError(
          data.message ||
            'Сессия не найдена. Загрузите файл сессии вручную.'
        )
      }
    } catch (err) {
      setError('Не удалось прочитать файл сессии.')
    }
    setLoading(false)
  }

  const downloadSession = async () => {
    setError('')
    let sess = sessionStr
    if (!sess && phone) {
      try {
        const res = await fetch(`${API_URL}/auth/export-session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone }),
        })
        const data = await res.json()
        if (data.status === 'success' && data.session) {
          sess = data.session
          setSessionStr(sess)
        } else {
          setError(
            data.message ||
              'Сессия не найдена. Загрузите файл сессии вручную.'
          )
          return
        }
      } catch (e) {
        setError('Не удалось получить сессию с сервера.')
        return
      }
    }
    if (!sess) {
      setError('Сессия не найдена. Загрузите файл сессии вручную.')
      return
    }
    const blob = new Blob([sess], { type: 'text/plain;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `telegramcode_session_${(phone || 'user').replace(/\W/g, '')}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const openMenuItem = (id) => {
    setActiveMenu(id)
    setMenuOpen(false)
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
        return (
          <div className="panel">
            <h2>Настройки</h2>
            <div className="settings-list">
              <div className="settings-row" onClick={() => openMenuItem('theme')}>
                <span>Тема оформления</span>
                <span className="settings-value">{theme === 'dark' ? 'Тёмная' : 'Светлая'}</span>
              </div>
              <div className="settings-row" onClick={() => openMenuItem('ai')}>
                <span>ИИ автоответ</span>
                <span className="settings-value">{aiEnabled ? 'Вкл' : 'Выкл'}</span>
              </div>
              <div className="settings-row" onClick={() => openMenuItem('stealth')}>
                <span>Скрытность</span>
                <span className="settings-value">{stealthOn ? 'Вкл' : 'Выкл'}</span>
              </div>
              <div className="settings-row" onClick={() => openMenuItem('commands')}>
                <span>Команды</span>
                <span className="settings-value">→</span>
              </div>
              <div className="settings-row" onClick={() => openMenuItem('account')}>
                <span>Аккаунт / сессия</span>
                <span className="settings-value">→</span>
              </div>
            </div>
          </div>
        )
      case 'chats':
        return (
          <div className="panel">
            <h2>Чаты</h2>
            {user && (
              <p>
                Вы вошли как:{' '}
                <b>
                  {user.first_name} {user.last_name || ''}
                </b>{' '}
                {user.username ? `(@${user.username})` : ''}
              </p>
            )}
            <div className="theme-buttons">
              <button className={chatTheme === 'default' ? 'active' : ''} onClick={() => setChatTheme('default')}>Обычная</button>
              <button className={chatTheme === 'compact' ? 'active' : ''} onClick={() => setChatTheme('compact')}>Компактная</button>
            </div>
            <p style={{ marginTop: 24 }}>Здесь будет список чатов</p>
          </div>
        )
      case 'commands':
        return (
          <div className="panel">
            <h2>Команды</h2>
            <ul className="cmd-list">
              <li><code>spam слово 10</code></li>
              <li><code>mute</code> / <code>unmute</code></li>
            </ul>
          </div>
        )
      case 'ai':
        return (
          <div className="panel">
            <h2>ИИ автоответ</h2>
            <label className="toggle">
              <input type="checkbox" checked={aiEnabled} onChange={(e) => setAiEnabled(e.target.checked)} />
              <span>{aiEnabled ? 'Включено' : 'Выключено'}</span>
            </label>
          </div>
        )
      case 'tg-settings':
        return (
          <div className="panel">
            <h2>Настройки Telegram</h2>
            <p className="hint">В разработке</p>
          </div>
        )
      case 'account':
        return (
          <div className="panel">
            <h2>Аккаунт</h2>
            {error && <div className="error">{error}</div>}
            {user && (
              <div className="account-card">
                <p>ID: {user.id}</p>
                <p>Имя: {user.first_name} {user.last_name || ''}</p>
                <p>Username: {user.username ? `@${user.username}` : 'нет'}</p>
                <p>Телефон: {user.phone || phone}</p>
              </div>
            )}
            <button type="button" onClick={downloadSession}>
              Скачать сессию
            </button>
            <button
              type="button"
              className="secondary-panel-btn"
              onClick={() => {
                setSessionInput('')
                setError('')
                setScreen('load-session')
              }}
            >
              Загрузить сессию
            </button>
            <button
              className="danger-btn"
              onClick={() => {
                try {
                  localStorage.removeItem('tg_session')
                  localStorage.removeItem('tg_phone')
                  localStorage.removeItem('tg_user')
                } catch (e) {}
                setScreen('landing')
                setUser(null)
                setSessionStr('')
                setPhone('')
                setCode('')
                setPassword2fa('')
                setFirstName('')
                setLastName('')
                setIsRegister(false)
                setMenuOpen(false)
              }}
            >
              Выйти
            </button>
            <p className="hint" style={{ marginTop: 16 }}>
              Сессия — полный доступ к аккаунту. Храни файл только у себя.
            </p>
          </div>
        )
      case 'custom-command':
        return (
          <div className="panel">
            <h2>Добавить свою команду</h2>
            <select defaultValue="python">
              <option value="javascript">JavaScript</option>
              <option value="python">Python</option>
              <option value="lua">Lua</option>
            </select>
            <textarea placeholder="// Ваш код..." rows={12}></textarea>
            <button type="button">Сохранить команду</button>
          </div>
        )
      case 'stealth':
        return (
          <div className="panel">
            <h2>Скрытность</h2>
            <label className="toggle">
              <input type="checkbox" checked={stealthOn} onChange={(e) => setStealthOn(e.target.checked)} />
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
        return <div className="panel"><p>Выберите раздел в меню ☰</p></div>
    }
  }

  if (screen === 'landing') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="landing">
          <div className="landing-content">
            <h1 className="logo">TelegramCode</h1>
            <button className="start-btn" onClick={() => setScreen('auth-choice')}>Начать</button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

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
            <button className="secondary" onClick={() => { setError(''); setSessionInput(''); setScreen('load-session'); }}>
              Загрузить сессию
            </button>
            <button
              className="register-link"
              onClick={() => { setIsRegister(true); setScreen('phone'); }}
            >
              Я не имею аккаунта (зарегистрироваться)
            </button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  if (screen === 'load-session') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Загрузка сессии</h1>
            {error && <div className="error">{error}</div>}
            <p>Вставь строку сессии или выбери файл</p>
            <textarea
              className="login-input session-area"
              rows={5}
              placeholder="Строка StringSession..."
              value={sessionInput}
              onChange={(e) => setSessionInput(e.target.value)}
            />
            <label className="file-btn">
              Выбрать файл сессии
              <input type="file" accept=".txt,.session,text/plain" hidden onChange={handleSessionFile} />
            </label>
            <button onClick={handleLoadSession} disabled={loading}>
              {loading ? 'Загрузка...' : 'Войти с сессией'}
            </button>
            <button className="secondary" onClick={() => setScreen('auth-choice')}>Назад</button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  if (screen === 'phone') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>{isRegister ? 'Регистрация' : 'Вход'}</h1>
            {error && <div className="error">{error}</div>}
            <p>Введите номер телефона</p>
            <input type="tel" placeholder="+7 999 123-45-67" value={phone} onChange={(e) => setPhone(e.target.value)} className="login-input" />
            <button onClick={handleSendCode} disabled={loading}>{loading ? 'Отправка...' : 'Получить код'}</button>
            <button className="secondary" onClick={() => setScreen('auth-choice')}>Назад</button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  if (screen === 'code') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Код подтверждения</h1>
            {error && <div className="error">{error}</div>}
            <p>Код отправлен на {phone}</p>
            <input type="text" placeholder="Код из Telegram / SMS" value={code} onChange={(e) => setCode(e.target.value)} className="login-input" />
            <button onClick={handleSignIn} disabled={loading}>{loading ? 'Проверка...' : isRegister ? 'Далее' : 'Войти'}</button>
            <button className="secondary" onClick={() => setScreen('phone')}>Назад</button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  if (screen === 'register') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Создание аккаунта</h1>
            {error && <div className="error">{error}</div>}
            <p>Как вас зовут?</p>
            <input type="text" placeholder="Имя" value={firstName} onChange={(e) => setFirstName(e.target.value)} className="login-input" />
            <input type="text" placeholder="Фамилия (необязательно)" value={lastName} onChange={(e) => setLastName(e.target.value)} className="login-input" />
            <button onClick={handleRegister} disabled={loading}>{loading ? 'Создание...' : 'Зарегистрироваться'}</button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  if (screen === '2fa') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Двухфакторная аутентификация</h1>
            {error && <div className="error">{error}</div>}
            <p>Введите пароль 2FA</p>
            <input type="password" placeholder="Пароль" value={password2fa} onChange={(e) => setPassword2fa(e.target.value)} className="login-input" />
            <button onClick={handleSignIn} disabled={loading}>{loading ? 'Проверка...' : 'Подтвердить'}</button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  if (screen === 'qr') {
    return (
      <div className={`app theme-${theme}`}>
        <div className="login-screen">
          <div className="login-box">
            <h1>Вход по QR</h1>
            <p>Отсканируйте QR в официальном Telegram</p>
            <div className="qr-placeholder">[ QR-код появится здесь ]</div>
            <button className="secondary" onClick={() => setScreen('auth-choice')}>Назад</button>
          </div>
          <div className="login-footer">| модифицированный телеграмм /code |</div>
        </div>
      </div>
    )
  }

  return (
    <div className={`app theme-${theme}`}>
      <div className="main-layout">
        <header className="topbar">
          <button type="button" className="hamburger" aria-label="Меню" onClick={() => setMenuOpen((v) => !v)}>☰</button>
          <span className="topbar-title">TelegramCode</span>
          {user && <span className="topbar-user">{user.first_name}</span>}
        </header>

        {menuOpen && <div className="menu-overlay" onClick={() => setMenuOpen(false)} />}

        <aside className={`sidebar ${menuOpen ? 'open' : ''}`}>
          <div className="sidebar-header">
            <span>Меню</span>
            <button type="button" className="sidebar-close" onClick={() => setMenuOpen(false)}>✕</button>
          </div>
          <nav className="sidebar-menu">
            {menuItems.map((item) => (
              <div
                key={item.id}
                className={`menu-item ${activeMenu === item.id ? 'active' : ''}`}
                onClick={() => openMenuItem(item.id)}
              >
                {item.label}
              </div>
            ))}
          </nav>
        </aside>

        <main className="content-area">{renderContent()}</main>
      </div>
    </div>
  )
}

export default App
