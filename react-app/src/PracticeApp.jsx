import React, { useState, useEffect, useRef } from 'react'
import { SAVOLLAR, PART12_SETS, PART2_CARDS, SAMPLES, PART2_SAMPLES, PART12_SAMPLES, PART3_SAMPLES } from './data.js'
import { speakQuestion, speakSample, stopSpeech, startRecording, stopRecording, teardownMic, getWaveAnalyser, isMicActive } from './audio.js'

const PREP_SEC = 5, ANSWER_SEC = 30
const PART2_PREP = 60, PART2_ANS = 120
const PART3_PREP = 60, PART3_ANS = 120
const PART3_IMAGES = Array.from({ length: 31 }, (_, i) => 'part3/' + (i + 1) + '.jpg')

function getSample(q, img) {
  if (img && PART12_SAMPLES[img]) return PART12_SAMPLES[img][q] || null
  if (img && PART3_SAMPLES[img]) return PART3_SAMPLES[img]
  return SAMPLES[q] || PART2_SAMPLES[q] || null
}

const PARTS = [
  { id: 'p1', label: 'Speaking Part 1.1', desc: 'Questions on the topic — 5s + 30s', icon: '🎤' },
  { id: 'p2', label: 'Speaking Part 1.2', desc: 'Pictures with questions — 10s + 45s', icon: '🖼️' },
  { id: 'p3', label: 'Speaking Part 2', desc: 'Cue card — 60s prep + 120s speaking', icon: '📋' },
  { id: 'p4', label: 'Speaking Part 3', desc: 'Task card (picture) — 60s prep + 120s', icon: '📊' },
]

function SubscribePlans() {
  const [plans, setPlans] = useState([])
  useEffect(() => {
    fetch('/api/plans').then(r => r.json()).then(setPlans).catch(() => {})
  }, [])
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginTop: 16 }}>
      {plans.map(p => (
        <div key={p.id} style={{ border: '1.5px solid var(--border)', borderRadius: 12, padding: 16, textAlign: 'center', background: '#fff' }}>
          <div style={{ fontWeight: 800, fontSize: 14 }}>{p.name}</div>
          <div style={{ color: 'var(--primary)', fontWeight: 900, fontSize: 20, margin: '6px 0' }}>{p.price_fmt}</div>
          <div style={{ color: 'var(--muted)', fontSize: 12 }}>{p.days} kun</div>
        </div>
      ))}
    </div>
  )
}

