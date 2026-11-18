#!/usr/bin/env python3
"""Tests of runner/block_check.py (JSA-294): the DeepSeek cases (scripts/test_cases/block_check_cases.json, written from
block_check_spec.md — rule 13; Claude's rulings on disagreements in block_check_verdicts.json) + the résumé-parse
values Workday showed before the fill (Hartalcor / Jain / Wynvernev 3.85 in UIUC's Overall Result; Hartalcor / Adobe "Job
Searching Agent" — the fill overwrote them there; here they stand for a fill that did not take) + the
whole-read hand-off (blocks_first) + the gate wiring (runner_common.block_problems, run_wd.block_problems)."""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner')); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'config'))
import block_check as BC  # noqa: E402

TODAY = '2026-11-11'
PROF = {'education': [
    {'school': 'University of Chicago', 'short': 'UChicago', 'match_re': 'chicago', 'level': 'master', 'degree': 'M.S. Applied Data Science',
     'major': 'Applied Data Science', 'start': '2026-09', 'end': '2027-12', 'current': True, 'city': 'Chicago', 'state': 'IL'},
    {'school': 'University of Illinois Urbana-Champaign', 'short': 'UIUC', 'match_re': 'illinois', 'level': 'bachelor', 'degree': 'B.A. Economics',
     'major': 'Economics', 'start': '2024-08', 'end': '2026-05', 'city': 'Urbana', 'state': 'IL'}],
    'answers': {'gpa': {'text': '3.60', 'note': 'UIUC cumulative 3.60/4.0 (institution 3.81, major 3.85)'},
                'gpa_threshold': {'by': {'cumulative': 3.60, 'major': 3.85}}}}
WD = {'education': [
    {'match': 'chicago', 'School': 'University of Chicago', 'Degree': 'master', 'Field': 'Data Science', 'GPA': '',
     'Field_alts': ['Applied Data Science', 'Data Analytics and Data Science'],
     'Field_prefs': ['Data Science', 'Applied Data Science', 'Data Analytics', 'Computer Science', 'Information Systems', 'Applied Statistics', 'Statistics'],
     'Field_search': ['Data', 'Statist', 'Analytic', 'Computer', 'Information']},
    {'match': 'illinois|urbana|uiuc', 'School': 'University of Illinois Urbana-Champaign', 'Degree': 'bachelor', 'Field': 'Economics', 'GPA': '3.60',
     'Field_alts': ['Economics (B.A.)', 'Other'], 'School_alts': ['University of Illinois at Urbana-Champaign'], 'Field_prefs': ['Economics'], 'Field_search': ['Econom']}],
    'work': [
    {'match': 'hyde park', 'Job Title': 'Business Analyst Intern', 'Company': 'Hyde Park Investment Services, Inc.', 'Location': 'Champaign, Illinois',
     'From': '08/2025', 'To': '10/2025', 'current': False,
     'Description': 'Designed a 0–5 scoring rubric for ChatGPT-assisted MD&A review, requiring cited evidence and senior analyst validation; contributed to a workflow that cut end-to-end review time by 70%. Cleaned Finviz and Yahoo Finance data and built standardized Excel forecast models for 14 companies so senior analysts could compare annual revenue, margins, and FCF consistently.'},
    {'match': 'frost', 'Job Title': 'Consulting Assistant Intern', 'Company': 'Frost & Sullivan', 'Location': 'Shanghai, China',
     'From': '06/2024', 'To': '08/2024', 'current': False,
     'Description': "Created tables and charts for 60+ pages of client-ready decks using Think-cell and Excel, supporting 40% faster turnaround with zero errors. Co-built, with a consultant, a levelized-cost model for Fortune 500 clients to assess green methanol's cost competitiveness and investment feasibility vs. grey methanol across carbon-price levels."}]}
ENTS = BC.entries(PROF, WD)

fails, n = [], 0


def check(name, got, want):
    global n
    n += 1
    if got != want:
        fails.append(f'{name}: got {got!r}, want {want!r}')


def verdicts(rows):
    j = BC.judge(rows, ENTS, page_only=True, today=TODAY)
    return [j[i]['verdict'] if i in j else None for i in range(len(rows))]


