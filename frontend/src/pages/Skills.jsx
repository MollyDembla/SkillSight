import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fmt, pct, qs, rupees, useApi } from '../api.js'
import { Card, PageHeader, Section, Skeleton, Table, Tabs } from '../components/ui.jsx'
import { CurriculumCard } from './Trades.jsx'

export default function Skills({ ctx }) {
  const { t } = useTranslation()
  const [tab, setTab] = useState(ctx.params.tab || 'pathways')
  const paths = useApi(tab === 'pathways' ? `/api/v1/pathways?${qs({ state: ctx.filters.state, limit: 60 })}` : null)
  const cur = useApi(tab === 'curriculum' ? '/api/v1/curriculum' : null)
  const [sel, setSel] = useState(null)
  return <>
    <PageHeader title={t('nav.skills')} subtitle="Turn mismatch into action: bridge courses that move surplus trainees into adjacent shortage trades, and NSQF qualification-pack revisions driven by the skills employers actually ask for." />
    <Tabs tabs={[['pathways', t('t.pathways')], ['curriculum', t('t.curriculum')]]} value={tab} onChange={setTab} />
    {tab === 'pathways' && (!paths.data ? <Skeleton h={400} /> : <div className="grid gap-3 xl:grid-cols-[1fr_1.3fr]">
      <Card><Section title={`${fmt(paths.data.total_absorbable)} surplus candidates could be redirected`} subtitle={`${ctx.filters.state || t('t.national')} · skill overlap = share of target-trade skills already covered by the source QP`} />
        <div className="grid gap-2">{paths.data.by_pair.map((p) => <div key={p.from_trade + p.to_trade} className="rounded-lg border p-3" style={{ borderColor: 'var(--border)' }}>
          <div className="flex flex-wrap items-center gap-2 text-[.88rem] font-semibold"><span>{p.from_trade}</span><span aria-hidden="true" style={{ color: 'var(--brand)' }}>→</span><span>{p.to_trade}</span></div>
          <div className="mt-1.5 flex items-center gap-2"><div className="h-2 flex-1 rounded-full" style={{ background: 'var(--grid)' }}><div className="h-2 rounded-full" style={{ width: `${p.skill_overlap * 100}%`, background: 'var(--brand)' }} /></div><span className="text-[.75rem] tabular">{pct(p.skill_overlap)} overlap</span></div>
          <div className="mt-1 text-[.76rem] ink2">~{p.bridge_hours} h bridge · <b>{fmt(p.absorbable)}</b> candidates · {p.districts} districts</div></div>)}</div>
      </Card>
      <Card><Section title="District-level bridge plans" subtitle="Ranked by candidates absorbable; cost is the bridge course vs. training a fresh candidate" />
        <Table maxHeight={640} rows={paths.data.pathways} columns={[{ key: 'district', label: t('t.district'), render: (r) => <span>{r.district}<div className="text-[.7rem] muted">{r.state}</div></span> },
          { key: 'path', label: 'Bridge', render: (r) => <span>{r.from_trade} → <b>{r.to_trade}</b><div className="text-[.7rem] muted">adds: {r.bridge_skills.slice(0, 4).join(', ')}</div></span> },
          { key: 'bridge_hours', label: 'Hours', num: true }, { key: 'absorbable', label: 'Candidates', num: true, render: (r) => fmt(r.absorbable) },
          { key: 'cost', label: 'Cost / saving', num: true, render: (r) => <span>{rupees(r.bridge_cost_per_candidate)}<div className="text-[.7rem]" style={{ color: 'var(--good)' }}>saves {rupees(r.savings_vs_fresh_training)}</div></span> }]} />
      </Card>
    </div>)}
    {tab === 'curriculum' && (!cur.data ? <Skeleton h={400} /> : <div className="grid gap-3 xl:grid-cols-[1fr_1.2fr]">
      <Card><Section title="QP freshness ranking" subtitle="Share of skill mentions in recent job posts that the current QP covers (lowest = revise first)" />
        <Table maxHeight={640} rows={cur.data} columns={[{ key: 'trade', label: t('t.trade'), render: (r) => <button className="text-left underline" onClick={() => setSel(r)}>{r.trade}<div className="text-[.7rem] muted no-underline">{r.qp_code}</div></button> },
          { key: 'freshness_score', label: t('t.freshness'), num: true, render: (r) => <span style={{ color: r.freshness_score < 60 ? 'var(--s-short)' : undefined }}>{r.freshness_score}%</span> },
          { key: 'revision_priority', label: 'Priority' }, { key: 'missing', label: t('t.missing'), render: (r) => r.missing_skills.slice(0, 3).map((s) => s.skill).join(', ') || '—' }]} />
      </Card>
      <Card><Section title={(sel || cur.data[0]).trade} subtitle={`${(sel || cur.data[0]).qp_code} · ${fmt((sel || cur.data[0]).postings_analysed)} postings analysed`} />
        <CurriculumCard c={sel || cur.data[0]} t={t} />
        <p className="mt-3 text-[.75rem] muted">Skills are extracted from posting text with a skill taxonomy (and Gemini for unseen phrasing when an API key is set). Growth compares the last six months with the six before.</p>
      </Card>
    </div>)}
  </>
}
