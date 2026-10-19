import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, download, qs, useApi } from '../api.js'
import { LANGS } from '../i18n.js'
import { Button, Card, PageHeader, Section, Select, Table } from '../components/ui.jsx'

const DATASETS = [['gaps', 'District × trade gaps', 'Demand P10/P50/P90, migration-aware supply, gap, status, severity, probabilities, drivers'], ['rankings', 'State × trade rankings', 'Severity-ranked shortages and surpluses for target setting'],
  ['alerts', 'Early-warning flags', 'Active flags with probability, lead quarter and workflow status'], ['forecasts', 'Forecasts', 'Monthly P10/P50/P90 for every node (district, state, national) × trade'], ['uldi', 'Demand index', 'Unified Labour Demand Index history with source count and trust']]

export default function Reports({ ctx }) {
  const { t } = useTranslation()
  const { state, sector } = ctx.filters
  const [dist, setDist] = useState(ctx.ref.districts.find((d) => d.state === (state || 'Odisha'))?.lgd)
  const [lang, setLang] = useState(ctx.lang)
  const keys = useApi('/api/v1/api-keys')
  const [newKey, setNewKey] = useState(null)
  const create = async () => { try { setNewKey(await api('/api/v1/api-keys', { method: 'POST', json: { name: 'Scheme MIS integration' } })); keys.reload() } catch (e) { ctx.notify(e.message) } }
  const origin = location.origin
  return <>
    <PageHeader title={t('nav.reports')} subtitle="Decision-ready outputs and an integration layer so forecasts feed directly into scheme target-setting workflows." />
    <div className="grid gap-3 xl:grid-cols-2">
      <Card><Section title={t('t.dsdp')} subtitle="Auto-drafted, print-ready plan for a District Skill Committee: outlook table, early warnings, bridge courses, capacity actions, curriculum signals, and a narrative grounded in computed figures (Gemini when configured)." />
        <div className="flex flex-wrap items-end gap-2">
          <Select label={t('f.district')} value={dist} onChange={setDist} options={ctx.ref.districts.filter((d) => !state || d.state === state).map((d) => [d.lgd, `${d.district} (${d.state})`])} className="min-w-[14rem]" />
          <Select label={t('t.language')} value={lang} onChange={setLang} options={LANGS} />
          <a className="btn btn-primary" href={`/api/v1/reports/dsdp/${dist}?lang=${lang}`} target="_blank" rel="noreferrer">{t('t.generate')} ↗</a>
        </div></Card>
      <Card><Section title="Exports" subtitle={`Scope: ${state || 'all pilot states'}${sector ? ` · ${sector}` : ''}`} />
        <div className="grid gap-2">{DATASETS.map(([k, label, desc]) => <div key={k} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-2.5" style={{ borderColor: 'var(--border)' }}>
          <div className="min-w-0"><b className="text-[.85rem]">{label}</b><div className="text-[.72rem] muted">{desc}</div></div>
          <div className="flex gap-1.5">{['xlsx', 'csv', 'json'].map((f) => <Button key={f} className="!min-h-8 !px-2.5 !text-[.72rem]" onClick={() => download(`/api/v1/exports/${k}.${f}?${qs({ state, sector })}`, {}, `skillsight-${k}.${f}`)}>{f.toUpperCase()}</Button>)}</div></div>)}</div></Card>
      <Card><Section title="API access for scheme systems" subtitle="Versioned REST API (/api/v1) with OpenAPI docs. Machine clients use read-only API keys." action={<a className="btn" href="/docs" target="_blank" rel="noreferrer">OpenAPI docs ↗</a>} />
        <Button variant="primary" onClick={create}>Create API key</Button>
        {newKey && <div className="mt-2 rounded-lg p-3 text-[.78rem]" style={{ background: 'var(--brand-soft)' }}><b>Copy now - shown once:</b><code className="mt-1 block break-all">{newKey.key}</code></div>}
        {keys.data?.length > 0 && <div className="mt-3"><Table rows={keys.data} columns={[{ key: 'name', label: 'Name' }, { key: 'prefix', label: 'Prefix', render: (r) => <code>{r.prefix}…</code> }, { key: 'created_at', label: 'Created' }, { key: 'revoked', label: 'Status', render: (r) => (r.revoked ? 'revoked' : 'active') }]} /></div>}
      </Card>
      <Card><Section title="Integration examples" />
        <pre className="m-0 overflow-x-auto whitespace-pre rounded-lg p-3 text-[.74rem] leading-5" style={{ background: 'var(--surface-2)' }}>{`# Severity-ranked shortages for target setting
curl -H "X-API-Key: $KEY" "${origin}/api/v1/rankings?by=state_trade&order=shortage"

# Next-cycle target sheet (MILP) as Excel
curl -X POST -H "Content-Type: application/json" \\
  -d '{"state":"Odisha","budget_change":0.1}' \\
  "${origin}/api/v1/targets/export?format=xlsx" -o targets.xlsx

# Early warnings for a state, newest first
curl "${origin}/api/v1/alerts?state=Karnataka&kind=emerging_shortage"`}</pre></Card>
    </div>
  </>
}
