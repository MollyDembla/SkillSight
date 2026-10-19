import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api, fmt, pct, qs, useApi } from '../api.js'
import { Button, Card, ErrorBox, PageHeader, Section, Skeleton, Table, Tabs } from '../components/ui.jsx'

export default function DataHub({ ctx }) {
  const { t } = useTranslation()
  const [tab, setTab] = useState('sources')
  return <>
    <PageHeader title={t('nav.data')} subtitle="Every signal keeps its provenance. Heterogeneous sources are harmonised (LGD districts, NCO-2015 codes), de-duplicated, benchmarked and fused into the Unified Labour Demand Index with weights the engine re-learns on every refresh." />
    <Tabs tabs={[['sources', 'Sources & fusion'], ['runs', 'Refresh runs'], ['coder', 'NCO auto-coder'], ['postings', 'Job postings'], ['import', 'Import data']]} value={tab} onChange={setTab} />
    {tab === 'sources' && <Sources />}
    {tab === 'runs' && <Runs ctx={ctx} />}
    {tab === 'coder' && <Coder />}
    {tab === 'postings' && <Postings />}
    {tab === 'import' && <Import ctx={ctx} />}
  </>
}

function Sources() {
  const s = useApi('/api/v1/sources')
  const q = useApi('/api/v1/quality')
  if (!s.data) return <Skeleton h={400} />
  const sectors = ['CN', 'EV', 'HC', 'IT', 'LG', 'RE']
  return <div className="grid gap-3">
    <Card><Section title="Source registry" subtitle="Weights are per sector: triple-collocation error variance + Poisson sampling precision × publication freshness" />
      <Table rows={s.data} columns={[{ key: 'name', label: 'Source', render: (r) => <span><b>{r.name}</b><div className="text-[.7rem] muted">{r.access_method}{r.is_synthetic ? ' · synthetic' : ' · imported'}</div></span> },
        { key: 'side', label: 'Role' }, { key: 'grain', label: 'Grain' }, { key: 'lag_months', label: 'Lag (m)', num: true }, { key: 'rows', label: 'Rows', num: true, render: (r) => fmt(r.rows) },
        ...sectors.map((sec) => ({ key: sec, label: `w·${sec}`, num: true, render: (r) => (r.weights?.[sec] ? pct(r.weights[sec].weight) : '') }))]} /></Card>
    <Card><Section title="Data trust by district (lowest first)" subtitle="Combines number of sources, agreement between them, signal volume and recency. Low trust widens forecast intervals." />
      {q.data ? <Table maxHeight={360} rows={q.data.slice(0, 40)} columns={[{ key: 'district', label: 'District' }, { key: 'state', label: 'State' }, { key: 'trust', label: 'Trust', num: true, render: (r) => pct(r.trust) }, { key: 'avg_sources', label: 'Avg sources (6 m)', num: true, render: (r) => (r.avg_sources || 0).toFixed(2) }]} /> : <Skeleton h={300} />}</Card>
  </div>
}

function Runs({ ctx }) {
  const runs = useApi('/api/v1/pipeline/runs')
  const [busy, setBusy] = useState(false)
  const trigger = async () => { setBusy(true); try { await api('/api/v1/pipeline/run', { method: 'POST' }); ctx.notify('Refresh started - takes ~20 seconds'); setTimeout(() => { runs.reload(); setBusy(false) }, 22000) } catch (e) { ctx.notify(e.message); setBusy(false) } }
  return <Card><Section title="Pipeline runs" subtitle="Ingest → NCO coding → de-dup → demand index → backtest → forecast → reconcile → gaps → alerts. Scheduled every 24 h (SKILLSIGHT_REFRESH_HOURS)." action={<Button variant="primary" onClick={trigger} disabled={busy}>{busy ? 'Refreshing…' : 'Run refresh now'}</Button>} />
    {!runs.data ? <Skeleton h={300} /> : <Table rows={runs.data} columns={[{ key: 'id', label: '#', num: true }, { key: 'started_at', label: 'Started (UTC)' }, { key: 'trigger', label: 'Trigger' }, { key: 'status', label: 'Status' },
      { key: 'dur', label: 'Duration', num: true, render: (r) => (r.summary.duration_s ? `${r.summary.duration_s}s` : '') },
      { key: 'u', label: 'Index error', num: true, render: (r) => pct(r.summary.uldi?.validation?.uldi_wape, 1) }, { key: 'f', label: 'Forecast WAPE', num: true, render: (r) => pct(r.summary.forecast?.holdout?.ensemble, 1) },
      { key: 'a', label: 'Alerts', num: true, render: (r) => fmt(Object.values(r.summary.alerts || {}).reduce((a, b) => a + b, 0)) }]} />}
  </Card>
}

