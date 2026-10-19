"""Printable District Skill Development Plan (DSDP) - HTML the browser can save as PDF."""
from __future__ import annotations
import html
from datetime import date
from .. import llm
from ..db import CURRENT_FY, GAP_WINDOW, NEXT_FY

L = {
    "en": {"title": "District Skill Development Plan", "draft": "Auto-drafted by SkillSight - for District Skill Committee review", "summary": "Executive summary",
           "gaps": "Demand-supply outlook by trade (next 12 months)", "trade": "Trade", "demand": "Forecast demand", "supply": "Expected supply", "gap": "Gap",
           "status": "Status", "seats": "Seats FY", "alerts": "Early warnings", "paths": "Re-skilling pathways", "capacity": "Training capacity",
           "curr": "Curriculum revision signals", "invest": "Investment pipeline", "print": "Print / Save as PDF", "none": "None", "data": "Synthetic demonstration data - not official statistics."},
    "hi": {"title": "जिला कौशल विकास योजना", "draft": "स्किलसाइट द्वारा स्वतः तैयार - जिला कौशल समिति की समीक्षा हेतु", "summary": "कार्यकारी सारांश",
           "gaps": "ट्रेड-वार मांग-आपूर्ति परिदृश्य (अगले 12 महीने)", "trade": "ट्रेड", "demand": "अनुमानित मांग", "supply": "अपेक्षित आपूर्ति", "gap": "अंतर",
           "status": "स्थिति", "seats": "सीटें वित्त वर्ष", "alerts": "प्रारंभिक चेतावनियाँ", "paths": "पुनः कौशल मार्ग", "capacity": "प्रशिक्षण क्षमता",
           "curr": "पाठ्यक्रम संशोधन संकेत", "invest": "निवेश परियोजनाएँ", "print": "प्रिंट / PDF सहेजें", "none": "कोई नहीं", "data": "सिंथेटिक प्रदर्शन डेटा - आधिकारिक आँकड़े नहीं।"},
}
STATUS_COLOR = {"Acute shortage": "#b42318", "Shortage": "#dc6803", "Balanced": "#667085", "Saturating": "#0e7090", "Oversupplied": "#1d4ed8"}


def _n(x):
    return f"{x:,.0f}"


def dsdp_html(prof: dict, paths: dict, site: dict | None, curriculum: list[dict], lang: str) -> str:
    t = L.get(lang, L["en"])
    d = prof["district"]
    gaps = sorted(prof["gaps"], key=lambda g: g["gap_ratio"])
    shortages = [g for g in gaps if g["status"] in ("Acute shortage", "Shortage")]
    surpluses = [g for g in gaps[::-1] if g["status"] in ("Saturating", "Oversupplied")]
    alerts = [g for g in gaps if g["severity"] >= 50 and g["status"] != "Balanced"]
    trades_here = {g["trade_code"] for g in shortages[:6]}
    cur = [c for c in curriculum if c["trade_code"] in trades_here and c["missing_skills"]]
    facts = {"district": d["district"], "state": d["state"], "demand": prof["totals"]["demand"], "supply": prof["totals"]["supply"], "gap_ratio": prof["totals"]["gap_ratio"],
             "trust": prof["totals"]["trust"], "aspirational": bool(d["aspirational"]),
             "top_shortages": [{"trade": g["trade"], "gap_ratio": g["gap_ratio"], "demand": round(g["demand_p50"]), "supply": round(g["supply"])} for g in shortages[:5]],
             "top_surpluses": [{"trade": g["trade"], "gap_ratio": g["gap_ratio"]} for g in surpluses[:4]],
             "pathway_absorbable": paths["total_absorbable"], "alert_count": len(alerts),
             "investments": [i["name"] for i in prof["investments"]], "capacity_action": site["action"] if site else None,
             "curriculum": [{"qp": c["qp_code"], "add": [s["skill"] for s in c["missing_skills"][:3]]} for c in cur[:3]]}
    nar = llm.dsdp_narrative(facts, lang)
    e = html.escape
    rows_html = "".join(
        f"<tr><td>{e(g['trade'])}<div class=sub>{e(g['qp_code'])}</div></td><td class=r>{_n(g['demand_p50'])}<div class=sub>{_n(g['demand_p10'])}-{_n(g['demand_p90'])}</div></td>"
        f"<td class=r>{_n(g['supply'])}</td><td class=r>{g['gap_ratio']:+.0%}</td><td><span class=pill style='background:{STATUS_COLOR[g['status']]}'>{e(g['status'])}</span></td>"
        f"<td class=r>{_n(g['seats'])}</td></tr>" for g in gaps if g["demand_p50"] >= 5)
    alert_html = "".join(f"<li><b>{e(g['trade'])}</b>: {e(g['status'])} ({g['gap_ratio']:+.0%}), P(shortage) {g['p_shortage']:.0%}, P(surplus) {g['p_surplus']:.0%}</li>" for g in alerts[:8]) or f"<li>{t['none']}</li>"
    path_html = "".join(f"<li><b>{e(p['from_trade'])} &rarr; {e(p['to_trade'])}</b>: {p['skill_overlap']:.0%} overlap, ~{p['bridge_hours']} h bridge, {_n(p['absorbable'])} candidates "
                        f"(adds: {e(', '.join(p['bridge_skills'][:4]))})</li>" for p in paths["pathways"][:6]) or f"<li>{t['none']}</li>"
    cur_html = "".join(f"<li><b>{e(c['trade'])}</b> ({e(c['qp_code'])}) - freshness {c['freshness_score']}%: {e(c['recommendation'])}</li>" for c in cur[:5]) or f"<li>{t['none']}</li>"
    inv_html = "".join(f"<li>{e(i['name'])} - {_n(i['jobs_ops'])} operations jobs, operations from {e(i['ops_start'])}</li>" for i in prof["investments"]) or f"<li>{t['none']}</li>"
    site_html = (f"<p><b>{e(site['action'])}</b>. {site['centres']} centres; seats needed for shortages {_n(site['seats_needed'])}; spare capacity {_n(site['spare_capacity'])}; "
                 f"repurposable {_n(site['repurposable_seats'])}.</p>") if site else ""
    paras = "".join(f"<p>{e(p)}</p>" for p in nar["text"].split("\n") if p.strip())
    return f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(t['title'])} - {e(d['district'])}</title>
