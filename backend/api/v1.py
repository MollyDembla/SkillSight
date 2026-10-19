"""Versioned REST API (/api/v1). OpenAPI docs at /docs."""
from __future__ import annotations
import csv, hashlib, io, json, secrets, sqlite3, threading
from typing import Literal, Optional
from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field
from .. import catalog, llm, resolve, services
from ..db import FUTURE, PERIODS, connect, rows
from ..models import insights, optimizer
from ..pipeline import nco_coder, run as pipeline
from . import exports, report

router = APIRouter(prefix="/api/v1")
DATA_LABEL = "Synthetic demonstration data - not official government statistics"


def _state():
    pipeline.ensure_ready()
    return pipeline.STATE


def _db():
    return connect()


# ---------------------------------------------------------------- reference & overview
@router.get("/reference", tags=["reference"])
def reference():
    c = _db()
    try:
        return services.reference(c)
    finally:
        c.close()


@router.get("/overview", tags=["intelligence"])
def overview(state: Optional[str] = None, sector: Optional[str] = None):
    c = _db()
    try:
        out = services.overview(c, state, sector)
        out["pipeline"] = pipeline.last_run(c)
        return out
    finally:
        c.close()


@router.get("/map", tags=["intelligence"])
def map_layer(state: Optional[str] = None, sector: Optional[str] = None, trade: Optional[str] = None):
    """District-level rollup for the choropleth (gap ratio, severity, trust)."""
    c = _db()
    try:
        return {"districts": services.rollup(c, "district", state=state, sector=sector, trade=trade), "states": services.rollup(c, "state", sector=sector, trade=trade)}
    finally:
        c.close()


@router.get("/gaps", tags=["intelligence"])
def gaps(state: Optional[str] = None, lgd: Optional[str] = None, sector: Optional[str] = None, trade: Optional[str] = None, status: Optional[str] = None,
         emerging: Optional[bool] = None, sort: str = "severity", limit: int = Query(100, ge=1, le=5000), offset: int = Query(0, ge=0)):
    c = _db()
    try:
        return services.gap_rows(c, state, lgd, sector, trade, status, emerging, sort, limit, offset)
    finally:
        c.close()


@router.get("/rankings", tags=["intelligence"])
def rankings(by: Literal["state", "district", "trade", "sector", "state_trade"] = "trade", state: Optional[str] = None, sector: Optional[str] = None,
             trade: Optional[str] = None, order: Literal["shortage", "surplus", "severity"] = "shortage", limit: int = Query(50, ge=1, le=1000)):
    c = _db()
    try:
        out = services.rollup(c, by, state, sector, trade)
        key = {"shortage": lambda r: r["gap_ratio"], "surplus": lambda r: -r["gap_ratio"], "severity": lambda r: -r["severity"]}[order]
        return sorted(out, key=key)[:limit]
    finally:
        c.close()


@router.get("/districts/{lgd}", tags=["intelligence"])
def district(lgd: str):
    c = _db()
    try:
        d = services.district_profile(c, lgd)
        if not d:
            raise HTTPException(404, "District not found")
        return d
    finally:
        c.close()


@router.get("/trades/{code}/series", tags=["forecast"])
def trade_series(code: str, node: str = "IN"):
    c = _db()
    try:
        if not c.execute("SELECT 1 FROM trades WHERE code=?", (code,)).fetchone():
            raise HTTPException(404, "Trade not found")
        return services.series(c, code, node)
    finally:
        c.close()


# ---------------------------------------------------------------- early warning
@router.get("/alerts", tags=["early-warning"])
def alerts(state: Optional[str] = None, lgd: Optional[str] = None, sector: Optional[str] = None, kind: Optional[str] = None, status: Optional[str] = None,
           limit: int = Query(200, ge=1, le=3000)):
    c = _db()
    try:
        return services.alerts(c, state, lgd, sector, kind, status, limit)
    finally:
        c.close()


