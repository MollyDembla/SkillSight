"""Google Gemini integration: "Disha" planning copilot (function calling over the LMIS), DSDP narratives and NCO
coding of hard job titles. Every feature degrades to a deterministic offline mode when no API key is configured,
and every number Gemini reports comes from a tool call into the computed data - never from the model.
"""
from __future__ import annotations
import json, os, re
from . import catalog, resolve, services
from .db import connect

MODEL = os.getenv("SKILLSIGHT_GEMINI_MODEL", "gemini-3.8-flash")
LANG_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada", "mr": "Marathi", "or": "Odia"}
_client = None


def _api_key() -> str | None:
    return os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")


def available() -> bool:
    return bool(_api_key()) and os.getenv("SKILLSIGHT_DISABLE_LLM") != "1"


def client():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types
        # 45 s per request; our own fallback chain handles retries, so turn the SDK's retries off.
        _client = genai.Client(api_key=_api_key(), http_options=types.HttpOptions(timeout=45_000, retry_options=types.HttpRetryOptions(attempts=1)))
    return _client


# Tried in order when the primary model is overloaded (503) or rate-limited (429).
FALLBACK_MODELS = [m.strip() for m in os.getenv("SKILLSIGHT_GEMINI_FALLBACKS",
    "gemini-3.7-flash,gemini-3.5-flash,gemini-3-flash-preview,gemini-flash-latest,gemini-3.5-flash-lite,gemini-flash-lite-latest").split(",") if m.strip()]


_health = {"preferred": None, "cooldown": {}}   # last working model; model -> unix time it may be retried


def _chain(models: list[str] | None) -> list[str]:
    import time
    if models:
        return models
    base = list(dict.fromkeys(([_health["preferred"]] if _health["preferred"] else []) + [MODEL] + FALLBACK_MODELS))
    ready = [m for m in base if _health["cooldown"].get(m, 0) <= time.time()]
    return ready or base


def _cooldown_seconds(e, code: int) -> float:
    """Daily free-tier quota errors carry a retryDelay (often hours); honour it. Otherwise back off briefly."""
    if code == 404:
        return 24 * 3600
    try:
        for d in (e.details or {}).get("error", {}).get("details", []):
            if "retryDelay" in d:
                return max(60.0, float(str(d["retryDelay"]).rstrip("s")))
    except (AttributeError, ValueError, TypeError):
        pass
    return 300.0


def _generate(contents, models: list[str] | None = None, **config):
    """generate_content over a model chain. Overloaded / rate-limited / retired models are skipped for a few
    minutes and the last working model is tried first, so a busy model costs one fast failure, not one per call.
    Returns (response, model)."""
    import time
    from google.genai import errors, types
    last_error = None
    for model in _chain(models):
        cfg = dict(config)
        for _attempt in range(2):
            try:
                resp = client().models.generate_content(model=model, contents=contents, config=types.GenerateContentConfig(**cfg))
                _health["preferred"] = model
                return resp, model
            except errors.APIError as e:
                code = getattr(e, "code", 0) or 0
                last_error = e
                if code == 400 and "thinking" in str(e).lower() and "thinking_config" in cfg:
                    cfg.pop("thinking_config")  # some (lite) models reject thinking settings; retry without
                    continue
                if code in (404, 429) or code >= 500:
                    _health["cooldown"][model] = time.time() + _cooldown_seconds(e, code)
                    if _health["preferred"] == model:
                        _health["preferred"] = None
                    break
                raise
    raise last_error


