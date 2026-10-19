import { Area, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useTranslation } from 'react-i18next'
import { compact, fmt, pct } from '../api.js'
import { gapColor, Legend, Table } from './ui.jsx'

function Tip({ active, payload, label, rows }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return <div className="tip"><div className="mb-1 font-bold">{label}</div>{rows(d).filter(Boolean).map(([k, v, c]) => <div key={k} className="flex items-center justify-between gap-4"><span className="inline-flex items-center gap-1.5 ink2">{c && <span className="dot" style={{ background: c }} />}{k}</span><b className="tabular">{v}</b></div>)}</div>
}

/** History line + forecast median + 80% band. data: [{period, actual?, p10?, p50?, p90?}] */
export function FanChart({ data, height = 280, ledger }) {
  const { t } = useTranslation()
  const rows = data.map((d) => ({ ...d, band: d.p10 != null ? [d.p10, d.p90] : undefined }))
  const lastActual = [...rows].reverse().find((r) => r.actual != null)
  if (lastActual) { const i = rows.indexOf(lastActual); if (rows[i + 1]) rows[i] = { ...rows[i], p50: rows[i].actual, band: [rows[i].actual, rows[i].actual] } }
  const ledgerMap = Object.fromEntries((ledger || []).map((l) => [l.period, l.forecast]))
  const merged = rows.map((r) => ({ ...r, past: ledgerMap[r.period] }))
  return <div>
    <div style={{ height }} role="img" aria-label={t('t.trend')}>
      <ResponsiveContainer><ComposedChart data={merged} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} />
        <XAxis dataKey="period" tickLine={false} axisLine={{ stroke: 'var(--axis)' }} minTickGap={28} />
        <YAxis tickFormatter={compact} tickLine={false} axisLine={false} width={52} />
        <Tooltip content={<Tip rows={(d) => [d.actual != null && [t('t.actual'), fmt(d.actual), 'var(--ink)'], d.p50 != null && d.actual == null && [`${t('t.forecast')} P50`, fmt(d.p50), 'var(--series-1)'], d.p10 != null && d.actual == null && ['P10 – P90', `${fmt(d.p10)} – ${fmt(d.p90)}`], d.past != null && [t('t.ledger'), fmt(d.past), 'var(--series-2)'], d.invest_effect > 1 && ['Investment uplift', fmt(d.invest_effect)]]} />} />
        <Area dataKey="band" stroke="none" fill="var(--band)" isAnimationActive={false} />
        {lastActual && <ReferenceLine x={lastActual.period} stroke="var(--axis)" strokeDasharray="3 3" />}
        <Line dataKey="actual" stroke="var(--ink)" strokeWidth={2} dot={false} isAnimationActive={false} />
        <Line dataKey="p50" stroke="var(--series-1)" strokeWidth={2} strokeDasharray="6 4" dot={false} isAnimationActive={false} />
        {ledger?.length > 0 && <Line dataKey="past" stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false} />}
      </ComposedChart></ResponsiveContainer>
    </div>
    <div className="mt-2"><Legend items={[[t('t.actual'), 'var(--ink)'], [`${t('t.forecast')} (P50)`, 'var(--series-1)'], ['80% interval', 'var(--band)'], ...(ledger?.length ? [[t('t.ledger'), 'var(--series-2)']] : [])]} /></div>
  </div>
}

export function FanTable({ data }) {
  return <Table columns={[{ key: 'period', label: 'Period' }, { key: 'actual', label: 'Actual', num: true, render: (r) => fmt(r.actual) }, { key: 'p10', label: 'P10', num: true, render: (r) => fmt(r.p10) }, { key: 'p50', label: 'P50', num: true, render: (r) => fmt(r.p50) }, { key: 'p90', label: 'P90', num: true, render: (r) => fmt(r.p90) }]} rows={data} maxHeight={320} />
}

