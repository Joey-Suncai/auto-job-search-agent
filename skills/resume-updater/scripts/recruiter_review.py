#!/usr/bin/env python3
"""Simulated recruiter scores a direction master, as advice only (JSA-252, spec materials-resume-framework.md ⑤).

    python3 recruiter_review.py --direction ai_pm            # the newest master (approved or still a draft) → resume/<YYYY-MM>/recruiter_ai_pm.{json,md}
    python3 recruiter_review.py --all                        # every approved direction master
    python3 recruiter_review.py --direction ai_pm --stdout   # print, write nothing

DeepSeek plays a recruiter who screens for the direction's role (role library: label + top competencies) and scores each
**bullet** and the **whole page** 1–5, one reason each, plus up to 5 short advice lines. It judges; it never writes a resume
sentence, and nothing it says is applied to a master or counted as a fact — Joey reads the .md next to the master and decides
(Joey 2026-11-08: his approval of the direction master is the only gate; no threshold, per-JD tweaks are not scored).
Pure and tested (scripts/test_recruiter_review.py): `bullets_of(master)`, `build_prompt(...)`, `parse_review(raw, n)`,
`render_md(...)`, and `review(master, role, ask)` with an injectable `ask` (the tests pass a fake). Only the headline, summary,
skills and bullets go to DeepSeek — no name, contact details or immigration status.
direction_master.py runs it right after it builds a master, so the scores are next to the draft when Joey approves.
Exit 0 ok (also when a review has problems, they are written into the result) · 2 no master / role file (`--all`: the other
directions are still written, the exit is the worst one).
"""
import argparse, datetime, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'config'))

SYSTEM = ("You are an experienced technical recruiter screening resumes for ONE role. You score what is on the page; you never "
          "rewrite it, never add facts, and never suggest claiming experience the page does not show. Scale: 5 = a recruiter "
          "would shortlist on this alone; 4 = strong; 3 = fine but generic; 2 = weak or unclear for this role; 1 = hurts the "
          "application. Judge relevance to the role, a clear result, and plain wording. Reply with JSON only: "
          '{"overall": {"score": 1-5, "reason": "one sentence"}, "bullets": [{"n": <number from the list>, "score": 1-5, '
          '"reason": "one short sentence"}], "advice": ["at most 5 short lines on what a recruiter would want to see more clearly, '
          'as questions or topics for the candidate to confirm — not new sentences"]}')


def bullets_of(master):
    """Pure. [{'n': 1.., 'entry': entry_id, 'text': ...}] in page order (entries → bullets)."""
    out = []
    for e in (master or {}).get('entries') or []:
        for b in e.get('bullets') or []:
            t = b.get('text') if isinstance(b, dict) else b
            if isinstance(t, str) and t.strip():
                out.append({'n': len(out) + 1, 'entry': e.get('entry_id') or '', 'text': t.strip()})
    return out


def build_prompt(master, role):
    """Pure. The user message: the role (label + top competencies) and the numbered page."""
    comps = ', '.join(c.get('label') or c.get('id') or '' for c in sorted((role or {}).get('competencies') or [],
                                                                         key=lambda c: -(c.get('weight') or 0))[:8])
    L = [f"Role: {(role or {}).get('label') or (role or {}).get('direction') or 'unknown'}", f"What this role asks for most: {comps or 'n/a'}", '']
    if master.get('headline'):
        L.append(f"Headline: {master['headline']}")
    if master.get('summary'):
        L.append(f"Summary: {master['summary']}")
    for g in master.get('skills') or []:
        L.append(f"Skills — {g.get('label', '')}: {', '.join(g.get('items') or [])}")
    L.append('')
    L += [f"[{b['n']}] ({b['entry']}) {b['text']}" for b in bullets_of(master)]
    return '\n'.join(L)


def _score(x):
    try:
        v = int(round(float(x)))
    except (TypeError, ValueError):
        return None
    return v if 1 <= v <= 5 else None


def parse_review(raw, n):
    """Pure. DeepSeek's JSON (dict) → {'overall': {score, reason}, 'bullets': {n: {score, reason}}, 'advice': [...], 'problems': [...]}.
    A score outside 1–5 or missing is None with a problem line; a bullet number the page does not have is ignored; the first of a
    duplicated number wins. n = how many bullets the page has."""
    raw = raw if isinstance(raw, dict) else {}
    problems = []
    ov = raw.get('overall') if isinstance(raw.get('overall'), dict) else {}
    overall = {'score': _score(ov.get('score')), 'reason': str(ov.get('reason') or '').strip()}
    if overall['score'] is None:
        problems.append('overall score missing or outside 1-5')
    got = {}
    for b in raw.get('bullets') or []:
        if not isinstance(b, dict):
            continue
        try:
            k = int(b.get('n'))
        except (TypeError, ValueError):
            continue
        if 1 <= k <= n and k not in got:
            s = _score(b.get('score'))
            if s is None:
                problems.append(f'bullet {k}: score missing or outside 1-5')
            got[k] = {'score': s, 'reason': str(b.get('reason') or '').strip()}
    for k in range(1, n + 1):
        if k not in got:
            problems.append(f'bullet {k}: not scored')
            got[k] = {'score': None, 'reason': ''}
    advice = [str(a).strip() for a in (raw.get('advice') or []) if str(a).strip()][:5]
    return {'overall': overall, 'bullets': got, 'advice': advice, 'problems': problems}