# ------------------------------------------------------------------ copilot tools
TOOL_SPECS = [
    {"name": "query_gaps", "description": "District x trade demand-supply gaps for the next 12 months. Use for 'where is the shortage of X', 'which trades are oversupplied in Y'. Statuses: Acute shortage, Shortage, Balanced, Saturating, Oversupplied.",
     "input_schema": {"type": "object", "properties": {"state": {"type": "string"}, "district": {"type": "string"}, "sector": {"type": "string", "enum": list(catalog.SECTORS)},
                                                       "trade": {"type": "string", "description": "Trade/occupation name or NCO code"}, "status": {"type": "string", "description": "Comma-separated statuses"},
                                                       "sort": {"type": "string", "enum": ["severity", "gap", "surplus", "demand"]}, "limit": {"type": "integer"}}}},
    {"name": "rollup", "description": "Aggregate demand, supply and gap by state, district, trade or sector, optionally filtered.",
     "input_schema": {"type": "object", "properties": {"by": {"type": "string", "enum": ["state", "district", "trade", "sector", "state_trade"]}, "state": {"type": "string"},
                                                       "sector": {"type": "string", "enum": list(catalog.SECTORS)}, "trade": {"type": "string"}}, "required": ["by"]}},
    {"name": "early_warnings", "description": "Active early-warning flags (acute_shortage, saturation, emerging_shortage, emerging_saturation) with probability and lead quarter.",
     "input_schema": {"type": "object", "properties": {"state": {"type": "string"}, "district": {"type": "string"}, "kind": {"type": "string"}, "limit": {"type": "integer"}}}},
    {"name": "forecast", "description": "Monthly demand history and P10/P50/P90 forecast for one trade, nationally (pilot states), for a state, or for a district.",
     "input_schema": {"type": "object", "properties": {"trade": {"type": "string"}, "state": {"type": "string"}, "district": {"type": "string"}}, "required": ["trade"]}},
    {"name": "reskilling_pathways", "description": "Bridge courses that move surplus trainees into adjacent shortage trades, ranked by absorbable candidates.",
     "input_schema": {"type": "object", "properties": {"state": {"type": "string"}, "district": {"type": "string"}}}},
    {"name": "curriculum_drift", "description": "NSQF QP freshness vs. skills demanded in job postings; missing and stale skills.",
     "input_schema": {"type": "object", "properties": {"trade": {"type": "string"}}}},
    {"name": "simulate_investment", "description": "What-if: effect of a new project (jobs) in a district on trade demand, gaps and extra seats needed.",
     "input_schema": {"type": "object", "properties": {"district": {"type": "string"}, "sector": {"type": "string", "enum": list(catalog.SECTORS)}, "jobs_ops": {"type": "integer"},
                                                       "jobs_build": {"type": "integer"}, "ops_start": {"type": "string", "description": "YYYY-MM"}}, "required": ["district", "sector", "jobs_ops", "ops_start"]}},
]

def _gemini_tools():
    from google.genai import types
    return [types.Tool(function_declarations=[types.FunctionDeclaration(name=t["name"], description=t["description"], parameters_json_schema=t["input_schema"]) for t in TOOL_SPECS])]


SYSTEM = f"""You are Disha, the planning copilot inside SkillSight, a Labour Market Intelligence System for India's Ministry of Skill Development
and Entrepreneurship (MSDE), NCVET and Sector Skill Council planners. Pilot scope: Karnataka, Maharashtra, Odisha, Uttar Pradesh; 24 trades in
{len(catalog.SECTORS)} sectors ({', '.join(catalog.SECTORS.values())}).

Answer planners' questions about skill demand, training supply, gaps, early warnings, re-skilling and curriculum. Always call tools to get numbers;
never invent figures. Gaps compare forecast demand (next 12 months) with expected certified supply (current-cycle seats x completion x certification,
adjusted for migration, plus absorbable e-Shram job-seekers). Negative gap ratio = shortage.

Write for a busy government planner: lead with the answer, then 3-6 short bullet points with the key numbers (Indian digit grouping), then one
concrete recommended action. Mention uncertainty (probability / trust) when it matters. The data is synthetic demonstration data; say so if asked
about provenance. Reply in the same language as the question (English, Hindi, Kannada, Marathi or Odia)."""


