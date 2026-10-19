import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { onAuthStateChanged, signOut } from 'firebase/auth'
import { useTranslation } from 'react-i18next'
import { firebaseAuth, firebaseConfigured } from './firebase.js'
import { api, useApi } from './api.js'
import { LANGS } from './i18n.js'
import { ConnectionScreen, SetupScreen, SignInScreen } from './components/Auth.jsx'
import { Select, Skeleton } from './components/ui.jsx'
import Copilot from './components/Copilot.jsx'

const PAGES = {
  overview: lazy(() => import('./pages/Overview.jsx')), map: lazy(() => import('./pages/GeoPage.jsx')), trades: lazy(() => import('./pages/Trades.jsx')),
  alerts: lazy(() => import('./pages/Alerts.jsx')), planner: lazy(() => import('./pages/Planner.jsx')), whatif: lazy(() => import('./pages/WhatIf.jsx')),
  mobility: lazy(() => import('./pages/Mobility.jsx')), skills: lazy(() => import('./pages/Skills.jsx')), data: lazy(() => import('./pages/DataHub.jsx')),
  reports: lazy(() => import('./pages/Reports.jsx')), method: lazy(() => import('./pages/Methodology.jsx')),
}
const NAV = [
  ['intel', [['overview', '◫'], ['map', '⌖'], ['trades', '▤'], ['alerts', '⚑'], ['mobility', '⇄']]],
  ['decide', [['planner', '▦'], ['whatif', '⌁'], ['skills', '✎']]],
  ['platform', [['data', '⇵'], ['reports', '▧'], ['method', 'ⓘ']]],
]

function parseHash() {
  const [page, query] = location.hash.slice(1).split('?')
  return { page: PAGES[page] ? page : 'overview', params: Object.fromEntries(new URLSearchParams(query || '')) }
}

function usePref(key, initial) {
  const [v, setV] = useState(() => { try { return localStorage.getItem(key) || initial } catch { return initial } })
  const set = (x) => { setV(x); try { localStorage.setItem(key, x) } catch { /* storage unavailable */ } }
  return [v, set]
}

