import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { fmt, pct, qs, useApi } from '../api.js'
import IndiaMap from '../components/IndiaMap.jsx'
import { Card, gapColor, Legend, PageHeader, Section, Select, Skeleton, Table, Tabs } from '../components/ui.jsx'

export default function Mobility({ ctx }) {
  const { t } = useTranslation()
  const [tab, setTab] = useState('flows')
  const [sector, setSector] = useState(ctx.filters.sector || 'CN')
  const flows = useApi(`/api/v1/mobility?${qs({ sector, min_share: 0.03, limit: 120 })}`)
  const siting = useApi(`/api/v1/siting?${qs({ state: ctx.filters.state, limit: 60 })}`)
  const map = useApi(`/api/v1/map?${qs({ sector })}`)
  const values = useMemo(() => Object.fromEntries((map.data?.districts || []).map((d) => [`${d.state}|${d.district}`, d])), [map.data])
  const maxW = Math.max(1, ...(flows.data || []).map((f) => f.workers))
  return <>
    <PageHeader title={t('nav.mobility')} subtitle="Trained workers move. Supply is counted where workers end up: out-migration is subtracted from origin districts and added to destinations, so an origin district may look over-supplied while it actually feeds a metro shortage." />
    <Tabs tabs={[['flows', 'Migration corridors'], ['siting', 'Centre siting & repurposing']]} value={tab} onChange={setTab} />
    {tab === 'flows' && <div className="grid gap-3 xl:grid-cols-[1.4fr_1fr]">
      <Card><Section title="Certified-worker flows" subtitle="Line width = annual certified workers moving; districts coloured by local gap" action={<Select label={t('f.sector')} value={sector} onChange={setSector} options={ctx.ref.sectors.map((s) => [s.sector, s.sector_name])} />} />
        {flows.data && map.data ? <IndiaMap height={540} showOthers={false} values={values} colorOf={(v) => gapColor(v?.gap_ratio)} label="Migration corridors"
          tooltip={(p, v) => <div><b>{p.d}</b> · {p.s}{v && <div>{t('t.gap_ratio')} {pct(v.gap_ratio, 0, true)}</div>}</div>}
          flows={flows.data.map((f) => ({ from: [f.olon, f.olat], to: [f.dlon, f.dlat], w: 0.6 + 5 * f.workers / maxW, title: `${f.origin} → ${f.dest}: ${fmt(f.workers)} workers/yr (${pct(f.share, 1)})` }))} /> : <Skeleton h={540} />}
        <div className="mt-2"><Legend items={[['Flow (origin → destination)', 'var(--ink-2)'], ['Shortage district', 'var(--s-short)'], ['Oversupplied district', 'var(--s-sat)']]} /></div>
      </Card>
      <Card><Section title="Largest corridors" />
        {flows.data ? <Table maxHeight={560} rows={flows.data.slice(0, 40)} columns={[{ key: 'origin', label: 'From', render: (r) => <span>{r.origin}<div className="text-[.7rem] muted">{r.origin_state}</div></span> }, { key: 'dest', label: 'To', render: (r) => <span>{r.dest}<div className="text-[.7rem] muted">{r.dest_state}</div></span> },
          { key: 'share', label: 'Share', num: true, render: (r) => pct(r.share, 1) }, { key: 'workers', label: 'Workers/yr', num: true, render: (r) => fmt(r.workers) }]} /> : <Skeleton h={400} />}
        <p className="mt-2 text-[.75rem] muted">Planning implication: train in origin districts for destination demand (with placement tie-ups) rather than sanctioning new metro centres.</p>
      </Card>
    </div>}
    {tab === 'siting' && <div className="grid gap-3 xl:grid-cols-[1.3fr_1fr]">
      <Card><Section title="Where training capacity is short" subtitle="Bubble size = net new seats needed after using spare capacity and repurposing surplus courses" />
        {siting.data ? <IndiaMap height={540} focusState={ctx.filters.state || undefined} showOthers={!ctx.filters.state} values={{}} colorOf={() => 'var(--surface-2)'} label="Centre siting"
          points={siting.data.filter((s) => s.net_new_capacity > 0).map((s) => ({ lon: s.lon, lat: s.lat, r: 3 + Math.sqrt(s.net_new_capacity) / 7, color: 'var(--s-short)', label: `${s.district}: ${s.action}` }))
            .concat(siting.data.filter((s) => s.net_new_capacity === 0 && s.repurposable_seats > 50).map((s) => ({ lon: s.lon, lat: s.lat, r: 3 + Math.sqrt(s.repurposable_seats) / 9, color: 'var(--s-sat)', label: `${s.district}: repurpose ${fmt(s.repurposable_seats)} seats` })))} /> : <Skeleton h={540} />}
        <div className="mt-2"><Legend items={[['New capacity needed', 'var(--s-short)'], ['Repurpose surplus seats', 'var(--s-sat)']]} /></div>
      </Card>
      <Card><Section title="Priority list" subtitle="Score weights aspirational districts and distance to existing centres" />
        {siting.data ? <Table maxHeight={600} rows={siting.data.slice(0, 40)} columns={[{ key: 'district', label: t('t.district'), render: (r) => <span>{r.district}{r.aspirational ? ' ★' : ''}<div className="text-[.7rem] muted">{r.state}</div></span> },
          { key: 'action', label: 'Recommended action', render: (r) => <span>{r.action}{r.priority_trades.length > 0 && <div className="text-[.7rem] muted">for {r.priority_trades.join(', ')}</div>}</span> }, { key: 'priority_score', label: 'Score', num: true, render: (r) => fmt(r.priority_score) }]} /> : <Skeleton h={400} />}
      </Card>
    </div>}
  </>
}
