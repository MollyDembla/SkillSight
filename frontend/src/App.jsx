import { useCallback, useEffect, useMemo, useState } from 'react'
import { createUserWithEmailAndPassword, onAuthStateChanged, sendPasswordResetEmail, signInWithEmailAndPassword, signOut } from 'firebase/auth'
import { firebaseAuth, firebaseConfigured } from './firebase.js'

const NAV = [
  ['overview', '◫', 'Executive overview'], ['geography', '⌖', 'Geographic intelligence'],
  ['occupations', '▤', 'Occupation explorer'], ['forecasts', '⌁', 'Forecasts & alerts'],
  ['allocation', '▦', 'Allocation simulator'], ['data', '⇧', 'Data sources & quality'],
  ['reports', '▧', 'Reports & exports'], ['methodology', 'ⓘ', 'Methodology'],
]
const FILTERS = [['state', 'State'], ['district', 'District'], ['sector', 'Sector'], ['period', 'Period']]
const fmt = (n) => Number(n || 0).toLocaleString('en-IN')
const query = (obj) => new URLSearchParams(Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== '' && v != null))).toString()
async function api(url, options) {
  const headers = new Headers(options?.headers || {})
  if (firebaseAuth?.currentUser) headers.set('Authorization', `Bearer ${await firebaseAuth.currentUser.getIdToken()}`)
  const response = await fetch(url, { ...options, headers })
  let data
  try { data = await response.json() } catch { data = await response.text() }
  if (!response.ok) throw new Error(typeof data === 'object' ? JSON.stringify(data.detail || data) : data)
  return data
}

