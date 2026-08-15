import React, { useState, useEffect } from 'react'
import PracticeApp from './PracticeApp.jsx'

/* ============ Helpers ============ */
function phonePrefix(el) {
  const v = el.target.value
  if (v.indexOf('+998') !== 0) {
    const d = v.replace(/[^0-9]/g, '').replace(/^998/, '')
    el.target.value = '+998 ' + d.slice(0, 9)
  }
}

async function postForm(url, data) {
  const fd = new FormData()
  Object.keys(data).forEach(k => fd.append(k, data[k]))
  const r = await fetch(url, { method: 'POST', body: fd })
  return { ok: r.ok, status: r.status, url: r.url }
}

/* ============ Navbar ============ */
function Navbar({ onNavigate }) {
  return (
    <nav className="nav">
      <div className="nav-inner">
        <div className="logo" onClick={() => onNavigate('landing')}>
          <div className="logo-icon">🎙️</div>
          <div className="logo-text">
            <span className="logo-main">Multilevel</span>
            <span className="logo-domain">Mock Test</span>
          </div>
        </div>
        <div className="nav-links">
          <a href="#features">Imkoniyatlar</a>
          <a href="#how">Qanday ishlaydi</a>
          <a href="#pricing">Tariflar</a>
          <a href="#faq">Savollar</a>
        </div>
        <button className="btn btn-primary btn-sm" onClick={() => onNavigate('register')}>Bepul boshlash</button>
      </div>
    </nav>
  )
}

/* ============ Hero ============ */
function Hero({ onNavigate }) {
  return (
    <section className="hero">
      <div className="hero-inner">
        <div className="hero-badge">🎯 CEFR Speaking — professional tayyorgarlik</div>
        <h1 className="hero-title">
          Speaking darajangizni <span className="grad">real imtihon formatida</span> oshiring
        </h1>
        <p className="hero-sub">
          Haqiqiy imtihon formatida speaking mashq qiling. Model javoblar, ovozli yozib olish va vaqt nazorati — hammasi bir joyda.
        </p>
        <div className="hero-cta">
          <button className="btn btn-primary btn-lg" onClick={() => onNavigate('register')}>🚀 Bepul boshlash</button>
          <a className="btn btn-outline btn-lg" href="#how">Qanday ishlaydi?</a>
        </div>
        <div className="hero-stats">
          <div className="stat"><div className="stat-v">4</div><div className="stat-l">Speaking bo’limi</div></div>
          <div className="stat"><div className="stat-v">100+</div><div className="stat-l">Savol</div></div>
          <div className="stat"><div className="stat-v">B2+</div><div className="stat-l">Model javoblar</div></div>
          <div className="stat"><div className="stat-v">24/7</div><div className="stat-l">Kirish</div></div>
        </div>
      </div>
    </section>
  )
}

