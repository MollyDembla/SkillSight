"""Simplify downloaded district GeoJSON (udit-001/india-maps-data, Census 2011 codes) into compact map assets.

Usage: python scripts/build_geo.py <geo_dir> <out_dir>
<geo_dir> holds india.geojson plus karnataka/maharashtra/odisha/uttar-pradesh.geojson.
Writes india-districts.json (all districts, Douglas-Peucker simplified) and districts-meta.json (centroids for pilot states).
"""
import json, sys
from pathlib import Path

PILOT = {"Karnataka", "Maharashtra", "Odisha", "Uttar Pradesh"}


def dp(points, eps):
    if len(points) < 4:
        return points
    stack, keep = [(0, len(points) - 1)], {0, len(points) - 1}
    while stack:
        a, b = stack.pop()
        (x1, y1), (x2, y2) = points[a], points[b]
        dx, dy = x2 - x1, y2 - y1
        norm = (dx * dx + dy * dy) ** 0.5 or 1e-12
        best, idx = 0.0, None
        for i in range(a + 1, b):
            x, y = points[i]
            d = abs(dy * x - dx * y + x2 * y1 - y2 * x1) / norm
            if d > best:
                best, idx = d, i
        if idx is not None and best > eps:
            keep.add(idx); stack += [(a, idx), (idx, b)]
    return [points[i] for i in sorted(keep)]


def simplify_ring(ring, eps):
    # Closed rings start and end on the same point; split at the farthest vertex so DP has a real baseline.
    x0, y0 = ring[0]
    far = max(range(len(ring)), key=lambda i: (ring[i][0] - x0) ** 2 + (ring[i][1] - y0) ** 2)
    pts = dp(ring[: far + 1], eps) + dp(ring[far:], eps)[1:]
    out = [[round(x, 3), round(y, 3)] for x, y in pts]
    return out if len(out) >= 4 else None


def simplify(geom, eps):
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    res = []
    for poly in polys:
        rings = [r for r in (simplify_ring(r, eps) for r in poly[:1]) if r]
        if rings:
            res.append(rings)
    return {"type": "MultiPolygon", "coordinates": res}


def centroid(geom):
    best = max((p[0] for p in geom["coordinates"]), key=len)
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(best, best[1:]):
        f = x1 * y2 - x2 * y1; a += f; cx += (x1 + x2) * f; cy += (y1 + y2) * f
    if abs(a) < 1e-12:
        xs, ys = zip(*best); return [sum(xs) / len(xs), sum(ys) / len(ys)]
    return [round(cx / (3 * a), 4), round(cy / (3 * a), 4)]


def main(src, out):
    src, out = Path(src), Path(out); out.mkdir(parents=True, exist_ok=True)
    feats, meta = [], []
    # Pilot states come from the per-state files (cleaner); the national file supplies background districts only.
    background = [f for f in json.load(open(src / "india.geojson"))["features"] if f["properties"].get("st_nm") not in PILOT]
    pilots = [f for name in ("karnataka", "maharashtra", "odisha", "uttar-pradesh") for f in json.load(open(src / f"{name}.geojson"))["features"]]
    for f in pilots + background:
        p = f["properties"]
        if not p.get("district"):
            continue
        pilot = p["st_nm"] in PILOT
        g = simplify(f["geometry"], 0.008 if pilot else 0.03)
        if not g["coordinates"]:
            continue
        feats.append({"type": "Feature", "properties": {"d": p["district"], "s": p["st_nm"], "c": p.get("dt_code", ""), "p": int(pilot)}, "geometry": g})
        if pilot:
            lon, lat = centroid(g)
            meta.append({"lgd": p.get("dt_code", ""), "district": p["district"], "state": p["st_nm"], "lat": lat, "lon": lon})
    (out / "india-districts.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")))
    (out / "districts-meta.json").write_text(json.dumps(sorted(meta, key=lambda m: (m["state"], m["district"])), indent=0))
    print(len(feats), "features;", len(meta), "pilot districts")


if __name__ == "__main__":
    main(*sys.argv[1:3])
