import React, { useState, useEffect, useRef } from 'react'
import './App.css'

const API_URL = (() => {
  let base = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  base = String(base).trim().replace(/\/$/, '')
  if (!base.startsWith('http://') && !base.startsWith('https://')) base = `https://${base}`
  return base.endsWith('/api') ? base : `${base}/api`
})()

function msgsEqual(a, b) {
  if (a === b) return true
  if (!a || !b || a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    if (a[i].id !== b[i].id || a[i].text !== b[i].text) return false
  }
  return true
}

function dialogsEqual(a, b) {
  if (a === b) return true
  if (!a || !b || a.length !== b.length) return false
  for (let i = 0; i < a.length; i++) {
    if (a[i].id !== b[i].id || a[i].last_message !== b[i].last_message || a[i].unread !== b[i].unread) return false
  }
  return true
}

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
  const [aiProvider, setAiProvider] = useState('groq')
  const [aiApiKey, setAiApiKey] = useState('')
  const [aiModel, setAiModel] = useState('openai/gpt-oss-20b')
  const [aiSaving, setAiSaving] = useState(false)
  const [aiMsg, setAiMsg] = useState('')
  const [aiLastError, setAiLastError] = useState('')
  const [freeModels, setFreeModels] = useState({
    groq: ['openai/gpt-oss-20b', 'openai/gpt-oss-120b', 'qwen/qwen3.8-27b', 'allam-2-7b'],
    openrouter: [
      'meta-llama/llama-3.2-3b-instruct:free',
      'google/gemma-2-9b-it:free',
      'microsoft/phi-3-mini-128k-instruct:free',
      'qwen/qwen-2-7b-instruct:free',
    ],
    openai: ['gpt-4o-mini', 'gpt-3.5-turbo'],
  })
  const [stealthOn, setStealthOn] = useState(false)
  const [dialogs, setDialogs] = useState([])
  const [activeChat, setActiveChat] = useState(null)
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [cmdMode, setCmdMode] = useState(false)
  const [chatsLoading, setChatsLoading] = useState(false)
  const [mutedIds, setMutedIds] = useState(() => {
    try {
      const raw = localStorage.getItem('tg_muted_ids')
      if (raw) return new Set(JSON.parse(raw).map(Number))
    } catch (e) {}
    return new Set()
  })
  // Локальный чат только на сайте (не в Telegram)
  const SYSTEM_CHAT_ID = 'local_system'
  const SYSTEM_CHAT = {
    id: SYSTEM_CHAT_ID,
    title: '⚡ TelegramCode',
    last_message: 'Команды и ошибки ИИ',
    unread: 0,
    local: true,
  }
  const [systemMessages, setSystemMessages] = useState(() => {
    try {
      const raw = localStorage.getItem('tg_system_log')
      if (raw) return JSON.parse(raw)
    } catch (e) {}
    return [{
      id: 'sys_welcome',
      text: 'Локальный чат сайта.\nСюда приходят ответы команд (help, status, ai test) и ошибки ИИ.\nВ Telegram этого чата нет.',
      out: false,
      sender: '⚡ TelegramCode',
      date: '',
      system: true,
    }]
  })
  const messagesEndRef = useRef(null)
  const activeChatRef = useRef(null)
  const phoneRef = useRef(phone)
  const screenRef = useRef(screen)
  const isSystemChat = (id) => id === SYSTEM_CHAT_ID || id === 'local_system'

  const AI_PROVIDERS = [
    { id: 'groq', label: 'Groq (бесплатно)', model: 'openai/gpt-oss-20b', url: 'https://console.groq.com/keys' },
    { id: 'openrouter', label: 'OpenRouter (:free модели)', model: 'meta-llama/llama-3.2-3b-instruct:free', url: 'https://openrouter.ai/keys' },
    { id: 'openai', label: 'OpenAI', model: 'gpt-4o-mini', url: 'https://platform.openai.com/api-keys' },
  ]

  useEffect(() => { activeChatRef.current = activeChat }, [activeChat])
  useEffect(() => { phoneRef.current = phone }, [phone])
  useEffect(() => { screenRef.current = screen }, [screen])

  // localStorage backup для AI (чтобы не терять ключ при рестарте UI)
  const saveAiLocal = (obj) => {
    try {
      localStorage.setItem('tg_ai_settings', JSON.stringify(obj || {
        enabled: aiEnabled,
        provider: aiProvider,
        api_key: aiApiKey,
        model: aiModel,
      }))
    } catch (e) {}
  }

  const loadAiLocal = () => {
    try {
      const raw = localStorage.getItem('tg_ai_settings')
      if (!raw) return null
      return JSON.parse(raw)
    } catch (e) {
      return null
    }
  }

  const loadAiSettings = async (p = phone) => {
    if (!p) {
      // хотя бы локально
      const loc = loadAiLocal()
      if (loc) {
        setAiEnabled(!!loc.enabled)
        setAiProvider(loc.provider || 'groq')
        if (loc.api_key) setAiApiKey(loc.api_key)
        if (loc.model) setAiModel(loc.model)
      }
      return
    }
    try {
      const res = await fetch(`${API_URL}/settings/ai/get`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: p }),
      })
      const data = await res.json()
      if (data.status === 'success' && data.settings) {
        const s = data.settings
        setAiEnabled(!!s.enabled)
        setAiProvider(s.provider || 'groq')
        if (s.api_key) setAiApiKey(s.api_key)
        if (s.model) setAiModel(s.model)
        setAiLastError(s.last_error || '')
        if (s.free_models && typeof s.free_models === 'object') {
          setFreeModels((prev) => ({ ...prev, ...s.free_models }))
        }
        // синхронизируем локально
        saveAiLocal({
          enabled: !!s.enabled,
          provider: s.provider || 'groq',
          api_key: s.api_key || aiApiKey,
          model: s.model || aiModel,
        })
        return
      }
    } catch (e) {}
    // fallback localStorage
    const loc = loadAiLocal()
    if (loc) {
      setAiEnabled(!!loc.enabled)
      setAiProvider(loc.provider || 'groq')
      if (loc.api_key) setAiApiKey(loc.api_key)
      if (loc.model) setAiModel(loc.model)
    }
  }

  const saveAiSettings = async () => {
    if (!phone) { setAiMsg('Сначала войдите'); return }
    setAiSaving(true)
    setAiMsg('')
    const payload = {
      phone,
      enabled: aiEnabled,
      provider: aiProvider,
      api_key: aiApiKey,
      model: aiModel,
    }
    // всегда пишем в localStorage сразу
    saveAiLocal(payload)
    try {
      const res = await fetch(`${API_URL}/settings/ai/set`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setAiMsg('Сохранено ✓ (сервер + локально)')
        if (data.settings && data.settings.last_error !== undefined) {
          setAiLastError(data.settings.last_error || '')
        } else {
          setAiLastError('')
        }
      } else {
        setAiMsg(data.message || data.detail || 'Ошибка')
      }
    } catch (e) {
      setAiMsg('Локально сохранено. Сервер: ' + String(e.message || e))
    } finally {
      setAiSaving(false)
    }
  }

  // при смене галочки — сразу сохраняем (чтобы ai on/off не терялось)
  const onAiToggle = async (checked) => {
    setAiEnabled(checked)
    setAiMsg('')
    if (!phone) return
    saveAiLocal({ enabled: checked, provider: aiProvider, api_key: aiApiKey, model: aiModel })
    try {
      await fetch(`${API_URL}/settings/ai/set`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone,
          enabled: checked,
          provider: aiProvider,
          api_key: aiApiKey,
          model: aiModel,
        }),
      })
    } catch (e) {}
  }

  const saveLocal = (p, sess, u) => {
    try {
      if (sess) localStorage.setItem('tg_session', sess)
      if (p) localStorage.setItem('tg_phone', p)
      if (u) localStorage.setItem('tg_user', JSON.stringify(u))
    } catch (e) {}
  }

  const loadDialogs = async (p = phone, tried = false, silent = false) => {
    if (!p) return
    if (!silent) setChatsLoading(true)
    try {
      const res = await fetch(`${API_URL}/chats/dialogs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: p }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        setDialogs((prev) => (dialogsEqual(prev, data.dialogs || []) ? prev : (data.dialogs || [])))
        if (Array.isArray(data.muted_ids)) {
          const s = new Set(data.muted_ids.map(Number))
          setMutedIds(s)
          try { localStorage.setItem('tg_muted_ids', JSON.stringify([...s])) } catch (e) {}
        }
        if (typeof data.ai_enabled === 'boolean') {
          setAiEnabled(data.ai_enabled)
        }
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
              if (!silent) setChatsLoading(false)
              return
            }
            if (!silent) setChatsLoading(false)
            return loadDialogs(next, true, silent)
          }
        }
        if (!silent) setError(data.message || 'Не удалось загрузить чаты')
      } else if (!silent) {
        setError(data.message || 'Не удалось загрузить чаты')
      }
    } catch (e) {
      if (!silent) setError('Ошибка загрузки чатов')
    }
    if (!silent) setChatsLoading(false)
  }

  const persistSystemLog = (msgs) => {
    try {
      const keep = (msgs || []).slice(-80)
      localStorage.setItem('tg_system_log', JSON.stringify(keep))
    } catch (e) {}
  }

  const loadMessages = async (chatId, p = phone) => {
    if (!p || !chatId || isSystemChat(chatId)) return
    try {
      const res = await fetch(`${API_URL}/chats/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone: p, chat_id: chatId, limit: 50 }),
      })
      const data = await res.json()
      if (data.status === 'success') {
        const next = data.messages || []
        setMessages((prev) => (msgsEqual(prev, next) ? prev : next))
      }
    } catch (e) {}
  }

  const openChat = (d) => {
    setActiveChat(d)
    setActiveMenu('chats')
    setMenuOpen(false)
    if (isSystemChat(d.id)) {
      setMessages(systemMessages)
    } else {
      loadMessages(d.id)
    }
  }

  const pushSystemMsg = (text, isError = false) => {
    const id = `sys_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`
    const msg = {
      id,
      text: text || '',
      out: false,
      sender: isError ? '⚠ Ошибка' : '⚡ TelegramCode',
      date: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      system: true,
      error: !!isError,
    }
    setSystemMessages((prev) => {
      const next = [...prev, msg].slice(-80)
      persistSystemLog(next)
      return next
    })
    // если сейчас открыт локальный чат — сразу показать
    if (activeChatRef.current && isSystemChat(activeChatRef.current.id)) {
      setMessages((prev) => [...prev, msg])
    }
  }

  const openSystemChat = () => {
    setActiveChat(SYSTEM_CHAT)
    setActiveMenu('chats')
    setMenuOpen(false)
    setMessages(systemMessages)
  }

  const sendText = async () => {
    if (!text.trim() || !activeChat || !phone) return
    const payload = text.trim()
    setText('')
    const inSystem = isSystemChat(activeChat.id)

    // В локальном чате — только команды
    if (inSystem && !(cmdMode || payload.startsWith('/') || true)) {
      // always treat as command in system chat if not empty
    }

    if (cmdMode || payload.startsWith('/') || inSystem) {
      const raw = payload.startsWith('/') ? payload.slice(1) : payload
      const parts = raw.split(/\s+/).filter(Boolean)
      const command = parts[0] || ''
      const args = parts.slice(1)
      if (!command) return
      setCmdMode(false)
      // chat_id для mute/spam: если локальный чат — шлём 0 (сервер не применит mute к локальному)
      const chatIdForCmd = inSystem ? 0 : activeChat.id
      try {
        const res = await fetch(`${API_URL}/chats/command`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone, chat_id: chatIdForCmd, command, args }),
        })
        const data = await res.json()
        if (data.status === 'success') {
          if (data.message && typeof data.message === 'string') {
            pushSystemMsg(data.message, false)
          } else {
            pushSystemMsg(`Команда «${command}» выполнена`, false)
          }
          // mute/unmute — обновляем бейджи
          if (command === 'mute' || command === 'unmute') {
            const cid = Number(data.chat_id != null ? data.chat_id : chatIdForCmd)
            setMutedIds((prev) => {
              const next = new Set(prev)
              if (command === 'mute') next.add(cid)
              else next.delete(cid)
              try { localStorage.setItem('tg_muted_ids', JSON.stringify([...next])) } catch (e) {}
              return next
            })
          }
          if (command === 'ai' && (args[0] === 'on' || args[0] === 'off')) {
            setAiEnabled(args[0] === 'on' || args[0] === 'вкл')
          }
          // spam/reply только в реальном чате
          if (!inSystem && (data.sent || command === 'spam' || command === 'reply' || command === 'clear')) {
            await loadMessages(activeChat.id)
          }
          await loadDialogs(phone, false, true)
          if (command === 'ai') loadAiSettings(phone)
          // для mute остаёмся в чате; для info-команд — локальный лог
          if (!inSystem && !['mute', 'unmute', 'spam', 'reply', 'clear'].includes(command)) {
            openSystemChat()
          }
        } else {
          const errText = data.message || data.detail || 'Ошибка команды'
          pushSystemMsg(errText, true)
          if (command === 'ai') loadAiSettings(phone)
          if (!inSystem) openSystemChat()
        }
      } catch (e) {
        pushSystemMsg('Ошибка сети при выполнении команды: ' + String(e.message || e), true)
        if (!inSystem) openSystemChat()
      }
      return
    }

    // обычная отправка только в реальные чаты
    try {
      const res = await fetch(`${API_URL}/chats/send`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone, chat_id: activeChat.id, text: payload }),
      })
      const data = await res.json()
      if (data.status === 'success' && data.message) {
        setMessages((prev) => {
          if (prev.some((m) => m.id === data.message.id)) return prev
          return [...prev, data.message]
        })
        loadDialogs(phone, false, true)
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
  }, [messages, systemMessages])

  useEffect(() => {
    if (screen === 'app' && phone) loadDialogs(phone)
  }, [screen, phone])

  // когда открыт локальный чат — синхронизируем ленту с systemMessages
  useEffect(() => {
    if (activeChat && isSystemChat(activeChat.id)) {
      setMessages(systemMessages)
    }
  }, [systemMessages, activeChat?.id])

  useEffect(() => {
    if (screen !== 'app' || !phone || !activeChat) return
    if (isSystemChat(activeChat.id)) return // локальный чат не поллим
    const chatId = activeChat.id
    const tick = () => {
      if (screenRef.current !== 'app') return
      if (!phoneRef.current) return
      if (!activeChatRef.current || activeChatRef.current.id !== chatId) return
      if (isSystemChat(activeChatRef.current.id)) return
      loadMessages(chatId, phoneRef.current)
    }
    const id = setInterval(tick, 2500)
    return () => clearInterval(id)
  }, [screen, phone, activeChat?.id])

  useEffect(() => {
    if (screen !== 'app' || !phone) return
    const tick = () => {
      if (screenRef.current !== 'app' || !phoneRef.current) return
      loadDialogs(phoneRef.current, false, true)
    }
    const id = setInterval(tick, 5000)
    return () => clearInterval(id)
  }, [screen, phone])

  const afterAuth = (data, p) => {
    setUser(data.user)
    if (data.session) {
      setSessionStr(data.session)
      saveLocal(p || data.phone || phone, data.session, data.user)
    }
    const realPhone = data.phone || p || phone
    if (data.phone) setPhone(data.phone)
    setScreen('app')
    setActiveMenu('chats')
    loadAiSettings(realPhone)
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
          {/* Локальный чат только на сайте */}
          <div
            key={SYSTEM_CHAT_ID}
            className={`dialog-item local-system ${activeChat?.id === SYSTEM_CHAT_ID ? 'active' : ''}`}
            onClick={() => openSystemChat()}
          >
            <div className="dialog-avatar">⚡</div>
            <div className="dialog-body">
              <div className="dialog-top">
                <span className="dialog-title">⚡ TelegramCode</span>
              </div>
              <div className="dialog-last">
                {(systemMessages[systemMessages.length - 1]?.text || 'Команды и ошибки ИИ').slice(0, 60)}
              </div>
            </div>
          </div>
          {dialogs.map((d) => (
            <div key={d.id} className={`dialog-item ${activeChat?.id === d.id ? 'active' : ''}`} onClick={() => openChat(d)}>
              <div className="dialog-avatar">{(d.title || '?')[0]}</div>
              <div className="dialog-body">
                <div className="dialog-top">
                  <span className="dialog-title">
                    {d.title}
                    {(mutedIds.has(Number(d.id)) || d.muted) ? ' 🔇' : ''}
                  </span>
                  {d.unread > 0 && <span className="badge">{d.unread}</span>}
                </div>
                <div className="dialog-last">{d.last_message || ''}</div>
              </div>
            </div>
          ))}
          {!chatsLoading && dialogs.length === 0 && (
            <div className="hint pad">Нет чатов Telegram. Локальный чат ⚡ всегда сверху.</div>
          )}
        </div>
      </div>
      <div className={`messages-pane ${!activeChat ? 'hidden-mobile' : ''}`}>
        {activeChat ? (
          <>
            <div className="chat-header">
              <button type="button" className="icon-btn mobile-only" onClick={() => setActiveChat(null)}>←</button>
              <span className="chat-title">{activeChat.title}</span>
              <div className="chat-header-badges">
                {isSystemChat(activeChat.id) ? (
                  <span className="chat-badge local">только сайт</span>
                ) : (
                  <>
                    {mutedIds.has(Number(activeChat.id)) && (
                      <span className="chat-badge mute" title="Входящие удаляются">🔇 МУТ</span>
                    )}
                    {aiEnabled && !activeChat.is_group && !activeChat.is_channel && (
                      <span className="chat-badge ai" title="ИИ отвечает в личке">🤖 АВТООТВЕТ</span>
                    )}
                    <span className="live-dot" title="Автообновление">●</span>
                  </>
                )}
              </div>
            </div>
            <div className="messages-list">
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={`bubble ${m.out ? 'out' : 'in'}${m.system ? ' system' : ''}${m.error ? ' sys-error' : ''}`}
                >
                  {!m.out && m.sender && <div className="bubble-sender">{m.sender}</div>}
                  <div className="bubble-text">{m.text}</div>
                  <div className="bubble-time">{m.date}</div>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
            <div className="composer">
              <button type="button" className={`cmd-toggle ${cmdMode || isSystemChat(activeChat.id) ? 'on' : ''}`} title="Команды" onClick={() => setCmdMode((v) => !v)}>| / |</button>
              <input
                className="composer-input"
                placeholder={
                  isSystemChat(activeChat.id)
                    ? 'help | status | ai test | ai on'
                    : (cmdMode ? 'help | status | ai test | mute' : 'Сообщение...')
                }
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
        <p>Кнопка <b>| / |</b> у поля ввода включает режим команд.</p>
        <ul className="cmd-list">
          <li><code>help</code> — список команд</li>
          <li><code>spam слово 10</code> — повторить (макс 20)</li>
          <li><code>mute</code> — удалять ВСЕ входящие в этом чате (текст, фото, видео, стикеры…)</li>
          <li><code>unmute</code> — снять mute</li>
          <li><code>status</code> — mute, ИИ и последняя ошибка</li>
          <li><code>id</code> — id чата</li>
          <li><code>ping</code> — проверка</li>
          <li><code>me</code> — кто я</li>
          <li><code>ai on</code> / <code>ai off</code> — автоответ ИИ</li>
          <li><code>ai test</code> — проверить ИИ (ответ/ошибка на экране)</li>
          <li><code>reply текст</code> — отправить от себя</li>
          <li><code>info</code> — инфа о чате</li>
          <li><code>clear 5</code> — удалить свои последние N сообщений</li>
        </ul>
      </div>
    )
    if (activeMenu === 'ai') {
      const prov = AI_PROVIDERS.find(p => p.id === aiProvider) || AI_PROVIDERS[0]
      return (
        <div className="panel">
          <h2>ИИ автоответ</h2>
          <p className="hint">Когда в личку приходит текст и галочка включена — ИИ отвечает вместо вас. Бесплатно: Groq или OpenRouter модели с :free.</p>
          <label className="toggle" style={{marginBottom: 16}}>
            <input type="checkbox" checked={aiEnabled} onChange={(e)=>onAiToggle(e.target.checked)} />
            <span>{aiEnabled ? 'Автоответ включён' : 'Автоответ выключен'}</span>
          </label>

          {aiLastError ? (
            <div className="ai-error-box" style={{
              background: 'rgba(220,60,60,0.15)',
              border: '1px solid rgba(220,60,60,0.5)',
              borderRadius: 8,
              padding: '10px 12px',
              marginBottom: 14,
              color: '#ffb4b4',
              fontSize: 13,
              lineHeight: 1.4,
              whiteSpace: 'pre-wrap',
            }}>
              <strong>Ошибка ИИ:</strong><br />
              {aiLastError}
              <div style={{marginTop: 8, opacity: 0.9}}>
                Что сделать: проверь ключ, подожди при 429, или смени модель на бесплатную (Groq / :free в OpenRouter).
              </div>
            </div>
          ) : null}

          <label className="field-label">Выберите тип</label>
          <select
            className="field-input"
            value={aiProvider}
            onChange={(e) => {
              const id = e.target.value
              setAiProvider(id)
              const p = AI_PROVIDERS.find(x => x.id === id)
              if (p) setAiModel(p.model)
              setAiMsg('')
              setAiLastError('')
            }}
          >
            {AI_PROVIDERS.map(p => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>

          <p className="hint" style={{marginTop: 12}}>
            <a href={prov.url} target="_blank" rel="noreferrer" className="ai-key-link">
              нажми сюда чтобы получить ключ, но сначала зарегистрируйся
            </a>
          </p>

          <label className="field-label">API ключ</label>
          <input
            className="field-input"
            type="password"
            placeholder="введите API ключ"
            value={aiApiKey}
            onChange={(e)=>setAiApiKey(e.target.value)}
          />

          <label className="field-label">Бесплатная модель</label>
          <select
            className="field-input"
            value={(freeModels[aiProvider] || []).includes(aiModel) ? aiModel : '__custom__'}
            onChange={(e) => {
              const v = e.target.value
              if (v !== '__custom__') setAiModel(v)
            }}
          >
            {(freeModels[aiProvider] || []).map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
            <option value="__custom__">Другая (ввести вручную)…</option>
          </select>
          {!(freeModels[aiProvider] || []).includes(aiModel) && (
            <input
              className="field-input"
              style={{ marginTop: 8 }}
              type="text"
              placeholder="имя модели"
              value={aiModel}
              onChange={(e) => setAiModel(e.target.value)}
            />
          )}
          <p className="hint" style={{ marginTop: 6, fontSize: 12 }}>
            {aiProvider === 'groq' && 'Актуальные бесплатные Groq: openai/gpt-oss-20b, openai/gpt-oss-120b, qwen/qwen3.8-27b'}
            {aiProvider === 'openrouter' && 'Бесплатно — модели с суффиксом :free'}
            {aiProvider === 'openai' && 'Платно: gpt-4o-mini / gpt-3.5-turbo'}
          </p>

          <button type="button" className="primary-btn" style={{ marginTop: 16 }} disabled={aiSaving} onClick={saveAiSettings}>
            {aiSaving ? 'Сохранение…' : 'Сохранить'}
          </button>
          {aiMsg && <p className="hint" style={{ marginTop: 8 }}>{aiMsg}</p>}
          <button type="button" className="secondary-panel-btn" style={{ marginTop: 8 }} onClick={() => loadAiSettings()}>
            Загрузить с сервера
          </button>
          <button
            type="button"
            className="secondary-panel-btn"
            style={{ marginTop: 8 }}
            onClick={() => { setAiLastError(''); loadAiSettings() }}
          >
            Обновить ошибку / статус
          </button>
          <p className="hint" style={{ marginTop: 12, fontSize: 12 }}>
            Проверка: в чате напиши <code>ai test</code> — ответ или ошибка появятся на экране.
          </p>
        </div>
      )
    }
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
                onClick={()=>{setActiveMenu(item.id);setMenuOpen(false);if(item.id==='chats')loadDialogs();if(item.id==='ai')loadAiSettings()}}>
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
