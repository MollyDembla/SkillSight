import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, fmt, pct } from '../api.js'
import { speak } from './ui.jsx'

const SUGGESTIONS = {
  en: ['Where are the biggest shortages in Odisha?', 'Forecast for EV battery technician in Pune', 'Which trades are oversupplied in Uttar Pradesh?', 'Reskilling options in Maharashtra', 'Which curricula need revision?', 'Show early warnings for Karnataka'],
  hi: ['ओडिशा में किन ट्रेडों में कमी है?', 'उत्तर प्रदेश में किन ट्रेडों में अधिक आपूर्ति है?', 'महाराष्ट्र के लिए पुनः कौशल विकल्प (reskill)', 'कर्नाटक की प्रारंभिक चेतावनी (alert)'],
}

function Md({ text }) {
  // Minimal, safe rendering: paragraphs, bullets and **bold** without injecting HTML.
  return <div className="space-y-1.5">{text.split('\n').filter(Boolean).map((line, i) => {
    const bullet = /^\s*[-*•]\s+/.test(line)
    const parts = line.replace(/^\s*[-*•]\s+/, '').split(/(\*\*[^*]+\*\*)/g).map((p, j) => p.startsWith('**') ? <b key={j}>{p.slice(2, -2)}</b> : <span key={j}>{p.replace(/^_|_$/g, '')}</span>)
    return bullet ? <div key={i} className="flex gap-2"><span aria-hidden="true">•</span><div>{parts}</div></div> : <p key={i} className="m-0">{parts}</p>
  })}</div>
}

function DataPeek({ data }) {
  const rows = data?.rows
  if (!rows?.length || typeof rows[0] !== 'object') return null
  const cols = ['district', 'trade', 'title', 'demand_p50', 'demand', 'supply', 'gap_ratio', 'status', 'p50', 'period', 'kind', 'probability'].filter((k) => k in rows[0]).slice(0, 5)
  if (!cols.length) return null
  return <details className="mt-2 text-[.75rem]"><summary className="cursor-pointer muted">Data used ({rows.length} rows)</summary><div className="mt-1 max-h-48 overflow-auto"><table className="tbl"><thead><tr>{cols.map((c) => <th key={c}>{c.replace('_p50', '').replace('_', ' ')}</th>)}</tr></thead><tbody>{rows.slice(0, 12).map((r, i) => <tr key={i}>{cols.map((c) => <td key={c}>{c === 'gap_ratio' || c === 'probability' ? pct(r[c], 0, c === 'gap_ratio') : typeof r[c] === 'number' ? fmt(r[c]) : String(r[c] ?? '')}</td>)}</tr>)}</tbody></table></div></details>
}

export default function Copilot({ ctx }) {
  const { t, i18n } = useTranslation()
  const [open, setOpen] = useState(false)
  const [msgs, setMsgs] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState(null)
  const end = useRef(null)
  useEffect(() => { if (open && !status) api('/api/v1/copilot/status').then(setStatus).catch(() => {}) }, [open, status])
  useEffect(() => { end.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])
  const send = async (text) => {
    const q = (text ?? input).trim()
    if (!q || busy) return
    setInput('')
    const history = msgs.map((m) => ({ role: m.role, content: m.content }))
    setMsgs((m) => [...m, { role: 'user', content: q }])
    setBusy(true)
    try {
      const r = await api('/api/v1/copilot/chat', { method: 'POST', json: { message: q, history } })
      setMsgs((m) => [...m, { role: 'assistant', content: r.answer, data: r.data, mode: r.mode, tools: r.tools }])
    } catch (e) { setMsgs((m) => [...m, { role: 'assistant', content: `Error: ${e.message}`, mode: 'error' }]) } finally { setBusy(false) }
  }
  return <>
    <button className="btn btn-primary fixed bottom-5 right-5 z-40 !rounded-full !px-4 !py-3 shadow-lg no-print" onClick={() => setOpen(true)} aria-haspopup="dialog" style={{ display: open ? 'none' : undefined }}>✦ {t('t.ask')}</button>
    {open && <div role="dialog" aria-label={t('t.copilot')} className="card fixed bottom-0 right-0 z-50 flex h-[min(640px,100dvh)] w-full flex-col sm:bottom-5 sm:right-5 sm:w-[420px]" style={{ boxShadow: '0 20px 50px rgba(0,0,0,.25)' }}>
      <div className="flex items-center gap-2 border-b px-4 py-3" style={{ borderColor: 'var(--border)' }}>
        <span className="grid size-8 place-items-center rounded-full font-bold" style={{ background: 'var(--brand-soft)', color: 'var(--brand)' }} aria-hidden="true">✦</span>
        <div className="min-w-0 flex-1"><div className="font-bold">{t('t.copilot')}</div><div className="text-[.7rem] muted">{status ? (status.mode === 'gemini' ? `Gemini · ${status.model}` : 'Offline engine · set GEMINI_API_KEY for Gemini') : '…'}</div></div>
        <button className="btn !min-h-8 !px-2" onClick={() => setOpen(false)} aria-label="Close">✕</button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-[.86rem] leading-6" aria-live="polite">
        {!msgs.length && <div><p className="m-0 mb-2 ink2">Ask in English, हिन्दी, ಕನ್ನಡ, मराठी or ଓଡ଼ିଆ. Answers are computed from the live gap, forecast and alert tables.</p>
          <div className="flex flex-wrap gap-1.5">{(SUGGESTIONS[i18n.language] || SUGGESTIONS.en).map((s) => <button key={s} className="chip !text-[.75rem] hover:brightness-95" onClick={() => send(s)}>{s}</button>)}</div></div>}
        {msgs.map((m, i) => <div key={i} className={m.role === 'user' ? 'ml-10 rounded-xl px-3 py-2' : 'mr-4'} style={m.role === 'user' ? { background: 'var(--brand-soft)' } : undefined}>
          {m.role === 'user' ? m.content : <><Md text={m.content} /><DataPeek data={m.data} />
            <div className="mt-1.5 flex items-center gap-3 text-[.7rem] muted">{m.tools?.length > 0 && <span>Tools: {m.tools.map((x) => x.name).join(', ')}</span>}<button className="underline" onClick={() => speak(m.content, i18n.language)}>{t('t.read_aloud')}</button></div></>}
        </div>)}
        {busy && <div className="muted">…</div>}
        <div ref={end} />
      </div>
      <form className="flex gap-2 border-t p-3" style={{ borderColor: 'var(--border)' }} onSubmit={(e) => { e.preventDefault(); send() }}>
        <label className="sr-only" htmlFor="copilot-input">{t('t.ask')}</label>
        <input id="copilot-input" className="input flex-1" value={input} onChange={(e) => setInput(e.target.value)} placeholder={t('t.ask_ph')} autoFocus />
        <button className="btn btn-primary" disabled={busy || !input.trim()}>↑</button>
      </form>
    </div>}
  </>
}