<style>
body{{font-family:"Noto Sans","Noto Sans Devanagari",Inter,system-ui,sans-serif;color:#101828;margin:0;background:#f2f4f7}}
main{{max-width:960px;margin:24px auto;background:#fff;padding:40px 48px;border-radius:12px;box-shadow:0 1px 3px #1018281a}}
header{{border-bottom:3px solid #0f766e;padding-bottom:16px;margin-bottom:20px}} h1{{margin:0;font-size:26px}} h2{{font-size:17px;margin:28px 0 10px;color:#0f766e}}
.meta{{color:#475467;font-size:13px;margin-top:6px}} .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}}
.kpi{{border:1px solid #eaecf0;border-radius:10px;padding:12px}} .kpi b{{display:block;font-size:20px;margin-top:4px}} .kpi span{{font-size:11px;color:#667085;text-transform:uppercase;letter-spacing:.05em}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}} th,td{{padding:7px 8px;border-bottom:1px solid #eaecf0;text-align:left;vertical-align:top}} th{{background:#f9fafb;font-size:11px;color:#475467}}
.r{{text-align:right}} .sub{{font-size:10.5px;color:#98a2b3}} .pill{{color:#fff;border-radius:999px;padding:2px 8px;font-size:11px;white-space:nowrap}}
li{{margin:5px 0;font-size:13.5px;line-height:1.5}} p{{line-height:1.6;font-size:14px}} .note{{font-size:11px;color:#98a2b3;margin-top:28px}}
.btn{{position:fixed;right:20px;top:20px;background:#0f766e;color:#fff;border:0;border-radius:8px;padding:10px 14px;font-weight:600;cursor:pointer}}
@media print{{.btn{{display:none}} body{{background:#fff}} main{{box-shadow:none;margin:0;padding:0}}}}
@media (max-width:700px){{main{{padding:20px 16px}} .kpis{{grid-template-columns:1fr 1fr}}}}
</style></head><body><button class=btn onclick="window.print()">{t['print']}</button><main>
<header><h1>{e(t['title'])}: {e(d['district'])}, {e(d['state'])}</h1>
<div class=meta>LGD {e(d['lgd'])}{' - Aspirational District' if d['aspirational'] else ''} - {e(t['draft'])} - {date.today().isoformat()} - window {GAP_WINDOW[0]} to {GAP_WINDOW[-1]} - next cycle FY {NEXT_FY}</div></header>
<div class=kpis><div class=kpi><span>{t['demand']}</span><b>{_n(prof['totals']['demand'])}</b></div><div class=kpi><span>{t['supply']}</span><b>{_n(prof['totals']['supply'])}</b></div>
<div class=kpi><span>{t['gap']}</span><b>{prof['totals']['gap_ratio']:+.0%}</b></div><div class=kpi><span>Trust</span><b>{prof['totals']['trust']:.0%}</b></div></div>
<h2>{t['summary']}</h2>{paras}<div class=sub>Narrative: {'Gemini (' + llm.MODEL + '), grounded in computed figures' if nar['mode'] == 'gemini' else 'template engine'}</div>
<h2>{t['gaps']}</h2><table><thead><tr><th>{t['trade']}</th><th class=r>{t['demand']} (P50, P10-P90)</th><th class=r>{t['supply']}</th><th class=r>{t['gap']}</th><th>{t['status']}</th><th class=r>{t['seats']} {CURRENT_FY}</th></tr></thead><tbody>{rows_html}</tbody></table>
<h2>{t['alerts']}</h2><ul>{alert_html}</ul>
<h2>{t['paths']}</h2><ul>{path_html}</ul>
<h2>{t['capacity']}</h2>{site_html}
<h2>{t['curr']}</h2><ul>{cur_html}</ul>
<h2>{t['invest']}</h2><ul>{inv_html}</ul>
<p class=note>{t['data']} Methodology: unified labour demand index (portal, NCS, EPFO), ensemble forecast with conformal intervals, migration-aware supply. Generated by SkillSight LMIS.</p>
</main></body></html>"""
