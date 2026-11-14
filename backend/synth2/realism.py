"""Realism measures: how well a classifier tells real paper pieces from synthetic papers (five views of the text,
AUC near 0.5 means it cannot), and how far each synthetic set's style is from the real pieces."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

LABEL = r"[A-Z][a-zA-Z'-]+ (?:et al\.|and [A-Z][a-zA-Z'-]+),? \(?(?:19|20)\d\d[a-z]?\)?"
SURFACE_NAMES = ["words", "headings", "table lines", "bullets", "paragraphs", "commas", "semicolons", "colons",
                 "parens", "quotes", "dashes", "percent", "digits", "capitals", "bold", "backticks", "sent len",
                 "sent len sd", "word len", "para len", "type-token", "we/our"]
FUNC = ["we", "our", "however", "thus", "such", "while", "so", "was", "were", "same"]

MASKS = [
    (LABEL, " CITE "),
    (r"\(([A-Z][a-zA-Z'-]+(?: et al\.)?,? (?:19|20)\d\d[a-z]?(?:; )?)+\)", " CITE "),
    (r"\[\d+(?:[,–-]\s*\d+)*\]", " CITE "),
    (r"(?i)\bretrieval[- ]augmented( generation| language model| llm| lm| model)?s?\b", " SYS_T "),
    (r"(?i)\bretrieve[- ]then[- ]read\b|\brag( pipeline| system| model)?s?\b|\bralms?\b", " SYS_T "),
    (r"(?i)\bclosed[- ]book( llm| lm| model| baseline| setting)?s?\b", " SYS_C "),
    (r"(?i)\bno[- ]retrieval( baseline| setting)?\b|\bwithout retrieval\b|\bvanilla (llm|lm|model)s?\b", " SYS_C "),
    (r"(?i)\b(large )?language models?\b|\bl?lms?\b|\bgenerators?\b|\breaders?\b|\bretrievers?\b", " MODEL "),
    (r"(?i)\bfactual accuracy\b|\bexact match\b|\bem\b|\baccuracy\b|\bperformance\b", " METRIC "),
    (r"\b[A-Z][a-z]*[A-Z][A-Za-z0-9-]*\b", " NAME "),        # CamelCase: TriviaShift, PopQA, OpenRecall, MetaQA
    (r"\b[A-Z]{2,}[0-9]*\b", " ACRO "),                       # NQ, QA, MMLU, GPT
    (r"\d+(?:[.,]\d+)*", " NUM "),
    (r"[|#*`_>-]+", " "),
]


# ---- loading ---------------------------------------------------------------------------------------------

def synthetic(root: Path):
    """(texts, groups) of the synthetic papers: root/papers/S*.md, or a grid's */s*/base/papers/S*.md. Lines that
    only carry the author label are dropped; pieces of one paper share a group."""
    files = root.glob("papers/S*.md") if (root / "papers").is_dir() else root.glob("*/s*/base/papers/S*.md")
    texts, groups = [], []
    for p in sorted(files):
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines()
                 if not (len(ln) < 120 and re.search(LABEL, ln) and len(re.sub(LABEL, "", ln).strip(" *_|-:")) < 25)]
        texts.append("\n".join(lines))
        groups.append("syn-" + p.stem.split("_p")[0])
    return texts, groups


def real(folder: Path):
    files = sorted(folder.glob("*_p*.md"))
    return [f.read_text(encoding="utf-8") for f in files], ["real-" + f.stem.split("_p")[0] for f in files]


def normalize(text: str) -> str:
    """Remove markup the real-paper converter cannot produce (bold, code marks, list bullets), on both sides."""
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"(?m)^\s*(?:[-*+•]|\d+[.)])\s+", "", text)


def mask(text: str) -> str:
    for pat, rep in MASKS:
        text = re.sub(pat, rep, text)
    return text


# ---- classifier views --------------------------------------------------------------------------------------

def surface(text: str) -> list[float]:
    """22 counts per 1,000 words (layout, punctuation, digits, sentence and word length, ...); no vocabulary."""
    lines = text.splitlines()
    words = text.split()
    w = max(len(words), 1) / 1000
    sents = [s for s in re.split(r"[.!?]+\s", text) if s.strip()]
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    return [
        len(words) / 1000,
        sum(ln.startswith("#") for ln in lines) / w,
        sum(ln.lstrip().startswith("|") for ln in lines) / w,
        sum(bool(re.match(r"\s*([-*]|\d+\.)\s", ln)) for ln in lines) / w,
        len(paras) / w,
        text.count(",") / w, text.count(";") / w, text.count(":") / w, text.count("(") / w,
        text.count('"') / w, text.count("—") / w + text.count("--") / w, text.count("%") / w,
        len(re.findall(r"\d", text)) / w,
        len(re.findall(r"\b[A-Z]", text)) / w,
        len(re.findall(r"\*\*", text)) / w,
        len(re.findall(r"`", text)) / w,
        np.mean([len(s.split()) for s in sents]) if sents else 0,
        np.std([len(s.split()) for s in sents]) if sents else 0,
        np.mean([len(x) for x in words]) if words else 0,
        np.mean([len(p.split()) for p in paras]) if paras else 0,
        len(set(x.lower() for x in words)) / max(len(words), 1),
        len(re.findall(r"\b(we|our|us)\b", text, re.I)) / w,
    ]


class Surface:
    def fit(self, X, y=None):
        return self

    def transform(self, X):
        return np.array([surface(t) for t in X])


def lr():
    return LogisticRegression(C=1.0, max_iter=5000)


def _words_model():
    return make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True), lr())


def _surface_model():
    return make_pipeline(Surface(), StandardScaler(), lr())


def oof(make, X, y, groups):
    s = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):
        m = make().fit([X[i] for i in tr], y[tr])
        s[te] = m.predict_proba([X[i] for i in te])[:, 1]
    return round(roc_auc_score(y, s), 3)


def cues(make, X, y, k=10):
    m = make().fit(X, y)
    vocab, coef = np.array(m[0].get_feature_names_out()), m[-1].coef_[0]
    return {"real": vocab[np.argsort(-coef)[:k]].tolist(), "synthetic": vocab[np.argsort(coef)[:k]].tolist()}


def c2st(real_dir: Path, synthetic_root: Path, log=None) -> dict:
    """Five views, each 5-fold GroupKFold + logistic regression, out-of-fold AUC (pieces of one paper stay in one
    fold): full words, masked words (names, citations, numbers masked), function words, surface counts, and
    masked words + surface together. Also the top cues and the strongest surface features (+ = real)."""
    real_t, real_g = real(real_dir)
    syn_t, syn_g = synthetic(synthetic_root)
    X, groups = [normalize(t) for t in real_t + syn_t], real_g + syn_g
    Xm = [mask(t) for t in X]
    y = np.array([1] * len(real_t) + [0] * len(syn_t))
    func = sorted(ENGLISH_STOP_WORDS)
    views = {
        "1 full words": (_words_model, X),
        "2 masked words": (_words_model, Xm),
        "3 function words": (lambda: make_pipeline(TfidfVectorizer(vocabulary=func, sublinear_tf=True), lr()), X),
        "4 surface only": (_surface_model, X),
    }
    out = {"real": len(real_t), "synthetic": len(syn_t), "auc": {}}
    for name, (make, data) in views.items():
        out["auc"][name] = oof(make, data, y, groups)
        if log:
            log(f"{name} {out['auc'][name]}")
    s = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups):  # masked words + surface: average the two models
        a, b = _words_model(), _surface_model()
        a.fit([Xm[i] for i in tr], y[tr])
        b.fit([X[i] for i in tr], y[tr])
        s[te] = (a.predict_proba([Xm[i] for i in te])[:, 1] + b.predict_proba([X[i] for i in te])[:, 1]) / 2
    out["auc"]["5 masked + surface"] = round(roc_auc_score(y, s), 3)
    out["cues masked words"] = cues(views["2 masked words"][0], Xm, y)
    out["cues function words"] = cues(views["3 function words"][0], X, y)
    sm = _surface_model().fit(X, y)
    order = np.argsort(-np.abs(sm[-1].coef_[0]))[:8]
    out["surface strongest (+ = real)"] = {SURFACE_NAMES[i]: round(float(sm[-1].coef_[0][i]), 2) for i in order}
    return out


# ---- style gap ---------------------------------------------------------------------------------------------

def gap_surface(text: str) -> list[float]:
    """The surface counts of c2st plus ten function-word rates, on normalised text."""
    text = normalize(text)
    lines, words = text.splitlines(), text.split()
    w = max(len(words), 1) / 1000
    sents = [s for s in re.split(r"[.!?]+\s", text) if s.strip()]
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    low = re.findall(r"[a-z]+", text.lower())
    base = [len(words) / 1000, sum(ln.startswith("#") for ln in lines) / w,
            sum(ln.lstrip().startswith("|") for ln in lines) / w,
            sum(bool(re.match(r"\s*([-*]|\d+\.)\s", ln)) for ln in lines) / w, len(paras) / w,
            text.count(",") / w, text.count(";") / w, text.count(":") / w, text.count("(") / w, text.count('"') / w,
            text.count("—") / w + text.count("--") / w, text.count("%") / w, len(re.findall(r"\d", text)) / w,
            len(re.findall(r"\b[A-Z]", text)) / w, len(re.findall(r"\*\*", text)) / w, len(re.findall(r"`", text)) / w,
            np.mean([len(s.split()) for s in sents]), np.std([len(s.split()) for s in sents]),
            np.mean([len(x) for x in words]), np.mean([len(p.split()) for p in paras]),
            len(set(x.lower() for x in words)) / max(len(words), 1),
            len(re.findall(r"\b(we|our|us)\b", text, re.I)) / w]
    return base + [low.count(f) / w for f in FUNC]


def load_features(root: Path):
    if (root / "papers").is_dir():
        files = sorted(root.glob("papers/S*.md"))
    elif any(root.glob("*_p*.md")):
        files = sorted(root.glob("*_p*.md"))
    else:
        files = sorted(root.glob("*/s*/base/papers/S*.md"))
    return np.array([gap_surface(f.read_text(encoding="utf-8")) for f in files])


def style_gap(real_dir: Path, sets: dict[str, Path]) -> dict:
    """Gap of a feature = (synthetic mean - real mean) / real standard deviation; 0 = same as real. Also the mean
    absolute gap, a single number that can move even when the classifier AUC stays at 1.0."""
    real_f = load_features(real_dir)
    mu, sd = real_f.mean(0), np.maximum(real_f.std(0), 1e-3)
    names = SURFACE_NAMES + [f"'{f}'" for f in FUNC]
    out = {}
    for name, root in sets.items():
        gap = (load_features(root).mean(0) - mu) / sd
        out[name] = {"mean |gap|": round(float(np.abs(gap).mean()), 2),
                     "biggest": {names[i]: round(float(gap[i]), 1) for i in np.argsort(-np.abs(gap))[:8]}}
    return out
