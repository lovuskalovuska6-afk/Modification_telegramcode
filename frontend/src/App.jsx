import React, { useState, useEffect, useRef } from 'react'
import './App.css'

const API_URL = (() => {
  let base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  base = String(base).trim().replace(/\/$/, '')
  if (!base.startsWith('http://') && !base.startsWith('https://')) base = `https://${base}`
  return base.endsWith('/api') ? base : `${base}/api`
})()

function App() {
  const [screen, setScreen] = useState('landing')
  const [phone, setPhone] = useState(() => localStorage.getItem('tg_phone') || '')
  const [code, setCode] = useState('')
  const [password2fa, setPassword2fa] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [user, setUser] = useState(null)
  const [sessionStr, setSessionStr] = useState(() => localStorage.getItem('tg_session') || '')
  const [sessionInput, setSessionInput] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [isRegister, setIsRegister] = useState(false)

  const [activeMenu, setActiveMenu] = useState('chats')
  const [theme, setTheme] = useState('dark')
  const [menuOpen, setMenuOpen] = useState(false)
  const [aiEnabled, setAiEnabled] = useState(false)
  const [stealthOn, setStealthOn] = useState(false)

  const [dialogs, setDialogs] = useState([])
  const [activeChat, setActiveChat] = useState(null)
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [cmdMode, setCmdMode] = useState(false)
  const [chatsLoading, setChatsLoading] = useState(false)
  const messagesEndRef = useRef(null)

  const saveLocal = (p, sess, u) => {
    try {
      if (sess) localStorage.setItem('tg_session', sess)
      if (p) localStorage.setItem('tg_phone', p)
      if (u) localStorage.setItem('tg_user', JSON.stringify(u))
    } catch (e) {}
  }

  const loadDialogs = async (p = phone, tried = false) => {
    if (!p) return
    setChatsLoading(true)
    try {
      const res = await fetch(`${API_URL}/chats/dialogs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: p }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setDialogs(data.dialogs || [])
        setError('')
      } else if (!tried) {
        const saved = localStorage.getItem('tg_session') || ''
        const savedPhone = localStorage.getItem('tg_phone') || p
        if (saved) {
          const lr = await fetch(`${API_URL}/auth/load-session`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session: saved, phone: savedPhone }),
          })
          const ld = await lr.json()
          if (ld.status === 'success') {
            const next = ld.phone || savedPhone
            if (ld.user) setUser(ld.user)
            if (ld.session) setSessionStr(ld.session)
            saveLocal(next, ld.session || saved, ld.user)
            if (next !== p) {
              setPhone(next)
              setChatsLoading(false)
              return
            }
            setChatsLoading(false)
            return loadDialogs(next, true)
          }
        }
        setError(data.message || 'Не удалось загрузить чаты')
      } else {
        setError(data.message || 'Не удалось загрузить чаты')
      }
    } catch (e) {
      setError('Ошибка загрузки чатов')
    }
    setChatsLoading(false)
  }

  const loadMessages = async (chatId, p = phone) => {
    if (!p || !chatId) return
    try {
      const res = await fetch(`${API_URL}/chats/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: p, chat_id: chatId, limit: 50 }),
      })
      const data = await res.json()
      if (data.status === 'success') setMessages(data.messages || [])
    } catch (e) {}
  }

  const openChat = (d) => {
    setActiveChat(d)
    setActiveMenu('chats')
    setMenuOpen(false)
    loadMessages(d.id)
  }

  const sendText = async () => {
    if (!text.trim() || !activeChat || !phone) return
    const payload = text.trim()
    setText('')

    if (cmdMode || payload.startsWith('/')) {
      const raw = payload.startsWith('/') ? payload.slice(1) : payload
      const parts = raw.split(/\s+/).filter(Boolean)
      const command = parts[0] || ''
      const args = parts.slice(1)
      setCmdMode(false)
      try {
        const res = await fetch(`${API_URL}/chats/command`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone, chat_id: activeChat.id, command, args }),
        })
        const data = await res.json()
        if (data.status === 'success') {
          await loadMessages(activeChat.id)
          await loadDialogs()
        } else setError(data.message || 'Ошибка команды')
      } catch (e) {
        setError('Ошибка команды')
      }
      return
    }

    try {
      const res = await fetch(`${API_URL}/chats/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, chat_id: activeChat.id, text: payload }),
      })
      const data = await res.json()
      if (data.status === 'success' && data.message) {
        setMessages((prev) => [...prev, data.message])
        loadDialogs()
      } else setError(typeof data.message === 'string' ? data.message : 'Не отправлено')
    } catch (e) {
      setError('Ошибка отправки')
    }
  }

  useEffect(() => {
    const p = localStorage.getItem('tg_phone') || ''
    const s = localStorage.getItem('tg_session') || ''
    if (!p || !s) return
    try {
      const raw = localStorage.getItem('tg_user')
      if (raw) setUser(JSON.parse(raw))
    } catch (e) {}
    setSessionStr(s)
    setPhone(p)
    setActiveMenu('chats')
    setScreen('app')
  }, [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (screen === 'app' && phone) loadDialogs(phone)
  }, [screen, phone])

  const afterAuth = (data, p) => {
    setUser(data.user)
    if (data.session) {
      setSessionStr(data.session)
      saveLocal(p || data.phone || phone, data.session, data.user)
    }
    if (data.phone) setPhone(data.phone)
    setScreen('app')
    setActiveMenu('chats')
  }

  const handleSendCode = async () => {
    if (phone.trim().length < 8) return setError('Введите корректный номер')
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_URL}/auth/send-code`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      })
      const data = await res.json()
      if (data.status === 'already_authorized') afterAuth(data, phone)
      else if (data.status === 'code_sent') setScreen('code')
      else setError(data.message || 'Ошибка')
    } catch (e) { setError('Не удалось связаться с сервером') }
    setLoading(false)
  }

  const handleSignIn = async () => {
    setLoading(true); setError('')
    try {
      const body = { phone, code, password: password2fa || null }
      if (isRegister) { body.first_name = firstName; body.last_name = lastName || null }
      const res = await fetch(`${API_URL}/auth/sign-in`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
      })
      const data = await res.json()
      if (data.status === 'success') afterAuth(data, phone)
      else if (data.status === '2fa_required') setScreen('2fa')
      else if (data.status === 'need_signup') { setIsRegister(true); setScreen('register') }
      else setError(data.message || 'Ошибка')
    } catch (e) { setError('Ошибка соединения') }
    setLoading(false)
  }

  const handleLoadSession = async () => {
    if (!sessionInput.trim()) return setError('Файл сессии не передан. Отправьте строку или файл сессии.')
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_URL}/auth/load-session`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session: sessionInput.trim(), phone: phone || null }),
      })
      const data = await res.json()
      if (data.status === 'success') afterAuth(data, data.phone)
      else setError(data.message || 'Сессия не найдена. Загрузите файл сессии вручную.')
    } catch (e) { setError('Не удалось загрузить сессию') }
    setLoading(false)
  }

  const handleSessionFile = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return setError('Файл сессии не передан.')
    const text = await file.text()
    if (!text.trim()) return setError('Файл сессии не передан или пустой.')
    setSessionInput(text.trim())
    setLoading(true); setError('')
    try {
      const res = await fetch(`${API_URL}/auth/load-session`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session: text.trim(), phone: phone || null }),
      })
      const data = await res.json()
      if (data.status === 'success') afterAuth(data, data.phone)
      else setError(data.message || 'Сессия не найдена. Загрузите файл сессии вручную.')
    } catch (err) { setError('Не удалось прочитать файл сессии.') }
    setLoading(false)
  }

  const downloadSession = async () => {
    let sess = sessionStr
    if (!sess && phone) {
      const res = await fetch(`${API_URL}/auth/export-session`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone }),
      })
      const data = await res.json()
      if (data.status === 'success') { sess = data.session; setSessionStr(sess) }
      else return setError(data.message || 'Сессия не найдена. Загрузите файл сессии вручную.')
    }
    if (!sess) return setError('Сессия не найдена. Загрузите файл сессии вручную.')
    const a = document.createElement('a')
    a.href = URL.createObjectURL(new Blob([sess], { type: 'text/plain' }))
    a.download = `telegramcode_session.txt`
    a.click()
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

  const renderChats = () => (
    <div className="chats-layout">
      <div className={`dialogs-pane ${activeChat ? 'hidden-mobile' : ''}`}>
        <div className="dialogs-header">
          <span>Чаты</span>
          <button type="button" className="icon-btn" onClick={() => loadDialogs()} title="Обновить">↻</button>
        </div>
        {chatsLoading && <div className="hint pad">Загрузка…</div>}
        <div className="dialogs-list">
          {dialogs.map((d) => (
            <div key={d.id} className={`dialog-item ${activeChat?.id === d.id ? 'active' : ''}`} onClick={() => openChat(d)}>
              <div className="dialog-avatar">{(d.title || '?')[0]}</div>
              <div className="dialog-body">
                <div className="dialog-top">
                  <span className="dialog-title">{d.title}</span>
                  {d.unread > 0 && <span className="badge">{d.unread}</span>}
                </div>
                <div className="dialog-last">{d.last_message || ''}</div>
              </div>
            </div>
          ))}
          {!chatsLoading && dialogs.length === 0 && (
            <div className="hint pad">Нет чатов. Обновите или проверьте сессию.</div>
          )}
        </div>
      </div>

      <div className={`messages-pane ${!activeChat ? 'hidden-mobile' : ''}`}>
        {activeChat ? (
          <>
            <div className="chat-header">
              <button type="button" className="icon-btn mobile-only" onClick={() => setActiveChat(null)}>←</button>
              <span className="chat-title">{activeChat.title}</span>
            </div>
            <div className="messages-list">
              {messages.map((m) => (
                <div key={m.id} className={`bubble ${m.out ? 'out' : 'in'}`}>
                  {!m.out && m.sender && <div className="bubble-sender">{m.sender}</div>}
                  <div className="bubble-text">{m.text}</div>
                  <div className="bubble-time">{m.date}</div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <div className="composer">
              <button
                type="button"
                className={`cmd-toggle ${cmdMode ? 'on' : ''}`}
                title="Команды"
                onClick={() => setCmdMode((v) => !v)}
              >
                | / |
              </button>
              <input
                className="composer-input"
                placeholder={cmdMode ? 'spam слово 5 | mute | unmute' : 'Сообщение...'}
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendText()}
              />
              <button type="button" className="send-btn" onClick={sendText}>➤</button>
            </div>
          </>
        ) : (
          <div className="no-chat">Выберите чат</div>
        )}
      </div>
    </div>
  )

  const renderContent = () => {
    if (activeMenu === 'chats') return renderChats()
    if (activeMenu === 'settings') return (
      <div className="panel">
        <h2>Настройки</h2>
        <div className="settings-list">
          {[['theme','Тема'],['ai','ИИ'],['stealth','Скрытность'],['account','Аккаунт']].map(([id,l]) => (
            <div key={id} className="settings-row" onClick={() => { setActiveMenu(id); setMenuOpen(false) }}>
              <span>{l}</span><span className="settings-value">→</span>
            </div>
          ))}
        </div>
      </div>
    )
    if (activeMenu === 'commands') return (
      <div className="panel">
        <h2>Команды</h2>
        <p>Кнопка <b>| / |</b> у поля ввода.</p>
        <ul className="cmd-list">
          <li><code>spam слово 10</code></li>
          <li><code>mute</code> / <code>unmute</code></li>
        </ul>
      </div>
    )
    if (activeMenu === 'ai') return (
      <div className="panel"><h2>ИИ автоответ</h2>
        <label className="toggle"><input type="checkbox" checked={aiEnabled} onChange={(e)=>setAiEnabled(e.target.checked)} /><span>{aiEnabled?'Вкл':'Выкл'}</span></label>
      </div>
    )
    if (activeMenu === 'stealth') return (
      <div className="panel"><h2>Скрытность</h2>
        <label className="toggle"><input type="checkbox" checked={stealthOn} onChange={(e)=>setStealthOn(e.target.checked)} /><span>Скрывать онлайн</span></label>
      </div>
    )
    if (activeMenu === 'theme') return (
      <div className="panel"><h2>Тема</h2>
        <div className="theme-buttons">
          <button className={theme==='dark'?'active':''} onClick={()=>setTheme('dark')}>Тёмная</button>
          <button className={theme==='light'?'active':''} onClick={()=>setTheme('light')}>Светлая</button>
        </div>
      </div>
    )
    if (activeMenu === 'custom-command') return (
      <div className="panel"><h2>Своя команда</h2>
        <select defaultValue="python"><option value="javascript">JS</option><option value="python">Python</option><option value="lua">Lua</option></select>
        <textarea rows={10} placeholder="// код"></textarea>
      </div>
    )
    if (activeMenu === 'tg-settings') return <div className="panel"><h2>Настройки Telegram</h2><p className="hint">Скоро</p></div>
    if (activeMenu === 'account') return (
      <div className="panel">
        <h2>Аккаунт</h2>
        {error && <div className="error">{error}</div>}
        {user && <div className="account-card">
          <p>{user.first_name} {user.last_name||''}</p>
          <p>@{user.username||'нет'} · {user.phone||phone}</p>
          <p>ID: {user.id}</p>
        </div>}
        <button type="button" onClick={downloadSession}>Скачать сессию</button>
        <button type="button" className="secondary-panel-btn" onClick={()=>{setScreen('load-session');setError('')}}>Загрузить сессию</button>
        <button className="danger-btn" onClick={()=>{
          localStorage.clear(); setScreen('landing'); setUser(null); setSessionStr(''); setDialogs([]); setActiveChat(null)
        }}>Выйти</button>
      </div>
    )
    return <div className="panel"><p>Меню ☰</p></div>
  }

  // ---- auth screens (compact) ----
  if (screen === 'landing') return (
    <div className={`app theme-${theme}`}><div className="landing"><div className="landing-content">
      <h1 className="logo">TelegramCode</h1>
      <button className="start-btn" onClick={()=>setScreen('auth-choice')}>Начать</button>
    </div><div className="login-footer">| модифицированный телеграмм /code |</div></div></div>
  )

  if (screen === 'auth-choice') return (
    <div className={`app theme-${theme}`}><div className="login-screen"><div className="login-box">
      <h1>TelegramCode</h1><p>Способ входа</p>
      <button onClick={()=>{setIsRegister(false);setScreen('phone')}}>Войти по номеру</button>
      <button className="secondary" onClick={()=>setScreen('qr')}>QR-код</button>
      <button className="secondary" onClick={()=>{setError('');setSessionInput('');setScreen('load-session')}}>Загрузить сессию</button>
      <button className="register-link" onClick={()=>{setIsRegister(true);setScreen('phone')}}>Я не имею аккаунта (зарегистрироваться)</button>
    </div><div className="login-footer">| модифицированный телеграмм /code |</div></div></div>
  )

  if (screen === 'load-session') return (
    <div className={`app theme-${theme}`}><div className="login-screen"><div className="login-box">
      <h1>Сессия</h1>{error&&<div className="error">{error}</div>}
      <textarea className="login-input session-area" rows={5} value={sessionInput} onChange={e=>setSessionInput(e.target.value)} placeholder="StringSession..." />
      <label className="file-btn">Файл сессии<input type="file" hidden accept=".txt,text/plain" onChange={handleSessionFile} /></label>
      <button onClick={handleLoadSession} disabled={loading}>{loading?'...':'Войти с сессией'}</button>
      <button className="secondary" onClick={()=>setScreen('auth-choice')}>Назад</button>
    </div></div></div>
  )

  if (screen === 'phone') return (
    <div className={`app theme-${theme}`}><div className="login-screen"><div className="login-box">
      <h1>{isRegister?'Регистрация':'Вход'}</h1>{error&&<div className="error">{error}</div>}
      <input className="login-input" type="tel" placeholder="+7..." value={phone} onChange={e=>setPhone(e.target.value)} />
      <button onClick={handleSendCode} disabled={loading}>{loading?'...':'Получить код'}</button>
      <button className="secondary" onClick={()=>setScreen('auth-choice')}>Назад</button>
    </div></div></div>
  )

  if (screen === 'code') return (
    <div className={`app theme-${theme}`}><div className="login-screen"><div className="login-box">
      <h1>Код</h1>{error&&<div className="error">{error}</div>}
      <p>{phone}</p>
      <input className="login-input" value={code} onChange={e=>setCode(e.target.value)} placeholder="Код" />
      <button onClick={handleSignIn} disabled={loading}>{loading?'...':isRegister?'Далее':'Войти'}</button>
      <button className="secondary" onClick={()=>setScreen('phone')}>Назад</button>
    </div></div></div>
  )

  if (screen === 'register') return (
    <div className={`app theme-${theme}`}><div className="login-screen"><div className="login-box">
      <h1>Имя</h1>{error&&<div className="error">{error}</div>}
      <input className="login-input" placeholder="Имя" value={firstName} onChange={e=>setFirstName(e.target.value)} />
      <input className="login-input" placeholder="Фамилия" value={lastName} onChange={e=>setLastName(e.target.value)} />
      <button onClick={()=>{if(!firstName.trim())return setError('Введите имя');setIsRegister(true);handleSignIn()}} disabled={loading}>Зарегистрироваться</button>
    </div></div></div>
  )

  if (screen === '2fa') return (
    <div className={`app theme-${theme}`}><div className="login-screen"><div className="login-box">
      <h1>2FA</h1>{error&&<div className="error">{error}</div>}
      <input className="login-input" type="password" value={password2fa} onChange={e=>setPassword2fa(e.target.value)} />
      <button onClick={handleSignIn} disabled={loading}>Подтвердить</button>
    </div></div></div>
  )

  if (screen === 'qr') return (
    <div className={`app theme-${theme}`}><div className="login-screen"><div className="login-box">
      <h1>QR</h1><div className="qr-placeholder">Скоро</div>
      <button className="secondary" onClick={()=>setScreen('auth-choice')}>Назад</button>
    </div></div></div>
  )

  return (
    <div className={`app theme-${theme}`}>
      <div className="main-layout">
        <header className="topbar">
          <button type="button" className="hamburger" onClick={()=>setMenuOpen(v=>!v)}>☰</button>
          <span className="topbar-title">TelegramCode</span>
          {user && <span className="topbar-user">{user.first_name}</span>}
        </header>
        {menuOpen && <div className="menu-overlay" onClick={()=>setMenuOpen(false)} />}
        <aside className={`sidebar ${menuOpen?'open':''}`}>
          <div className="sidebar-header"><span>Меню</span>
            <button type="button" className="sidebar-close" onClick={()=>setMenuOpen(false)}>✕</button>
          </div>
          <nav className="sidebar-menu">
            {menuItems.map(item=>(
              <div key={item.id} className={`menu-item ${activeMenu===item.id?'active':''}`}
                onClick={()=>{setActiveMenu(item.id);setMenuOpen(false);if(item.id==='chats')loadDialogs()}}>
                {item.label}
              </div>
            ))}
          </nav>
        </aside>
        <main className="content-area">{error && activeMenu!=='account' && <div className="error banner">{error}</div>}{renderContent()}</main>
      </div>
    </div>
  )
}

export default App