export default function App() {
  const { t, i18n } = useTranslation()
  const [route, setRoute] = useState(parseHash)
  const [filters, setFilters] = useState({ state: '', sector: '' })
  const [toast, setToast] = useState('')
  const [navOpen, setNavOpen] = useState(false)
  const [theme, setTheme] = usePref('lmis-theme', 'auto')
  const [size, setSize] = usePref('lmis-size', 'md')
  const [health, setHealth] = useState(null)
  const [healthError, setHealthError] = useState('')
  const [authUser, setAuthUser] = useState(null)
  const [authReady, setAuthReady] = useState(!firebaseConfigured)

  useEffect(() => { const h = () => setRoute(parseHash()); window.addEventListener('hashchange', h); return () => window.removeEventListener('hashchange', h) }, [])
  useEffect(() => { const el = document.documentElement; if (theme === 'auto') el.removeAttribute('data-theme'); else el.setAttribute('data-theme', theme) }, [theme])
  useEffect(() => { document.documentElement.setAttribute('data-size', size) }, [size])
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    // The API needs ~30 s on first start (data generation + model fit); keep retrying until it answers.
    api('/api/health').then((h) => { setHealth(h); setHealthError('') }).catch((e) => { setHealthError(e.message); window.setTimeout(() => setAttempt((a) => a + 1), 3000) })
  }, [attempt])
  useEffect(() => {
    if (health?.model_ready !== false) return undefined
    const id = window.setTimeout(() => api('/api/health').then(setHealth).catch(() => {}), 5000)
    return () => window.clearTimeout(id)
  }, [health])
  useEffect(() => { if (!firebaseConfigured) return undefined; return onAuthStateChanged(firebaseAuth, (u) => { setAuthUser(u); setAuthReady(true) }) }, [])

  const authMismatch = Boolean(health && health.auth_required) !== firebaseConfigured
  const ready = Boolean(health && !authMismatch && (!health.auth_required || (authReady && authUser)))
  const ref = useApi(ready ? '/api/v1/reference' : null)
  const notify = useCallback((m) => { setToast(m); window.setTimeout(() => setToast(''), 3200) }, [])
  const go = useCallback((page, params = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '')).toString()
    location.hash = `${page}${q ? `?${q}` : ''}`
    setNavOpen(false)
    window.scrollTo({ top: 0 })
  }, [])
  const ctx = useMemo(() => ({ filters, setFilters, ref: ref.data, go, notify, params: route.params, lang: i18n.language }), [filters, ref.data, go, notify, route.params, i18n.language])

  if (healthError && !health) return <ConnectionScreen error={`${healthError} - retrying automatically (first start builds the data and models, ~30 s)…`} />
  if (!health) return <div className="grid min-h-screen place-items-center muted">{t('t.loading')}</div>
  if (authMismatch) return <SetupScreen backendRequiresAuth={health.auth_required} frontendHasFirebase={firebaseConfigured} />
  if (health.auth_required && (!authReady || !authUser)) return <SignInScreen />
  const Page = PAGES[route.page]

  return <div className="min-h-screen lg:grid lg:grid-cols-[250px_1fr]">
    <a href="#main" className="skip-link">Skip to content</a>
    <aside className={`${navOpen ? 'fixed inset-0 z-40 block' : 'hidden'} overflow-y-auto border-r lg:sticky lg:top-0 lg:block lg:h-screen`} style={{ background: 'var(--surface)', borderColor: 'var(--border)' }}>
      <div className="flex items-center gap-2.5 px-4 pb-3 pt-4">
        <span className="grid size-9 place-items-center rounded-lg text-[1.05rem] font-black" style={{ background: 'var(--brand)', color: 'var(--brand-ink)' }} aria-hidden="true">S</span>
        <div className="min-w-0"><div className="text-[1rem] font-extrabold tracking-[-.01em]">{t('app')}</div><div className="truncate text-[.66rem] font-semibold uppercase tracking-[.08em] muted">{t('tagline')}</div></div>
        <button className="btn ml-auto !min-h-8 !px-2 lg:hidden" onClick={() => setNavOpen(false)} aria-label="Close menu">✕</button>
      </div>
      <nav aria-label="Primary" className="px-2.5 pb-6">
        {NAV.map(([group, items]) => <div key={group} className="mt-3"><div className="px-2 pb-1 text-[.64rem] font-bold uppercase tracking-[.1em] muted">{t(`group.${group}`)}</div>
          {items.map(([k, icon]) => <button key={k} className="nav-item" aria-current={route.page === k ? 'page' : undefined} onClick={() => go(k)}><span aria-hidden="true" className="w-4 text-center">{icon}</span>{t(`nav.${k}`)}</button>)}</div>)}
        <div className="mt-5 rounded-lg p-3 text-[.7rem] leading-5 ink2" style={{ background: 'var(--surface-2)' }}>{t('ministry')}<br /><span className="muted">SIH 2026 · PS 26246</span></div>
      </nav>
    </aside>
    <div className="min-w-0 overflow-x-clip">
      <header className="sticky top-0 z-30 border-b px-3 py-2.5 backdrop-blur sm:px-6 no-print" style={{ background: 'color-mix(in srgb, var(--page) 88%, transparent)', borderColor: 'var(--border)' }}>
        <div className="flex flex-wrap items-end gap-2.5">
          <button className="btn !min-h-9 lg:hidden" onClick={() => setNavOpen(true)} aria-label="Open menu">☰</button>
          <Select label={t('f.state')} value={filters.state} onChange={(v) => setFilters((f) => ({ ...f, state: v }))} placeholder={t('f.all_states')} options={ref.data?.states || []} />
          <Select label={t('f.sector')} value={filters.sector} onChange={(v) => setFilters((f) => ({ ...f, sector: v }))} placeholder={t('f.all_sectors')} options={(ref.data?.sectors || []).map((s) => [s.sector, s.sector_name])} />
          <div className="flex w-full flex-wrap items-end gap-2 sm:ml-auto sm:w-auto">
            <Select label={t('t.language')} value={i18n.language} onChange={(l) => i18n.changeLanguage(l)} options={LANGS} className="!min-w-[7rem]" />
            <Select label={t('t.theme')} value={theme} onChange={setTheme} options={[['auto', 'Auto'], ['light', t('t.light')], ['dark', t('t.dark')], ['contrast', t('t.contrast')]]} className="!min-w-[7rem]" />
            <div className="grid gap-1 text-[.7rem] font-semibold muted">{t('t.text_size')}<div className="flex gap-1" role="group" aria-label={t('t.text_size')}>{[['md', 'A'], ['lg', 'A+'], ['xl', 'A++']].map(([k, l]) => <button key={k} className="btn !min-h-[2.4rem] !px-2.5" aria-pressed={size === k} style={size === k ? { borderColor: 'var(--brand)', color: 'var(--brand)' } : undefined} onClick={() => setSize(k)}>{l}</button>)}</div></div>
          </div>
        </div>
      </header>
      <div className="mx-3 mt-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-[.75rem] sm:mx-6" style={{ borderColor: 'var(--warn)', color: 'var(--ink-2)' }}>
        <span><b style={{ color: 'var(--warn)' }}>ⓘ</b> {t('synthetic')}</span>
        <span className="flex items-center gap-3">{health.model_ready === false && <span className="chip">Model warming up…</span>}{authUser && <button className="underline" onClick={() => signOut(firebaseAuth)}>Sign out</button>}</span>
      </div>
      <main id="main" className="px-3 pb-24 pt-4 sm:px-6">
        {!ref.data ? <Skeleton h={400} /> : <Suspense fallback={<Skeleton h={400} />}><Page ctx={ctx} /></Suspense>}
      </main>
    </div>
    {ref.data && <Copilot ctx={ctx} />}
    {toast && <div role="status" className="fixed bottom-5 left-1/2 z-50 -translate-x-1/2 rounded-lg px-4 py-2.5 text-[.85rem] font-semibold shadow-lg" style={{ background: 'var(--ink)', color: 'var(--page)' }}>{toast}</div>}
  </div>
}
