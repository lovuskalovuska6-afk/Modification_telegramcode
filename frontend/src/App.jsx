import React, { useState } from 'react'
import './App.css'

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)

  return (
    <div className="app">
      {!isLoggedIn ? (
        <div className="login-screen">
          <div className="login-box">
            <h1>Modified Telegram</h1>
            <p>Вход в аккаунт</p>
            <button onClick={() => setIsLoggedIn(true)}>
              Войти (заглушка)
            </button>
          </div>
          <div className="login-footer">
            | модифицированный телеграмм /code |
          </div>
        </div>
      ) : (
        <div className="main-layout">
          <aside className="sidebar">
            <div className="sidebar-header">☰</div>
            <nav className="sidebar-menu">
              <div className="menu-item">Настройки</div>
              <div className="menu-item">Чаты</div>
              <div className="menu-item">Команды</div>
              <div className="menu-item">ИИ автоответ</div>
              <div className="menu-item">Настройки Telegram</div>
              <div className="menu-item">Изменить аккаунт</div>
              <div className="menu-item">Добавить свою команду</div>
              <div className="menu-item">Скрытность</div>
            </nav>
          </aside>
          <main className="chat-area">
            <div className="chat-placeholder">
              Выберите чат или начните новый
            </div>
          </main>
        </div>
      )}
    </div>
  )
}

export default App