# --- the résumé-parse values run_wd recorded before its fill (corpus rows, as recorded)
JM = [  # 2026-11-01 Hartalcor Customer Experience (Workday, legacy record: no sections)
    ('Job Title', 'Job Searching Agent', 'wd_profile:work'), ('Company', '', 'wd_profile:work'), ('Location', '', 'wd_profile:work'),
    ('I currently work here', '', 'wd_profile:work'), ('From', '', 'wd_profile:work'), ('To', '', 'wd_profile:work'),
    ('Role Description', 'Personal project, built with Claude Code) Ongoing. Designed and operate an agent that collects internships', 'wd_profile:work'),
    ('Job Title', 'Consulting Assistant Intern', 'wd_profile:work'), ('Company', 'FROST & SULLIVAN', 'wd_profile:work'),
    ('From', '6/2024', 'wd_profile:work'), ('To', '8/2024', 'wd_profile:work'),
    ('Role Description', 'Produced tables and charts for 60+ pages of client-ready decks using Think-cell and Excel', 'wd_profile:work'),
    ('School or University', 'THE UNIVERSITY OF CHICAGO', 'wd_profile:education'), ('Degree', '', 'wd_profile:education'),
    ('Overall Result (GPA)', '', 'wd_profile:education'), ('From', '', 'wd_profile:education'), ('To (Actual or Expected)', '2027', 'wd_profile:education'),
    ('School or University', 'UNIVERSITY OF ILLINOIS URBANA', 'wd_profile:education'), ('Degree', '', 'wd_profile:education'),
    ('Field of Study', 'Economics | Economics', 'prefs-match'), ('Overall Result (GPA)', '3.85', 'wd_profile:education'),
    ('From', '', 'wd_profile:education'), ('To (Actual or Expected)', '2026', 'wd_profile:education')]
PLANNED = {0: 'Business Analyst Intern', 1: 'Hyde Park Investment Services, Inc.'}   # what the runner wrote (the corpus 'planned')
rows = [{'question': l, 'page': p, 'source': s, 'planned': PLANNED.get(i)} for i, (l, p, s) in enumerate(JM)]
v = verdicts(rows)
check('JM title', v[0], 'bad'); check('JM description', v[6], 'bad'); check('JM GPA 3.85 in UIUC', v[20], 'bad')
check('JM others ok', [x for i, x in enumerate(v) if i not in (0, 6, 20)], ['ok'] * (len(v) - 3))
probs = BC.problems(rows, ENTS, today=TODAY)
check('JM problems', len(probs), 3)
check('JM GPA line names the entry', 'University of Illinois Urbana-Champaign' in probs[-1] and '3.60' in probs[-1], True)

# Workday live plan rows (section + entry dict) — the same GPA with sections
wd_live = [{'label': 'School or University', 'page': 'University of Illinois Urbana-Champaign', 'section': 'Education 2', 'kind': 'education', 'entry': WD['education'][1]},
           {'label': 'Overall Result (GPA)', 'page': '3.85', 'section': 'Education 2', 'kind': 'education', 'entry': WD['education'][1]},
           {'label': 'School or University', 'page': 'University of Chicago', 'section': 'Education 1', 'kind': 'education', 'entry': WD['education'][0]},
           {'label': 'Overall Result (GPA)', 'page': '3.60', 'section': 'Education 1', 'kind': 'education', 'entry': WD['education'][0]}]
check('WD live', verdicts(wd_live), ['ok', 'bad', 'ok', 'bad'])
# answers.json override: Joey's per-application GPA wins
check('override', [BC.judge(wd_live[:2], ENTS, True, TODAY, {'edu:University of Illinois Urbana-Champaign:GPA': '3.85'})[1]['verdict']], ['ok'])

# level-only option lists (CorBrakel 10-30: "Undergraduate Degree" / "Post Graduate Degree")
check('levels', [BC.level_of(x) for x in ('Undergraduate Degree', 'Post Graduate Degree', 'Graduate Degree', 'Bachelors (±16 years of education)', 'MS', 'Doctorate')],
      ['bachelor', 'master', 'master', 'bachelor', 'master', 'phd'])
# a lone rule question is not a block; a Greenhouse rule block is
gh = [{'label': 'What is your GPA?', 'page': '3.60', 'source': 'rules:gpa'}, {'label': 'Email', 'page': 'x@y.z', 'source': 'rules:email'},
      {'label': 'School', 'page': 'University of Chicago', 'source': 'rules:school'}, {'label': 'Degree', 'page': "Master's Degree", 'source': 'rules:degree'},
      {'label': 'Discipline', 'page': 'Data Science', 'source': 'rules:discipline'}, {'label': 'Start date month', 'page': 'September', 'source': 'rules:start_month'},
      {'label': 'Start date year', 'page': '2026', 'source': 'rules:start_year'}, {'label': 'End date month', 'page': 'December', 'source': 'rules:end_month'},
      {'label': 'End date year', 'page': '2026', 'source': 'rules:end_year'}]