def _norm(args: dict) -> dict:
    out = dict(args)
    if out.get("state"):
        out["state"] = resolve.state(out["state"]) or out["state"]
    if out.get("district"):
        d = resolve.district(out["district"], out.get("state"))
        out["lgd"] = d["lgd"] if d else None
        if d:
            out["district_name"] = d["district"]
    if out.get("trade"):
        t = resolve.trade(out["trade"])
        out["trade_code"] = t["code"] if t else None
    return out


def _slim_gap(r):
    return {k: r[k] for k in ("state", "district", "trade", "sector", "demand_p50", "supply", "gap", "gap_ratio", "status", "severity", "p_shortage", "p_surplus", "lead_quarter", "trust", "seats")}


def run_tool(name: str, args: dict, state_obj: dict | None = None):
    a = _norm(args)
    c = connect()
    try:
        if name == "query_gaps":
            res = services.gap_rows(c, state=a.get("state"), lgd=a.get("lgd"), sector=a.get("sector"), trade=a.get("trade_code"), status=a.get("status"),
                                    sort=a.get("sort", "severity"), limit=min(int(a.get("limit", 15)), 40))
            return [_slim_gap(r) for r in res]
        if name == "rollup":
            res = services.rollup(c, a.get("by", "state"), state=a.get("state"), sector=a.get("sector"), trade=a.get("trade_code"))
            res = sorted(res, key=lambda r: r["gap_ratio"])
            keep = ("state", "district", "trade_code", "title", "sector", "sector_name", "demand", "supply", "gap", "gap_ratio", "status", "severity", "growth", "seats")
            return [{k: r[k] for k in keep if k in r} for r in res[:40]]
        if name == "early_warnings":
            res = services.alerts(c, state=a.get("state"), lgd=a.get("lgd"), kind=a.get("kind"), limit=min(int(a.get("limit", 12)), 30))
            return [{k: r[k] for k in ("district", "state", "trade", "kind", "probability", "lead_quarter", "severity", "message")} for r in res]
        if name == "forecast":
            if not a.get("trade_code"):
                return {"error": "Unknown trade"}
            node = a.get("lgd") or (f"ST:{a['state']}" if a.get("state") else "IN")
            s = services.series(c, a["trade_code"], node)
            return {"node": node, "last_12_months_actual": round(sum(h["actual"] for h in s["history"][-12:])),
                    "next_12_months_p50": round(sum(f["p50"] for f in s["forecast"][:12])), "next_12_months_p10": round(sum(f["p10"] for f in s["forecast"][:12])),
                    "next_12_months_p90": round(sum(f["p90"] for f in s["forecast"][:12])), "investment_uplift_next_12m": round(sum(f["invest_effect"] for f in s["forecast"][:12])),
                    "monthly_forecast": s["forecast"][:12], "backtest": s["backtest"]}
        if name == "reskilling_pathways":
            from .models import insights
            res = insights.pathways(state_obj, lgd=a.get("lgd"), state_name=a.get("state"), limit=12)
            return {"total_absorbable": res["total_absorbable"], "top": [{k: p[k] for k in ("district", "from_trade", "to_trade", "skill_overlap", "bridge_hours", "absorbable", "bridge_skills")} for p in res["pathways"][:10]],
                    "by_pair": res["by_pair"][:8]}
        if name == "curriculum_drift":
            from .models import insights
            res = insights.curriculum(c, a.get("trade_code"))
            return [{k: r[k] for k in ("trade", "qp_code", "freshness_score", "revision_priority", "recommendation")} | {"missing_skills": [s["skill"] for s in r["missing_skills"]]} for r in res[:10]]
        if name == "simulate_investment":
            from .models import insights
            if not a.get("lgd"):
                return {"error": "Unknown district"}
            res = insights.simulate_investment(state_obj, a["lgd"], a["sector"], int(a["jobs_ops"]), int(a.get("jobs_build") or a["jobs_ops"]), a["ops_start"])
            return {k: res[k] for k in ("district", "state", "trades", "total_extra_seats", "total_extra_cost", "new_shortages")}
        return {"error": f"unknown tool {name}"}
    except (ValueError, KeyError) as e:
        return {"error": str(e)}
    finally:
        c.close()


