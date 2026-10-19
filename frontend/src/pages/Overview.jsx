import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { compact, fmt, pct, qs, useApi } from '../api.js'
import { FanChart, FanTable, GapBars } from '../components/charts.jsx'
import IndiaMap from '../components/IndiaMap.jsx'
import { OfficialStrip } from '../components/OfficialContext.jsx'
import { Card, ChartFrame, ErrorBox, gapColor, Kpi, PageHeader, Section, Skeleton, StatusBadge, StatusLegend, Table, speak } from '../components/ui.jsx'

export function DistrictTip({ p, v, t }) {
  if (!v) return <div><b>{p.d}</b><div className="muted">{p.s}</div></div>
  return <div><b>{p.d}</b> <span className="muted">· {p.s}</span>{v.aspirational ? <div className="text-[.7rem]" style={{ color: 'var(--warn)' }}>Aspirational district</div> : null}
    <div className="mt-1 grid grid-cols-2 gap-x-3 text-[.76rem]"><span className="muted">{t('t.demand')}</span><b className="tabular">{fmt(v.demand)}</b><span className="muted">{t('t.supply')}</span><b className="tabular">{fmt(v.supply)}</b>
      <span className="muted">{t('t.gap_ratio')}</span><b className="tabular" style={{ color: gapColor(v.gap_ratio) }}>{pct(v.gap_ratio, 0, true)}</b><span className="muted">{t('t.trust')}</span><b>{pct(v.trust)}</b></div>
    <div className="mt-1"><StatusBadge status={v.status} /></div></div>
}

