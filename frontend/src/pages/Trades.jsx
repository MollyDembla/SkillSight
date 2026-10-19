import { useTranslation } from 'react-i18next'
import { fmt, pct, qs, useApi } from '../api.js'
import { FanChart, FanTable } from '../components/charts.jsx'
import { Card, ChartFrame, ErrorBox, GapBar, Kpi, PageHeader, Section, Select, Skeleton, StatusBadge, Table } from '../components/ui.jsx'

const MODEL_LABEL = { ensemble: 'Ensemble (deployed)', global_gbm: 'Global gradient boosting', damped_holt: 'Damped Holt (ETS)', seasonal_growth: 'Seasonal growth', linear_baseline: 'Linear trend (legacy baseline)' }

export default function Trades({ ctx }) {
  const { t } = useTranslation()
  const code = ctx.params.code || '8212.0300'
  const node = ctx.params.node || (ctx.filters.state ? `ST:${ctx.filters.state}` : 'IN')
  const trade = ctx.ref.trades.find((x) => x.code === code)
  const s = useApi(`/api/v1/trades/${code}/series?${qs({ node })}`)
  const dists = useApi(`/api/v1/gaps?${qs({ trade: code, state: node.startsWith('ST:') ? node.slice(3) : '', sort: 'gap_ratio', limit: 200 })}`)
  const cur = useApi(`/api/v1/curriculum?${qs({ trade: code })}`)
  const nodeOptions = [['IN', t('t.national')], ...ctx.ref.states.map((x) => [`ST:${x}`, x]), ...ctx.ref.districts.filter((d) => !ctx.filters.state || d.state === ctx.filters.state).map((d) => [d.lgd, `${d.district} (${d.state})`])]
  const data = s.data ? [...s.data.history, ...s.data.forecast] : []
  const lastOrigin = s.data?.ledger?.length ? [...new Set(s.data.ledger.map((l) => l.origin))].at(-2) : null
  const led = s.data?.ledger?.filter((l) => l.origin === lastOrigin) || []
  const next12 = s.data?.forecast.slice(0, 12).reduce((a, f) => a + f.p50, 0)
  const last12 = s.data?.history.slice(-12).reduce((a, h) => a + h.actual, 0)
  const uplift = s.data?.forecast.slice(0, 12).reduce((a, f) => a + f.invest_effect, 0)
  return <>
    <PageHeader title={t('nav.trades')} subtitle={trade ? `${trade.title} · NCO-2015 ${trade.nco_code || 'not verified'} · QP ${trade.qp_code} · NSQF level ${trade.nsqf_level} · ${trade.hours} h · ${trade.sector_name}${trade.emerging ? ' · emerging trade' : ''}` : ''} />
    {trade && <div className="mb-3 flex flex-wrap items-center gap-2 text-[.75rem]">
      <span className="chip">NCO: {trade.nco_status}</span><span className="chip">QP: {trade.qp_status}</span>
      <span className="ink2">Official QP: {trade.qp_title}{trade.code_note ? ` · ${trade.code_note}` : ''}</span>
      <a className="underline" href={trade.source_url} target="_blank" rel="noreferrer">source ↗</a>
    </div>}
    <div className="mb-3 flex flex-wrap gap-2.5">
      <Select label={t('f.trade')} value={code} onChange={(v) => ctx.go('trades', { code: v, node })} options={ctx.ref.trades.map((x) => [x.code, `${x.title}`])} />
      <Select label="Geography" value={node} onChange={(v) => ctx.go('trades', { code, node: v })} options={nodeOptions} className="min-w-[14rem]" />
    </div>
    {s.error && <ErrorBox error={s.error} />}
    {s.data && <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">
      <Kpi label="Last 12 months (index)" value={fmt(last12)} /><Kpi label="Next 12 months (P50)" value={fmt(next12)} note={pct(next12 / Math.max(1, last12) - 1, 1, true)} />
      <Kpi label="Investment hiring waves (net)" value={`${uplift > 0 ? "+" : ""}${fmt(uplift)}`} note="vs. pipeline frozen today; negative = a hiring wave fading" /><Kpi label={t('t.trust')} value={pct(s.data.history.at(-1)?.trust)} note="latest month" />
    </div>}
    <div className="mt-3 grid gap-3 xl:grid-cols-[1.6fr_1fr]">
      {s.data ? <ChartFrame title={t('t.trend')} subtitle={`Orange = what the model forecast at ${lastOrigin || '–'} (accountability ledger)`} chart={<FanChart data={data} ledger={led} height={320} />} table={<FanTable data={data} />} /> : <Skeleton h={380} />}
      <Card><Section title={t('t.backtest')} subtitle="Rolling-origin WAPE across all districts (lower is better)" />
        {s.data && <Table rows={s.data.backtest} columns={[{ key: 'model', label: 'Model', render: (r) => MODEL_LABEL[r.model] || r.model }, { key: 'wape', label: 'WAPE', num: true, render: (r) => pct(r.wape, 1) }, { key: 'weight', label: 'Weight', num: true, render: (r) => r.model === 'ensemble' || r.model === 'linear_baseline' ? '—' : pct(r.weight) }]} />}
        <p className="mt-2 text-[.75rem] muted">Ensemble weights are chosen per trade on backtests; intervals are split-conformal and widened where data trust is low.</p>
      </Card>
    </div>
    <div className="mt-3 grid gap-3 xl:grid-cols-[1.4fr_1fr]">
      <Card><Section title="Districts for this trade" subtitle="Sorted from most acute shortage to largest surplus" />
        {!dists.data ? <Skeleton h={300} /> : <Table maxHeight={420} rows={dists.data.filter((g) => g.demand_p50 >= 5)} columns={[
          { key: 'district', label: t('t.district'), render: (r) => <button className="text-left underline" onClick={() => ctx.go('map', { state: r.state, district: r.district, trade: code })}>{r.district}<span className="muted"> · {r.state}</span></button> },
          { key: 'demand_p50', label: t('t.demand'), num: true, render: (r) => fmt(r.demand_p50) }, { key: 'supply', label: t('t.supply'), num: true, render: (r) => fmt(r.supply) },
          { key: 'gap_ratio', label: t('t.gap_ratio'), render: (r) => <GapBar value={r.gap_ratio} /> }, { key: 'status', label: t('t.status'), render: (r) => <StatusBadge status={r.status} /> }]} />}
      </Card>
      <Card><Section title={t('t.curriculum')} subtitle="Employer-demanded skills (job posts) vs. the NSQF qualification pack" />
        {cur.data?.[0] ? <CurriculumCard c={cur.data[0]} t={t} /> : <Skeleton h={200} />}
      </Card>
    </div>
  </>
}

export function CurriculumCard({ c, t }) {
  return <div className="text-[.82rem]">
    <div className="flex items-baseline gap-2"><span className="text-[1.6rem] font-extrabold">{c.freshness_score}%</span><span className="muted">{t('t.freshness')} · revision priority <b>{c.revision_priority}</b> · {fmt(c.postings_analysed)} postings</span></div>
    <p className="my-2 ink2">{c.recommendation}</p>
    <Table maxHeight={260} rows={c.skills.slice(0, 12)} columns={[{ key: 'skill', label: 'Skill', render: (r) => <span>{r.skill} {r.in_qp ? <span className="chip !text-[.62rem]">in QP</span> : <span className="chip !text-[.62rem]" style={{ borderColor: 'var(--s-short)', color: 'var(--s-short)' }}>missing</span>}</span> },
      { key: 'share_recent', label: 'Share of posts', num: true, render: (r) => pct(r.share_recent) }, { key: 'growth', label: 'Change', num: true, render: (r) => pct(r.growth, 0, true) }]} />
  </div>
}