/* ============ Features ============ */
function Features() {
  const items = [
    { icon: '🎯', title: 'Real imtihon formati', desc: 'CEFR imtihonlari bilan bir xil vaqt, savol turlari va tuzilma.' },
    { icon: '🎙️', title: 'Ovozli yozib olish', desc: 'Har bir javobingiz avtomatik yozib olinadi — keyin tinglab, xatolaringizni ko’rasiz.' },
    { icon: '📋', title: 'Model javoblar', desc: 'Har bir savolga B2+ darajadagi namunaviy javob — qanday javob berishni o’rganing.' },
    { icon: '⏱️', title: 'Vaqt nazorati', desc: 'Aynan imtihondagidek — tayyorgarlik va javob vaqtlari avtomatik hisoblanadi.' },
    { icon: '📊', title: 'Barcha bo’limlar', desc: 'Part 1, Part 1.2, Part 2, Part 3 — hammasi.' },
    { icon: '📱', title: 'Mobil versiya', desc: 'Telefoningizda ham ishlaydi — istalgan joyda mashq qiling.' },
  ]
  return (
    <section id="features" className="section">
      <div className="container">
        <div className="section-head">
          <h2>Imkoniyatlar</h2>
          <p>Speaking darajangizni oshirish uchun kerakli hamma narsa</p>
        </div>
        <div className="features-grid">
          {items.map((f, i) => (
            <div className="feature-card" key={i}>
              <div className="feature-icon">{f.icon}</div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ============ How it works ============ */
function HowItWorks() {
  const steps = [
    { title: 'Ro’yxatdan o’ting', desc: 'Telefon raqamingiz bilan 30 soniyada ro’yxatdan o’ting.' },
    { title: 'Bo’lim tanlang', desc: 'Part 1, 1.2, 2 yoki 3 — kerakli bo’limni tanlang.' },
    { title: 'Savollarga javob bering', desc: 'Imtihon vaqt chegaralari bilan ovozli javob yozing.' },
    { title: 'Natijani ko’ring', desc: 'Javoblaringizni tinglang, o’zingizni baholang.' },
  ]
  return (
    <section id="how" className="section section-alt">
      <div className="container">
        <div className="section-head">
          <h2>Qanday ishlaydi?</h2>
          <p>4 oddiy qadam — darhol speaking mashqini boshlang</p>
        </div>
        <div className="steps-grid">
          {steps.map((s, i) => (
            <div className="step-card" key={i}>
              <div className="step-num">{i + 1}</div>
              <h3>{s.title}</h3>
              <p>{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ============ Pricing ============ */
function Pricing() {
  const [plans, setPlans] = useState([])
  useEffect(() => {
    fetch('/api/plans').then(r => r.json()).then(setPlans).catch(() => {})
  }, [])
  const features = ['Barcha bo’limlar', 'Model javoblar', 'Cheksiz mashq', 'Ovozli yozib olish', 'Mock test']
  const base = plans.length ? plans[0].price : 0
  return (
    <section id="pricing" className="section">
      <div className="container">
        <div className="section-head">
          <h2>Tariflar</h2>
          <p>Bepul ko’rishdan keyin o’zingizga mos tarifni tanlang</p>
        </div>
        <div className="pricing-grid">
          {plans.map((p, i) => {
            const months = p.days ? Math.round(p.days / 30) : 1
            const perMonth = p.days ? Math.round(p.price / months) : p.price
            const savings = months > 1 && base > 0 ? (base * months) - p.price : 0
            return (
              <div className={`plan-card ${i === 1 ? 'popular' : ''}`} key={p.id}>
                {i === 1 && <div className="plan-badge">Eng mashhur</div>}
                <h3>{p.name}</h3>
                <div className="plan-price">{p.price_fmt}</div>
                {months > 1 && <div className="plan-per">{perMonth.toLocaleString('ru-RU')} so’m / oy</div>}
                {savings > 0 && <div className="plan-save">Tejaysiz: {savings.toLocaleString('ru-RU')} so’m</div>}
                <div className="plan-period">{p.days} kun davom etadi</div>
                <ul className="plan-features">
                  {features.map((f, j) => <li key={j}>✓ {f}</li>)}
                </ul>
                <a className="btn btn-primary" href="/paywall">Boshlash</a>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}

/* ============ FAQ ============ */
function FAQ() {
  const [open, setOpen] = useState(0)
  const items = [
    { q: 'Bepul nimalar bor?', a: 'Har bo’limdan bir nechta savol, rasm yoki karta bepul. Part 1.1 dan dastlabki savollar, Part 1.2 dan 1 rasm, Part 2 dan 1 karta, Part 3 dan 1 rasm bepul.' },
    { q: 'Qanday to’lov qilish mumkin?', a: 'Karta raqamiga pul o’tkazib, chekni Telegram (@rahmatovturgun) yoki sayt orqali yuborasiz. Admin tasdiqlagach kirish ochiladi.' },
    { q: 'Obuna qancha muddatga?', a: '1 oylik, 2 oylik va 3 oylik obunalar bor. Muddat tugagach uzaytirishingiz mumkin.' },
    { q: 'Mikrofon kerakmi?', a: 'Ha, javob berish uchun mikrofon kerak. Brauzer mikrofon ruxsatini so’raydi.' },
    { q: 'Telefonda ishlaydimi?', a: 'Ha, mobil versiya mavjud. Telefon brauzerida ishlaydi.' },
  ]
  return (
    <section id="faq" className="section section-alt">
      <div className="container">
        <div className="section-head"><h2>Ko’p so’raladigan savollar</h2></div>
        <div className="faq-list">
          {items.map((item, i) => (
            <div className={`faq-item ${open === i ? 'open' : ''}`} key={i}>
              <button className="faq-q" onClick={() => setOpen(open === i ? -1 : i)}>
                {item.q}<span className="arrow">▾</span>
              </button>
              <div className="faq-a">{item.a}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

/* ============ Register form ============ */
function RegisterForm({ onSuccess }) {
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('+998 ')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    if (phone.trim().replace(/\s/g, '').length < 10) { setError('Telefon raqamni to’liq kiriting'); return }
    if (password.length < 4) { setError('Parol kamida 4 belgi'); return }
    const r = await postForm('/auth/register', { name, phone, password })
    if (r.ok) { onSuccess() } else { setError('Ro’yxatdan o’tishda xatolik') }
  }

  return (
    <form className="auth-form" onSubmit={handleSubmit}>
      <h3>Ro’yxatdan o’tish</h3>
      <p className="auth-sub">30 soniyada — bepul</p>
      {error && <div className="auth-error">{error}</div>}
      <div className="field"><label>Ismingiz</label><input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Ismingiz" /></div>
      <div className="field"><label>Telefon raqam</label><input type="text" value={phone} onChange={e => { setPhone(e.target.value); phonePrefix(e) }} placeholder="+998 90 123 45 67" /></div>
      <div className="field"><label>Parol (kamida 4 belgi)</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" /></div>
      <button type="submit" className="btn btn-primary btn-lg btn-full">🚀 Bepul boshlash</button>
      <p className="auth-foot">Allaqachon ro’yxatdan o’tganmisiz? <a href="/paywall">Kirish</a></p>
    </form>
  )
}

/* ============ Landing ============ */
function Landing() {
  const [showRegister, setShowRegister] = useState(false)
  function onRegisterSuccess() { window.location.href = '/' }
  function goRegister() {
    setShowRegister(true)
    setTimeout(() => {
      const el = document.getElementById('register-section')
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    }, 120)
  }
  return (
    <div>
      <Navbar onNavigate={goRegister} />
      <Hero onNavigate={goRegister} />
      <Features />
      <HowItWorks />
      {showRegister ? (
        <section className="section" id="register-section">
          <div className="container"><RegisterForm onSuccess={onRegisterSuccess} /></div>
        </section>
      ) : null}
      <Pricing />
      <FAQ />
      <footer className="footer">
        <div className="container footer-inner">
          <span>© 2026 Multilevel Mock Test</span>
          <div className="footer-links">
            <a href="#features">Imkoniyatlar</a>
            <a href="#pricing">Tariflar</a>
            <a href="#faq">Savollar</a>
            <a href="/paywall">Kirish</a>
          </div>
        </div>
      </footer>
    </div>
  )
}

/* ============ Paywall ============ */
function Paywall() {
  const [tab, setTab] = useState('login')
  const [plans, setPlans] = useState([])
  const [selPlan, setSelPlan] = useState(null)
  const [card, setCard] = useState(null)
  const [phone, setPhone] = useState('+998 ')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const [file, setFile] = useState(null)
  const [hint, setHint] = useState('')

  useEffect(() => {
    fetch('/api/plans').then(r => r.json()).then(d => { setPlans(d); setSelPlan(d[0]) }).catch(() => {})
    fetch('/api/config-public').then(r => r.json()).then(setCard).catch(() => {})
  }, [])

  async function handleAuth(e) {
    e.preventDefault()
    setError('')
    if (tab === 'login') {
      const r = await postForm('/auth/login', { phone, password })
      if (r.ok) { window.location.href = '/' } else { setError('Telefon yoki parol noto’g’ri') }
    } else {
      if (password.length < 4) { setError('Parol kamida 4 belgi'); return }
      const r = await postForm('/auth/register', { name, phone, password })
      if (r.ok) { window.location.reload() } else { setError('Ro’yxatdan o’tishda xatolik') }
    }
  }

  async function startPay() {
    if (!selPlan) return
    if (!file) { alert('Iltimos, to’lov chekini yuklang'); return }
    const fd = new FormData()
    fd.append('plan_id', selPlan.id)
    fd.append('receipt', file)
    const r = await fetch('/api/pay/checkout', { method: 'POST', body: fd })
    const d = await r.json()
    if (d.ok) { setHint('✅ To’lov #' + d.payment_id + ' qabul qilindi. Admin tekshirib tasdiqlaydi.') } else { alert(d.error || 'Xatolik') }
  }

  return (
    <div className="paywall-wrap">
      <div className="paywall-card">
        <div className="tabs">
          <button className={`tab ${tab === 'login' ? 'active' : ''}`} onClick={() => setTab('login')}>Kirish</button>
          <button className={`tab ${tab === 'register' ? 'active' : ''}`} onClick={() => setTab('register')}>Ro’yxatdan o’tish</button>
        </div>
        {error && <div className="auth-error">{error}</div>}
        <form onSubmit={handleAuth}>
          {tab === 'register' && <div className="field"><label>Ismingiz</label><input type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Ismingiz" /></div>}
          <div className="field"><label>Telefon raqam</label><input type="text" value={phone} onChange={e => { setPhone(e.target.value); phonePrefix(e) }} placeholder="+998 90 123 45 67" /></div>
          <div className="field"><label>Parol</label><input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••" /></div>
          <button type="submit" className="btn btn-primary btn-lg btn-full">{tab === 'login' ? 'Kirish' : 'Ro’yxatdan o’tish'}</button>
        </form>

        <h3 className="plans-title">Tarif tanlang</h3>
        <div className="plans-list">
          {plans.map(p => (
            <div className={`plan-opt ${selPlan && selPlan.id === p.id ? 'selected' : ''}`} key={p.id} onClick={() => setSelPlan(p)}>
              <span className="po-name">{p.name}</span>
              <span className="po-price">{p.price_fmt}</span>
            </div>
          ))}
        </div>

        <div className="card-box">
          <div className="card-label">To’lov kartasi</div>
          <div className="card-num">{card ? card.card_number : '—'}</div>
          <div className="card-holder">{card ? card.card_holder : '—'}</div>
        </div>

        <div className="tg-box">
          <div className="tg-title">📱 Telegram orqali sotib olish</div>
          <p className="tg-text">Pulni kartaga o’tkazing, so’ng xabarni Telegramga yuboring (chekni ilova qiling):</p>
          <div className="tg-msg">Assalomu aleykum, men sizni website ingizni premium package ini sotib olmoqchiman</div>
          <div className="tg-actions">
            <button className="btn btn-outline" onClick={() => navigator.clipboard.writeText('Assalomu aleykum, men sizni website ingizni premium package ini sotib olmoqchiman')}>📋 Nusxalash</button>
            <a className="btn btn-telegram" href="https://t.me/rahmatovturgun" target="_blank">📤 Telegram</a>
          </div>
        </div>

        <div className="file-upload" onClick={() => document.getElementById('receipt').click()}>
          📸 To’lov chekini yuklang (skrinshot)
          <input id="receipt" type="file" accept="image/*,.pdf" style={{ display: 'none' }} onChange={e => setFile(e.target.files[0])} />
        </div>
        {file && <div className="file-name">📎 {file.name}</div>}
        <button className="btn btn-primary btn-lg btn-full" onClick={startPay}>📤 Chekni yuborish</button>
        {hint && <div className="hint">{hint}</div>}
      </div>
    </div>
  )
}

/* ============ App ============ */
export default function App() {
  const [state, setState] = useState('loading')
  const [me, setMe] = useState(null)

  useEffect(() => {
    const path = window.location.pathname
    fetch('/api/me').then(r => r.json()).then(m => {
      setMe(m)
      if (m.ok) {
        // Logged in → practice app (freemium: free trial then premium)
        setState('practice')
        return
      }
      if (path === '/paywall') {
        setState('paywall')
      } else {
        setState('landing')
      }
    }).catch(() => setState('landing'))
  }, [])

  function logout() {
    window.location.href = '/logout'
  }

  if (state === 'loading') {
    return <div className="loading"><div className="spinner" /></div>
  }
  if (state === 'practice') {
    return <PracticeApp hasAccess={!!(me && me.access)} onLogout={logout} />
  }
  if (state === 'paywall') {
    return <Paywall />
  }
  return <Landing />
}