def chat(question: str, history: list[dict], state_obj: dict) -> dict:
    if not available():
        return offline_chat(question, state_obj)
    from google.genai import errors, types
    contents = [types.Content(role="user" if m["role"] == "user" else "model", parts=[types.Part.from_text(text=m["content"])])
                for m in history[-8:] if m.get("role") in ("user", "assistant") and m.get("content")]
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))
    used, last = [], None
    tools = _gemini_tools()
    pinned = None
    try:
        for _ in range(6):
            resp, used_model = _generate(contents, models=pinned, system_instruction=SYSTEM, tools=tools, temperature=0.2,
                                         thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW),
                             automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True))
            pinned = [used_model]  # thought signatures are model-specific: stay on this model
            if not resp.candidates or resp.candidates[0].content is None:
                return {"answer": "I can't help with that request. Please ask about skill demand, supply, gaps or training plans.", "mode": "gemini", "tools": used}
            calls = resp.function_calls or []
            if not calls:
                return {"answer": (resp.text or "").strip(), "mode": "gemini", "model": used_model, "tools": used, "data": last}
            # Keep the model turn as returned (it carries thought signatures required by newer Gemini models).
            contents.append(resp.candidates[0].content)
            parts = []
            for fc in calls:
                args = dict(fc.args or {})
                out = run_tool(fc.name, args, state_obj)
                used.append({"name": fc.name, "input": args})
                last = {"tool": fc.name, "rows": out if isinstance(out, list) else None}
                payload = json.loads(json.dumps(out, default=str))
                parts.append(types.Part.from_function_response(name=fc.name, response={"result": payload}))
            contents.append(types.Content(role="user", parts=parts))
        return {"answer": "I needed too many steps for that question - please narrow it (e.g. one state or trade).", "mode": "gemini", "tools": used}
    except errors.APIError as e:
        return offline_chat(question, state_obj, note=f"Gemini API error {getattr(e, 'code', '')}; answered with the offline engine.")
    except Exception:
        return offline_chat(question, state_obj, note="Gemini was unreachable; answered with the offline engine.")


# ------------------------------------------------------------------ offline intent engine
HINDI = {"कमी": "shortage", "अभाव": "shortage", "अधिक": "surplus", "अधिशेष": "surplus", "पूर्वानुमान": "forecast", "चेतावनी": "alert", "पाठ्यक्रम": "curriculum", "कौशल": "skill"}


def _fmt(n):
    n = float(n)
    if abs(n) >= 1e7:
        return f"{n / 1e7:.2f} crore"
    if abs(n) >= 1e5:
        return f"{n / 1e5:.2f} lakh"
    return f"{n:,.0f}"


