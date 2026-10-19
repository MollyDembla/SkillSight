import { useMemo, useState } from "react"
import { useTranslation } from 'react-i18next'
import { fmt, pct, qs, useApi } from '../api.js'
import { GapBars, QuarterBars } from '../components/charts.jsx'
import IndiaMap from '../components/IndiaMap.jsx'
import { Card, ErrorBox, GapBar, gapColor, Kpi, PageHeader, Section, Select, Skeleton, StatusBadge, StatusLegend, Table } from '../components/ui.jsx'
import { DistrictTip } from './Overview.jsx'

export default function GeoPage({ ctx }) {
  const { t } = useTranslation()
  const params = ctx.params
  const state = params.state ?? ctx.filters.state ?? ''
  const trade = params.trade || ''
  const districts = ctx.ref.districts
  const selected = useMemo(() => districts.find((d) => d.district === params.district && d.state === (params.state || state)), [districts, params.district, params.state, state])
  const map = useApi(`/api/v1/map?${qs({ sector: ctx.filters.sector, trade })}`)
  const values = useMemo(() => Object.fromEntries((map.data?.districts || []).map((d) => [`${d.state}|${d.district}`, d])), [map.data])
  const stateRows = map.data?.states || []
  const choose = (s, d) => ctx.go('map', { state: s, district: d, trade })
  return <>
    <PageHeader title={t('nav.map')} subtitle="Drill down from the four pilot states to any of 170 districts. Colour shows the next-12-month gap ratio; pick a trade to map one occupation." />
    <nav aria-label="Breadcrumb" className="mb-3 flex flex-wrap items-center gap-1.5 text-[.85rem]">
      <button className="underline" onClick={() => ctx.go('map', { state: '', trade })}>{t('t.national')}</button>
      {state && <><span className="muted">›</span><button className="underline" onClick={() => ctx.go('map', { state, trade })}>{state}</button></>}
      {selected && <><span className="muted">›</span><b>{selected.district}</b></>}
    </nav>
    <div className="grid gap-3 xl:grid-cols-[1.25fr_1fr]">
      <Card>
        <div className="mb-3 flex flex-wrap gap-2.5">
          <Select label={t('f.state')} value={state} onChange={(v) => ctx.go("map", { state: v, trade })} placeholder={t('f.all_states')} options={ctx.ref.states} />
          <Select label={t('f.trade')} value={trade} onChange={(v) => ctx.go('map', { state, district: params.district, trade: v })} placeholder={t('f.all_trades')} options={ctx.ref.trades.map((x) => [x.code, x.title])} />
        </div>
        {map.data ? <IndiaMap height={540} values={values} focusState={state || undefined} showOthers={!state} selected={selected ? `${selected.state}|${selected.district}` : undefined}
          label={t('t.map_title')} colorOf={(v) => gapColor(v?.gap_ratio)} tooltip={(p, v) => <DistrictTip p={p} v={v} t={t} />} onSelect={(p) => choose(p.s, p.d)} /> : <Skeleton h={540} />}
        <div className="mt-2"><StatusLegend /></div>
      </Card>
      <div className="grid content-start gap-3">
        {!selected && <Card><Section title={state ? `${state}: districts ranked by severity` : 'Pilot states'} />
          {state ? <Table maxHeight={560} rows={(map.data?.districts || []).filter((d) => d.state === state).sort((a, b) => b.severity - a.severity)} columns={[
            { key: 'district', label: t('t.district'), render: (r) => <button className="text-left font-semibold underline" onClick={() => choose(r.state, r.district)}>{r.district}{r.aspirational ? ' ★' : ''}</button> },
            { key: 'gap_ratio', label: t('t.gap_ratio'), render: (r) => <GapBar value={r.gap_ratio} /> }, { key: 'severity', label: t('t.severity'), num: true, render: (r) => Math.round(r.severity) },
            { key: 'trust', label: t('t.trust'), num: true, render: (r) => pct(r.trust) }]} />
            : <Table rows={stateRows} columns={[{ key: 'state', label: t('t.state'), render: (r) => <button className="font-semibold underline" onClick={() => ctx.go("map", { state: r.state, trade })}>{r.state}</button> },
              { key: 'demand', label: t('t.demand'), num: true, render: (r) => fmt(r.demand) }, { key: 'supply', label: t('t.supply'), num: true, render: (r) => fmt(r.supply) },
              { key: 'shortage', label: 'Unmet', num: true, render: (r) => fmt(r.shortage) }, { key: 'surplus', label: 'Excess', num: true, render: (r) => fmt(r.surplus) }]} />}
          {state && <p className="mt-2 text-[.72rem] muted">★ Aspirational district (NITI Aayog)</p>}
        </Card>}
        {selected && <DistrictPanel lgd={selected.lgd} ctx={ctx} t={t} />}
      </div>
    </div>
  </>
}