export default function Overview({ ctx }) {
  const { t, i18n } = useTranslation()
  const { state, sector } = ctx.filters
  const ov = useApi(`/api/v1/overview?${qs({ state, sector })}`)
  const map = useApi(`/api/v1/map?${qs({ sector })}`)
  const alerts = useApi(`/api/v1/alerts?${qs({ state, sector, limit: 8 })}`)
  const values = useMemo(() => Object.fromEntries((map.data?.districts || []).map((d) => [`${d.state}|${d.district}`, d])), [map.data])
  if (ov.error) return <ErrorBox error={ov.error} />
  const d = ov.data
  const k = d?.kpis
  const summary = d && `${state || t('t.national')}: ${t('kpi.demand')} ${compact(k.forecast_demand)}, ${t('kpi.supply')} ${compact(k.expected_supply)}, ${t('kpi.unmet')} ${compact(k.unmet_demand)}.`
  return <>
    <PageHeader title={t('nav.overview')} subtitle={d ? `${state || t('t.national')} · data to ${d.as_of} · gap window ${d.gap_window} · training cycle ${d.training_cycle}` : ''}
      action={summary && <button className="btn" onClick={() => speak(summary, i18n.language)}>🔊 {t('t.read_aloud')}</button>} />
    {!d ? <Skeleton h={110} /> : <div className="grid grid-cols-2 gap-3 xl:grid-cols-5">
      <Kpi label={t('kpi.demand')} value={compact(k.forecast_demand)} note={`${pct(k.demand_growth, 1, true)} ${t('kpi.growth')}`} />
      <Kpi label={t('kpi.supply')} value={compact(k.expected_supply)} note={`${compact(k.training_seats)} ${t('kpi.seats').toLowerCase()}`} />
      <Kpi label={t('kpi.unmet')} value={compact(k.unmet_demand)} tone="var(--s-short)" note={`${fmt(k.shortage_cells)} / ${fmt(k.cells)} ${t('kpi.cells')}`} />
      <Kpi label={t('kpi.excess')} value={compact(k.excess_supply)} tone="var(--s-sat)" note={`${fmt(k.surplus_cells)} / ${fmt(k.cells)} ${t('kpi.cells')}`} />
      <Kpi label={t('kpi.alerts')} value={fmt(Object.values(k.alerts).reduce((a, b) => a + b, 0))} note={`${compact(k.investment_driven_demand)} ${t('kpi.invest')}`} />
    </div>}
    <div className="mt-3 grid gap-3 xl:grid-cols-[1.35fr_1fr]">
      <Card>
        <Section title={t('t.map_title')} subtitle={t('t.map_sub')} />
        {map.data ? <IndiaMap height={500} values={values} focusState={state || undefined} showOthers={!state} label={t('t.map_title')}
          colorOf={(v) => gapColor(v?.gap_ratio)} tooltip={(p, v) => <DistrictTip p={p} v={v} t={t} />}
          onSelect={(p) => ctx.go('map', { state: p.s, district: p.d })} /> : <Skeleton h={500} />}
        <div className="mt-2"><StatusLegend /></div>
      </Card>
      <div className="grid gap-3">
        {d && <ChartFrame title={t('t.trend')} subtitle={t('t.trend_sub')} chart={<FanChart data={d.trend} height={230} />} table={<FanTable data={d.trend} />} />}
        <Card>
          <Section title={t('t.ticker')} action={<button className="btn !min-h-8 !text-[.75rem]" onClick={() => ctx.go('alerts')}>{t('t.view_all')} →</button>} />
          {!alerts.data ? <Skeleton h={200} /> : <ul className="m-0 list-none space-y-2 p-0">{alerts.data.slice(0, 6).map((a) => <li key={a.id} className="flex gap-2.5 text-[.8rem] leading-5">
            <span className="mt-1 dot flex-none" style={{ background: gapColor(a.kind.includes('shortage') ? -0.5 : 0.8) }} />
            <span><b>{a.trade}</b> · {a.district} <span className="muted">({a.state})</span><br /><span className="ink2">{t(`kind.${a.kind}`)} · P={pct(a.probability)}{a.lead_quarter ? ` · Q${a.lead_quarter}` : ''} · {t('t.severity')} {Math.round(a.severity)}</span></span></li>)}</ul>}
        </Card>
      </div>
    </div>
    {d && <div className="mt-3 grid gap-3 lg:grid-cols-2">
      <ChartFrame title={t('t.top_short')} subtitle="Gap ratio = (supply − demand) / demand, next 12 months" chart={<GapBars items={d.top_shortages.map((x) => ({ ...x, label: x.title }))} onClick={(x) => ctx.go('trades', { code: x.trade_code })} />}
        table={<TradeTable rows={d.top_shortages} t={t} />} />
      <ChartFrame title={t('t.top_surplus')} subtitle="Candidates for seat reduction, repurposing or bridge courses" chart={<GapBars items={d.top_surpluses.map((x) => ({ ...x, label: x.title }))} onClick={(x) => ctx.go('trades', { code: x.trade_code })} />}
        table={<TradeTable rows={d.top_surpluses} t={t} />} />
    </div>}
    <div className="mt-3"><OfficialStrip state={state} onOpen={() => ctx.go('data', { tab: 'official' })} /></div>
    {d?.pipeline && <Card className="mt-3"><Section title="Engine status" subtitle={`Last refresh ${d.pipeline.finished_at} UTC · trigger: ${d.pipeline.trigger} · ${d.pipeline.summary.duration_s}s`} />
      <div className="grid gap-3 text-[.8rem] sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Demand-index error (vs. simulated truth)" value={pct(d.pipeline.summary.uldi.validation.uldi_wape, 1)} note={`best single source ${pct(Math.min(d.pipeline.summary.uldi.validation.portal_only_wape, d.pipeline.summary.uldi.validation.ncs_only_wape, d.pipeline.summary.uldi.validation.epfo_only_wape), 1)}`} />
        <Metric label="Forecast error, holdout (WAPE)" value={pct(d.pipeline.summary.forecast.holdout.ensemble, 1)} note={`legacy linear trend ${pct(d.pipeline.summary.forecast.holdout.linear_baseline, 1)}`} />
        <Metric label="80% interval coverage" value={pct(d.pipeline.summary.forecast.interval_coverage_p10_p90)} note="calibrated by split conformal" />
        <Metric label="Job posts auto-coded to NCO" value={pct(d.pipeline.summary.nco_coding.auto_coded_share)} note={`accuracy ${pct(d.pipeline.summary.nco_coding.auto_coded_accuracy, 1)} · ${pct(d.pipeline.summary.dedup.duplicate_share)} duplicates removed`} />
      </div></Card>}
  </>
}

function Metric({ label, value, note }) { return <div className="rounded-lg p-3" style={{ background: 'var(--surface-2)' }}><div className="text-[.72rem] muted">{label}</div><div className="text-[1.25rem] font-extrabold">{value}</div><div className="text-[.72rem] ink2">{note}</div></div> }

function TradeTable({ rows, t }) {
  return <Table columns={[{ key: 'title', label: t('t.trade') }, { key: 'demand', label: t('t.demand'), num: true, render: (r) => fmt(r.demand) }, { key: 'supply', label: t('t.supply'), num: true, render: (r) => fmt(r.supply) },
    { key: 'gap_ratio', label: t('t.gap_ratio'), num: true, render: (r) => pct(r.gap_ratio, 0, true) }, { key: 'status', label: t('t.status'), render: (r) => <StatusBadge status={r.status} /> }]} rows={rows} />
}

