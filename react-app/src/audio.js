/* Audio utils: TTS (speechSynthesis) + mic recording (WebAudio) + waveform */

let _ttsVoices = []

function refreshVoices() {
  try { _ttsVoices = window.speechSynthesis.getVoices() || [] } catch (e) { _ttsVoices = [] }
}

export function pickVoice(pref) {
  refreshVoices()
  return _ttsVoices.find(v => /en(-|_)/i.test(v.lang) && pref.test(v.name))
    || _ttsVoices.find(v => /^en(-|_)/i.test(v.lang))
    || _ttsVoices.find(v => /en/i.test(v.lang))
    || null
}

function waitVoices() {
  return new Promise(resolve => {
    refreshVoices()
    if (_ttsVoices.length) { resolve(); return }
    const start = Date.now()
    const poll = () => {
      refreshVoices()
      if (_ttsVoices.length || Date.now() - start > 1500) { resolve(); return }
      setTimeout(poll, 120)
    }
    poll()
  })
}

let speakChainToken = 0

async function speechReadyForSpeak() {
  await waitVoices()
  let needCancel = false
  try { needCancel = window.speechSynthesis.speaking || window.speechSynthesis.pending } catch (e) { needCancel = true }
  if (needCancel) {
    try { window.speechSynthesis.cancel() } catch (e) {}
    const t0 = Date.now()
    let busy = true
    while (Date.now() - t0 < 600 && busy) {
      try { busy = window.speechSynthesis.speaking || window.speechSynthesis.pending } catch (e) { busy = false }
      await new Promise(r => setTimeout(r, 40))
    }
    await new Promise(r => setTimeout(r, 250))
    try { window.speechSynthesis.cancel() } catch (e) {}
    try { const ru = new SpeechSynthesisUtterance('\u00A0'); ru.volume = 0; window.speechSynthesis.speak(ru); await new Promise(r => setTimeout(r, 80)) } catch (e) {}
    try { window.speechSynthesis.cancel() } catch (e) {}
  }
  try { window.speechSynthesis.resume() } catch (e) {}
}

export function stopSpeech() {
  speakChainToken++
  try { window.speechSynthesis.cancel() } catch (e) {}
}

function splitIntoChunks(text) {
  const sentences = String(text).match(/[^.!?]+[.!?]*/g) || [String(text)]
  const chunks = []
  let cur = ''
  for (const part of sentences) {
    const p = part.trim()
    if (!p) continue
    if (cur && (cur + ' ' + p).length > 200) { chunks.push(cur); cur = p }
    else { cur = cur ? cur + ' ' + p : p }
  }
  if (cur) chunks.push(cur)
  if (!chunks.length) chunks.push(String(text))
  return chunks
}

function speakChunked(chunks, onDone, opts) {
  const token = speakChainToken
  let i = 0
  const next = () => {
    if (token !== speakChainToken) return
    if (i >= chunks.length) { if (onDone) onDone(); return }
    const u = new SpeechSynthesisUtterance(chunks[i])
    u.lang = 'en-US'
    u.rate = opts.rate
    u.pitch = opts.pitch
    if (opts.voice) { u.voice = opts.voice; u.lang = opts.voice.lang }
    u.onend = () => setTimeout(next, 40)
    u.onerror = () => { if (token === speakChainToken) setTimeout(next, 60) }
    i++
    try { window.speechSynthesis.speak(u) } catch (e) { next() }
  }
  next()
}

export async function speakQuestion(text, onDone) {
  try {
    await speechReadyForSpeak()
    speakChainToken++
    const chunks = splitIntoChunks(text)
    const voice = pickVoice(/samantha|karen|zira|jenny|aria|hazel|susan|victoria|google|natural|microsoft|female|en-us/i)
    speakChunked(chunks, onDone, { rate: 0.95, pitch: 1, voice })
  } catch (e) { if (onDone) onDone() }
}