check('GH block', verdicts(gh), [None, None, 'ok', 'ok', 'ok', 'ok', 'ok', 'ok', 'bad'])
# SuccessFactors prefixes
sf = [{'label': 'Education (UIUC): Degree', 'page': "Master's Degree", 'source': 'education_combo'},
      {'label': 'Education (UIUC): Major/Area of Focus', 'page': 'Economics', 'source': 'education_combo'},
      {'label': 'Education (UChicago): Major/Area of Focus', 'page': 'Economics', 'source': 'education_combo'},
      {'label': 'Previous Employment (Frost & Sullivan): Title', 'page': 'Business Analyst Intern', 'source': 'background'},
      {'label': 'Previous Employment (Frost & Sullivan): Division', 'page': 'N/A', 'source': 'background'}]
check('SF prefixes', verdicts(sf), ['bad', 'ok', 'bad', 'bad', 'unknown'])
# TikTok formily keys
tt = [{'label': 'education[0].school', 'page': 'University of Chicago'}, {'label': 'education[0].degree', 'page': "Bachelor's degree"},
      {'label': 'education[0].period', 'page': '2026-09 2027-12'}, {'label': 'internship[0].company', 'page': 'Frost & Sullivan'},
      {'label': 'internship[0].title', 'page': 'Consulting Assistant Intern'}, {'label': 'internship[0].period', 'page': '2024-06 2024-09'}]
check('TikTok', verdicts(tt), ['ok', 'bad', 'ok', 'ok', 'ok', 'bad'])

# whole read: block boxes decided by code, unknown ones get the entry in the label, lone questions untouched
import whole_read as W  # noqa: E402
items = [dict(r, key='k%d' % i, value=r['page'], rule=r.get('source'), pos=i) for i, r in enumerate(gh + [
    {'label': 'Minor', 'page': 'None', 'source': 'rules:discipline'}])]
dec, rest = W.blocks_first(items, items, ENTS)
check('blocks_first decided', sorted(dec), ['k2', 'k3', 'k4', 'k5', 'k6', 'k7', 'k8'])
check('blocks_first bad', dec['k8']['agree'], False)
check('blocks_first rest', [r['key'] for r in rest], ['k0', 'k1', 'k9'])
check('blocks_first lone label unchanged', rest[0]['label'], 'What is your GPA?')
# Minor right after the education section: a box the code cannot judge → the model reads it WITH the entry
check('blocks_first minor with entry', [r['label'] for r in rest][2:], ['Minor — education entry: University of Chicago, M.S. Applied Data Science (2026-09 – 2027-12, in progress)'])

# gate wiring: runner_common + run_wd helpers
import runner_common as RC  # noqa: E402
res = {'fields': [{'label': 'Education (University of Chicago): Overall GPA', 'page': '3.60', 'source': 'background'}]}
_e = BC.entries
BC.entries = lambda prof=None, wd=None: ENTS
try:
    check('runner_common.block_problems', len(RC.block_problems(res)), 1)
    check('runner_common clean', RC.block_problems({'fields': [{'label': 'Education (UIUC): GPA', 'page': '3.60', 'source': 'background'}]}), [])
finally:
    BC.entries = _e

# --- the DeepSeek cases
cases = json.load(open(os.path.join(HERE, 'test_cases', 'block_check_cases.json'), encoding='utf-8'))
try:
    rulings = json.load(open(os.path.join(HERE, 'test_cases', 'block_check_verdicts.json'), encoding='utf-8'))
except OSError:
    rulings = {}
ds_fail = 0
for c in cases:
    want = list(c['expect'])
    for idx, val in (rulings.get(c['name']) or {}).get('expect', {}).items():
        want[int(idx)] = val                                       # Claude's ruling: the case misread the spec at this row
    got = verdicts(c['rows'])
    if got != want:
        ds_fail += 1
        diff = [(i, c['rows'][i]['label'][:30], c['rows'][i].get('page', '')[:25], g, w) for i, (g, w) in enumerate(zip(got, want)) if g != w]
        fails.append(f"case {c['name']}: {diff}")
    n += 1
print(f'{n} checks, {len(fails)} fails ({len(cases)} DeepSeek cases, {ds_fail} differ)')
for f in fails:
    print('  FAIL', f)
sys.exit(1 if fails else 0)
