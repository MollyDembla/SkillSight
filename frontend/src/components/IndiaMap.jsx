import { useEffect, useMemo, useRef, useState } from 'react'
import { geoMercator, geoPath } from 'd3-geo'

let geoCache = null
function useGeo() {
  const [geo, setGeo] = useState(geoCache)
  useEffect(() => {
    if (geoCache) return
    fetch('/geo/india-districts.json').then((r) => r.json()).then((g) => {
      // d3-geo expects clockwise exterior rings (the reverse of RFC 7946); a counter-clockwise ring is read
      // as "the whole globe minus this district". Reverse rings with positive planar area.
      for (const f of g.features) for (const poly of f.geometry.coordinates) for (const ring of poly) {
        let a = 0
        for (let i = 0; i < ring.length - 1; i++) a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
        if (a > 0) ring.reverse()
      }
      geoCache = g; setGeo(g)
    }).catch(() => setGeo({ type: 'FeatureCollection', features: [] }))
  }, [])
  return geo
}

/**
 * District choropleth. values: {[districtName|state]: {...}}, keyed by `${state}|${district}`.
 * colorOf(value) -> fill; tooltip(feature, value) -> node. flows: [{from:[lon,lat], to:[lon,lat], w}]. points: [{lon,lat,r,label}]
 */
export default function IndiaMap({ values = {}, colorOf, tooltip, focusState, selected, onSelect, flows, points, height: maxHeight = 520, label = 'Map', showOthers = true }) {
  const geo = useGeo()
  const wrap = useRef(null)
  const [w, setW] = useState(600)
  const [hover, setHover] = useState(null)
  useEffect(() => {
    const el = wrap.current
    if (!el) return undefined
    setW(Math.max(280, el.getBoundingClientRect().width))
    const ro = new ResizeObserver(([e]) => setW(Math.max(280, e.contentRect.width)))
    ro.observe(el)
    return () => ro.disconnect()
  }, [Boolean(geo)])
  const height = Math.min(maxHeight, Math.round(w * 1.05))
  const { path, features, proj } = useMemo(() => {
    if (!geo?.features?.length) return { features: [] }
    const pilot = geo.features.filter((f) => f.properties.p)
    const shown = focusState ? geo.features.filter((f) => f.properties.s === focusState) : showOthers ? geo.features : pilot
    const fitTo = { type: 'FeatureCollection', features: focusState ? shown : (showOthers ? geo.features : pilot) }
    const proj = geoMercator().fitSize([w, height], fitTo)
    return { path: geoPath(proj), features: shown, proj }
  }, [geo, focusState, w, height, showOthers])
  if (!geo) return <div ref={wrap} className="skeleton w-full" style={{ height: maxHeight }} />
  const key = (f) => `${f.properties.s}|${f.properties.d}`
  return <div ref={wrap} className="relative w-full" onMouseLeave={() => setHover(null)}>
    <svg width="100%" height={height} viewBox={`0 0 ${w} ${height}`} role="img" aria-label={label}>
      <title>{label}</title>
      <g>{features.map((f, i) => {
        const v = values[key(f)], pilot = f.properties.p
        return <path key={i} d={path(f)} className={`map-path ${pilot ? 'pilot' : ''} ${selected && selected === key(f) ? 'sel' : ''}`}
          fill={pilot ? colorOf(v, f) : 'var(--nodata)'} opacity={pilot ? 1 : 0.45}
          tabIndex={pilot && onSelect ? 0 : undefined} aria-label={pilot ? `${f.properties.d}, ${f.properties.s}` : undefined}
          onMouseMove={pilot ? (e) => { const r = wrap.current.getBoundingClientRect(); setHover({ f, v, x: e.clientX - r.left, y: e.clientY - r.top }) } : undefined}
          onFocus={pilot ? () => { const [x, y] = path.centroid(f); setHover({ f, v, x, y }) } : undefined}
          onBlur={() => setHover(null)}
          onClick={pilot && onSelect ? () => onSelect(f.properties, v) : undefined}
          onKeyDown={pilot && onSelect ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect(f.properties, v) } } : undefined} />
      })}</g>
      {flows && proj && <g fill="none">{flows.map((fl, i) => {
        const a = proj(fl.from), b = proj(fl.to)
        if (!a || !b) return null
        const mx = (a[0] + b[0]) / 2 - (b[1] - a[1]) * 0.25, my = (a[1] + b[1]) / 2 + (b[0] - a[0]) * 0.25
        return <path key={i} d={`M${a[0]},${a[1]} Q${mx},${my} ${b[0]},${b[1]}`} stroke={fl.color || 'var(--ink-2)'} strokeOpacity={0.45} strokeWidth={Math.max(0.6, fl.w)} strokeLinecap="round"><title>{fl.title}</title></path>
      })}</g>}
      {points && proj && <g>{points.map((p, i) => { const xy = proj([p.lon, p.lat]); return xy ? <circle key={i} cx={xy[0]} cy={xy[1]} r={p.r} fill={p.color || 'var(--series-1)'} fillOpacity={0.75} stroke="var(--surface)" strokeWidth={1.5}><title>{p.label}</title></circle> : null })}</g>}
    </svg>
    {hover && tooltip && <div className="tip pointer-events-none absolute z-10 max-w-[17rem]" style={{ left: Math.min(hover.x + 14, w - 250), top: Math.max(0, hover.y - 10) }}>{tooltip(hover.f.properties, hover.v)}</div>}
  </div>
}
