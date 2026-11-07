#!/usr/bin/env python3
"""Job priority v2 = value level + chance of an interview (JSA-096, ADR-0006; spec scripts/test_cases/score_v2_spec.md).

Value is three levels because Joey's preferences inside the eligible Summer 2027 pool are close to flat (two blind
checks, docs/specs/pipeline-scoring-v2.md): top (AI PM, or his 👍), standard, exclude (off-field, hardware, pure ML
engineering, or his 👎). Inside a level the order comes from the chance factors — priors for now, to be recalibrated
from tracker outcomes. store.save("jobs") runs score_rows(), so every new row reaches the dashboard scored.

    python3 scripts/scoring/score_v2.py [--report]     # dry run on data/store/jobs.jsonl: tiers before / after
"""
import datetime as dt, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from features import role_category

OFF_CYCLE = re.compile(r"\b(fall|spring|winter|autumn|co-?op|part[- ]time|year[- ]round|semester)\b", re.I)
HARDWARE = re.compile(r"\b(hardware|firmware|embedded|silicon|chip|vlsi|asic|fpga|rf|mechanical|electrical)\b", re.I)
PURE_ML = re.compile(r"\b(machine learning|ml|computer vision|deep learning)\b", re.I)
CLIENT = re.compile(r"\b(forward deployed|solutions|customer|field|consultant|consulting|implementation)\b", re.I)
SUMMER27 = re.compile(r"(summer\s*2027|2027\s*summer)", re.I)
BLOCKED_ELIG = ("不可投", "已关闭", "重复")
S_VALUE = {"top": 70, "standard": 40, "exclude": 0, "off_target": 0}
W = {"s_referral": 0.40, "s_timing": 0.25, "s_sponsor": 0.20, "s_fresh": 0.15}   # priors (spec 3); refit from outcomes


def value_level(job):
    t = job.get("title") or ""
    if job.get("level") != "Internship" or OFF_CYCLE.search(t):
        return "off_target"
    pref = job.get("joey_pref")
    if pref == "down":
        return "exclude"
    if pref == "up":
        return "top"
    role = role_category(t)
    if role == "other" or HARDWARE.search(t) or (role == "ai_engineering" and PURE_ML.search(t) and not CLIENT.search(t)):
        return "exclude"
    return "top" if role == "ai_pm" else "standard"


def _candidate():
    """The candidate's work-authorization facts (config/profile.json → eligibility; JSA-081). Default = needs
    sponsorship, not a citizen / PR (the safe side for an F-1 student)."""
    import json as _json
    try:
        e = _json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                                         'config', 'profile.json'), encoding='utf-8')).get('eligibility') or {}
    except (OSError, ValueError):
        e = {}
    return {'needs_sponsorship': e.get('needs_sponsorship', True) is not False, 'citizen_or_pr': e.get('citizen_or_pr') is True}


CAND = _candidate()


def sponsor_factor(label, cand=None):
    """Pure (tested). The sponsorship factor for a job's `sponsorship` label, for this candidate. A candidate who does
    not need sponsorship gets 1.0 whatever the label says (it does not matter to them). Otherwise: a label starting with
    "Blocked" → 0.0; "Posting offers sponsorship" 1.0, "Strong H-1B sponsor" 0.8, "Some H-1B history" 0.6, anything else 0.4."""
    c = cand or CAND
    if not c.get('needs_sponsorship', True):
        return 1.0
    sp = str(label or '')
    return 0.0 if sp.startswith('Blocked') else {'Posting offers sponsorship': 1.0, 'Strong H-1B sponsor': 0.8,
                                                  'Some H-1B history': 0.6}.get(sp, 0.4)


def label_blocks(label, cand=None):
    """Pure (tested). Does a job's `sponsorship` label rule this candidate out? "Blocked: citizenship required" → only a
    candidate who is not a citizen / permanent resident; "Blocked: no sponsorship" → only a candidate who needs
    sponsorship; any other label starting with "Blocked" → yes (an unknown block stays a block); else no."""
    c = cand or CAND
    sp = str(label or '')
    if not sp.startswith('Blocked'):
        return False
    if re.search(r'citizenship required', sp, re.I):
        return not c.get('citizen_or_pr', False)
    if re.search(r'no sponsorship', sp, re.I):
        return bool(c.get('needs_sponsorship', True))
    return True


def _date(s):
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def factors(job):
    r = job.get("referral") or ""
    ref = 1.0 if r.startswith("1st-degree") else 0.8 if "LinkedIn" in r else 0.6 if r.startswith("Warm") else \
        0.4 if r == "School alumni" else 0.0
    src = job.get("sources")
    text = f"{job.get('title') or ''} {'; '.join(src) if isinstance(src, list) else (src or '')}"
    tim = 1.0 if SUMMER27.search(text) else 0.8 if re.search(r"summer|2027", text, re.I) else 0.5
    spo = sponsor_factor(job.get("sponsorship"))         # profile-aware (open-source users may be citizens, 11-03)
    p, a = _date(job.get("posted")), _date(job.get("added"))
    if p and a:
        age = max(0, (a - p).days)
        fr = 1.0 if age <= 7 else 0.8 if age <= 14 else 0.6 if age <= 30 else 0.3 if age <= 90 else 0.2
    else:
        fr = 0.2
    return {"s_referral": ref, "s_timing": tim, "s_sponsor": spo, "s_fresh": fr}


def score_row(job):
    out = dict(job)
    if "score_v1" not in out and out.get("score_version") != "v2":
        out["score_v1"] = job.get("score")
    lvl = value_level(job); f = factors(job)
    chance = round(sum(W[k] * v for k, v in f.items()), 3)
    score = round(S_VALUE[lvl] + 30 * chance, 1)
    tier = {"top": "A", "exclude": "D", "off_target": "D"}.get(lvl) or ("B" if chance >= 0.5 else "C")
    out.update(f, v_level=lvl, s_value=S_VALUE[lvl], s_chance=chance, score=score, tier_orig=tier,
               score_version="v2")
    blocked = job.get("elig") in BLOCKED_ELIG or label_blocks(job.get("sponsorship"))
    out["tier"] = "Blocked" if blocked else tier
    return out


def score_rows(rows):
    return [score_row(r) for r in rows]


if __name__ == "__main__":
    import collections
    here = os.path.dirname(os.path.abspath(__file__))
    store = os.path.join(os.path.dirname(os.path.dirname(here)), "data", "store", "jobs.jsonl")
    rows = [json.loads(l) for l in open(store, encoding="utf-8")]
    new = score_rows(rows)
    live = [(o, n) for o, n in zip(rows, new) if o.get("elig") in ("可投", "待核实")]
    print("可投 / 待核实:", len(live))
    print("tier before:", dict(sorted(collections.Counter(o.get("tier") for o, _ in live).items())))
    print("tier after: ", dict(sorted(collections.Counter(n["tier"] for _, n in live).items())))
    print("value level:", dict(collections.Counter(n["v_level"] for _, n in live)))