class AlertUpdate(BaseModel):
    status: Literal["open", "acknowledged", "assigned", "actioned", "dismissed"]
    assignee: str = Field("", max_length=120)
    note: str = Field("", max_length=1000)


@router.patch("/alerts/{aid}", tags=["early-warning"])
def update_alert(aid: int, body: AlertUpdate):
    c = _db()
    try:
        cur = c.execute("UPDATE alerts SET status=?, assignee=?, note=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (body.status, body.assignee, body.note, aid))
        c.commit()
        if not cur.rowcount:
            raise HTTPException(404, "Alert not found")
        return rows(c, "SELECT * FROM alerts WHERE id=?", (aid,))[0]
    finally:
        c.close()


@router.get("/alerts/digest", tags=["early-warning"])
def alert_digest(state: Optional[str] = None, channel: Literal["whatsapp", "email", "sms"] = "whatsapp", lang: str = "en"):
    """Preview of the periodic alert digest sent to state planning units (delivery is simulated)."""
    c = _db()
    try:
        items = services.alerts(c, state=state, limit=6)
    finally:
        c.close()
    head = {"en": f"SkillSight early warnings - {state or 'pilot states'}", "hi": f"स्किलसाइट प्रारंभिक चेतावनियाँ - {state or 'पायलट राज्य'}"}.get(lang, "SkillSight early warnings")
    lines = [f"{i + 1}. {a['trade']} | {a['district']} | {a['kind'].replace('_', ' ')} | P={a['probability']:.0%}" + (f" | by Q{a['lead_quarter']}" if a["lead_quarter"] else "") for i, a in enumerate(items)]
    if channel == "sms":
        body = head + ": " + "; ".join(f"{a['trade']} {a['district']} {a['kind'].split('_')[0]}" for a in items[:3])
        return {"channel": channel, "body": body[:300]}
    return {"channel": channel, "subject": head, "body": "\n".join([f"*{head}*" if channel == "whatsapp" else head, *lines, "Open dashboard: /#alerts"])}


class WebhookIn(BaseModel):
    url: str = Field(pattern=r"^https?://", max_length=500)
    min_severity: float = Field(60, ge=0, le=100)
    state: str = ""


@router.post("/webhooks", tags=["early-warning"])
def add_webhook(body: WebhookIn):
    c = _db()
    try:
        wid = c.execute("INSERT INTO webhooks(url, min_severity, state) VALUES(?,?,?)", (body.url, body.min_severity, body.state)).lastrowid
        c.commit()
        return {"id": wid, **body.model_dump(), "note": "Registered. Alert payloads are delivered after each pipeline run (delivery simulated in the demo)."}
    finally:
        c.close()


@router.get("/webhooks", tags=["early-warning"])
def list_webhooks():
    c = _db()
    try:
        return rows(c, "SELECT * FROM webhooks ORDER BY id")
    finally:
        c.close()


# ---------------------------------------------------------------- decision support
class OptimiseIn(BaseModel):
    state: Optional[str] = None
    sector: Optional[str] = None
    budget_change: float = Field(0.0, ge=-0.5, le=1.0)
    max_change: float = Field(0.5, ge=0.0, le=1.0)
    women_target: Optional[float] = Field(None, ge=0, le=0.8)
    protect_aspirational: bool = True
    risk: float = Field(0.0, ge=0, le=1)
    shortage_weight: float = Field(1.0, ge=0.1, le=5)
    surplus_weight: float = Field(0.6, ge=0, le=5)


def _optimise(body: OptimiseIn):
    st = _state()
    return optimizer.optimise(st, body.state, body.budget_change, body.max_change, body.women_target, body.protect_aspirational, body.risk,
                              body.shortage_weight, body.surplus_weight, body.sector)


@router.post("/targets/optimize", tags=["decision"])
def optimise(body: OptimiseIn, rows_limit: int = Query(300, ge=1, le=5000)):
    res = _optimise(body)
    if res["status"] == "infeasible":
        raise HTTPException(422, res["reason"])
    return {**res, "rows": res["rows"][:rows_limit], "rows_total": len(res["rows"])}


@router.post("/targets/export", tags=["decision", "export"])
def export_targets(body: OptimiseIn, format: Literal["xlsx", "csv", "json"] = "xlsx"):
    res = _optimise(body)
    if res["status"] == "infeasible":
        raise HTTPException(422, res["reason"])
    return exports.targets(res, format)


class ScenarioIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    request: OptimiseIn


@router.post("/scenarios", tags=["decision"])
def save_scenario(body: ScenarioIn):
    res = _optimise(body.request)
    if res["status"] == "infeasible":
        raise HTTPException(422, res["reason"])
    c = _db()
    try:
        sid = c.execute("INSERT INTO scenarios(name, kind, inputs_json, result_json) VALUES(?, 'targets', ?, ?)",
                        (body.name, json.dumps(body.request.model_dump()), json.dumps({k: v for k, v in res.items() if k != "rows"} | {"rows": res["rows"][:2000]}))).lastrowid
        c.commit()
        return {"id": sid, "name": body.name, "summary": res["summary"]}
    finally:
        c.close()


@router.get("/scenarios", tags=["decision"])
def list_scenarios():
    c = _db()
    try:
        out = []
        for r in rows(c, "SELECT id, name, kind, inputs_json, result_json, created_at FROM scenarios ORDER BY id DESC"):
            res = json.loads(r.pop("result_json"))
            r["inputs"] = json.loads(r.pop("inputs_json"))
            r["summary"] = res.get("summary")
            out.append(r)
        return out
    finally:
        c.close()


@router.get("/scenarios/{sid}", tags=["decision"])
def get_scenario(sid: int):
    c = _db()
    try:
        r = c.execute("SELECT * FROM scenarios WHERE id=?", (sid,)).fetchone()
        if not r:
            raise HTTPException(404, "Scenario not found")
        return {"id": r["id"], "name": r["name"], "created_at": r["created_at"], "inputs": json.loads(r["inputs_json"]), "result": json.loads(r["result_json"])}
    finally:
        c.close()


class InvestmentIn(BaseModel):
    lgd: str
    sector: str
    jobs_ops: int = Field(ge=10, le=100000)
    jobs_build: int = Field(0, ge=0, le=200000)
    ops_start: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    build_months: int = Field(9, ge=3, le=36)
    ramp_months: int = Field(12, ge=1, le=36)
    name: str = Field("Hypothetical project", max_length=120)


@router.post("/simulate/investment", tags=["decision"])
def simulate(body: InvestmentIn):
    try:
        return insights.simulate_investment(_state(), body.lgd, body.sector, body.jobs_ops, body.jobs_build, body.ops_start, body.build_months, body.ramp_months, body.name)
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/pathways", tags=["decision"])
def pathways(state: Optional[str] = None, lgd: Optional[str] = None, limit: int = Query(50, ge=1, le=500)):
    return insights.pathways(_state(), lgd=lgd, state_name=state, limit=limit)


@router.get("/curriculum", tags=["decision"])
def curriculum(trade: Optional[str] = None):
    c = _db()
    try:
        return insights.curriculum(c, trade)
    finally:
        c.close()


@router.get("/siting", tags=["decision"])
def siting(state: Optional[str] = None, limit: int = Query(60, ge=1, le=200)):
    c = _db()
    try:
        return insights.siting(c, _state(), state)[:limit]
    finally:
        c.close()


@router.get("/mobility", tags=["intelligence"])
def mobility(sector: Optional[str] = None, min_share: float = Query(0.02, ge=0, le=1), limit: int = Query(250, ge=1, le=2000)):
    c = _db()
    try:
        return services.mobility(c, sector, min_share, limit)
    finally:
        c.close()


@router.get("/centres", tags=["reference"])
def centres(lgd: Optional[str] = None, state: Optional[str] = None):
    c = _db()
    try:
        sql, args = "SELECT ce.*, d.district, d.state FROM centres ce JOIN districts d USING(lgd) WHERE 1=1", []
        if lgd:
            sql += " AND ce.lgd=?"
            args.append(lgd)
        if state:
            sql += " AND d.state=?"
            args.append(state)
        return rows(c, sql, args)
    finally:
        c.close()


# ---------------------------------------------------------------- reports & AI
@router.get("/reports/dsdp/{lgd}", response_class=HTMLResponse, tags=["reports"])
def dsdp(lgd: str, lang: Literal["en", "hi", "kn", "mr", "or"] = "en"):
    c = _db()
    try:
        prof = services.district_profile(c, lgd)
        if not prof:
            raise HTTPException(404, "District not found")
        cur = insights.curriculum(c)
    finally:
        c.close()
    st = _state()
    paths = insights.pathways(st, lgd=lgd, limit=8)
    site = next((s for s in insights.siting(connect(), st, prof["district"]["state"]) if s["lgd"] == lgd), None)
    return report.dsdp_html(prof, paths, site, cur, lang)


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[dict] = Field(default_factory=list, max_length=20)


@router.post("/copilot/chat", tags=["ai"])
def copilot(body: ChatIn):
    return llm.chat(body.message, body.history, _state())


@router.get("/copilot/status", tags=["ai"])
def copilot_status():
    return {"llm_available": llm.available(), "provider": "Google Gemini", "model": (llm._health["preferred"] or llm.MODEL) if llm.available() else None, "mode": "gemini" if llm.available() else "offline"}


class ClassifyIn(BaseModel):
    titles: list[str] = Field(min_length=1, max_length=50)
    descriptions: list[str] = Field(default_factory=list)
    use_llm: bool = True


@router.post("/nco/classify", tags=["ai"])
def classify(body: ClassifyIn):
    c = _db()
    try:
        model = nco_coder.get_model(c)
    finally:
        c.close()
    descs = body.descriptions + [""] * (len(body.titles) - len(body.descriptions))
    preds = nco_coder.predict(model, list(zip(body.titles, descs)))
    titles = nco_coder.trade_titles()
    low = [i for i, p in enumerate(preds) if p["confidence"] < nco_coder.THRESHOLD]
    llm_res = llm.llm_code_titles([{"title": body.titles[i], "description": descs[i]} for i in low]) if body.use_llm and low else None
    out = []
    for i, (t, p) in enumerate(zip(body.titles, preds)):
        r = {"title": t, "code": p["code"], "occupation": titles.get(p["code"]), "confidence": round(p["confidence"], 3), "method": "tfidf-logreg",
             "needs_review": p["confidence"] < nco_coder.THRESHOLD, "alternatives": [a | {"occupation": titles.get(a["code"])} for a in p["alternatives"]]}
        if llm_res and i in low:
            hit = next((x for x in llm_res if x["index"] == low.index(i)), None)
            if hit and hit["code"] in titles:
                r.update({"code": hit["code"], "occupation": titles[hit["code"]], "confidence": round(hit["confidence"], 3), "method": "gemini", "reason": hit["reason"], "needs_review": hit["confidence"] < 0.6})
        out.append(r)
    return {"results": out, "threshold": nco_coder.THRESHOLD, "llm_used": bool(llm_res)}


# ---------------------------------------------------------------- data hub
@router.get("/sources", tags=["data"])
def sources():
    c = _db()
    try:
        return services.sources(c)
    finally:
        c.close()


@router.get("/postings", tags=["data"])
def postings(lgd: Optional[str] = None, code: Optional[str] = None, coder: Optional[str] = None, ghost: Optional[bool] = None, limit: int = Query(50, ge=1, le=500)):
    c = _db()
    try:
        sql = "SELECT p.id, p.portal, p.posted_on, d.district, p.employer, p.raw_title, p.salary, p.nco_code, t.title occupation, p.nco_conf, p.coder, p.cluster_id, p.ghost FROM postings p JOIN districts d USING(lgd) LEFT JOIN trades t ON t.code=p.nco_code WHERE 1=1"
        args = []
        for col, val in [("p.lgd", lgd), ("p.nco_code", code), ("p.coder", coder)]:
            if val:
                sql += f" AND {col}=?"
                args.append(val)
        if ghost is not None:
            sql += " AND p.ghost=?"
            args.append(int(ghost))
        return rows(c, sql + " ORDER BY p.posted_on DESC LIMIT ?", args + [limit])
    finally:
        c.close()


@router.get("/pipeline/runs", tags=["data"])
def runs(limit: int = 10):
    c = _db()
    try:
        out = rows(c, "SELECT * FROM pipeline_runs ORDER BY id DESC LIMIT ?", (limit,))
        for r in out:
            r["summary"] = json.loads(r.pop("summary_json") or "{}")
        return out
    finally:
        c.close()


_bg = {"running": False}


@router.post("/pipeline/run", tags=["data"])
def trigger_run(wait: bool = False):
    if wait:
        return pipeline.run("api")
    if _bg["running"]:
        return {"status": "already running"}

    def go():
        _bg["running"] = True
        try:
            pipeline.run("api")
        finally:
            _bg["running"] = False
    threading.Thread(target=go, daemon=True).start()
    return {"status": "started"}


@router.get("/quality", tags=["data"])
def quality(state: Optional[str] = None):
    """Data trust by district (coverage, agreement, recency) for the data-quality map."""
    c = _db()
    try:
        q = """SELECT d.lgd, d.state, d.district, AVG(g.trust) trust, (SELECT AVG(n_sources) FROM uldi u WHERE u.lgd=d.lgd AND u.period>=?) avg_sources
               FROM gaps g JOIN districts d USING(lgd) WHERE 1=1""" + (" AND d.state=?" if state else "") + " GROUP BY d.lgd ORDER BY trust"
        return rows(c, q, [PERIODS[-6]] + ([state] if state else []))
    finally:
        c.close()


@router.post("/import", tags=["data"])
async def import_signals(request: Request, file: UploadFile = File(...), source_name: str = Query("CSV import", min_length=1, max_length=120)):
    """Import aggregate demand signals. Columns: period, state, district, occupation, value. District and occupation names are
    harmonised to LGD and NCO codes (fuzzy match); unresolved rows reject the whole file."""
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(415, "Only CSV uploads are supported.")
    raw = await file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(413, "CSV exceeds 5 MiB limit.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    except UnicodeDecodeError:
        raise HTTPException(422, "CSV must be UTF-8 encoded.")
    required = {"period", "state", "district", "occupation", "value"}
    if not reader.fieldnames or not required.issubset({f.strip() for f in reader.fieldnames}):
        raise HTTPException(422, {"message": "Missing required columns", "required": sorted(required)})
    parsed, errors, mapping = [], [], {}
    for line, row in enumerate(reader, start=2):
        try:
            p = row["period"].strip()
            if len(p) != 7 or p[4] != "-" or not 1 <= int(p[5:]) <= 12:
                raise ValueError("period must be YYYY-MM")
            st = resolve.state(row["state"])
            if not st:
                raise ValueError(f"unknown state '{row['state']}'")
            d = resolve.district(row["district"], st)
            if not d:
                raise ValueError(f"district '{row['district']}' could not be matched in {st}")
            t = resolve.trade(row["occupation"])
            if not t:
                raise ValueError(f"occupation '{row['occupation']}' could not be coded to NCO")
            v = float(row["value"])
            if v < 0:
                raise ValueError("value must be nonnegative")
            mapping[(row["district"].strip(), row["occupation"].strip())] = (d["district"], d["score"], t["title"], t["code"], t["score"])
            parsed.append((p, d["lgd"], t["code"], v))
        except (ValueError, TypeError, KeyError) as e:
            errors.append({"line": line, "error": str(e)})
    if errors:
        raise HTTPException(422, {"message": "Import rejected; no rows were saved.", "errors": errors[:50], "invalid_row_count": len(errors)})
    if not parsed:
        raise HTTPException(422, "CSV contains no data rows.")
    if len({(p, l, t) for p, l, t, _ in parsed}) != len(parsed):
        raise HTTPException(422, "Duplicate period/district/occupation rows found; no rows were saved.")
    sector_of = {t["code"]: t["sector"] for t in catalog.trades()}
    c = _db()
    try:
        c.execute("BEGIN IMMEDIATE")
        sid = c.execute("INSERT INTO sources(name, source_type, access_method, is_synthetic, grain, side, reporting_note) VALUES(?, 'imported', 'user CSV upload', 0, 'district x NCO x month', 'demand', ?)",
                        (source_name, "Imported; provenance supplied by uploader. Held for review before it is fused into the demand index.")).lastrowid
        c.execute("UPDATE sources SET key=? WHERE id=?", (f"import-{sid}", sid))
        c.executemany("INSERT INTO signals VALUES(?,?,?,?,?,?)", [(sid, p, l, sector_of[t], t, v) for p, l, t, v in parsed])
        c.commit()
    except sqlite3.Error as e:
        c.rollback()
        raise HTTPException(422, f"Import transaction rolled back: {e}")
    finally:
        c.close()
    return {"source_id": sid, "rows_imported": len(parsed), "status": "committed",
            "harmonisation": [{"raw_district": k[0], "district": v[0], "district_match": v[1], "raw_occupation": k[1], "occupation": v[2], "nco_code": v[3], "occupation_match": v[4]} for k, v in list(mapping.items())[:100]]}


# ---------------------------------------------------------------- exports & API keys
@router.get("/exports/{dataset}.{fmt}", tags=["export"])
def export(dataset: Literal["gaps", "forecasts", "alerts", "rankings", "uldi"], fmt: Literal["csv", "xlsx", "json"], state: Optional[str] = None, sector: Optional[str] = None):
    c = _db()
    try:
        return exports.dataset(c, dataset, fmt, state, sector)
    finally:
        c.close()


class KeyIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.post("/api-keys", tags=["access"])
def create_key(body: KeyIn):
    key = "sk_lmis_" + secrets.token_urlsafe(24)
    c = _db()
    try:
        kid = c.execute("INSERT INTO api_keys(name, key_hash, prefix) VALUES(?,?,?)", (body.name, hashlib.sha256(key.encode()).hexdigest(), key[:12])).lastrowid
        c.commit()
        return {"id": kid, "name": body.name, "key": key, "note": "Store this key now; only its hash is kept. Send it as the X-API-Key header."}
    finally:
        c.close()


@router.get("/api-keys", tags=["access"])
def list_keys():
    c = _db()
    try:
        return rows(c, "SELECT id, name, prefix, created_at, revoked FROM api_keys ORDER BY id DESC")
    finally:
        c.close()


@router.delete("/api-keys/{kid}", tags=["access"])
def revoke_key(kid: int):
    c = _db()
    try:
        c.execute("UPDATE api_keys SET revoked=1 WHERE id=?", (kid,))
        c.commit()
        return {"id": kid, "revoked": True}
    finally:
        c.close()


@router.get("/methodology/metrics", tags=["reference"])
def methodology_metrics():
    c = _db()
    try:
        last = pipeline.last_run(c)
        weights = rows(c, "SELECT * FROM source_weights ORDER BY sector, source_key")
        bt = rows(c, "SELECT b.*, t.title FROM backtests b JOIN trades t ON t.code=b.trade_code ORDER BY t.title, b.wape")
        return {"run": last, "source_weights": weights, "backtests": bt, "forecast_periods": [FUTURE[0], FUTURE[-1]]}
    finally:
        c.close()