function DistrictPanel({ lgd, ctx, t }) {
  const p = useApi(`/api/v1/districts/${lgd}`)
  const [focus, setFocus] = useState(null)
  if (p.error) return <ErrorBox error={p.error} />
  if (!p.data) return <Skeleton h={600} />
  const { district: d, gaps, totals, investments, migration_out: mout, migration_in: min } = p.data
  const sorted = [...gaps].filter((g) => g.demand_p50 >= 5).sort((a, b) => a.gap_ratio - b.gap_ratio)
  const sel = focus ? gaps.find((g) => g.trade_code === focus) : sorted[0]
  return <>
    <Card>
      <Section title={`${d.district}, ${d.state}`} subtitle={`LGD ${d.lgd}${d.aspirational ? ' · Aspirational district' : ''} · ${gaps.length} trades`}
        action={<a className="btn btn-primary" href={`/api/v1/reports/dsdp/${d.lgd}?lang=${ctx.lang}`} target="_blank" rel="noreferrer">{t('t.dsdp')} ↗</a>} />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Kpi label={t('t.demand')} value={fmt(totals.demand)} /><Kpi label={t('t.supply')} value={fmt(totals.supply)} />
        <Kpi label={t('t.gap_ratio')} value={pct(totals.gap_ratio, 0, true)} tone={gapColor(totals.gap_ratio)} /><Kpi label={t('t.trust')} value={pct(totals.trust)} />
      </div>
    </Card>
    <Card><Section title="Trades in this district" subtitle="Click a bar for drivers and quarterly outlook" />
      <GapBars items={sorted.map((g) => ({ ...g, label: g.trade, demand: g.demand_p50 }))} onClick={(x) => setFocus(x.trade_code)} />
    </Card>
    {sel && <Card><Section title={sel.trade} subtitle={`${sel.qp_code} · NCO ${sel.trade_code}`} action={<><StatusBadge status={sel.status} /><button className="btn !min-h-8 !text-[.75rem]" onClick={() => ctx.go('trades', { code: sel.trade_code, node: d.lgd })}>Forecast →</button></>} />
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="text-[.82rem]">
          <div className="grid grid-cols-2 gap-y-1"><span className="muted">{t('t.demand')} (P10–P90)</span><b className="tabular">{fmt(sel.demand_p50)} ({fmt(sel.demand_p10)}–{fmt(sel.demand_p90)})</b>
            <span className="muted">Local certified</span><b className="tabular">{fmt(sel.local_certified)}</b><span className="muted">− out-migration</span><b className="tabular">{fmt(sel.outflow)}</b>
            <span className="muted">+ in-migration</span><b className="tabular">{fmt(sel.inflow)}</b><span className="muted">+ e-Shram seekers</span><b className="tabular">{fmt(sel.seekers)}</b>
            <span className="muted">= {t('t.supply')}</span><b className="tabular">{fmt(sel.supply)}</b><span className="muted">P(shortage) / P(surplus)</span><b>{pct(sel.p_shortage)} / {pct(sel.p_surplus)}</b>
            <span className="muted">Placement rate · wage growth</span><b>{pct(sel.placement_rate)} · {pct(sel.wage_growth, 0, true)}</b></div>
          <h3 className="mb-1 mt-3 text-[.8rem] font-bold">{t('t.drivers')}</h3>
          <ul className="m-0 space-y-1 pl-4">{sel.drivers.map((x) => <li key={x.key}>{x.label}: <b>{x.value > 0 ? '+' : ''}{fmt(x.value)}</b>{x.projects?.length ? <span className="muted"> ({x.projects.join('; ')})</span> : null}</li>)}</ul>
        </div>
        <div><h3 className="m-0 mb-1 text-[.8rem] font-bold">{t('t.quarters')}</h3><QuarterBars data={sel.quarters.map((q) => ({ ...q, label: `Q${q.q}` }))} />
          <h3 className="mb-1 mt-2 text-[.8rem] font-bold">Past cycles</h3><div className="flex flex-wrap gap-2">{sel.history.map((h) => <span key={h.fy} className="chip"><span className="dot" style={{ background: gapColor(h.gap_ratio) }} />FY{h.fy} {pct(h.gap_ratio, 0, true)}</span>)}</div></div>
      </div>
    </Card>}
    <div className="grid gap-3 sm:grid-cols-2">
      <Card><Section title="Investment pipeline" />{investments.length ? <ul className="m-0 space-y-1.5 pl-4 text-[.8rem]">{investments.map((i) => <li key={i.id}><b>{i.name}</b><br /><span className="muted">{fmt(i.jobs_ops)} ops jobs · ops from {i.ops_start} · ₹{fmt(i.capex_cr)} cr</span></li>)}</ul> : <p className="text-[.8rem] muted">No announced projects.</p>}</Card>
      <Card><Section title="Migration corridors" />
        <div className="text-[.78rem]">{mout.length > 0 && <><div className="font-semibold">Outbound</div>{mout.slice(0, 4).map((m, i) => <div key={i}>→ {m.district} ({m.sector}) {pct(m.share, 1)}</div>)}</>}
          {min.length > 0 && <><div className="mt-1 font-semibold">Inbound</div>{min.slice(0, 4).map((m, i) => <div key={i}>← {m.district} ({m.sector}) {pct(m.share, 1)}</div>)}</>}
          {!mout.length && !min.length && <span className="muted">No significant corridors.</span>}</div></Card>
    </div>
  </>
}