export async function speakSample(text, onDone) {
  try {
    await speechReadyForSpeak()
    speakChainToken++
    const chunks = splitIntoChunks(text)
    const voice = pickVoice(/david|daniel|george|guy|mark|alex|james|ryan|tom|thomas|oliver|matthew|anthony|sean|aaron|fred|lee|microsoft|male/i)
    speakChunked(chunks, onDone, { rate: 0.92, pitch: 1, voice })
  } catch (e) { if (onDone) onDone() }
}

/* ============ Recording ============ */

let micCtx = null
let micProc = null
let pcmBuf = null
let micActive = false
let micStream = null
let waveAnalyser = null

async function initMic() {
  if (!micStream) {
    micStream = await navigator.mediaDevices.getUserMedia({ audio: true })
  }
  if (micCtx) return
  const AC = window.AudioContext || window.webkitAudioContext
  micCtx = new AC()
  const src = micCtx.createMediaStreamSource(micStream)
  micProc = micCtx.createScriptProcessor(4096, 1, 1)
  const silencer = micCtx.createGain()
  silencer.gain.value = 0
  src.connect(micProc)
  micProc.connect(silencer)
  silencer.connect(micCtx.destination)
  waveAnalyser = micCtx.createAnalyser()
  waveAnalyser.fftSize = 256
  waveAnalyser.smoothingTimeConstant = 0.5
  src.connect(waveAnalyser)
  micProc.onaudioprocess = (e) => {
    if (!micActive || !pcmBuf) return
    pcmBuf.push(new Float32Array(e.inputBuffer.getChannelData(0)))
  }
}

export async function startRecording() {
  await initMic()
  pcmBuf = []
  micActive = true
}

function writeWavString(dv, offset, str) {
  for (let i = 0; i < str.length; i++) dv.setUint8(offset + i, str.charCodeAt(i))
}

function buildWavBlob(all, sampleRate) {
  const numFrames = all.length
  const buffer = new ArrayBuffer(44 + numFrames * 2)
  const dv = new DataView(buffer)
  writeWavString(dv, 0, 'RIFF')
  dv.setUint32(4, 36 + numFrames * 2, true)
  writeWavString(dv, 8, 'WAVE')
  writeWavString(dv, 12, 'fmt ')
  dv.setUint32(16, 16, true)
  dv.setUint16(20, 1, true)
  dv.setUint16(22, 1, true)
  dv.setUint32(24, sampleRate, true)
  dv.setUint32(28, sampleRate * 2, true)
  dv.setUint16(32, 2, true)
  dv.setUint16(34, 16, true)
  writeWavString(dv, 36, 'data')
  dv.setUint32(40, numFrames * 2, true)
  let offset = 44
  for (let i = 0; i < all.length; i++) {
    let s = Math.max(-1, Math.min(1, all[i]))
    s = s < 0 ? s * 0x8000 : s * 0x7FFF
    dv.setInt16(44 + i * 2, s, true)
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

export function stopRecording() {
  return new Promise(resolve => {
    micActive = false
    let all = null
    if (pcmBuf && pcmBuf.length > 0) {
      let total = 0
      pcmBuf.forEach(c => { total += c.length })
      all = new Float32Array(total)
      let off = 0
      pcmBuf.forEach(c => { all.set(c, off); off += c.length })
    }
    if (!all || all.length === 0) { resolve(null); return }
    const sr = micCtx ? micCtx.sampleRate : 44100
    resolve({ blob: buildWavBlob(all, sr), seconds: Math.round(all.length / sr) })
  })
}

export function teardownMic() {
  micActive = false
  if (micProc) { try { micProc.disconnect() } catch (e) {} }
  if (micCtx) { try { micCtx.close() } catch (e) {} }
  micCtx = null; micProc = null; waveAnalyser = null
  if (micStream) { micStream.getTracks().forEach(t => t.stop()); micStream = null }
}

export function getWaveAnalyser() { return waveAnalyser }
export function isMicActive() { return micActive }
