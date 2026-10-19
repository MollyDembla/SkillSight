import { useCallback, useEffect, useRef, useState } from 'react'
import { firebaseAuth } from './firebase.js'

export async function api(url, options = {}) {
  const headers = new Headers(options.headers || {})
  if (firebaseAuth?.currentUser) headers.set('Authorization', `Bearer ${await firebaseAuth.currentUser.getIdToken()}`)
  if (options.json !== undefined) { headers.set('Content-Type', 'application/json'); options = { ...options, body: JSON.stringify(options.json) } }
  const response = await fetch(url, { ...options, headers })
  if (options.raw) { if (!response.ok) throw new Error(await response.text()); return response }
  let data
  try { data = await response.json() } catch { data = null }
  if (!response.ok) throw new Error(typeof data?.detail === 'string' ? data.detail : JSON.stringify(data?.detail || data || response.statusText))
  return data
}

export const qs = (obj) => new URLSearchParams(Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== '' && v != null && v !== undefined))).toString()

/** Fetch JSON for a URL; refetches when the URL changes. Returns { data, error, loading, reload }. */
export function useApi(url) {
  const [state, setState] = useState({ data: null, error: '', loading: Boolean(url) })
  const [tick, setTick] = useState(0)
  const live = useRef(0)
  useEffect(() => {
    if (!url) return
    const id = ++live.current
    setState((s) => ({ ...s, loading: true, error: '' }))
    api(url).then((data) => { if (id === live.current) setState({ data, error: '', loading: false }) })
      .catch((e) => { if (id === live.current) setState({ data: null, error: e.message, loading: false }) })
  }, [url, tick])
  const reload = useCallback(() => setTick((t) => t + 1), [])
  return { ...state, reload }
}

export async function download(url, options, filename) {
  const res = await api(url, { ...options, raw: true })
  const blob = await res.blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = filename || (res.headers.get('content-disposition') || '').split('filename=')[1] || 'export'
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 2000)
}

const lakhFmt = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 })
export const fmt = (n) => (n == null || Number.isNaN(+n) ? '–' : lakhFmt.format(Math.round(+n)))
export const compact = (n) => {
  const v = Math.abs(+n || 0), s = n < 0 ? '-' : ''
  if (v >= 1e7) return `${s}${(v / 1e7).toFixed(2)} Cr`
  if (v >= 1e5) return `${s}${(v / 1e5).toFixed(2)} L`
  if (v >= 1e3) return `${s}${(v / 1e3).toFixed(1)}k`
  return `${s}${Math.round(v)}`
}
export const pct = (x, digits = 0, signed = false) => (x == null ? '–' : `${signed && x > 0 ? '+' : ''}${(x * 100).toFixed(digits)}%`)
export const rupees = (n) => `₹${compact(n)}`
