import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { pct } from '../api.js'

export const STATUS_VAR = { 'Acute shortage': 'var(--s-acute)', Shortage: 'var(--s-short)', Balanced: 'var(--s-bal)', Saturating: 'var(--s-sat-soft)', Oversupplied: 'var(--s-over)' }
// Shape glyph so status never relies on colour alone.
export const STATUS_GLYPH = { 'Acute shortage': '▼▼', Shortage: '▼', Balanced: '●', Saturating: '▲', Oversupplied: '▲▲' }
export const KIND_STATUS = { acute_shortage: 'Acute shortage', emerging_shortage: 'Shortage', saturation: 'Oversupplied', emerging_saturation: 'Saturating' }

/** Diverging colour for a gap ratio: red (shortage) - neutral - blue (oversupply). */
export function gapColor(gr) {
  if (gr == null) return 'var(--nodata)'
  if (gr <= -0.4) return 'var(--s-acute)'
  if (gr <= -0.15) return 'var(--s-short)'
  if (gr <= -0.05) return 'var(--s-short-soft)'
  if (gr < 0.05) return 'var(--s-bal)'
  if (gr < 0.6) return 'var(--s-sat-soft)'
  if (gr < 1.2) return 'var(--s-sat)'
  return 'var(--s-over)'
}

export function Card({ children, className = '', ...rest }) { return <section className={`card min-w-0 p-3.5 sm:p-5 ${className}`} {...rest}>{children}</section> }

export function Section({ title, subtitle, action, as: H = 'h2' }) {
  return <div className="mb-3 flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><H className="m-0 text-[1rem] font-bold tracking-[-.01em]">{title}</H>{subtitle && <p className="m-0 mt-1 text-[.8rem] leading-5 muted">{subtitle}</p>}</div>{action && <div className="flex flex-wrap items-center gap-2">{action}</div>}</div>
}

export function PageHeader({ title, subtitle, action }) {
  return <div className="mb-4 flex flex-wrap items-end justify-between gap-3"><div><h1 className="m-0 text-[1.45rem] font-extrabold tracking-[-.02em]">{title}</h1>{subtitle && <p className="m-0 mt-1 max-w-3xl text-[.86rem] leading-6 ink2">{subtitle}</p>}</div>{action && <div className="flex flex-wrap gap-2">{action}</div>}</div>
}

export function Button({ children, variant = 'default', className = '', ...props }) {
  return <button className={`btn ${variant === 'primary' ? 'btn-primary' : ''} ${className}`} {...props}>{children}</button>
}

export function Pill({ children, tone = 'slate' }) {
  const tones = { slate: '', amber: 'border-amber-300 bg-amber-50 text-amber-900', green: 'border-emerald-300 bg-emerald-50 text-emerald-900', red: 'border-rose-300 bg-rose-50 text-rose-900' }
  return <span className={`chip ${tones[tone] || ''}`}>{children}</span>
}

export function StatusBadge({ status }) {
  const { t } = useTranslation()
  return <span className="chip" title={status}><span className="dot" style={{ background: STATUS_VAR[status] }} /><span aria-hidden="true" className="text-[.6rem]">{STATUS_GLYPH[status]}</span>{t(`status.${status}`, status)}</span>
}

export function GapBar({ value, max = 1.2 }) {
  // Diverging bar centred on zero: left = shortage, right = surplus.
  const v = Math.max(-1, Math.min(max, value || 0))
  const w = Math.abs(v) / max * 50
  return <div className="flex items-center gap-2" title={pct(value, 0, true)}><div className="relative h-2 w-24 flex-none rounded-full" style={{ background: 'var(--grid)' }}><div className="absolute top-0 h-2 rounded-full" style={{ left: v < 0 ? `${50 - w}%` : '50%', width: `${w}%`, background: gapColor(value) }} /><div className="absolute -top-0.5 left-1/2 h-3 w-px" style={{ background: 'var(--axis)' }} /></div><span className="tabular text-[.78rem] font-semibold">{pct(value, 0, true)}</span></div>
}

export function Kpi({ label, value, note, tone }) {
  return <Card className="min-w-0 !p-4"><div className="text-[.72rem] font-semibold uppercase tracking-[.06em] muted [overflow-wrap:anywhere]">{label}</div><div className="mt-1.5 text-[1.35rem] sm:text-[1.6rem] font-extrabold tracking-[-.02em]" style={tone ? { color: tone } : undefined}>{value}</div>{note && <div className="mt-0.5 text-[.75rem] ink2">{note}</div>}</Card>
}

