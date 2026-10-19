"""AI occupation auto-coder: free-text job titles/descriptions -> NCO-2015 code with a confidence score.

Offline model: TF-IDF character n-grams (robust to typos, transliteration and casing) + multinomial logistic
regression, trained on the reference title dictionary and human-coded ("gold") postings. Postings below the
confidence threshold are queued for human review or, when an API key is configured, coded by Gemini.
"""
from __future__ import annotations
import re
from functools import lru_cache
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from .. import catalog

THRESHOLD = 0.55
_SKILLS_RE = re.compile(r"Skills required:(.*?)\.", re.I)


def model_text(title: str, description: str = "") -> str:
    m = _SKILLS_RE.search(description or "")
    return f"{title} | {m.group(1) if m else description[:160]}".lower()


def reference_corpus() -> tuple[list[str], list[str]]:
    texts, labels = [], []
    for t in catalog.trades():
        qp, market = catalog.SKILLS[t["code"]]
        for v in catalog.TITLE_VARIANTS[t["code"]] + [t["title"]]:
            texts.append(model_text(v, f"Skills required: {', '.join(market[:4])}."))
            labels.append(t["code"])
            texts.append(model_text(v))
            labels.append(t["code"])
    return texts, labels


def train(gold: list[tuple[str, str, str]]):
    texts, labels = reference_corpus()
    for title, desc, code in gold:
        texts.append(model_text(title, desc))
        labels.append(code)
    model = make_pipeline(
        TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True, min_df=1),
        LogisticRegression(max_iter=2000, C=8.0),
    )
    model.fit(texts, labels)
    return model


def predict(model, items: list[tuple[str, str]]) -> list[dict]:
    if not items:
        return []
    proba = model.predict_proba([model_text(t, d) for t, d in items])
    classes = model.classes_
    out = []
    for row in proba:
        order = np.argsort(row)[::-1][:3]
        out.append({"code": classes[order[0]], "confidence": float(row[order[0]]),
                    "alternatives": [{"code": classes[k], "confidence": round(float(row[k]), 3)} for k in order[1:]]})
    return out


def code_postings(c) -> dict:
    """Code every posting; persist code/confidence; return evaluation metrics against held-out labels."""
    rows = c.execute("SELECT id, raw_title, description, gold_code, eval_code FROM postings").fetchall()
    gold = [(r["raw_title"], r["description"], r["gold_code"]) for r in rows if r["gold_code"]]
    model = train(gold)
    _cache["model"] = model
    preds = predict(model, [(r["raw_title"], r["description"]) for r in rows])
    updates, correct, n_eval, hi, hi_correct = [], 0, 0, 0, 0
    for r, p in zip(rows, preds):
        coder = "human-gold" if r["gold_code"] else ("auto" if p["confidence"] >= THRESHOLD else "review-queue")
        code = r["gold_code"] or p["code"]
        updates.append((code, round(p["confidence"], 4), coder, r["id"]))
        if not r["gold_code"]:
            n_eval += 1
            ok = p["code"] == r["eval_code"]
            correct += ok
            if p["confidence"] >= THRESHOLD:
                hi += 1
                hi_correct += ok
    c.executemany("UPDATE postings SET nco_code=?, nco_conf=?, coder=? WHERE id=?", updates)
    return {"postings": len(rows), "gold_labelled": len(gold), "evaluated": n_eval,
            "accuracy": round(correct / max(1, n_eval), 4), "auto_coded_share": round(hi / max(1, n_eval), 4),
            "auto_coded_accuracy": round(hi_correct / max(1, hi), 4), "threshold": THRESHOLD}


_cache: dict = {}


def get_model(c=None):
    if "model" not in _cache:
        gold = []
        if c is not None:
            gold = [(r["raw_title"], r["description"], r["gold_code"]) for r in c.execute("SELECT raw_title, description, gold_code FROM postings WHERE gold_code IS NOT NULL")]
        _cache["model"] = train(gold)
    return _cache["model"]


@lru_cache(maxsize=1)
def trade_titles() -> dict[str, str]:
    return {t["code"]: t["title"] for t in catalog.trades()}