function Section({ title, subtitle, action }) {
  return <div className="mb-3 flex flex-wrap items-end justify-between gap-3"><div><h2 className="font-bold text-[15px] tracking-[-.02em] text-[#1a2c40]">{title}</h2>{subtitle && <p className="mt-1 text-[12px] leading-5 text-slate-500">{subtitle}</p>}</div>{action}</div>
}
function Card({ children, className = '' }) { return <section className={`rounded-xl border border-slate-200 bg-white p-4 shadow-[0_2px_8px_rgba(23,43,59,.04)] sm:p-5 ${className}`}>{children}</section> }
function Table({ columns, rows, empty = 'No records match the selected filters.' }) {
  return <div className="overflow-x-auto"><table className="w-full border-collapse text-left text-[12px]"><thead><tr>{columns.map((c) => <th key={c} className="whitespace-nowrap border-b border-slate-100 bg-slate-50/70 px-3 py-2.5 text-[9px] font-bold uppercase tracking-[.09em] text-slate-500">{c}</th>)}</tr></thead><tbody>{rows.length ? rows : <tr><td colSpan={columns.length} className="px-3 py-8 text-center text-slate-400">{empty}</td></tr>}</tbody></table></div>
}
const td = 'whitespace-nowrap border-b border-slate-100 px-3 py-2.5 text-slate-600'
function TrendChart({ data, field = 'value', title = 'Demand trend' }) {
  if (!data?.length) return <div className="grid h-44 place-items-center text-xs text-slate-400">No trend observations available.</div>
  const w = 640, h = 190, p = 30, vals = data.map((d) => Number(d[field] || 0)), min = Math.min(...vals), range = Math.max(...vals) - min || 1
  const points = vals.map((v, i) => [p + i * (w - 2 * p) / Math.max(1, vals.length - 1), h - p - (v - min) / range * (h - 2 * p)])
  const line = points.map((pt) => pt.join(',')).join(' ')
  const area = `${p},${h - p} ${line} ${w - p},${h - p}`
  return <div className="h-48 w-full" role="img" aria-label={title}><svg className="h-full w-full overflow-visible" viewBox={`0 0 ${w} ${h}`}><title>{title}</title>{[0, 1, 2, 3].map((n) => <line key={n} className="chart-grid" x1={p} x2={w - p} y1={p + n * (h - 2 * p) / 3} y2={p + n * (h - 2 * p) / 3} />)}<polygon className="chart-area" points={area} /><polyline className="chart-line" points={line} />{points.map(([x, y], i) => <circle key={i} cx={x} cy={y} r="3" fill="#147d78"><title>{data[i].period}: {vals[i]}</title></circle>)}<text className="chart-label" x={p} y={h - 5}>{data[0].period}</text><text className="chart-label" textAnchor="end" x={w - p} y={h - 5}>{data.at(-1).period}</text></svg></div>
}
function Bars({ data, field, label = (x) => x.occupation_title }) {
  if (!data?.length) return <div className="grid h-36 place-items-center text-xs text-slate-400">No records available.</div>
  const max = Math.max(1, ...data.map((d) => Number(d[field] || 0))), h = Math.max(160, data.length * 31)
  return <div className="w-full overflow-hidden" style={{ height: h }}><svg viewBox={`0 0 620 ${h}`} className="h-full w-full"><title>{field} by category</title>{data.map((d, i) => <g key={`${label(d)}-${i}`}><text className="chart-label" x="0" y={i * 31 + 18}>{String(label(d)).slice(0, 25)}</text><rect className="bar-fill" x="200" y={i * 31 + 5} width={Math.max(2, Number(d[field] || 0) / max * 365)} height="16" rx="4" /><text className="chart-label" x={Math.min(580, 205 + Number(d[field] || 0) / max * 365)} y={i * 31 + 18}>{fmt(d[field])}</text></g>)}</svg></div>
}
function Pill({ children, tone = 'slate' }) {
  const tones = { slate: 'bg-slate-100 text-slate-600', amber: 'bg-amber-50 text-amber-800', green: 'bg-emerald-50 text-emerald-800', red: 'bg-rose-50 text-rose-800' }
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[10px] font-semibold ${tones[tone]}`}>{children}</span>
}
function Button({ children, variant = 'primary', className = '', ...props }) {
  const cls = variant === 'primary' ? 'border-teal-700 bg-teal-700 text-white hover:bg-teal-800' : 'border-slate-200 bg-white text-slate-700 hover:bg-slate-50'
  return <button className={`inline-flex min-h-9 items-center justify-center rounded-md border px-3 py-2 text-[11px] font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${cls} ${className}`} {...props}>{children}</button>
}
function EmptyError({ error }) { return error ? <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div> : null }

export default function App() {
  const [page, setPage] = useState(location.hash.slice(1) || 'overview')
  const [filters, setFilters] = useState({ state: '', district: '', sector: '', period: '' })
  const [options, setOptions] = useState({ state: [], district: [], sector: [], period: [] })
  const [toast, setToast] = useState('')
  const [error, setError] = useState('')
  const [data, setData] = useState(null)
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState('')
  const [authUser, setAuthUser] = useState(null)
  const [authReady, setAuthReady] = useState(!firebaseConfigured)
  const [refresh, setRefresh] = useState(0)
  const filtersQuery = useMemo(() => query(filters), [filters])
  const notify = (message) => { setToast(message); window.setTimeout(() => setToast(''), 2800) }
  const changePage = (next) => { setPage(next); history.replaceState(null, '', `#${next}`) }
  const reload = useCallback(() => setRefresh((v) => v + 1), [])

  useEffect(() => { api('/api/health').then(setHealth).catch((e) => setHealthError(e.message)) }, [])
  useEffect(() => {
    if (!firebaseConfigured) return undefined
    return onAuthStateChanged(firebaseAuth, (user) => { setAuthUser(user); setAuthReady(true) })
  }, [])
  const authMismatch = Boolean(health && health.auth_required) !== firebaseConfigured
  const applicationReady = Boolean(health && !authMismatch && (!health.auth_required || (authReady && authUser)))

  useEffect(() => {
    if (!applicationReady) return
    api(`/api/filters?${query(filters.state ? { state: filters.state } : {})}`).then((d) => setOptions(d)).catch((e) => setError(e.message))
  }, [filters.state, refresh, applicationReady])
  useEffect(() => {
    if (!applicationReady) return
    setError(''); setData(null)
    const endpoints = {
      overview: `/api/overview?${filtersQuery}`,
      geography: `/api/geography?${filtersQuery}`,
      occupations: `/api/occupations?${filtersQuery}`,
      forecasts: `/api/forecasts?${query({ ...filters, horizon: 3 })}`,
      data: '/api/sources',
      allocation: '/api/scenarios',
    }
    if (!endpoints[page]) return
    api(endpoints[page]).then(setData).catch((e) => setError(e.message))
  }, [page, filtersQuery, filters, refresh, applicationReady])

  const updateFilter = async (key, value) => {
    const next = { ...filters, [key]: value }
    if (key === 'state') next.district = ''
    setFilters(next)
    if (key === 'state') {
      try { const values = await api(`/api/filters?${query(value ? { state: value } : {})}`); setOptions(values) } catch (e) { setError(e.message) }
    }
  }
  const clearFilters = () => setFilters({ state: '', district: '', sector: '', period: '' })

  if (healthError) return <ConnectionScreen error={healthError} />
  if (!health) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">Connecting to SkillSight API…</div>
  if (authMismatch) return <SetupScreen backendRequiresAuth={health.auth_required} frontendHasFirebase={firebaseConfigured} />
  if (health.auth_required && (!authReady || !authUser)) return <SignInScreen />

  return <div className="min-h-screen bg-[#f5f7f9] text-[#1a2c40]">
    <aside className="fixed inset-x-0 top-0 z-20 border-b border-slate-700 bg-[#12243a] text-slate-100 lg:inset-y-0 lg:right-auto lg:w-[248px] lg:border-b-0 lg:border-r">
      <a className="flex items-center gap-3 px-4 py-3 text-white no-underline lg:px-6 lg:pb-9 lg:pt-7" href="#overview" onClick={() => changePage('overview')}><span className="grid size-9 place-items-center rounded-[10px] bg-[#2b9a8e] font-extrabold text-xl">S</span><span className="font-extrabold tracking-tight">SkillSight<span className="mt-0.5 block text-[8px] font-bold tracking-[.18em] text-slate-400">LABOUR INTELLIGENCE</span></span></a>
      <div className="hidden px-7 pb-3 text-[9px] font-bold tracking-[.15em] text-slate-400 lg:block">PLANNING WORKSPACE</div>
      <nav className="flex gap-1 overflow-x-auto px-2 pb-2 lg:grid lg:gap-1 lg:px-3">{NAV.map(([id, icon, name]) => <button key={id} onClick={() => changePage(id)} className={`flex shrink-0 items-center gap-3 rounded-md px-3 py-2.5 text-left text-[11px] font-medium transition lg:w-full ${page === id ? 'bg-[#28455f] text-white shadow-[inset_3px_0_#3ac0ad]' : 'text-slate-300 hover:bg-[#203851] hover:text-white'}`}><span className="w-4 text-center text-base text-teal-200">{icon}</span><span className="hidden sm:inline lg:inline">{name}</span></button>)}</nav>
      <div className="absolute bottom-5 hidden px-6 text-[10px] leading-6 text-slate-300 lg:block"><span className="mr-2 inline-block size-2 rounded-full bg-emerald-400" />Local demonstration environment<br /><span className="pl-4 text-slate-500">Prototype · planner review required</span></div>
    </aside>
    <main className="pt-[108px] lg:ml-[248px] lg:pt-0">
      <header className="sticky top-0 z-10 flex h-[72px] items-center justify-between border-b border-slate-200 bg-white/95 px-4 backdrop-blur sm:px-7"><div><div className="text-[9px] font-bold tracking-[.13em] text-slate-400">MSDE · DECISION SUPPORT PROTOTYPE</div><h1 className="mt-1 text-[18px] font-bold tracking-tight">{NAV.find(([id]) => id === page)?.[2] || 'Executive overview'}</h1></div><div className="flex items-center gap-4"><span className="hidden items-center gap-1.5 text-[11px] text-slate-500 sm:flex"><i className="size-2 rounded-full bg-emerald-500" />Local data</span><span className="grid size-8 place-items-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-600">PL</span></div></header>
      <div className="mx-auto max-w-[1500px] space-y-4 p-3 sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-[#fff7e9] px-3.5 py-3 text-[11px] text-amber-900"><div className="flex flex-wrap items-center gap-x-3 gap-y-1"><b>ⓘ Synthetic demonstration data</b><span className="text-amber-800/80">Not official government statistics. No live government systems are connected.</span></div><div className="flex items-center gap-3"><Pill tone={health.auth_required ? 'green' : 'amber'}>{health.auth_required ? authUser?.role || 'viewer' : 'Local demo · auth not configured'}</Pill>{authUser && <button className="font-semibold text-slate-700 underline" onClick={() => signOut(firebaseAuth)}>Sign out</button>}</div></div>
        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">{FILTERS.map(([key, label]) => <label key={key} className="grid min-w-[135px] flex-1 gap-1.5 text-[10px] font-semibold text-slate-500">{label}<select value={filters[key]} onChange={(e) => updateFilter(key, e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-[11px] text-slate-700 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"><option value="">{key === 'period' ? 'Latest available' : `All ${label.toLowerCase()}${key === 'district' ? 's' : 's'}`}</option>{(options[key] || []).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>)}<button onClick={clearFilters} className="h-9 px-2 text-[11px] font-semibold text-teal-700 hover:text-teal-900">Reset filters</button></div>
        <EmptyError error={error} />
        {page === 'overview' && <Overview data={data} filters={filters} navigate={changePage} />}
        {page === 'geography' && <Geography data={data} />}
        {page === 'occupations' && <Occupations filters={filters} />}
        {page === 'forecasts' && <Forecasts filters={filters} notify={notify} />}
        {page === 'allocation' && <Allocation data={data} filters={filters} stateOptions={options.state || []} notify={notify} reload={reload} />}
        {page === 'data' && <DataQuality sources={data} reload={reload} notify={notify} />}
        {page === 'reports' && <Reports filtersQuery={filtersQuery} />}
        {page === 'methodology' && <Methodology />}
        <footer className="flex flex-wrap gap-2 py-5 text-[10px] text-slate-400">SkillSight prototype <span>·</span> Data definitions & limits in Methodology <span>·</span><a className="text-teal-700" href="/docs" target="_blank" rel="noreferrer">API documentation ↗</a></footer>
      </div>
    </main>
    {toast && <div role="status" aria-live="polite" className="fixed bottom-5 right-5 z-50 rounded-lg bg-[#18344b] px-4 py-3 text-xs text-white shadow-xl">{toast}</div>}
  </div>
}