export default function PracticeApp({ hasAccess, onLogout }) {
  const [screen, setScreen] = useState('setup')
  const [selectedPart, setSelectedPart] = useState('p1')
  const [showSamples, setShowSamples] = useState(true)

  // selection state
  const [selGroupStart, setSelGroupStart] = useState(0)
  const [selGroupEnd, setSelGroupEnd] = useState(0)
  const [picSelStart, setPicSelStart] = useState(0)
  const [picTotal, setPicTotal] = useState(PART12_SETS.length)
  const [cardStart, setCardStart] = useState(0)
  const [cardEnd, setCardEnd] = useState(0)
  const [taskStart, setTaskStart] = useState(0)
  const [taskTotal, setTaskTotal] = useState(PART3_IMAGES.length)

  // practice state
  const [questions, setQuestions] = useState([])
  const [modePics, setModePics] = useState([])
  const [cuePoints, setCuePoints] = useState([])
  const [prepSecs, setPrepSecs] = useState([])
  const [ansSecs, setAnsSecs] = useState([])
  const [mode, setMode] = useState('q')
  const [idx, setIdx] = useState(0)
  const [phase, setPhase] = useState('prep')
  const [timer, setTimer] = useState(0)
  const [results, setResults] = useState([])
  const [sample, setSample] = useState(null)
  const [sampleShown, setSampleShown] = useState(false)
  const [paused, setPaused] = useState(false)
  const [micStatus, setMicStatus] = useState('Listen to the question...')

  const timerRef = useRef(null)
  const phaseRef = useRef('prep')
  const idxRef = useRef(0)
  const questionsRef = useRef([])
  const modePicsRef = useRef([])
  const prepSecsRef = useRef([])
  const ansSecsRef = useRef([])
  const pausedRef = useRef(false)
  const canvasRef = useRef(null)
  const waveRaf = useRef(null)

  useEffect(() => {
    function drawWave() {
      waveRaf.current = requestAnimationFrame(drawWave)
      const canvas = canvasRef.current
      if (!canvas) return
      const ctx = canvas.getContext('2d')
      const w = canvas.width, h = canvas.height
      ctx.clearRect(0, 0, w, h)
      const analyser = getWaveAnalyser()
      const micOn = isMicActive() && analyser
      if (micOn) {
        const buf = new Uint8Array(analyser.fftSize)
        analyser.getByteTimeDomainData(buf)
        ctx.strokeStyle = '#3b82f6'
        ctx.lineWidth = 2.5
        ctx.lineJoin = 'round'
        ctx.beginPath()
        const step = buf.length / w
        for (let i = 0; i < w; i++) {
          const v = buf[Math.floor(i * step)] / 128.0 - 1.0
          const y = (v * 0.75 + 0.5) * h
          if (i === 0) ctx.moveTo(i, y); else ctx.lineTo(i, y)
        }
        ctx.stroke()
        ctx.strokeStyle = 'rgba(59,130,246,.18)'
        ctx.lineWidth = 1
        ctx.beginPath(); ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2); ctx.stroke()
      } else {
        ctx.strokeStyle = '#e5e7eb'
        ctx.lineWidth = 2
        ctx.beginPath(); ctx.moveTo(0, h / 2); ctx.lineTo(w, h / 2); ctx.stroke()
      }
    }
    drawWave()
    return () => cancelAnimationFrame(waveRaf.current)
  }, [])

  function clearTimer() { if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null } }
  function startTimer(seconds, onEnd) {
    clearTimer()
    let remain = seconds
    setTimer(seconds)
    timerRef.current = setInterval(() => {
      remain--
      setTimer(remain)
      if (remain <= 0) { clearTimer(); onEnd() }
    }, 1000)
  }
  function fmtTime(s) { if (s >= 60) return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); return s }
  function setPhaseAndRef(p) { setPhase(p); phaseRef.current = p }

  function startAnswer() {
    stopSpeech()
    setPhaseAndRef('answer')
    setMicStatus('Microphone is recording your answer...')
    startRecording()
    startTimer(ansSecsRef.current[idxRef.current] || ANSWER_SEC, () => afterAnswer())
  }

  async function afterAnswer() {
    clearTimer()
    stopSpeech()
    const rec = await stopRecording()
    const q = questionsRef.current[idxRef.current]
    const img = modePicsRef.current[idxRef.current]
    setResults(prev => [...prev, { question: q, rec, img }])
    const s = showSamples ? getSample(q, img) : null
    if (s) {
      setSample(s); setSampleShown(true); setPhaseAndRef('sample')
      setMicStatus('Sample answer is being read aloud...')
      speakSample(s, () => setTimeout(() => nextQuestion(), 800))
    } else {
      nextQuestion()
    }
  }

  function nextQuestion() {
    const next = idxRef.current + 1
    if (next >= questionsRef.current.length) {
      if (!hasAccess) setScreen('subscribe'); else setScreen('results')
      teardownMic()
      return
    }
    idxRef.current = next; setIdx(next)
    setSampleShown(false); setSample(null)
    setPhaseAndRef('prep')
    setMicStatus('Listen to the question...')
    const q = questionsRef.current[next]
    speakQuestion(q, () => startTimer(prepSecsRef.current[next] || PREP_SEC, () => startAnswer()))
  }

  function startFlow(qs, pics, cps, ps, as, m) {
    questionsRef.current = qs; modePicsRef.current = pics; prepSecsRef.current = ps; ansSecsRef.current = as
    setQuestions(qs); setModePics(pics); setCuePoints(cps); setPrepSecs(ps); setAnsSecs(as); setMode(m)
    setResults([])
    idxRef.current = 0; setIdx(0)
    setScreen('practice'); setPhaseAndRef('prep')
    setMicStatus('Listen to the question...')
    speakQuestion(qs[0], () => startTimer(ps[0], () => startAnswer()))
  }

  function beginPractice() {
    let qs = [], pics = [], cps = [], ps = [], as = [], m = 'q'
    if (selectedPart === 'p1') {
      const start = selGroupStart, end = selGroupEnd === 0 ? SAVOLLAR.length : selGroupEnd
      qs = SAVOLLAR.slice(start, end)
      m = 'q'
    } else if (selectedPart === 'p2') {
      const sets = PART12_SETS.slice(picSelStart, picSelStart + picTotal)
      sets.forEach(s => s.q.forEach(q => { qs.push(q); pics.push(s.img) }))
      m = 'pic'
    } else if (selectedPart === 'p3') {
      const cards = PART2_CARDS.slice(cardStart, cardEnd === 0 ? PART2_CARDS.length : cardEnd)
      cards.forEach(c => { qs.push(c.q); cps.push(c.p || []) })
      m = 'p2'
    } else if (selectedPart === 'p4') {
      const imgs = PART3_IMAGES.slice(taskStart, taskStart + taskTotal)
      imgs.forEach(img => { qs.push('Speaking Part 3 — task card'); pics.push(img) })
      m = 'p3'
    }
    ps = qs.map(() => (m === 'p2' || m === 'p3' ? 60 : m === 'pic' ? 10 : PREP_SEC))
    as = qs.map(() => (m === 'p2' || m === 'p3' ? 120 : m === 'pic' ? 45 : ANSWER_SEC))
    cps = qs.map((_, i) => cps[i] || [])
    startFlow(qs, pics, cps, ps, as, m)
  }

  function beginMock() {
    // Full mock: Part 1.1 (3 q) + Part 1.2 (1 pic 3 q) + Part 2 (1 card) + Part 3 (1 task)
    const qs = [], pics = [], cps = [], ps = [], as = []
    const p1 = SAVOLLAR.slice(0, 3)
    p1.forEach(q => { qs.push(q); pics.push(null); cps.push([]); ps.push(PREP_SEC); as.push(ANSWER_SEC) })
    const set = PART12_SETS[0]
    set.q.forEach(q => { qs.push(q); pics.push(set.img); cps.push([]); ps.push(10); as.push(45) })
    const card = PART2_CARDS[0]
    qs.push(card.q); pics.push(null); cps.push(card.p || []); ps.push(PART2_PREP); as.push(PART2_ANS)
    const img = PART3_IMAGES[0]
    qs.push('Speaking Part 3 — task card'); pics.push(img); cps.push([]); ps.push(PART3_PREP); as.push(PART3_ANS)
    startFlow(qs, pics, cps, ps, as, 'mock')
  }

  function skip() {
    stopSpeech(); clearTimer()
    if (phaseRef.current === 'prep') startAnswer()
    else if (phaseRef.current === 'answer') afterAnswer()
    else if (phaseRef.current === 'sample') nextQuestion()
  }

  function pauseResume() {
    if (phaseRef.current === 'sample') {
      if (pausedRef.current) { pausedRef.current = false; setPaused(false); setMicStatus('Sample answer is being read aloud...'); speakSample(sample, () => setTimeout(() => nextQuestion(), 800)) }
      else { pausedRef.current = true; setPaused(true); stopSpeech(); setMicStatus('Sample paused') }
    } else {
      if (pausedRef.current) { pausedRef.current = false; setPaused(false); if (phaseRef.current === 'answer') setMicStatus('Microphone is recording...') }
      else { pausedRef.current = true; setPaused(true); setMicStatus('Paused') }
    }
  }

  function goHome() {
    stopSpeech(); clearTimer(); teardownMic()
    setScreen('setup'); setPhaseAndRef('prep'); setResults([])
  }

  /* ============ GROUP OPTIONS ============ */
  function groupOptions() {
    if (selectedPart === 'p1') {
      const n = SAVOLLAR.length
      const groups = [{ from: 0, to: 0, label: 'All (1–' + n + ')', all: true }]
      for (let f = 0; f < n; f += 3) {
        const t = Math.min(f + 3, n)
        if (t - f === n) continue
        groups.push({ from: f, to: t, label: (f + 1) + '–' + t })
      }
      return groups
    } else if (selectedPart === 'p2') {
      const n = PART12_SETS.length
      const groups = [{ from: 0, to: 0, label: 'All pictures (1–' + n + ')', all: true }]
      for (let f = 0; f < n; f++) groups.push({ from: f, to: 1, label: 'Picture ' + (f + 1) })
      return groups
    } else if (selectedPart === 'p3') {
      const n = PART2_CARDS.length
      const groups = [{ from: 0, to: 0, label: 'All cards (1–' + n + ')', all: true }]
      for (let f = 0; f < n; f++) groups.push({ from: f, to: 1, label: String(f + 1) })
      return groups
    } else {
      const n = PART3_IMAGES.length
      const groups = [{ from: 0, to: 0, label: 'All tasks (1–' + n + ')', all: true }]
      for (let f = 0; f < n; f++) groups.push({ from: f, to: 1, label: String(f + 1) })
      return groups
    }
  }

  function isGroupSelected(g) {
    if (selectedPart === 'p1') return g.all ? selGroupEnd === 0 : (selGroupStart === g.from && selGroupEnd === g.to)
    if (selectedPart === 'p2') return g.all ? picTotal === PART12_SETS.length : (picSelStart === g.from && picTotal === 1)
    if (selectedPart === 'p3') return g.all ? cardEnd === 0 : (cardStart === g.from && cardEnd === 1)
    return g.all ? taskTotal === PART3_IMAGES.length : (taskStart === g.from && taskTotal === 1)
  }

  function selectGroup(g) {
    if (selectedPart === 'p1') { setSelGroupStart(g.from); setSelGroupEnd(g.all ? 0 : g.to) }
    else if (selectedPart === 'p2') { setPicSelStart(g.from); setPicTotal(g.all ? PART12_SETS.length : 1) }
    else if (selectedPart === 'p3') { setCardStart(g.from); setCardEnd(g.all ? 0 : 1) }
    else { setTaskStart(g.from); setTaskTotal(g.all ? PART3_IMAGES.length : 1) }
  }

  const groupTitle = selectedPart === 'p1' ? 'Choose a group of questions'
    : selectedPart === 'p2' ? 'Choose pictures (each picture has 3 questions)'
    : selectedPart === 'p3' ? 'Choose a group of cue cards'
    : 'Choose a task card'

  /* ============ SETUP ============ */
  if (screen === 'setup') {
    return (
      <div className="prac-wrap">
        <div className="prac-top">
          <h1 className="prac-title">Multilevel Mock Test</h1>
          <p className="prac-sub">CEFR Speaking — professional tayyorgarlik</p>
        </div>
        <div className="prac-card">
          <div className="prac-section-title">Choose the exam part</div>
          <div className="part-grid">
            {PARTS.map(p => (
              <div key={p.id} className={`part-btn ${selectedPart === p.id ? 'active' : ''}`} onClick={() => setSelectedPart(p.id)}>
                <span className="part-icon">{p.icon}</span>
                <span className="part-label">{p.label}</span>
                <span className="part-desc">{p.desc}</span>
              </div>
            ))}
          </div>

          <div className="group-panel">
            <div className="group-title">{groupTitle}</div>
            <div className="group-list">
              {groupOptions().map((g, i) => (
                <button key={i} className={`group-btn ${isGroupSelected(g) ? 'active' : ''}`} onClick={() => selectGroup(g)}>
                  {g.label}
                </button>
              ))}
            </div>
          </div>

          <label className="toggle-row">
            <input type="checkbox" checked={showSamples} onChange={e => setShowSamples(e.target.checked)} />
            <span>Show B2 sample answers after each answer</span>
          </label>

          <div className="prac-actions">
            <button className="btn btn-primary btn-lg" onClick={beginPractice}>🎯 Start the practice</button>
            <button className="btn btn-outline btn-lg" onClick={beginMock}>📝 Start Full Mock Test</button>
          </div>
        </div>
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <button className="home-float" onClick={onLogout}>🚪 Chiqish</button>
        </div>
      </div>
    )
  }

  /* ============ SUBSCRIBE ============ */
  if (screen === 'subscribe') {
    return (
      <div className="prac-wrap">
        <div className="prac-card" style={{ textAlign: 'center' }}>
          <div className="subscribe-icon">🔒</div>
          <h2 className="subscribe-title">Bepul sinov tugadi</h2>
          <p className="subscribe-sub">Barcha savollarga to'liq kirish uchun obuna (Premium) oling.</p>
          <SubscribePlans />
          <div style={{ marginTop: 18 }}>
            <a className="btn btn-telegram btn-lg" href="https://t.me/rahmatovturgun" target="_blank">📤 Telegram orqali obuna olish</a>
          </div>
          <p style={{ marginTop: 14, color: 'var(--muted)', fontSize: 13 }}>
            Obuna olish uchun Telegramga yozing: "Assalomu aleykum, men sizni website ingizni premium package ini sotib olmoqchiman"
          </p>
          <button className="btn btn-outline" style={{ marginTop: 14 }} onClick={goHome}>⌂ Bosh sahifa</button>
        </div>
      </div>
    )
  }

  /* ============ RESULTS ============ */
  if (screen === 'results') {
    return (
      <div className="prac-wrap">
        <div className="prac-card">
          <div className="prac-section-title">Results</div>
          <div className="result-list">
            {results.map((r, i) => (
              <div className="result-item" key={i}>
                <div className="result-q">{i + 1}. {r.question}</div>
                {r.rec && r.rec.blob && <audio controls src={URL.createObjectURL(r.rec.blob)} style={{ width: '100%', marginTop: 6 }} />}
                {getSample(r.question, r.img) && <div className="result-sample">📋 Sample: {getSample(r.question, r.img).slice(0, 120)}...</div>}
              </div>
            ))}
          </div>
          <div className="prac-actions">
            <button className="btn btn-primary" onClick={goHome}>↺ Start over</button>
          </div>
        </div>
      </div>
    )
  }

  /* ============ PRACTICE ============ */
  const q = questions[idx]
  const isP2 = mode === 'p2'
  const isP3 = mode === 'p3'
  const isPic = mode === 'pic'
  const isMock = mode === 'mock'

  return (
    <div className="prac-wrap">
      <button className="home-float" onClick={goHome}>⌂ Home</button>
      <div className="prac-card">
        <div className="prac-status">
          <span className="prac-counter">
            {isP2 ? 'Cue card ' + (idx + 1) : isP3 ? 'Task ' + (idx + 1) : isPic ? 'Picture ' + (Math.floor(idx / 3) + 1) + ' · Q' + (idx % 3 + 1) + '/3' : 'Question ' + (idx + 1)} / {questions.length}
          </span>
          <span className={`prac-chip ${phase}`}>
            {phase === 'prep' ? 'Preparation' : phase === 'answer' ? 'Answering' : 'Sample answer'}
          </span>
        </div>

        <div className="prac-grid">
          {isPic && modePics[idx] && (
            <div className="prac-pic"><img src={modePics[idx]} alt="Pictures" /></div>
          )}
          <div className="prac-main">
            <div className="prac-question">{q}</div>
            {isP2 && cuePoints[idx] && cuePoints[idx].length > 0 && (
              <div className="prac-cue">
                <div className="prac-cue-label">Cue card points</div>
                <ul>{cuePoints[idx].map((pt, i) => <li key={i}>{pt}</li>)}</ul>
              </div>
            )}
            {isP3 && modePics[idx] && (
              <div className="prac-pic"><img src={modePics[idx]} alt="Task" /></div>
            )}
            <div className="prac-timer">
              <div className="prac-timer-num">{fmtTime(timer)}</div>
              <div className="prac-mic">{micStatus}</div>
            </div>
            <canvas ref={canvasRef} width="480" height="90" className="prac-wave" />
            {sampleShown && sample && (
              <div className="prac-sample">
                <div className="prac-sample-label">Sample answer — B2 level</div>
                <div className="prac-sample-text">{sample}</div>
              </div>
            )}
          </div>
        </div>

        <div className="prac-controls">
          <button className="btn btn-outline" onClick={pauseResume}>{paused ? '▶ Resume' : '⏸ Pause'}</button>
          <button className="btn btn-outline" onClick={skip}>Skip</button>
        </div>
      </div>
    </div>
  )
}