def review(master, role, ask):
    """Impure only through `ask(system, user) -> dict`. Returns the full record (also when the model answers badly)."""
    bl = bullets_of(master)
    prompt = build_prompt(master, role)
    try:
        raw = ask(SYSTEM, prompt)
    except Exception as e:   # no key, no network, bad JSON: advice is optional, the master stays as approved
        return {'overall': {'score': None, 'reason': ''}, 'bullets': [dict(b, score=None, reason='') for b in bl], 'advice': [],
                'problems': [f'review not available: {type(e).__name__}: {str(e)[:120]}']}
    p = parse_review(raw, len(bl))
    return {'overall': p['overall'], 'bullets': [dict(b, **p['bullets'][b['n']]) for b in bl], 'advice': p['advice'], 'problems': p['problems']}


def render_md(direction, rec, when):
    """Pure. The note shown next to the master."""
    o = rec['overall']
    L = [f"# Simulated recruiter — {direction} master ({when})", '',
         "Advice only. Not a gate and not a fact: nothing here is applied to the master; you decide (your approval of the master is the gate).", '',
         f"**Overall: {o['score'] if o['score'] is not None else 'n/a'}/5** — {o['reason']}", '', '| # | Entry | Score | Bullet | Reason |', '|---|---|---|---|---|']
    for b in rec['bullets']:
        L.append(f"| {b['n']} | {b['entry']} | {b['score'] if b['score'] is not None else '–'} | {b['text'].replace('|', '/')} | {b['reason'].replace('|', '/')} |")
    if rec['advice']:
        L += ['', '## What the recruiter would want to see (topics to confirm, not sentences)'] + [f'- {a}' for a in rec['advice']]
    if rec['problems']:
        L += ['', '## Review problems'] + [f'- {p}' for p in rec['problems']]
    low = [b for b in rec['bullets'] if b['score'] is not None and b['score'] <= 2]
    if low:
        L += ['', '## Lowest-scored bullets (2 or less) — for you to judge, nothing changed'] + [f"- [{b['n']}] {b['text']}" for b in low]
    return '\n'.join(L) + '\n'


def _ask_deepseek(system, user):
    sys.path.insert(0, os.path.join(REPO, 'skills', 'auto-apply', 'runner'))
    import ladder
    usage = {'calls': 0, 'prompt': 0, 'out': 0}
    return ladder.ask_deepseek(user, usage, system=system)


def latest_master(direction, resume_dir):
    """(master dict, path) of the newest master_<direction>.json in resume/<YYYY-MM>/ — approved or not, because the point is that
    Joey sees the scores BEFORE he approves it. (None, None) when there is none."""
    import glob
    for p in sorted(glob.glob(os.path.join(resume_dir, '*', f'master_{direction}.json')), reverse=True):
        try:
            d = json.load(open(p, encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(d.get('master'), dict):
            return d['master'], p
    return None, None


def run_direction(direction, ask=None, stdout=False, resume_dir=None, role_path=None):
    import paths
    master, path = latest_master(direction, resume_dir or paths.resume())
    rp = role_path or paths.role_file(f'{direction}.json')   # the data home's copy first (JSA-377), else the repository's
    if not master or not os.path.exists(rp):
        print(f'recruiter_review: no master or role file for {direction}', file=sys.stderr)
        return 2
    role = json.load(open(rp, encoding='utf-8'))
    rec = review(master, role, ask or _ask_deepseek)
    when = datetime.date.today().isoformat()
    md = render_md(direction, rec, when)
    if stdout:
        print(md); return 0
    base = os.path.join(os.path.dirname(path), f'recruiter_{direction}')
    with open(base + '.json', 'w', encoding='utf-8') as fh:
        json.dump(dict(rec, direction=direction, master=os.path.basename(path), reviewed=when), fh, ensure_ascii=False, indent=1)
    with open(base + '.md', 'w', encoding='utf-8') as fh:
        fh.write(md)
    print(f"recruiter_review: {direction} overall {rec['overall']['score']} → {base}.md" + (f" ({len(rec['problems'])} problem(s))" if rec['problems'] else ''))
    return 0


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--direction'); ap.add_argument('--all', action='store_true'); ap.add_argument('--stdout', action='store_true')
    a = ap.parse_args()
    dirs = ['ai_pm', 'data_analyst', 'data_engineer', 'ai_agentic'] if a.all else [a.direction] if a.direction else []
    if not dirs:
        ap.error('--direction or --all')
    return max([run_direction(d, stdout=a.stdout) for d in dirs] or [0])


if __name__ == '__main__':
    sys.exit(main())
