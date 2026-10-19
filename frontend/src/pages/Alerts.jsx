import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, fmt, pct, qs, useApi } from '../api.js'
import { Button, Card, ErrorBox, gapColor, KIND_STATUS, PageHeader, Section, Select, Skeleton, StatusBadge, Tabs } from '../components/ui.jsx'

const KINDS = ['emerging_shortage', 'acute_shortage', 'emerging_saturation', 'saturation']

export default function Alerts({ ctx }) {
  const { t } = useTranslation()
  const [kind, setKind] = useState('')
  const [status, setStatus] = useState('')
  const { state, sector } = ctx.filters
  const list = useApi(`/api/v1/alerts?${qs({ state, sector, kind, status, limit: 3000 })}`)
  const [channel, setChannel] = useState('whatsapp')
  const digest = useApi(`/api/v1/alerts/digest?${qs({ state, channel, lang: ctx.lang === 'hi' ? 'hi' : 'en' })}`)
  const counts = {}
  ;(list.data || []).forEach((a) => { counts[a.kind] = (counts[a.kind] || 0) + 1 })
  const act = async (a, s) => {
    const assignee = s === 'assigned' ? `${a.state} State Skill Development Mission` : a.assignee
    try { await api(`/api/v1/alerts/${a.id}`, { method: 'PATCH', json: { status: s, assignee, note: a.note || '' } }); ctx.notify(`Alert ${s}`); list.reload() } catch (e) { ctx.notify(e.message) }
  }
  return <>
    <PageHeader title={t('nav.alerts')} subtitle="Probabilistic flags raised before a mismatch shows up in placement data. Emerging flags give the quarter in which the forecast distribution crosses the shortage or saturation threshold with at least 60% probability." />
    <div className="mb-3 flex flex-wrap items-end gap-2.5">
      <Select label="Type" value={kind} onChange={setKind} placeholder="All types" options={KINDS.map((k) => [k, t(`kind.${k}`)])} />
      <Select label="Workflow" value={status} onChange={setStatus} placeholder="Any status" options={['open', 'acknowledged', 'assigned', 'actioned', 'dismissed']} />
      <div className="flex flex-wrap gap-1.5 pb-1">{KINDS.map((k) => <span key={k} className="chip"><span className="dot" style={{ background: gapColor(k.includes('shortage') ? -0.5 : 0.8) }} />{t(`kind.${k}`)}: {counts[k] || 0}</span>)}</div>
    </div>
    <div className="grid gap-3 xl:grid-cols-[1.6fr_1fr]">
      <div className="grid content-start gap-2.5">
        <ErrorBox error={list.error} />
        {!list.data ? <Skeleton h={500} /> : list.data.length === 0 ? <Card><p className="muted">No alerts for this selection.</p></Card> : list.data.slice(0, 60).map((a) => <Card key={a.id} className="!p-4">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div><div className="flex flex-wrap items-center gap-2"><StatusBadge status={KIND_STATUS[a.kind]} /><b>{t(`kind.${a.kind}`)}</b>{a.lead_quarter ? <span className="chip">expected by Q{a.lead_quarter}</span> : null}<span className="chip">{a.status}{a.assignee ? ` → ${a.assignee}` : ''}</span></div>
              <h3 className="m-0 mt-1.5 text-[1rem] font-bold">{a.trade} · {a.district} <span className="font-normal muted">({a.state})</span></h3></div>
            <div className="text-right"><div className="text-[1.4rem] font-extrabold">{pct(a.probability)}</div><div className="text-[.7rem] muted">{t('t.probability')} · sev {Math.round(a.severity)}</div></div>
          </div>
          <p className="my-2 text-[.82rem] ink2">{a.message}</p>
          <div className="flex flex-wrap gap-1.5 text-[.74rem]">{a.drivers.slice(0, 5).map((d) => <span key={d.key} className="chip">{d.label.split('(')[0].trim()}: {d.value > 0 ? '+' : ''}{fmt(d.value)}</span>)}</div>
          <div className="mt-2.5 flex flex-wrap gap-1.5">
            <Button onClick={() => act(a, 'acknowledged')}>{t('t.acknowledge')}</Button>
            <Button onClick={() => act(a, 'assigned')}>{t('t.assign')} → SSDM</Button>
            <Button onClick={() => act(a, 'dismissed')}>{t('t.dismiss')}</Button>
            <Button onClick={() => ctx.go('map', { state: a.state, district: a.district, trade: a.trade_code })}>Investigate →</Button>
          </div>
        </Card>)}
      </div>
      <div className="grid content-start gap-3">
        <Card><Section title="Digest for state planning units" subtitle="Sent after every refresh (delivery simulated)" />
          <Tabs tabs={[['whatsapp', 'WhatsApp'], ['email', 'Email'], ['sms', 'SMS']]} value={channel} onChange={setChannel} />
          {digest.data ? <pre className="m-0 whitespace-pre-wrap rounded-lg p-3 text-[.78rem] leading-5" style={{ background: 'var(--surface-2)', fontFamily: 'inherit' }}>{channel === 'email' && digest.data.subject ? `Subject: ${digest.data.subject}\n\n` : ''}{digest.data.body}</pre> : <Skeleton h={160} />}
        </Card>
        <Webhook ctx={ctx} />
      </div>
    </div>
  </>
}

function Webhook({ ctx }) {
  const [url, setUrl] = useState('https://ssdm.example.gov.in/hooks/lmis')
  const [min, setMin] = useState(60)
  const hooks = useApi('/api/v1/webhooks')
  const add = async (e) => { e.preventDefault(); try { await api('/api/v1/webhooks', { method: 'POST', json: { url, min_severity: +min, state: ctx.filters.state } }); ctx.notify('Webhook registered'); hooks.reload() } catch (err) { ctx.notify(err.message) } }
  return <Card><Section title="Push alerts to scheme systems" subtitle="Webhook subscription (JSON payload per flag)" />
    <form className="grid gap-2" onSubmit={add}><label className="grid gap-1 text-[.72rem] font-semibold muted">Endpoint URL<input className="input" value={url} onChange={(e) => setUrl(e.target.value)} /></label>
      <label className="grid gap-1 text-[.72rem] font-semibold muted">Minimum severity: {min}<input type="range" min="0" max="100" value={min} onChange={(e) => setMin(e.target.value)} /></label>
      <Button variant="primary">Subscribe</Button></form>
    {hooks.data?.length > 0 && <ul className="mb-0 mt-3 space-y-1 pl-4 text-[.75rem]">{hooks.data.map((h) => <li key={h.id}>{h.url} · ≥{h.min_severity}{h.state ? ` · ${h.state}` : ''}</li>)}</ul>}
  </Card>
}
