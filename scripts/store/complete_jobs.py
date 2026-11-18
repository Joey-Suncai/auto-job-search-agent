#!/usr/bin/env python3
"""Fill the dashboard fields a job row is missing (JSA-095).

Writers that add rows straight to the store (wd_search, the LinkedIn / Built In import, board_search, cert_supply)
skip build_jobs / export_dash, so their rows lack sources-as-text, sponsorship / H-1B / green card, referral, remote,
track and the score parts — the dashboard then shows blanks, and a list in `sources` stopped the whole page.
`complete(rows, companies)` fills only absent / null fields (never overwrites) from the companies table and safe
defaults; store.save("jobs") runs it, so every writer's rows arrive complete. Spec: scripts/test_cases/complete_jobs_spec.md.

    python3 scripts/store/complete_jobs.py      # report how many store rows are incomplete (no write)
"""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills", "job-hunt-pipeline", "scripts"))
import h1b_match  # noqa: E402  (group_key: alias company rows merged into one, JSA-098)

# same rules as skills/job-hunt-pipeline/scripts/build_jobs.py norm() / TRACKS (display names as export_dash.TRACK)
SUFFIX = r"\b(inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|limited|plc|lp|llp|holdings?|group|the|usa|us|america|na|n\.a|services|technologies|technology|labs?|global|international)\b"
TRACKS = [
    ("AI Product Manager", r"(?=.*(?:\b(?:ai|artificial intelligence|machine learning|ml|llm|genai|gen ai|generative|agents?|agentic|conversational)\b|\ba\.i\.(?!\w)))(?=.*\b(?:product manag\w*|product owner|apm|associate product|product lead|product intern|product strategy)\b)"),   # Joey 2026-11-03: AI PM is its own track, checked before AI Agentic Eng
    ("AI Agentic Eng", r"\b(ai|a\.i\.|artificial intelligence|machine learning|ml|llm|genai|gen ai|generative|agent|agentic|nlp|deep learning|applied scien|research engineer|ai/ml|computer vision|mlops)\b"),
    ("Data Engineer", r"\b(data engineer|data engineering|analytics engineer|data platform|data infrastructure|etl|data pipeline|big data|data warehouse|database|data ops|dataops|data architect)\b"),
    ("Data Analyst", r"\b(data analysts?|data analytics|business analysts?|business analytics|bi analyst|bi developer|power bi|business intelligence|analytics analyst|analytics intern|reporting analyst|insights analyst|marketing analyst|operations analyst|business operations|data visuali[sz]ation|data & analytics|data and analytics|analyst, data|analyst, business intelligence|analyst, reporting|analyst, client reporting|financial data analyst|master data analyst|data integrity|growth analyst|strategy analyst)\b"),
    ("Product Manager", r"\b(product manager|product management|apm|associate product|product analyst|product owner|product operations|product strategy|technical program|program manager|product designer|product intern|product)\b"),
    ("Data Sci / Analytics", r"\b(data scien|data analy|analytics|business intelligence|bi analyst|business analyst|quantitative|quant|insights|statistic|decision scien|operations research|economist|research analyst|data intern|data)\b"),
]
SOURCE_LABEL = {"workday_search": "Workday search", "linkedin": "LinkedIn", "builtin": "Built In",
                "ashby_search": "Ashby boards", "lever_search": "Lever boards", "cert_supply": "Cert supply",
                "indeed_search": "Indeed", "wellfound_search": "Wellfound", "dice_search": "Dice", "usajobs_search": "USAJOBS"}
COMPANY_FIELDS = {"sponsorship": "Unknown — verify", "h1b_fy25": 0, "h1b_total": 0, "h1b_since": "", "gc_sponsor": "",
                  "gc_perm": "", "gc_months": "", "referral": "Cold", "contacts": "", "warm_path": ""}
SCORE_PARTS = ("s_role", "s_timing", "s_sponsor", "s_greencard", "s_referral", "s_fresh")


def norm(c):
    c = (c or "").lower().replace("&", " and ")
    c = re.sub(r"\.com\b", "", c)
    c = re.sub(r"[^a-z0-9 ]+", " ", c)
    c = re.sub(SUFFIX, " ", c)
    return re.sub(r"\s+", " ", c).strip()