function ConnectionScreen({ error }) {
  return <div className="grid min-h-screen place-items-center bg-[#f5f7f9] p-5"><Card className="w-full max-w-lg p-7"><div className="mb-5 flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-teal-700 text-lg font-extrabold text-white">S</span><div><b className="text-lg">SkillSight</b><div className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">Local planner workspace</div></div></div><h1 className="text-xl font-bold">Backend connection unavailable</h1><p className="mt-2 text-sm leading-6 text-slate-600">The React server is running, but the FastAPI service is not responding at port 8000.</p><div className="my-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">{error}<br />From <code>C:\Projects\SkillSight\frontend</code>, run <code className="font-bold">npm run dev:full</code> to start both services together.</div><Button onClick={() => window.location.reload()}>Retry connection</Button></Card></div>
}
function SetupScreen({ backendRequiresAuth, frontendHasFirebase }) {
  return <div className="grid min-h-screen place-items-center bg-[#f5f7f9] p-5"><Card className="w-full max-w-xl p-7"><div className="mb-5 flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-teal-700 text-lg font-extrabold text-white">S</span><b className="text-lg">SkillSight setup</b></div><h1 className="text-xl font-bold">Firebase configuration mismatch</h1><p className="mt-2 text-sm leading-6 text-slate-600">The frontend Firebase settings and backend token-verification setting must both be configured for the same Firebase project.</p><div className="my-4 space-y-2 rounded-lg bg-slate-50 p-4 text-xs leading-5 text-slate-700"><div>Frontend Firebase config: <b>{frontendHasFirebase ? 'present' : 'missing'}</b></div><div>Backend token verification: <b>{backendRequiresAuth ? 'enabled' : 'disabled'}</b></div><div>Use the same Project ID in `frontend/.env.local` and the backend environment variable `FIREBASE_PROJECT_ID`. Restart Vite after changing frontend settings.</div></div><p className="text-[11px] text-slate-500">See the Firebase setup section in README.md. For a local demo, leave both unconfigured and restart the services.</p></Card></div>
}
function SignInScreen() {
  const [email, setEmail] = useState(''), [password, setPassword] = useState(''), [confirmPassword, setConfirmPassword] = useState(''), [creatingAccount, setCreatingAccount] = useState(false), [error, setError] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false)
  const submit = async (e) => {
    e.preventDefault(); setError(''); setMessage('')
    if (creatingAccount && password !== confirmPassword) { setError('The passwords do not match.'); return }
    setBusy(true)
    try {
      if (creatingAccount) await createUserWithEmailAndPassword(firebaseAuth, email.trim(), password)
      else await signInWithEmailAndPassword(firebaseAuth, email.trim(), password)
    } catch (e) {
      const messages = {
        'auth/invalid-credential': 'Email or password is incorrect.',
        'auth/email-already-in-use': 'An account already exists for this email. Sign in instead.',
        'auth/weak-password': 'Choose a password with at least 6 characters.',
        'auth/operation-not-allowed': 'Email and password sign-in is not enabled in Firebase Console.',
        'auth/invalid-email': 'Enter a valid email address.',
      }
      setError(messages[e.code] || e.message)
    } finally { setBusy(false) }
  }
  const reset = async () => { setError(''); setMessage(''); if (!email.trim()) { setError('Enter your email first, then choose password reset.'); return } try { await sendPasswordResetEmail(firebaseAuth, email.trim()); setMessage('If the account exists, a password reset email has been sent.') } catch (e) { setError(e.message) } }
  return <div className="grid min-h-screen place-items-center bg-[#f5f7f9] p-5"><Card className="w-full max-w-md p-7 sm:p-9"><div className="mb-7 flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-teal-700 text-lg font-extrabold text-white">S</span><div><b className="text-lg tracking-tight">SkillSight</b><div className="text-[9px] font-bold uppercase tracking-[.16em] text-slate-400">Planner access</div></div></div><div className="mb-6"><div className="text-[10px] font-bold uppercase tracking-[.14em] text-teal-700">Government planning workspace</div><h1 className="mt-2 text-2xl font-bold tracking-tight">{creatingAccount ? 'Create your account' : 'Sign in to continue'}</h1><p className="mt-2 text-sm leading-6 text-slate-500">{creatingAccount ? 'Create an account to access the SkillSight planning workspace.' : 'Sign in with your SkillSight account.'}</p></div><form className="space-y-4" onSubmit={submit}><label className="grid gap-1.5 text-xs font-semibold text-slate-600">Email address<input autoComplete="username" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} className="h-11 rounded-lg border border-slate-200 px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100" placeholder="name@department.gov.in" /></label><label className="grid gap-1.5 text-xs font-semibold text-slate-600">Password<input autoComplete={creatingAccount ? 'new-password' : 'current-password'} type="password" minLength={6} required value={password} onChange={(e) => setPassword(e.target.value)} className="h-11 rounded-lg border border-slate-200 px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100" /></label>{creatingAccount && <label className="grid gap-1.5 text-xs font-semibold text-slate-600">Confirm password<input autoComplete="new-password" type="password" minLength={6} required value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} className="h-11 rounded-lg border border-slate-200 px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100" /></label>}{error && <div role="alert" className="rounded-md bg-rose-50 p-3 text-xs leading-5 text-rose-800">{error}</div>}{message && <div role="status" className="rounded-md bg-emerald-50 p-3 text-xs text-emerald-800">{message}</div>}<Button disabled={busy} className="w-full">{busy ? 'Please wait?' : creatingAccount ? 'Create account' : 'Sign in securely'}</Button></form>{!creatingAccount && <button onClick={reset} className="mt-4 text-xs font-semibold text-teal-700 hover:underline">Forgot password?</button>}<div className="mt-5 text-center text-xs text-slate-500">{creatingAccount ? 'Already have an account?' : 'New to SkillSight?'} <button type="button" onClick={() => { setCreatingAccount(!creatingAccount); setError(''); setMessage('') }} className="font-semibold text-teal-700 hover:underline">{creatingAccount ? 'Sign in' : 'Create an account'}</button></div><div className="mt-5 border-t border-slate-100 pt-4 text-[10px] leading-5 text-slate-400">New accounts receive viewer access. Contact your Firebase administrator for planner permissions.</div></Card></div>
}