def offline_chat(question: str, state_obj: dict, note: str | None = None) -> dict:
    q = question.lower()
    for k, v in HINDI.items():
        if k in question:
            q += f" {v}"
    hi = bool(re.search(r"[ऀ-ॿ]", question))
    ent = resolve.find_in_text(question)
    st, dist, tr = ent["state"] or (ent["district"] or {}).get("state"), ent["district"], ent["trade"]
    scope = dist["district"] if dist else (st or "the pilot states")
    lines, data, tool = [], None, None
    if any(w in q for w in ("curriculum", "syllabus", "qp", "nos", "skills missing", "revise")):
        tool = "curriculum_drift"
        res = run_tool(tool, {"trade": tr["title"]} if tr else {}, state_obj)
        data = res
        lines.append(f"Curriculum freshness (share of employer-demanded skills covered by the NSQF QP), lowest first:")
        lines += [f"- {r['trade']} ({r['qp_code']}): {r['freshness_score']}% - {r['recommendation']}" for r in res[:5]]
    elif any(w in q for w in ("reskill", "re-skill", "pathway", "bridge", "upskill", "convert")):
        tool = "reskilling_pathways"
        res = run_tool(tool, {"state": st, "district": dist["district"] if dist else None}, state_obj)
        data = res["top"]
        lines.append(f"About {_fmt(res['total_absorbable'])} surplus candidates in {scope} could move to shortage trades via bridge courses:")
        lines += [f"- {p['from_trade']} -> {p['to_trade']}: {p['skill_overlap']:.0%} skill overlap, ~{p['bridge_hours']} h bridge, {_fmt(p['absorbable'])} candidates" for p in res["by_pair"][:5]]
    elif any(w in q for w in ("alert", "warning", "early", "flag", "emerging")):
        tool = "early_warnings"
        res = run_tool(tool, {"state": st, "district": dist["district"] if dist else None, "limit": 8}, state_obj)
        data = res
        lines.append(f"Top early-warning flags for {scope}:")
        lines += [f"- {r['message']}" for r in res[:6]]
    elif tr and any(w in q for w in ("forecast", "next year", "demand", "trend", "predict")):
        tool = "forecast"
        res = run_tool(tool, {"trade": tr["title"], "state": st, "district": dist["district"] if dist else None}, state_obj)
        data = res["monthly_forecast"]
        lines.append(f"{tr['title']} in {scope}: forecast demand for the next 12 months is {_fmt(res['next_12_months_p50'])} "
                     f"(80% interval {_fmt(res['next_12_months_p10'])}-{_fmt(res['next_12_months_p90'])}) vs {_fmt(res['last_12_months_actual'])} in the last 12 months.")
        if res["investment_uplift_next_12m"] > 1:
            lines.append(f"- {_fmt(res['investment_uplift_next_12m'])} of this comes from announced investment projects.")
    else:
        want_surplus = any(w in q for w in ("surplus", "oversupp", "saturat", "excess", "too many"))
        tool = "query_gaps"
        status = "Saturating,Oversupplied" if want_surplus else "Acute shortage,Shortage"
        res = run_tool(tool, {"state": st, "district": dist["district"] if dist else None, "trade": tr["title"] if tr else None, "status": status,
                              "sort": "surplus" if want_surplus else "gap", "limit": 8}, state_obj)
        data = res
        kind = "oversupply" if want_surplus else "shortage"
        if not res:
            lines.append(f"No {kind} found for {scope}{' in ' + tr['title'] if tr else ''} in the next 12 months.")
        else:
            lines.append(f"Largest {kind} gaps for {scope} over the next 12 months{' (' + tr['title'] + ')' if tr else ''}:")
            lines += [f"- {r['trade']}, {r['district']}: demand {_fmt(r['demand_p50'])} vs supply {_fmt(r['supply'])} ({r['gap_ratio']:+.0%}, {r['status']}, "
                      f"{'P(shortage)' if not want_surplus else 'P(surplus)'} {r['p_shortage' if not want_surplus else 'p_surplus']:.0%})" for r in res[:6]]
            lines.append("Recommended action: " + ("cut or repurpose seats in these trades and offer bridge courses (see Pivot Pathways)." if want_surplus
                                                  else "raise next-cycle targets here - run the Target Planner for a budget-feasible allocation."))
    if hi:
        lines.insert(0, "(ऑफ़लाइन मोड: उत्तर अंग्रेज़ी में; पूर्ण हिंदी उत्तर के लिए Gemini API कुंजी कॉन्फ़िगर करें)")
    if note:
        lines.append(f"_{note}_")
    return {"answer": "\n".join(lines), "mode": "offline", "tools": [{"name": tool, "input": {"state": st, "district": dist, "trade": tr}}], "data": {"tool": tool, "rows": data if isinstance(data, list) else None}}


