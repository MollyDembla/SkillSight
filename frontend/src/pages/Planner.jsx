import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, compact, download, fmt, pct, rupees, useApi } from '../api.js'
import { Button, Card, ErrorBox, GapBar, Kpi, PageHeader, Section, Select, Table } from '../components/ui.jsx'

export default function Planner({ ctx }) {
  const { t } = useTranslation()
  const [form, setForm] = useState({ state: ctx.filters.state || 'Odisha', sector: ctx.filters.sector || '', budget_change: 0, max_change: 0.5, women_target: '', protect_aspirational: true, risk: 0.2, shortage_weight: 1, surplus_weight: 0.6 })
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [name, setName] = useState('')
  const scenarios = useApi('/api/v1/scenarios')
  const body = () => ({ ...form, state: form.state || null, sector: form.sector || null, women_target: form.women_target === '' ? null : +form.women_target, budget_change: +form.budget_change, max_change: +form.max_change, risk: +form.risk, shortage_weight: +form.shortage_weight, surplus_weight: +form.surplus_weight })
  const run = async () => { setBusy(true); setError(''); try { setRes(await api('/api/v1/targets/optimize?rows_limit=400', { method: 'POST', json: body() })) } catch (e) { setError(e.message); setRes(null) } finally { setBusy(false) } }
  const save = async () => { try { await api('/api/v1/scenarios', { method: 'POST', json: { name: name || `${form.state || 'All'} plan`, request: body() } }); ctx.notify('Scenario saved'); scenarios.reload() } catch (e) { ctx.notify(e.message) } }
  const set = (k) => (v) => setForm((f) => ({ ...f, [k]: v }))
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { run() }, [])
  const s = res?.summary
  return <>
    <PageHeader title={t('nav.planner')} subtitle="Recommends next-cycle (FY 2027-28) seat targets for every district × trade with a mixed-integer programme: minimise forecast shortage and excess supply within budget, centre capacity, change limits, women-share floor and protection for aspirational districts." />
    <div className="grid gap-3 xl:grid-cols-[340px_1fr]">
      <Card className="content-start">
        <Section title="Constraints & policy levers" />
        <div className="grid gap-3">
          <Select label={t('f.state')} value={form.state} onChange={set('state')} placeholder={t('f.all_states')} options={ctx.ref.states} />
          <Select label={t('f.sector')} value={form.sector} onChange={set('sector')} placeholder={t('f.all_sectors')} options={ctx.ref.sectors.map((x) => [x.sector, x.sector_name])} />
          <Slider label="Budget vs current cycle" value={form.budget_change} min={-0.3} max={0.5} step={0.05} onChange={set('budget_change')} fmt={(v) => pct(v, 0, true)} />
          <Slider label="Max change per course (±)" value={form.max_change} min={0.1} max={1} step={0.05} onChange={set('max_change')} fmt={(v) => pct(v)} />
          <Slider label="Risk appetite (plan above P50)" value={form.risk} min={0} max={1} step={0.1} onChange={set('risk')} fmt={(v) => (+v === 0 ? 'P50' : `P50 + ${pct(v)} of band`)} />
          <Slider label="Weight on shortage" value={form.shortage_weight} min={0.2} max={3} step={0.1} onChange={set('shortage_weight')} fmt={(v) => (+v).toFixed(1)} />
          <Slider label="Weight on excess supply" value={form.surplus_weight} min={0} max={3} step={0.1} onChange={set('surplus_weight')} fmt={(v) => (+v).toFixed(1)} />
          <label className="grid gap-1 text-[.72rem] font-semibold muted">Women-friendly seat share floor<input className="input" type="number" min="0" max="0.8" step="0.01" placeholder="default: keep current share" value={form.women_target} onChange={(e) => set('women_target')(e.target.value)} /></label>
          <label className="flex items-center gap-2 text-[.82rem]"><input type="checkbox" checked={form.protect_aspirational} onChange={(e) => set('protect_aspirational')(e.target.checked)} /> No seat cuts in aspirational districts</label>
          <Button variant="primary" onClick={run} disabled={busy}>{busy ? t('t.running') : t('t.optimise')}</Button>
        </div>
      </Card>
      <div className="grid content-start gap-3">
        <ErrorBox error={error} />
        {!res && !error && <Card><p className="m-0 ink2">Set the levers and run the optimiser. A typical state solves in under a second (HiGHS MILP). Results can be exported as a scheme target sheet (XLSX/CSV/JSON) or saved as a scenario for comparison.</p></Card>}
        {s && <>
          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
            <Kpi label="Unmet demand closed" value={pct(s.shortage_closed_pct / 100)} note={`${compact(s.unmet_demand_before)} → ${compact(s.unmet_demand_after)}`} tone="var(--s-short)" />
            <Kpi label="Excess supply removed" value={pct(s.excess_reduced_pct / 100)} note={`${compact(s.excess_supply_before)} → ${compact(s.excess_supply_after)}`} tone="var(--s-sat)" />
            <Kpi label="Training spend" value={rupees(s.recommended_cost)} note={`budget ${rupees(s.budget)} · saves ${rupees(Math.max(0, s.budget - s.recommended_cost))}`} />
            <Kpi label="Seats re-allocated" value={compact(s.seats_moved)} note={`${compact(s.current_seats)} → ${compact(s.recommended_seats)} · women ${pct(s.women_share_before, 1)} → ${pct(s.women_share_after, 1)}`} />
          </div>
          <Card>
            <Section title={`Recommended targets · ${res.cycle} · ${res.scope}`} subtitle={`Demand window ${res.demand_window} · ${res.status} · ${fmt(res.rows_total)} district-trade cells (largest changes first)`}
              action={<><Button onClick={() => download('/api/v1/targets/export?format=xlsx', { method: 'POST', json: body() })}>⬇ XLSX target sheet</Button><Button onClick={() => download('/api/v1/targets/export?format=csv', { method: 'POST', json: body() })}>CSV</Button><Button onClick={() => download('/api/v1/targets/export?format=json', { method: 'POST', json: body() }, 'targets.json')}>JSON</Button></>} />
            <Table maxHeight={480} rows={res.rows} columns={[
              { key: 'district', label: t('t.district'), render: (r) => <span>{r.district}{r.aspirational ? ' ★' : ''}<div className="text-[.7rem] muted">{r.state}</div></span> },
              { key: 'trade', label: t('t.trade'), render: (r) => <span>{r.trade}<div className="text-[.7rem] muted">{r.qp_code}</div></span> },
              { key: 'current_seats', label: 'Current', num: true, render: (r) => fmt(r.current_seats) },
              { key: 'recommended_seats', label: 'Recommended', num: true, render: (r) => <b>{fmt(r.recommended_seats)}</b> },
              { key: 'change', label: 'Change', num: true, render: (r) => <span style={{ color: r.change > 0 ? 'var(--s-short)' : r.change < 0 ? 'var(--s-sat)' : undefined }}>{r.change > 0 ? '+' : ''}{fmt(r.change)}</span> },
              { key: 'forecast_demand', label: t('t.demand'), num: true, render: (r) => fmt(r.forecast_demand) },
              { key: 'gap_ratio_before', label: 'Gap before → after', render: (r) => <div className="grid gap-1"><GapBar value={r.gap_ratio_before} /><GapBar value={r.gap_ratio_after} /></div> }]} />
          </Card>
          <Card><Section title="Save as scenario" /><div className="flex flex-wrap gap-2"><input className="input flex-1" placeholder="Scenario name" value={name} onChange={(e) => setName(e.target.value)} /><Button onClick={save}>{t('t.save')}</Button></div></Card>
        </>}
        {scenarios.data?.length > 0 && <Card><Section title="Saved scenarios" />
          <Table rows={scenarios.data} columns={[{ key: 'name', label: 'Name' }, { key: 'scope', label: 'Scope', render: (r) => r.inputs.state || 'All' }, { key: 'closed', label: 'Shortage closed', num: true, render: (r) => pct((r.summary?.shortage_closed_pct || 0) / 100) },
            { key: 'cost', label: 'Spend', num: true, render: (r) => rupees(r.summary?.recommended_cost) }, { key: 'created_at', label: 'Saved' }]} /></Card>}
      </div>
    </div>
  </>
}

function Slider({ label, value, min, max, step, onChange, fmt: f }) {
  return <label className="grid gap-1 text-[.72rem] font-semibold muted"><span className="flex justify-between">{label}<b style={{ color: 'var(--ink)' }}>{f(value)}</b></span><input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(e.target.value)} /></label>
}