def track_of(title):
    t = (title or "").lower()
    for name, rx in TRACKS:
        if re.search(rx, t):
            return name
    return "Other"


def _missing(r, k):
    return r.get(k) is None


def _sources(r):
    s = r.get("sources")
    if isinstance(s, list):
        return "; ".join(SOURCE_LABEL.get(str(x), str(x)) for x in s)
    if s is not None:
        return s
    src = r.get("source")
    if src:
        return SOURCE_LABEL.get(src, src)
    return "Cert supply" if r.get("cert_supply") else "Unknown"


def complete_row(r, by_company):
    out = dict(r)
    out["sources"] = _sources(r)
    if _missing(out, "n_sources"):
        out["n_sources"] = len([x for x in out["sources"].split("; ") if x])
    comp = by_company.get(norm(r.get("company"))) or by_company.get(("g", h1b_match.group_key(r.get("company"))), {})
    for k, default in COMPANY_FIELDS.items():
        if _missing(out, k):
            v = comp.get(k)
            out[k] = default if v is None else v
    if _missing(out, "referral_detail"):
        out["referral_detail"] = out["referral"]
    for k in ("li_connections", "li_alumni"):
        if _missing(out, k):
            out[k] = 0
    if _missing(out, "remote"):
        out["remote"] = "Yes" if re.search(r"\bremote\b", out.get("location") or "", re.I) else "No"
    for k in ("salary", "posted"):
        if _missing(out, k):
            out[k] = ""
    if _missing(out, "track"):
        out["track"] = track_of(out.get("title"))
    for k in SCORE_PARTS:
        if _missing(out, k):
            out[k] = 0
    return out


def complete(rows, companies):
    by_company = {}
    for c in companies or []:
        by_company.setdefault(norm(c.get("company")), c)
        by_company.setdefault(("g", h1b_match.group_key(c.get("company"))), c)   # "Verizon Communications" -> the Verizon row
    return [complete_row(r, by_company) for r in rows]


NEW_SOURCE = {"Workday search": ("Company job boards (API)", "As needed"),
              "Cert supply": ("Certification test supply", "As needed"),
              "Indeed": ("Job site", "Weekly full refresh (job Chrome)")}


def _labels(j):
    s = j.get("sources")
    if isinstance(s, list):
        return [str(x) for x in s]
    return [x for x in (s or "").split("; ") if x]


def update_sources(sources, jobs, today, github_ok, boards_ok):
    """The Sources table after a refresh: counts from the jobs, last_run for what ran today, rows for new labels.
    Spec: scripts/test_cases/update_sources_spec.md."""
    count = {}
    for j in jobs:
        for lb in set(_labels(j)):
            count[lb] = count.get(lb, 0) + 1
    out, have = [], set()
    for r in sources:
        r = dict(r); have.add(r["source"])
        r["in_dashboard"] = count.get(r["source"], 0)
        if github_ok and r.get("type") == "Curated GitHub list":
            r["last_run"], r["cadence"] = today, "Daily 08:15"
        if boards_ok and r["source"] in ("Lever boards", "Ashby boards"):
            r["last_run"], r["cadence"] = today, "Daily 08:15 (board search)"
        out.append(r)
    for lb, n in count.items():
        if lb in have or lb == "Unknown":
            continue
        typ, cad = NEW_SOURCE.get(lb, ("Other", "As needed"))
        out.append({"source": lb, "type": typ, "cadence": cad, "last_run": today, "in_dashboard": n})
    return sorted(out, key=lambda r: r["source"])


def load_companies(store_dir):
    p = os.path.join(store_dir, "companies.jsonl")
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(here)), "config"))
    import paths                                   # the data home (JSA-375: not the code checkout)
    store = paths.data("store")
    rows = [json.loads(l) for l in open(os.path.join(store, "jobs.jsonl"), encoding="utf-8")]
    done = complete(rows, load_companies(store))
    print("jobs %d · incomplete %d" % (len(rows), sum(a != b for a, b in zip(rows, done))))