# ------------------------------------------------------------------ DSDP narrative
def dsdp_narrative(facts: dict, lang: str = "en") -> dict:
    if available():
        try:
            prompt = (f"Write the executive summary of a District Skill Development Plan for {facts['district']} ({facts['state']}) in {LANG_NAMES.get(lang, 'English')}. "
                      "Use only the facts in the JSON below; do not add numbers. 3 short paragraphs (situation, priorities, actions for the next training cycle), "
                      "about 220 words, plain text without markdown headings.\n\n" + json.dumps(facts, default=str))
            resp, _ = _generate(prompt, temperature=0.3)
            if resp.text:
                return {"text": resp.text.strip(), "mode": "gemini"}
        except Exception:
            pass
    return {"text": template_narrative(facts, lang), "mode": "template"}


def template_narrative(f: dict, lang: str) -> str:
    sh = ", ".join(x["trade"] for x in f["top_shortages"][:3]) or "-"
    su = ", ".join(x["trade"] for x in f["top_surpluses"][:3]) or "-"
    if lang == "hi":
        return (f"{f['district']} ({f['state']}) में अगले 12 महीनों में कुशल कार्यबल की अनुमानित मांग {_fmt(f['demand'])} है, जबकि अपेक्षित प्रमाणित आपूर्ति {_fmt(f['supply'])} है "
                f"(अंतर {f['gap_ratio']:+.0%})। सबसे गंभीर कमी वाले ट्रेड: {sh}। अधिशेष वाले ट्रेड: {su}।\n\n"
                f"अगले प्रशिक्षण चक्र के लिए कमी वाले ट्रेडों में सीटें बढ़ाने, अधिशेष ट्रेडों से सीटों को पुनः आवंटित करने तथा ब्रिज कोर्स के माध्यम से "
                f"लगभग {_fmt(f['pathway_absorbable'])} उम्मीदवारों को कमी वाले ट्रेडों में स्थानांतरित करने की अनुशंसा की जाती है।\n\n"
                f"सक्रिय प्रारंभिक चेतावनियाँ: {f['alert_count']}। डेटा विश्वसनीयता स्कोर: {f['trust']:.0%}। (सिंथेटिक प्रदर्शन डेटा)")
    return (f"{f['district']} ({f['state']}) is forecast to need {_fmt(f['demand'])} skilled workers across the 24 pilot trades over the next 12 months, against an expected "
            f"certified supply of {_fmt(f['supply'])} (overall gap {f['gap_ratio']:+.0%}). The most severe shortages are in {sh}; the largest surpluses are in {su}.\n\n"
            f"Priorities for the next training cycle: raise targets in shortage trades, repurpose seats from saturated courses, and run bridge courses that could move about "
            f"{_fmt(f['pathway_absorbable'])} surplus candidates into shortage trades. {f['alert_count']} early-warning flags are active for the district.\n\n"
            f"Data trust score is {f['trust']:.0%}; figures are synthetic demonstration data and need validation by the District Skill Committee before adoption.")


# ------------------------------------------------------------------ NCO coding of hard titles
def llm_code_titles(items: list[dict]) -> list[dict] | None:
    if not available() or not items:
        return None
    codes = "\n".join(f"{t['code']}: {t['title']} (QP {t['qp_code']})" for t in catalog.trades())
    schema = {"type": "object", "properties": {"results": {"type": "array", "items": {"type": "object", "properties": {"index": {"type": "integer"}, "code": {"type": "string"},
              "confidence": {"type": "number"}, "reason": {"type": "string"}}, "required": ["index", "code", "confidence", "reason"], "additionalProperties": False}}},
              "required": ["results"], "additionalProperties": False}
    prompt = ("Assign each job posting to the best matching NCO-2015 code from this list, or 'UNCLASSIFIED' if none fits.\n" + codes + "\n\nPostings:\n" +
              "\n".join(f"{i}. {x['title']} | {x.get('description', '')[:300]}" for i, x in enumerate(items)))
    try:
        resp, _ = _generate(prompt, temperature=0, response_mime_type="application/json", response_json_schema=schema)
        return json.loads(resp.text)["results"]
    except Exception:
        return None
