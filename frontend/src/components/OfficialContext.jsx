import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { compact, fmt, pct, qs, useApi } from '../api.js'
import { Card, Legend, Section, Skeleton, Table } from './ui.jsx'

const STATE_COLORS = { Maharashtra: 'var(--series-1)', Karnataka: 'var(--series-2)', 'Uttar Pradesh': 'var(--series-3)', Odisha: 'var(--series-4)' }
const PLFS_ROWS = [
  ['ur_15plus_us', 'Unemployment rate, 15+ (usual status)'],
  ['ur_15_29_us', 'Youth unemployment rate, 15–29 (usual status)'],
  ['lfpr_15plus_us', 'Labour force participation, 15+ (usual status)'],
  ['ur_15plus_cws', 'Unemployment rate, 15+ (current weekly status)'],
]
const PLFS_PERIODS = ['2022-23', '2023-24', 'CY2025']

function useOfficial(state) { return useApi(`/api/v1/official?${qs({ state })}`) }

/** Compact strip for the command centre: latest official PLFS and EPFO figures per pilot state. */
export function OfficialStrip({ state, onOpen }) {
  const o = useOfficial(state)
  if (!o.data) return <Skeleton h={120} />
  const plfs = (st, ind, per) => o.data.plfs.find((r) => r.state === st && r.indicator === ind && r.period === per)?.value
  const fy = Object.fromEntries(o.data.shares.map((s) => [s.state, s.official_epfo_share]))
  const states = [...new Set(o.data.epfo.map((r) => r.state))].filter((s) => s !== 'All India')
  return <Card>
    <Section title="Official context" subtitle="Real published figures: PLFS calendar year 2025 (MoSPI) · EPFO net payroll FY 2024-25 share of the pilot states" action={<button className="btn !min-h-8 !text-[.75rem]" onClick={onOpen}>Sources & trends →</button>} />
    <div className="grid grid-cols-2 gap-2 xl:grid-cols-4">{states.map((st) => <div key={st} className="rounded-lg p-3 text-[.78rem]" style={{ background: 'var(--surface-2)' }}>
      <div className="font-bold">{st}</div>
      <div className="mt-1 grid grid-cols-[1fr_auto] gap-x-2 gap-y-0.5"><span className="muted">Unemployment 15+</span><b className="tabular">{plfs(st, 'ur_15plus_us', 'CY2025') ?? '–'}%</b>
        <span className="muted">Youth unemployment</span><b className="tabular">{plfs(st, 'ur_15_29_us', 'CY2025') ?? '–'}%</b>
        <span className="muted">LFPR 15+</span><b className="tabular">{plfs(st, 'lfpr_15plus_us', 'CY2025') ?? '–'}%</b>
        <span className="muted">EPFO hiring share</span><b className="tabular">{fy[st] != null ? pct(fy[st]) : '–'}</b></div>
    </div>)}</div>
  </Card>
}

/** Full panel for the Data hub. */
export function OfficialPanel({ state }) {
  const o = useOfficial(state)
  const chart = useMemo(() => {
    if (!o.data) return []
    const by = {}
    o.data.epfo.filter((r) => r.state !== 'All India').forEach((r) => { (by[r.period] ||= { period: r.period })[r.state] = r.value })
    return Object.values(by)
  }, [o.data])
  if (!o.data) return <Skeleton h={500} />
  const states = Object.keys(STATE_COLORS).filter((s) => chart.some((r) => r[s] != null))
  const plfs = (st, ind, per) => o.data.plfs.find((r) => r.state === st && r.indicator === ind && r.period === per)
  const byUrl = new Map()
  ;[...o.data.epfo, ...o.data.plfs].forEach((r) => { const e = byUrl.get(r.url) || { label: r.definition.split(';').at(-1).split(', latest')[0].trim(), periods: new Set() }; e.periods.add(r.period); byUrl.set(r.url, e) })
  const urls = [...byUrl.entries()].map(([u, e]) => { const ps = [...e.periods].sort(); return [u, `${e.label} · ${ps.length > 1 ? `${ps[0]} to ${ps.at(-1)}` : ps[0]}`] })
  return <div className="grid gap-3">
    <Card><Section title="EPFO net payroll additions by state (official)" subtitle="Persons per month; latest published vintage (EPFO revises heavily). The series ends Jul 2025, the last release on the EPFO data hub." />
      <div style={{ height: 300 }} role="img" aria-label="EPFO net payroll by state">
        <ResponsiveContainer><LineChart data={chart} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} /><XAxis dataKey="period" tickLine={false} minTickGap={24} axisLine={{ stroke: 'var(--axis)' }} /><YAxis tickFormatter={compact} tickLine={false} axisLine={false} width={52} />
          <Tooltip content={({ active, payload, label }) => active && payload?.length ? <div className="tip"><b>{label}</b>{payload.map((p) => <div key={p.dataKey} className="flex justify-between gap-4"><span className="inline-flex items-center gap-1.5"><span className="dot" style={{ background: p.color }} />{p.dataKey}</span><b className="tabular">{fmt(p.value)}</b></div>)}</div> : null} />
          {states.map((st) => <Line key={st} dataKey={st} stroke={STATE_COLORS[st]} strokeWidth={2} dot={false} isAnimationActive={false} />)}
        </LineChart></ResponsiveContainer>
      </div>
      <div className="mt-2"><Legend items={states.map((st) => [st, STATE_COLORS[st]])} /></div>
    </Card>
    <div className="grid gap-3 xl:grid-cols-2">
      <Card><Section title="PLFS labour indicators (official, %)" subtitle="Annual reports: July–June 2022-23 and 2023-24; calendar year 2025 after the survey redesign" />
        <Table rows={[...states, 'All India'].flatMap((st) => PLFS_ROWS.map(([ind, label]) => ({ key: st + ind, st, label, vals: PLFS_PERIODS.map((p) => plfs(st, ind, p)?.value) })))}
          columns={[{ key: 'st', label: 'State' }, { key: 'label', label: 'Indicator' }, ...PLFS_PERIODS.map((p, i) => ({ key: p, label: p, num: true, render: (r) => (r.vals[i] != null ? r.vals[i].toFixed(1) : '–') }))]} maxHeight={420} />
      </Card>
      <Card><Section title="State anchoring" subtitle={o.data.note} />
        <Table rows={o.data.shares} columns={[{ key: 'state', label: 'State' }, { key: 'official_epfo_share', label: 'Official EPFO share (FY24-25)', num: true, render: (r) => pct(r.official_epfo_share, 1) },
          { key: 'index_formal_share', label: 'Index formal-hiring share', num: true, render: (r) => pct(r.index_formal_share, 1) }]} />
        <h3 className="mb-1 mt-4 text-[.85rem] font-bold">Sources</h3>
        <ul className="m-0 space-y-1 pl-4 text-[.75rem]">{urls.map(([u, d]) => <li key={u}><a className="underline" href={u} target="_blank" rel="noreferrer">{d || u}</a></li>)}</ul>
      </Card>
    </div>
  </div>
}
