import { useTranslation } from 'react-i18next'
import { pct, useApi } from '../api.js'
import { Card, PageHeader, Section, Skeleton, Table } from '../components/ui.jsx'

const STEPS = [
  ['1. Harmonise', 'District names → LGD codes (fuzzy matching + alias table). Free-text job titles → NCO-2015 via a character n-gram classifier; low-confidence titles go to Gemini or a human review queue.'],
  ['2. Clean', 'Cross-posted vacancies are clustered with MinHash/LSH (Jaccard ≥ 0.6, same district, ≤ 14 days) and counted once; evergreen "ghost" listings are flagged. NCS is shifted by its 1-month publication lag; sector-level EPFO payroll is apportioned to trades.'],
  ['3. Benchmark', 'Each source is scaled to annual state × sector hiring benchmarks (coverage rate), then cross-calibrated per district against EPFO with empirical-Bayes shrinkage, removing urban/rural reach bias.'],
  ['4. Fuse (ULDI)', 'Unified Labour Demand Index = precision-weighted mean of source estimates. Structural error variance per source is estimated without ground truth by triple collocation; per-cell Poisson sampling variance and publication freshness complete the weight. Weights re-learn on every refresh.'],
  ['5. Forecast', 'Ensemble of seasonal-growth, damped Holt and a global gradient-boosting model (direct multi-horizon, lag ratios, calendar, trade/sector, announced-investment pipeline). Weights per trade from rolling-origin backtests. P10–P90 by split conformal prediction, widened where data trust is low.'],
  ['6. Reconcile', 'District, state and national forecasts are reconciled (WLS / MinT-diagonal), so every drill-down sums exactly.'],
  ['7. Supply', 'S = seats × enrolment × certification yield × (1 − out-migration) + in-migration from origin districts + absorbable e-Shram job-seekers.'],
  ['8. Gap & flags', 'Gap ratio = (S − D) / D. Five classes from acute shortage (≤ −40%) to oversupplied (≥ +60%). P(shortage) and P(surplus) from the forecast distribution; quarterly, seasonally adjusted outlook gives the lead time of each early warning. Severity (0–100) blends magnitude, persistence across past cycles, acceleration, wage signal and trust.'],
  ['9. Decide', 'MILP target optimiser (HiGHS), re-skilling pathways from QP skill overlap, curriculum freshness from posting skills, investment what-if via counterfactual re-forecast, centre siting from net capacity need.'],
]

export default function Methodology() {
  const { t } = useTranslation()
  const m = useApi('/api/v1/methodology/metrics')
  const s = m.data?.run?.summary
  const bt = {}
  ;(m.data?.backtests || []).forEach((b) => { (bt[b.model] ||= []).push(b.wape) })
  return <>
    <PageHeader title={t('nav.method')} subtitle="How heterogeneous labour-market data become one demand index, forecasts, gaps and recommendations. Every number in the product traces back to these steps; validation figures below are recomputed on each refresh." />
    <div className="grid gap-3 xl:grid-cols-[1.3fr_1fr]">
      <Card><Section title="Pipeline" /><ol className="m-0 list-none space-y-3 p-0">{STEPS.map(([h, d]) => <li key={h}><b className="text-[.9rem]">{h}</b><p className="m-0 mt-0.5 text-[.84rem] leading-6 ink2">{d}</p></li>)}</ol></Card>
      <div className="grid content-start gap-3">
        <Card><Section title="Validation (latest run)" subtitle="Synthetic data has a known ground truth, so the index itself can be scored" />
          {!s ? <Skeleton h={200} /> : <Table rows={[
            ['Demand index error (monthly)', pct(s.uldi.validation.uldi_wape, 1)], ['Demand index error (quarterly)', pct(s.uldi.validation.uldi_quarterly_wape, 1)],
            ['Portal only / NCS only / EPFO only', `${pct(s.uldi.validation.portal_only_wape, 1)} / ${pct(s.uldi.validation.ncs_only_wape, 1)} / ${pct(s.uldi.validation.epfo_only_wape, 1)}`],
            ['Forecast holdout WAPE: ensemble', pct(s.forecast.holdout.ensemble, 1)], ['Forecast holdout WAPE: legacy linear trend', pct(s.forecast.holdout.linear_baseline, 1)],
            ['P10–P90 empirical coverage (nominal 80%)', pct(s.forecast.interval_coverage_p10_p90, 1)], ['Hierarchy incoherence (max)', String(s.forecast.reconciliation_max_incoherence)],
            ['NCO auto-coding accuracy (held-out)', pct(s.nco_coding.accuracy, 1)], ['Duplicate postings removed', pct(s.dedup.duplicate_share, 1)]].map(([k, v]) => ({ k, v }))}
            columns={[{ key: 'k', label: 'Metric' }, { key: 'v', label: 'Value', num: true }]} />}
        </Card>
        <Card><Section title="Learned source weights" subtitle="Share of the demand index each source contributes, by sector" />
          {m.data ? <Table rows={Object.values(m.data.source_weights.reduce((acc, w) => { (acc[w.sector] ||= { sector: w.sector })[w.source_key] = w.weight; return acc }, {}))}
            columns={[{ key: 'sector', label: 'Sector' }, { key: 'portal', label: 'Portals', num: true, render: (r) => pct(r.portal) }, { key: 'ncs', label: 'NCS', num: true, render: (r) => pct(r.ncs) }, { key: 'epfo', label: 'EPFO', num: true, render: (r) => pct(r.epfo) }]} /> : <Skeleton h={160} />}
        </Card>
        <Card><Section title="Governance" /><p className="m-0 text-[.82rem] leading-6 ink2">Aggregate, non-personal data only. Every row carries source provenance; imported data is held for review before fusion. Recommendations are advisory and require planner review. LLM outputs are grounded in tool calls on computed tables and labelled; the system works fully offline without them. NCO / QP mappings in the pilot are illustrative and must be verified against the official registers.</p></Card>
      </div>
    </div>
  </>
}