function Coder() {
  const [text, setText] = useState('solar mistri urgent\nbike mechanic chahiye\nward boy for hospital\npython developer fresher\nwarehouse helper\nTechnician')
  const [res, setRes] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const run = async () => { setBusy(true); setError(''); try { setRes(await api('/api/v1/nco/classify', { method: 'POST', json: { titles: text.split('\n').map((x) => x.trim()).filter(Boolean).slice(0, 50) } })) } catch (e) { setError(e.message) } finally { setBusy(false) } }
  return <div className="grid gap-3 xl:grid-cols-[1fr_1.4fr]">
    <Card><Section title="Try the occupation auto-coder" subtitle="Character n-gram TF-IDF + logistic regression handles typos, Hinglish and casing. Low-confidence titles go to Gemini (if configured) or the human review queue." />
      <textarea className="input !h-48 w-full !py-2" value={text} onChange={(e) => setText(e.target.value)} aria-label="Job titles, one per line" />
      <div className="mt-2"><Button variant="primary" onClick={run} disabled={busy}>{busy ? '…' : 'Code to NCO-2015'}</Button></div><ErrorBox error={error} /></Card>
    <Card><Section title="Results" subtitle={res ? `threshold ${res.threshold} · ${res.llm_used ? 'Gemini used for low-confidence titles' : 'offline model only'}` : ''} />
      {res ? <Table rows={res.results} columns={[{ key: 'title', label: 'Raw title' }, { key: 'occupation', label: 'NCO occupation', render: (r) => <span>{r.occupation}<div className="text-[.7rem] muted">{r.code} · {r.method}</div></span> },
        { key: 'confidence', label: 'Conf.', num: true, render: (r) => pct(r.confidence) }, { key: 'needs_review', label: 'Review', render: (r) => (r.needs_review ? <span className="chip" style={{ color: 'var(--warn)' }}>review</span> : '✓') }]} /> : <p className="muted">Run the coder to see results.</p>}</Card>
  </div>
}

function Postings() {
  const [filter, setFilter] = useState('')
  const p = useApi(`/api/v1/postings?${qs({ limit: 80, coder: filter === 'review' ? 'review-queue' : '', ghost: filter === 'ghost' ? true : undefined })}`)
  return <Card><Section title="Raw job postings" subtitle="Simulated 12-month scrape. Near-duplicate clusters (MinHash/LSH) count once; ghost postings (re-posted in 3+ months) are excluded from skill analysis." action={<select className="input" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter postings"><option value="">All</option><option value="review">Review queue</option><option value="ghost">Ghost postings</option></select>} />
    {!p.data ? <Skeleton h={400} /> : <Table maxHeight={560} rows={p.data} columns={[{ key: 'posted_on', label: 'Date' }, { key: 'portal', label: 'Portal' }, { key: 'district', label: 'District' }, { key: 'raw_title', label: 'Raw title', render: (r) => <span>{r.raw_title}<div className="text-[.7rem] muted">{r.employer}</div></span> },
      { key: 'occupation', label: 'Coded as', render: (r) => <span>{r.occupation}<div className="text-[.7rem] muted">{r.coder} · {pct(r.nco_conf)}</div></span> }, { key: 'cluster_id', label: 'Cluster', num: true, render: (r) => (r.cluster_id !== r.id ? `dup of #${r.cluster_id}` : '') },
      { key: 'ghost', label: 'Ghost', render: (r) => (r.ghost ? '👻' : '') }]} />}
  </Card>
}

function Import({ ctx }) {
  const [res, setRes] = useState(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const upload = async (e) => {
    e.preventDefault(); const form = new FormData(e.currentTarget); if (!form.get('file')?.size) return
    setBusy(true); setError(''); setRes(null)
    try { setRes(await api(`/api/v1/import?${qs({ source_name: form.get('source_name') })}`, { method: 'POST', body: form })); ctx.notify('Import committed') } catch (err) { setError(err.message) } finally { setBusy(false) }
  }
  return <div className="grid gap-3 xl:grid-cols-[1fr_1.3fr]">
    <Card><Section title="Import aggregate demand signals" subtitle="CSV columns: period (YYYY-MM), state, district, occupation, value. Names are harmonised automatically (e.g. Bangalore → Bengaluru Urban, 'ward boy' → General Duty Assistant). Any unresolved row rejects the whole file." />
      <form className="grid gap-2" onSubmit={upload}><input className="input" name="source_name" defaultValue="State employment exchange extract" aria-label="Source name" /><input className="input !py-1.5" type="file" name="file" accept=".csv" aria-label="CSV file" />
        <Button variant="primary" disabled={busy}>{busy ? 'Validating…' : 'Validate & import'}</Button></form>
      <a className="mt-2 inline-block text-[.8rem] underline" href={'data:text/csv;charset=utf-8,' + encodeURIComponent('period,state,district,occupation,value\n2026-09,Karnataka,Bangalore,Solar technician,40\n2026-09,Orissa,Bhubaneswar,ward boy,22\n2026-09,UP,Noida,Data entry operator,65\n')} download="lmis-import-template.csv">Download template</a>
      <p className="text-[.75rem] muted">Only aggregate, non-personal data. Imported sources are held for review before being fused into the index.</p>
      <ErrorBox error={error} /></Card>
    {res && <Card><Section title={`Committed: ${res.rows_imported} rows (source #${res.source_id})`} subtitle="Harmonisation log" />
      <Table rows={res.harmonisation} columns={[{ key: 'raw_district', label: 'Raw district' }, { key: 'district', label: 'LGD district', render: (r) => `${r.district} (${Math.round(r.district_match)})` }, { key: 'raw_occupation', label: 'Raw occupation' }, { key: 'occupation', label: 'NCO occupation', render: (r) => `${r.occupation} (${r.nco_code})` }]} /></Card>}
  </div>
}
