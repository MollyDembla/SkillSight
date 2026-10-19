import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, fmt, rupees } from '../api.js'
import { CompareLines } from '../components/charts.jsx'
import { Button, Card, ErrorBox, GapBar, Kpi, PageHeader, Section, Select, StatusBadge, Table } from '../components/ui.jsx'

const PRESETS = [
  { label: '2 GW solar park · Kalahandi', state: 'Odisha', district: 'Kalahandi', sector: 'RE', jobs_ops: 1800, jobs_build: 5000, ops_start: '2027-06' },
  { label: 'EV two-wheeler plant · Dharwad', state: 'Karnataka', district: 'Dharwad', sector: 'EV', jobs_ops: 3500, jobs_build: 2000, ops_start: '2027-03' },
  { label: 'Super-speciality hospital · Varanasi', state: 'Uttar Pradesh', district: 'Varanasi', sector: 'HC', jobs_ops: 2200, jobs_build: 1500, ops_start: '2027-01' },
  { label: 'Logistics park · Aurangabad', state: 'Maharashtra', district: 'Aurangabad', sector: 'LG', jobs_ops: 4000, jobs_build: 2500, ops_start: '2027-04' },
]

export default function WhatIf({ ctx }) {
  const { t } = useTranslation()
  const [form, setForm] = useState({ ...PRESETS[0], name: PRESETS[0].label, build_months: 9, ramp_months: 12 })
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { run() }, [])
  const dists = ctx.ref.districts.filter((d) => d.state === form.state)
  const run = async (f = form) => {
    const d = ctx.ref.districts.find((x) => x.state === f.state && x.district === f.district)
    if (!d) { setError('Choose a district'); return }
    setBusy(true); setError('')
    try { setRes(await api('/api/v1/simulate/investment', { method: 'POST', json: { lgd: d.lgd, sector: f.sector, jobs_ops: +f.jobs_ops, jobs_build: +f.jobs_build, ops_start: f.ops_start, build_months: +f.build_months, ramp_months: +f.ramp_months, name: f.name } })) } catch (e) { setError(e.message) } finally { setBusy(false) }
  }
  return <>
    <PageHeader title={t('nav.whatif')} subtitle="Test a proposed industrial project before it is announced. The forecasting model is re-run with the project in its investment-pipeline features; the gap engine shows which trades tip into shortage and how many extra seats are needed, in time to plan training ahead of hiring." />
    <div className="grid gap-3 xl:grid-cols-[340px_1fr]">
      <Card className="content-start"><Section title="Project" />
        <div className="mb-3 flex flex-wrap gap-1.5">{PRESETS.map((p) => <button key={p.label} className="chip hover:brightness-95" onClick={() => { const f = { ...form, ...p, name: p.label }; setForm(f); run(f) }}>{p.label}</button>)}</div>
        <div className="grid gap-2.5">
          <label className="grid gap-1 text-[.72rem] font-semibold muted">Name<input className="input" value={form.name} onChange={(e) => set('name')(e.target.value)} /></label>
          <Select label={t('f.state')} value={form.state} onChange={(v) => setForm((f) => ({ ...f, state: v, district: ctx.ref.districts.find((d) => d.state === v)?.district }))} options={ctx.ref.states} />
          <Select label={t('f.district')} value={form.district} onChange={set('district')} options={dists.map((d) => d.district)} />
          <Select label={t('f.sector')} value={form.sector} onChange={set('sector')} options={ctx.ref.sectors.map((s) => [s.sector, s.sector_name])} />
          <div className="grid grid-cols-2 gap-2">
            <label className="grid gap-1 text-[.72rem] font-semibold muted">Operations jobs<input className="input" type="number" min="10" value={form.jobs_ops} onChange={(e) => set('jobs_ops')(e.target.value)} /></label>
            <label className="grid gap-1 text-[.72rem] font-semibold muted">Construction jobs<input className="input" type="number" min="0" value={form.jobs_build} onChange={(e) => set('jobs_build')(e.target.value)} /></label>
            <label className="grid gap-1 text-[.72rem] font-semibold muted">Operations start<input className="input" type="month" value={form.ops_start} onChange={(e) => set('ops_start')(e.target.value)} /></label>
            <label className="grid gap-1 text-[.72rem] font-semibold muted">Hiring ramp (months)<input className="input" type="number" min="1" max="36" value={form.ramp_months} onChange={(e) => set('ramp_months')(e.target.value)} /></label>
          </div>
          <Button variant="primary" onClick={() => run()} disabled={busy}>{busy ? t('t.running') : t('t.what_if')}</Button>
        </div>
      </Card>
      <div className="grid content-start gap-3">
        <ErrorBox error={error} />
        {!res && <Card><p className="m-0 ink2">Pick a preset or describe a project. Construction-phase hiring (masons, electricians, bar benders) starts before operations; operations hiring ramps up from the start date.</p></Card>}
        {res && <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Kpi label="Trades affected" value={res.trades.length} />
            <Kpi label="New shortages" value={res.new_shortages.length} note={res.new_shortages.join(', ') || '—'} tone="var(--s-short)" />
            <Kpi label="Extra seats needed" value={fmt(res.total_extra_seats)} note="to keep supply ≥ demand" />
            <Kpi label="Extra training cost" value={rupees(res.total_extra_cost)} />
          </div>
          <Card><Section title={`${res.project.name} · ${res.district}, ${res.state}`} subtitle="Monthly demand for affected trades, before vs after the project" />
            <CompareLines data={res.series} a="before" b="after" labels={['Baseline forecast', 'With project']} /></Card>
          <Card><Section title="Impact by trade (next 12 months)" />
            <Table rows={res.trades} columns={[{ key: 'trade', label: t('t.trade') }, { key: 'demand_before', label: 'Demand before', num: true, render: (r) => fmt(r.demand_before) }, { key: 'demand_after', label: 'After', num: true, render: (r) => <b>{fmt(r.demand_after)}</b> },
              { key: 'supply', label: t('t.supply'), num: true, render: (r) => fmt(r.supply) }, { key: 'gr', label: 'Gap after', render: (r) => <GapBar value={r.gap_ratio_after} /> },
              { key: 'status', label: t('t.status'), render: (r) => <StatusBadge status={r.status_after} /> }, { key: 'extra', label: 'Extra seats', num: true, render: (r) => fmt(r.extra_seats_needed) }]} /></Card>
          <p className="m-0 text-[.75rem] muted">{res.method}</p>
        </>}
      </div>
    </div>
  </>
}