export function Select({ label, value, onChange, options, placeholder, className = '' }) {
  return <label className={`grid min-w-0 flex-1 gap-1 text-[.7rem] font-semibold muted sm:min-w-[9rem] sm:flex-none ${className}`}>{label}<select className="input" value={value ?? ''} onChange={(e) => onChange(e.target.value)}>{placeholder !== undefined && <option value="">{placeholder}</option>}{options.map((o) => Array.isArray(o) ? <option key={o[0]} value={o[0]}>{o[1]}</option> : <option key={o} value={o}>{o}</option>)}</select></label>
}

export function ErrorBox({ error }) { return error ? <div role="alert" className="rounded-lg border p-3 text-[.82rem]" style={{ borderColor: 'var(--crit)', color: 'var(--crit)' }}>{error}</div> : null }

export function Skeleton({ h = 160, className = '' }) { return <div className={`skeleton ${className}`} style={{ height: h }} aria-hidden="true" /> }

export function Empty({ children }) { const { t } = useTranslation(); return <div className="grid place-items-center py-10 text-[.85rem] muted">{children || t('t.none')}</div> }

export function Table({ columns, rows, empty, maxHeight = 520, caption }) {
  return <div className="overflow-auto rounded-lg" style={{ maxHeight }}><table className="tbl">{caption && <caption className="sr-only">{caption}</caption>}<thead><tr>{columns.map((c) => <th key={c.key || c.label} className={c.num ? 'num' : ''} scope="col">{c.label}</th>)}</tr></thead><tbody>{rows.length ? rows.map((r, i) => <tr key={r.id ?? r.key ?? i}>{columns.map((c) => <td key={c.key || c.label} className={c.num ? 'num' : ''}>{c.render ? c.render(r) : r[c.key]}</td>)}</tr>) : <tr><td colSpan={columns.length}><Empty>{empty}</Empty></td></tr>}</tbody></table></div>
}

/** Wraps a chart with an accessible "table view" toggle. */
export function ChartFrame({ title, subtitle, chart, table, action }) {
  const { t } = useTranslation()
  const [asTable, setAsTable] = useState(false)
  return <Card><Section title={title} subtitle={subtitle} action={<>{action}{table && <button className="btn !min-h-8 !py-1 !text-[.75rem]" onClick={() => setAsTable(!asTable)} aria-pressed={asTable}>{asTable ? t('t.chart_view') : t('t.table_view')}</button>}</>} />{asTable ? table : chart}</Card>
}

export function Tabs({ tabs, value, onChange }) {
  return <div role="tablist" className="mb-3 inline-flex flex-wrap gap-1 rounded-lg p-1" style={{ background: 'var(--surface-2)' }}>{tabs.map(([k, label]) => <button key={k} role="tab" aria-selected={value === k} onClick={() => onChange(k)} className="rounded-md px-3 py-1.5 text-[.8rem] font-semibold" style={value === k ? { background: 'var(--surface)', boxShadow: 'var(--shadow)', color: 'var(--ink)' } : { color: 'var(--muted)', background: 'transparent', border: 0 }}>{label}</button>)}</div>
}

export function Legend({ items }) {
  return <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[.75rem] ink2">{items.map(([label, color, glyph]) => <span key={label} className="inline-flex items-center gap-1.5"><span className="dot" style={{ background: color }} />{glyph && <span aria-hidden="true" className="text-[.6rem]">{glyph}</span>}{label}</span>)}</div>
}

export function StatusLegend() {
  const { t } = useTranslation()
  return <Legend items={Object.keys(STATUS_VAR).map((s) => [t(`status.${s}`, s), STATUS_VAR[s], STATUS_GLYPH[s]])} />
}

export function speak(text, lang) {
  try {
    const u = new SpeechSynthesisUtterance(text)
    u.lang = { en: 'en-IN', hi: 'hi-IN', kn: 'kn-IN', mr: 'mr-IN', or: 'or-IN' }[lang] || 'en-IN'
    window.speechSynthesis.cancel(); window.speechSynthesis.speak(u)
  } catch { /* speech unavailable */ }
}