function Loading() { return <div className="grid grid-cols-2 gap-3 xl:grid-cols-4">{[1, 2, 3, 4].map((i) => <div key={i} className="h-24 animate-pulse rounded-xl bg-slate-200" />)}</div> }
function Kpi({ title, value, note, symbol }) { return <Card><div className="flex justify-between text-[11px] font-semibold text-slate-500">{title}<span className="text-base text-teal-700">{symbol}</span></div><div className="my-2 text-[26px] font-extrabold tracking-tight text-[#182e43]">{value}</div><div className="text-[10px] text-slate-400">{note}</div></Card> }
function Overview({ data, navigate }) {
  if (!data) return <Loading />
  const rows = data.occupations?.slice(0, 7).map((o) => <tr key={o.occupation_code}><td className={td}><b className="text-slate-700">{o.occupation_title}</b><span className="block text-[10px] text-slate-400">{o.occupation_code}</span></td><td className={td}>{o.sector}</td><td className={td}>{fmt(o.demand)}</td><td className={td}>{fmt(o.training_seats)}</td><td className={td}><button className="font-semibold text-teal-700" onClick={() => navigate('occupations')}>View →</button></td></tr>) || []
  return <><div className="grid grid-cols-2 gap-3 xl:grid-cols-4"><Kpi title="Observed demand" value={fmt(data.observed_demand_count)} note={`Count proxy · ${data.reporting_period || '—'} · latest filtered month`} symbol="↗" /><Kpi title="Occupations analysed" value={data.occupation_count} note="Distinct occupation codes in filtered records" symbol="▤" /><Kpi title="Training seats" value={fmt(data.training_seats)} note="Recorded capacity · latest filtered month" symbol="▦" /><Kpi title="Comparable supply" value={<span className="text-[18px]">Unavailable</span>} note="No supported demand–supply gap classification" symbol="ⓘ" /></div>
    <div className="grid gap-3 xl:grid-cols-[1.5fr_1fr]"><Card><Section title="Historical demand signal" subtitle="Observed synthetic proxy totals by reporting month" /><TrendChart data={data.demand_trend} /></Card><Card><Section title="Demand by occupation" subtitle="Accumulated over the periods shown" /><Bars data={data.occupations?.slice(0, 5)} field="demand" /></Card></div>
    <div className="grid gap-3 xl:grid-cols-[1.4fr_1fr]"><Card><Section title="Occupation signals" subtitle="Select an occupation to inspect its profile." /><Table columns={['Occupation', 'Sector', 'Demand proxy', 'Training seats', '']} rows={rows} /></Card><Card><Section title="Data context" subtitle="Coverage and evidence quality" /><InfoBox><>{data.data_label}<br />Sources: {data.source_count} · Rows with quality notes: {data.quality_issues}<br />Workforce supply: {data.workforce_supply}<br /><b>{data.gap_classification}</b><br />Recommendations require planner review.</></InfoBox><div className="mt-4"><Section title="Priority actions" subtitle="Evidence-led next steps" /><InfoBox>Review demand signals in Forecasts & alerts.<br />Compare district capacity with observed demand.<br />Validate imported sources and periods.</InfoBox></div></Card></div></>
}
function InfoBox({ children }) { return <div className="rounded-md bg-slate-50 p-3 text-[11px] leading-6 text-slate-600">{children}</div> }
function Geography({ data }) {
  if (!data) return <Loading />
  const rows = data.areas?.map((a) => <tr key={`${a.state}-${a.district}`}><td className={td}>{a.state}</td><td className={`${td} font-semibold text-slate-700`}>{a.district}</td><td className={td}>{fmt(a.observed_demand)}</td><td className={td}>{fmt(a.training_seats)}</td><td className={td}><Pill tone="amber">Insufficient evidence</Pill></td></tr>) || []
  return <><Section title="District comparison" subtitle={`Latest period ${data.reporting_period || '—'} · no boundary file was supplied.`} /><Card><Table columns={['State', 'District', 'Demand proxy', 'Training seats', 'Gap evidence']} rows={rows} /><div className="mt-3"><InfoBox>{data.note} High observed demand alone is not evidence of a shortage.</InfoBox></div></Card></>
}
function Occupations({ filters }) {
  const [search, setSearch] = useState(''), [items, setItems] = useState(null), [detail, setDetail] = useState(null), [error, setError] = useState('')
  useEffect(() => { api(`/api/occupations?${query({ ...filters, q: search })}`).then(setItems).catch((e) => setError(e.message)) }, [filters, search])
  const inspect = async (code) => { try { setDetail(await api(`/api/occupations/${encodeURIComponent(code)}?${query(filters)}`)); setError('') } catch (e) { setError(e.message) } }
  const rows = items?.map((o) => <tr key={o.code}><td className={td}>{o.code}</td><td className={td}><button className="font-semibold text-teal-700 hover:underline" onClick={() => inspect(o.code)}>{o.title}</button></td><td className={td}>{o.sector}</td><td className={td}>{fmt(o.demand_count)}</td><td className={td}>{fmt(o.training_seats)}</td><td className={td}><Pill>Demo code · not NCO</Pill></td></tr>) || []
  return <><Section title="Occupation catalogue" subtitle="Search the available occupation labels and source-backed indicators." /><Card><div className="mb-4 flex flex-wrap items-center justify-between gap-3"><input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search title, code or sector" className="h-9 w-full max-w-sm rounded-md border border-slate-200 px-3 text-xs outline-none focus:border-teal-600" /><span className="text-[11px] text-slate-400">{items?.length ?? '…'} results</span></div><Table columns={['Code', 'Occupation', 'Sector', 'Demand observations', 'Training seats', 'Classification']} rows={rows} /></Card><EmptyError error={error} />{detail && <Card className="mt-4"><Section title={detail.title} subtitle={`${detail.code} · ${detail.sector}`} /><TrendChart data={detail.demand_trend} field="demand" title="Occupation demand trend" /><InfoBox>Latest training seats: {fmt(detail.training_seats_latest)}. Sources: {detail.sources.join(', ')}.<br />{detail.classification_note} Skills and course mappings were not supplied.</InfoBox></Card>}</>
}
function Forecasts({ filters, notify }) {
  const [horizon, setHorizon] = useState(3), [bundle, setBundle] = useState(null), [error, setError] = useState('')
  useEffect(() => { Promise.all([api(`/api/forecasts?${query({ ...filters, horizon })}`), api(`/api/alerts?${query(filters)}`), api(`/api/overview?${query(filters)}`)]).then(([forecast, alerts, overview]) => setBundle({ forecast, alerts, overview })).catch((e) => setError(e.message)) }, [filters, horizon])
  if (!bundle) return <><Section title="Demand trend baseline" subtitle="Deterministic least-squares trend over filtered observations." /><Loading /><EmptyError error={error} /></>
  const { forecast, alerts, overview } = bundle, f = forecast.forecast
  const setH = async (v) => { setHorizon(Number(v)); try { const result = await api(`/api/forecasts?${query({ ...filters, horizon: v })}`); notify(`Forecast recalculated: ${result.forecast.status.replaceAll('_', ' ')}`) } catch (e) { setError(e.message) } }
  return <><Section title="Demand trend baseline" subtitle="Deterministic least-squares trend over filtered observations." action={<label className="flex items-center gap-2 text-[11px] text-slate-500">Horizon<select value={horizon} onChange={(e) => setH(e.target.value)} className="h-9 rounded-md border border-slate-200 bg-white px-2 text-xs"><option value="3">3 months</option><option value="6">6 months</option><option value="12">12 months</option></select></label>} /><EmptyError error={error} /><div className="grid gap-3 xl:grid-cols-2"><Card><Section title="Forecast" subtitle={f.note} />{f.status === 'baseline' ? <><TrendChart data={overview.demand_trend} /><Table columns={['Forecast period', 'Baseline demand proxy']} rows={f.points.map((p) => <tr key={p.period}><td className={td}>{p.period}</td><td className={td}>{fmt(p.value)}</td></tr>)} /></> : <InfoBox>Insufficient history: {f.history_periods} distinct month(s); at least 3 are required.</InfoBox>}<div className="mt-3"><InfoBox>Method: {f.method} · History periods: {f.history_periods || 0}. No accuracy or confidence score is asserted.</InfoBox></div></Card><Card><Section title="Early-warning rules" subtitle={`Latest comparison period: ${alerts.period || '—'}.`} /><InfoBox>{alerts.rule_note} Each alert requires human review and is not a shortage classification.</InfoBox><div className="mt-2 space-y-2">{alerts.alerts?.length ? alerts.alerts.slice(0, 12).map((a, i) => <div key={`${a.occupation_code}-${a.district}-${i}`} className="rounded-r-md border-l-[3px] border-amber-400 bg-amber-50/70 p-3 text-[11px]"><b className="text-amber-950">{a.occupation_title} · {a.district}, {a.state}</b><p className="mt-1 leading-5 text-slate-600">{a.rule}: {a.previous_demand} → {a.current_demand} ({a.change_percent}%). {a.interpretation}</p></div>) : <div className="py-8 text-center text-xs text-slate-400">No observations crossed the threshold for this period.</div>}</div></Card></div></>
}
function Allocation({ data, filters, stateOptions, notify, reload }) {
  const [form, setForm] = useState({ budget: 3000000, district_capacity: 80, cost_per_seat: 30000, minimum_total_seats: 0, state: '', district: '' })
  const [result, setResult] = useState(null), [scenarios, setScenarios] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false)
  useEffect(() => { api('/api/scenarios').then(setScenarios).catch((e) => setError(e.message)) }, [data, reload])
  const setField = (key, value) => setForm((v) => ({ ...v, [key]: ['budget', 'district_capacity', 'cost_per_seat', 'minimum_total_seats'].includes(key) ? Number(value) : value }))
  const request = { ...form, state: form.state || filters.state || null, district: form.district || filters.district || null, sector: filters.sector || null, period: filters.period || null }
  const calculate = async (e) => { e?.preventDefault(); setBusy(true); setError(''); try { setResult(await api('/api/allocations/optimize', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(request) })) } catch (ex) { setError(ex.message) } finally { setBusy(false) } }
  const save = async () => { if (!result || result.result?.status !== 'feasible') { notify('Calculate a feasible allocation before saving.'); return } const name = window.prompt('Name this scenario'); if (!name) return; try { const saved = await api('/api/scenarios', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, request }) }); notify(`Saved scenario #${saved.id}`); reload() } catch (e) { setError(e.message) } }
  const open = async (id) => { try { const s = await api(`/api/scenarios/${id}`); setForm((v) => ({ ...v, ...s.request, state: s.request.state || '', district: s.request.district || '' })); setResult(s.data); notify(`Reloaded ${s.name}`) } catch (e) { setError(e.message) } }
  const fields = [['budget', 'Budget (₹)'], ['district_capacity', 'District seat capacity'], ['cost_per_seat', 'Estimated cost per seat (₹)'], ['minimum_total_seats', 'Minimum seats (feasibility check)']]
  return <><Section title="Allocation simulator" subtitle="Find an integer-seat plan under a budget and district capacity." /><EmptyError error={error} /><div className="grid gap-3 xl:grid-cols-[1.25fr_1fr]"><Card><Section title="Scenario inputs" subtitle="Maximize seats assigned to recorded demand proxy, subject to budget and seat capacity." /><form onSubmit={calculate}><div className="grid gap-3 sm:grid-cols-2">{fields.map(([key, label]) => <label key={key} className="grid gap-1.5 text-[10px] font-semibold text-slate-500">{label}<input type="number" min={key === 'cost_per_seat' ? 1 : 0} value={form[key]} onChange={(e) => setField(key, e.target.value)} className="h-9 rounded-md border border-slate-200 px-2.5 text-xs text-slate-700" /></label>)}<label className="grid gap-1.5 text-[10px] font-semibold text-slate-500">State<select value={form.state} onChange={(e) => setField('state', e.target.value)} className="h-9 rounded-md border border-slate-200 px-2 text-xs"><option value="">Use global filter / all</option>{stateOptions.map((s) => <option key={s}>{s}</option>)}</select></label><label className="grid gap-1.5 text-[10px] font-semibold text-slate-500">District<input value={form.district} onChange={(e) => setField('district', e.target.value)} placeholder="Use global filter / all" className="h-9 rounded-md border border-slate-200 px-2.5 text-xs" /></label></div><div className="mt-4 flex flex-wrap gap-2"><Button disabled={busy}>{busy ? 'Calculating…' : 'Calculate allocation'}</Button><Button type="button" variant="secondary" onClick={save}>Save scenario</Button></div></form>{result && <div className="mt-4 rounded-lg border border-slate-200 p-4"><Section title={result.result.status === 'feasible' ? 'Proposed allocation' : 'Infeasible scenario'} subtitle={result.result.status === 'feasible' ? 'Exact integer plan under submitted constraints.' : result.result.reason} />{result.result.status === 'feasible' ? <><div className="mb-3 grid grid-cols-3 gap-2">{[['Seats', result.result.total_seats], ['Estimated cost', `₹${fmt(result.result.total_cost)}`], ['Demand proxy covered', result.result.covered_demand_proxy]].map(([k, v]) => <div key={k} className="rounded-md bg-slate-50 p-3"><div className="text-[9px] text-slate-500">{k}</div><b className="mt-1 block text-base">{v}</b></div>)}</div><Table columns={['Occupation', 'Seats', 'Estimated cost', 'Demand proxy']} rows={result.result.allocations.filter((a) => a.seats).map((a) => <tr key={a.occupation_code}><td className={td}>{a.occupation_title}</td><td className={td}>{a.seats}</td><td className={td}>₹{fmt(a.cost)}</td><td className={td}>{a.demand_proxy}</td></tr>)} /><div className="mt-3"><InfoBox>Budget ₹{fmt(result.result.budget)} · Capacity {result.result.capacity} seats · Human review required.</InfoBox></div></> : <InfoBox>{result.result.reason}</InfoBox>}</div>}</Card><Card><Section title="Saved scenarios" subtitle="Stored in the local SQLite database." />{scenarios?.length ? <Table columns={['Name', 'Saved', '']} rows={scenarios.map((s) => <tr key={s.id}><td className={td}><b>{s.name}</b></td><td className={td}>{s.created_at}</td><td className={td}><button onClick={() => open(s.id)} className="font-semibold text-teal-700">Reload</button></td></tr>)} /> : <p className="py-6 text-center text-xs text-slate-400">No saved scenarios yet.</p>}<div className="mt-3"><InfoBox>Costs are user-entered assumptions. Demand coverage is a proxy, not a placement impact estimate. Human review is required.</InfoBox></div></Card></div></>
}
function DataQuality({ sources, reload, notify }) {
  const [error, setError] = useState(''), [busy, setBusy] = useState(false), [source, setSource] = useState({ name: 'Planner CSV import', type: 'imported', method: 'user CSV upload' })
  const upload = async (e) => { e.preventDefault(); const formElement = e.currentTarget, form = new FormData(formElement), file = form.get('file'); if (!file?.size) return; setBusy(true); setError(''); try { const q = query({ source_name: source.name, source_type: source.type, access_method: source.method }); const r = await api(`/api/import?${q}`, { method: 'POST', body: form }); notify(`Imported ${r.rows_imported} rows`); formElement.reset(); reload() } catch (ex) { setError(ex.message) } finally { setBusy(false) } }
  const rows = sources?.map((s) => <tr key={s.id}><td className={`${td} font-semibold text-slate-700`}>{s.name}</td><td className={td}><Pill tone={s.is_synthetic ? 'amber' : 'green'}>{s.source_type}</Pill></td><td className={td}>{s.access_method}</td><td className={td}>{s.first_period || '—'} – {s.last_period || '—'}</td><td className={td}>{fmt(s.observation_count)}</td><td className={td}>{s.is_synthetic ? 'Synthetic demo' : 'Imported'}</td></tr>) || []
  return <><Section title="Source registry" subtitle="Provenance, reporting coverage, and record counts." /><Card><Table columns={['Source', 'Type', 'Access method', 'Reporting period', 'Records', 'Provenance']} rows={rows} /></Card><div className="grid gap-3 xl:grid-cols-2"><Card><Section title="Import observations" subtitle="CSV only · UTF-8 · maximum 5 MiB · atomic validation." /><EmptyError error={error} /><form onSubmit={upload} className="space-y-3"><label className="grid gap-1 text-[10px] font-semibold text-slate-500">CSV file<input name="file" type="file" accept=".csv,text/csv" required className="rounded-md border border-slate-200 p-2 text-xs" /></label><div className="grid gap-3 sm:grid-cols-3">{[['name', 'Source label'], ['type', 'Source type'], ['method', 'Access method']].map(([k, label]) => <label key={k} className="grid gap-1 text-[10px] font-semibold text-slate-500">{label}<input required value={source[k]} onChange={(e) => setSource((v) => ({ ...v, [k]: e.target.value }))} className="h-9 rounded-md border border-slate-200 px-2 text-xs" /></label>)}</div><Button disabled={busy}>{busy ? 'Validating…' : 'Validate & import'}</Button></form><p className="mt-3 text-[10px] leading-5 text-slate-500">Required fields: period, state, district, sector, occupation_code, occupation_title, demand_count, training_seats. <a className="text-teal-700 underline" href="/static/demo-template.csv" download>Download CSV template</a></p></Card><Card><Section title="Data quality" subtitle="Known coverage limitations." /><InfoBox>Synthetic demonstration data — not official government statistics.<br />Unique key per source: period, state, district, occupation code.<br />Unknown occupation codes are retained without invented mappings.<br />Personal worker records are not collected.</InfoBox></Card></div></>
}
function Reports({ filtersQuery }) {
  return <><Section title="Reports & exports" subtitle="Download persisted observations with provenance or saved scenario results." /><div className="grid gap-3 md:grid-cols-3">{[['Observation extract', 'CSV includes source provenance and quality notes.', `/api/exports/observations.csv?${filtersQuery}`, 'Download observations CSV'], ['Saved scenarios', 'Saved inputs and optimizer results from this database.', '/api/exports/scenarios.csv', 'Download scenarios CSV']].map(([title, desc, href, action]) => <Card key={title}><h3 className="font-bold">{title}</h3><p className="my-2 min-h-8 text-[11px] leading-5 text-slate-500">{desc}</p><a href={href} className="inline-flex rounded-md border border-teal-700 bg-teal-700 px-3 py-2 text-[11px] font-semibold text-white no-underline hover:bg-teal-800">{action}</a></Card>)}<Card><h3 className="font-bold">Reproducibility</h3><p className="my-2 text-[11px] leading-5 text-slate-500">Demo fixture is deterministic and versioned with this project.</p><InfoBox>Reset demo database: <code>python -m backend.seed --reset</code></InfoBox></Card></div><Card className="mt-3"><Section title="Evidence and interpretation" subtitle="Exported counts are source observations or labelled demo values." /><InfoBox>Exports do not contain model confidence, inferred placements, workforce supply, or unsupported gap classifications. Review source type and reporting period before using results.</InfoBox></Card></>
}
function Methodology() {
  return <><Section title="Definitions and methods" subtitle="Interpretation is bounded by records actually available." /><div className="grid gap-3 xl:grid-cols-2"><Card><Section title="Measures" /><InfoBox><b>Observed demand:</b> count provided by a source; synthetic values are demonstration only.<br /><b>Training seats:</b> recorded capacity; latest period shown as snapshot.<br /><b>Workforce supply and gap:</b> unavailable without comparable measures.<br /><b>Occupation codes:</b> demo labels, not NCO mappings.<br /><b>Geography:</b> input labels; district boundaries are not implied.</InfoBox><Section title="Provenance" /><InfoBox>Observations reference source type, access method, period, geography, units and quality notes. NCO is an occupational classification; NCS is an employment and career service. PLFS is survey-based, not a live vacancy source. No government integration is implemented.</InfoBox></Card><Card><Section title="Forecast and warnings" /><InfoBox>Forecasts use ordinary least squares on monthly period indices. At least three months are required; horizon is 1–12 months. No seasonality, confidence interval or accuracy claim is provided.<br /><br />Alerts compare the last two observed periods per occupation and district; a rise of 25% or more prompts review. It is not a shortage finding.</InfoBox><Section title="Allocation" /><InfoBox>Exact integer-seat optimization maximizes seats up to latest observed demand proxy, subject to budget, unit cost, observed seat caps and district capacity. Optional minimum seats can demonstrate infeasibility. It does not model outcomes. Human review is required.</InfoBox></Card></div><Card className="mt-3"><Section title="Governance and limitations" subtitle="Local prototype controls and limits." /><InfoBox>There is no authentication, role-based access, approval workflow or secure government infrastructure. Use only permitted aggregate data; do not upload personal worker information. The prototype is not production-certified.</InfoBox></Card></>
}
