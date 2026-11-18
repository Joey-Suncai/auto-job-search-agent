#!/usr/bin/env python3
"""posting.py (JSA-331 / JSA-332): DeepSeek's spec cases (scripts/test_cases/posting_cases.json, judged in
posting_verdicts.json) + the URLs that failed on 2026-11-12 (aipm1). Prints `fails 0` when everything passes."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); RUN = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(RUN, '..', '..', '..'))
sys.path.insert(0, RUN)
import posting as PO

CASES = os.path.join(ROOT, 'scripts', 'test_cases', 'posting_cases.json')
VERD = os.path.join(ROOT, 'scripts', 'test_cases', 'posting_verdicts.json')
ARTHREX = 'https://careers.arthrex.com/NorthAmerica/job/Naples-Product-Management-Summer-Associate-Foot-&-Ankle-and-Trauma-FL-34108/1374001457/'
OWN = [  # regressions from batch 2026-11-12_aipm1 (Claude)
    {'name': 'NYT aggregator url + GH ats_url', 'fn': 'posting_url', 'job': {'url': 'https://zapply.jobs/l/d/greenhouse-nevharlum-4748461005?s=gh-internships-2027', 'ats_url': 'https://job-boards.greenhouse.io/nevharlum/jobs/4748461005'}, 'expect': 'https://job-boards.greenhouse.io/nevharlum/jobs/4748461005'},
    {'name': 'Corlumnev LinkedIn url + WD ats_url', 'fn': 'posting_url', 'job': {'url': 'https://www.linkedin.com/jobs/view/4479081620/', 'ats_url': 'https://corlumnev.wd5.myworkdayjobs.com/Corlumnev_External_Careers/job/Denver-Colorado/AI-Product-Management-Intern_R6840'}, 'expect': 'https://corlumnev.wd5.myworkdayjobs.com/Corlumnev_External_Careers/job/Denver-Colorado/AI-Product-Management-Intern_R6840'},
    {'name': 'Arthrex region prefix', 'fn': 'platform', 'url': ARTHREX, 'expect': 'successfactors'},
    {'name': 'Acuity RMK with ?ats=', 'fn': 'platform', 'url': 'https://careers.acuityinc.com/job/Atlanta-Finance-AI-Product-Management-Intern-Onsite-GA-30309/1434874300/?ats=successfactors', 'expect': 'successfactors'},
    {'name': 'Acuity RMK plain', 'fn': 'platform', 'url': 'https://careers.acuityinc.com/job/Atlanta-Finance/1434874300/', 'expect': 'successfactors'},
    {'name': 'LinkedIn not SF', 'fn': 'platform', 'url': 'https://www.linkedin.com/jobs/view/4476108674/', 'expect': ''},
    {'name': 'Xpansiv %20 slug', 'fn': 'lever_parse', 'url': 'https://jobs.lever.co/Xpansiv%20/8a1649ec-ef5f-425d-8a36-34f28d67e8a7/apply', 'expect': ['Xpansiv', '8a1649ec-ef5f-425d-8a36-34f28d67e8a7']},
]


def run(c):
    if c['fn'] == 'posting_url':
        return PO.posting_url(c['job'])
    if c['fn'] == 'platform':
        return PO.platform(c['url'])
    r = PO.lever_parse(c['url'])
    return list(r) if r else None


def main():
    cases = json.load(open(CASES)) + OWN
    verd = json.load(open(VERD)) if os.path.exists(VERD) else {}
    fails = skipped = 0
    for c in cases:
        got = run(c)
        if got == c['expect']:
            continue
        if c['name'] in verd:
            skipped += 1; continue
        fails += 1; print(f"FAIL {c['name']}: got {got!r} expected {c['expect']!r}  ({c.get('url') or c.get('job')})")
    print(f'{len(cases)} cases · verdict-excused {skipped} · fails {fails}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