/** Horizontal diverging bars of gap ratio. items: [{label, gap_ratio, demand, supply}] */
export function GapBars({ items, height, onClick }) {
  const { t } = useTranslation()
  const h = height || Math.max(180, items.length * 30 + 30)
  const data = items.map((x) => ({ ...x, v: Math.max(-1, Math.min(1.5, x.gap_ratio)) }))
  return <div style={{ height: h }} role="img" aria-label={t('t.gap_ratio')}>
    <ResponsiveContainer><BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, left: 4, bottom: 4 }} barCategoryGap={6}>
      <CartesianGrid horizontal={false} />
      <XAxis type="number" tickFormatter={(v) => pct(v)} domain={[(min) => Math.min(-0.2, Math.floor(min * 5) / 5), (max) => Math.max(0.2, Math.ceil(max * 5) / 5)]} tickLine={false} axisLine={false} />
      <YAxis type="category" dataKey="label" width={170} tickLine={false} axisLine={false} tick={{ fontSize: 11.5, fill: 'var(--ink-2)' }} />
      <ReferenceLine x={0} stroke="var(--axis)" />
      <Tooltip cursor={{ fill: 'var(--surface-2)' }} content={<Tip rows={(d) => [[t('t.gap_ratio'), pct(d.gap_ratio, 0, true), gapColor(d.gap_ratio)], [t('t.demand'), fmt(d.demand)], [t('t.supply'), fmt(d.supply)]]} />} />
      <Bar dataKey="v" radius={4} isAnimationActive={false} onClick={onClick ? (d) => onClick(d.payload || d) : undefined} style={onClick ? { cursor: 'pointer' } : undefined}>
        {data.map((d, i) => <Cell key={i} fill={gapColor(d.gap_ratio)} />)}
      </Bar>
    </BarChart></ResponsiveContainer>
  </div>
}

/** Two-series monthly comparison (e.g. what-if before/after). */
export function CompareLines({ data, a, b, labels, height = 240 }) {
  return <div><div style={{ height }}><ResponsiveContainer><ComposedChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
    <CartesianGrid vertical={false} /><XAxis dataKey="period" tickLine={false} minTickGap={24} axisLine={{ stroke: 'var(--axis)' }} /><YAxis tickFormatter={compact} tickLine={false} axisLine={false} width={52} />
    <Tooltip content={<Tip rows={(d) => [[labels[0], fmt(d[a]), 'var(--series-1)'], [labels[1], fmt(d[b]), 'var(--series-2)']]} />} />
    <Line dataKey={a} stroke="var(--series-1)" strokeWidth={2} dot={false} isAnimationActive={false} />
    <Line dataKey={b} stroke="var(--series-2)" strokeWidth={2} dot={false} isAnimationActive={false} />
  </ComposedChart></ResponsiveContainer></div><div className="mt-2"><Legend items={[[labels[0], 'var(--series-1)'], [labels[1], 'var(--series-2)']]} /></div></div>
}

/** Simple vertical bars for one measure (e.g. quarterly outlook). */
export function QuarterBars({ data, height = 150 }) {
  const { t } = useTranslation()
  return <div style={{ height }}><ResponsiveContainer><BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
    <CartesianGrid vertical={false} /><XAxis dataKey="label" tickLine={false} axisLine={{ stroke: 'var(--axis)' }} /><YAxis tickFormatter={(v) => pct(v)} tickLine={false} axisLine={false} width={44} domain={[(min) => Math.min(0, min), (max) => Math.max(0, max)]} />
    <ReferenceLine y={0} stroke="var(--axis)" />
    <Tooltip cursor={{ fill: 'var(--surface-2)' }} content={<Tip rows={(d) => [[t('t.gap_ratio'), pct(d.gap_ratio, 0, true), gapColor(d.gap_ratio)], ['P(shortage)', pct(d.p_shortage)], ['P(surplus)', pct(d.p_surplus)]]} />} />
    <Bar dataKey="gap_ratio" radius={4} isAnimationActive={false}>{data.map((d, i) => <Cell key={i} fill={gapColor(d.gap_ratio)} />)}</Bar>
  </BarChart></ResponsiveContainer></div>
}
