#!/usr/bin/env python3
"""Cases for recruiter_review (JSA-252). Expected values derived by hand from the module docstring; the fake `ask` stands in
for DeepSeek, the master is shaped like a real direction master (entries[].bullets[].text).
    python3 scripts/test_recruiter_review.py   → "fails 0" """
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'resume-updater', 'scripts'))
import recruiter_review as R

MASTER = {'headline': 'AI Product Intern', 'summary': 'M.S. student.', 'skills': [{'label': 'AI', 'items': ['LLM', 'RAG']}],
          'entries': [{'entry_id': 'jsa', 'bullets': [{'text': 'Designed a multi-agent system that submitted 337 applications in 15 days.'},
                                                       {'text': 'Automated tailoring of 417 resumes with guardrails.'}]},
                      {'entry_id': 'hp', 'bullets': [{'text': 'Built a 0-5 rubric that cut review time by 70%.'}]}]}
ROLE = {'direction': 'ai_pm', 'label': 'AI Product Manager', 'competencies': [{'id': 'a', 'label': 'Roadmaps', 'weight': 0.1}, {'id': 'b', 'label': 'LLM evaluation', 'weight': 0.4}]}
fails = 0
def check(name, cond, detail=''):
    global fails
    if not cond: fails += 1; print('FAIL', name, detail)
    else: print('ok  ', name)

bl = R.bullets_of(MASTER)
check('bullets numbered in page order with their entry', [(b['n'], b['entry']) for b in bl] == [(1, 'jsa'), (2, 'jsa'), (3, 'hp')], bl)
check('empty / odd masters give no bullets', R.bullets_of({}) == [] and R.bullets_of({'entries': [{'bullets': [{'text': '  '}, {}]}]}) == [])
pr = R.build_prompt(MASTER, ROLE)
check('prompt: role, top competency first, numbered bullets, no contact data', 'Role: AI Product Manager' in pr and pr.index('LLM evaluation') < pr.index('Roadmaps') and '[3] (hp) Built a 0-5 rubric' in pr and '@' not in pr, pr)
good = {'overall': {'score': 4, 'reason': 'Clear and quantified.'}, 'bullets': [{'n': 1, 'score': 5, 'reason': 'x'}, {'n': 2, 'score': 3, 'reason': 'y'}, {'n': 3, 'score': 2, 'reason': 'z'}],
        'advice': ['a', 'b', 'c', 'd', 'e', 'f']}
rec = R.review(MASTER, ROLE, lambda s, u: good)
check('scores attach to bullets, overall kept, advice cut to 5', [b['score'] for b in rec['bullets']] == [5, 3, 2] and rec['overall']['score'] == 4 and len(rec['advice']) == 5 and rec['problems'] == [], rec)
p = R.parse_review({'overall': {'score': 9}, 'bullets': [{'n': 1, 'score': 6}, {'n': 1, 'score': 3}, {'n': 7, 'score': 5}, {'n': 'x'}, 'junk', {'n': 2, 'score': '4'}]}, 3)
check('bad scores → None + problem; duplicate: first wins; unknown n ignored; strings parse; missing bullet noted',
      p['overall']['score'] is None and p['bullets'][1]['score'] is None and p['bullets'][2]['score'] == 4 and p['bullets'][3]['score'] is None
      and sorted(p['problems']) == ['bullet 1: score missing or outside 1-5', 'bullet 3: not scored', 'overall score missing or outside 1-5'], p)
def boom(s, u): raise RuntimeError('no key')
rec2 = R.review(MASTER, ROLE, boom)
check('model failure → a record with problems, nothing raised, master untouched', rec2['overall']['score'] is None and len(rec2['bullets']) == 3 and 'review not available' in rec2['problems'][0] and len(MASTER['entries']) == 2)
check('non-dict answer does not crash', R.parse_review(None, 2)['problems'] != [] and R.parse_review([], 0)['bullets'] == {})
md = R.render_md('ai_pm', rec, '2026-11-17')
check('md: advice-only banner, overall line, low-score list, advice list', 'Advice only' in md and '**Overall: 4/5**' in md and '- [3] Built a 0-5 rubric' in md and '## What the recruiter would want' in md and 'Review problems' not in md, md)
md3 = R.render_md('x', {'overall': {'score': 1, 'reason': 'a'}, 'bullets': [{'n': 1, 'entry': 'e', 'score': 1, 'text': 't|u', 'reason': 'r|s'}], 'advice': [], 'problems': []}, 'd')
check('md: a "|" in a bullet or reason cannot break the table', '| 1 | e | 1 | t/u | r/s |' in md3, md3)
check('md shows the problems of a failed review', 'Review problems' in R.render_md('ai_pm', rec2, 'd'))
import json, tempfile, io, contextlib
tmp = tempfile.mkdtemp(); os.makedirs(os.path.join(tmp, '2026-11')); os.makedirs(os.path.join(tmp, '2026-10'))
json.dump({'master': {'entries': [{'entry_id': 'old', 'bullets': [{'text': 'Old.'}]}]}, 'approved': '2026-10-01'}, open(os.path.join(tmp, '2026-10', 'master_ai_pm.json'), 'w'))
json.dump({'master': MASTER, 'approved': None}, open(os.path.join(tmp, '2026-11', 'master_ai_pm.json'), 'w'))   # a draft, not yet approved
rp = os.path.join(tmp, 'role.json'); json.dump(ROLE, open(rp, 'w'))
with contextlib.redirect_stdout(io.StringIO()):
    code = R.run_direction('ai_pm', ask=lambda s, u: good, resume_dir=tmp, role_path=rp)
out = os.path.join(tmp, '2026-11', 'recruiter_ai_pm.json')
saved = json.load(open(out)) if os.path.exists(out) else {}
check('run_direction scores the newest master even while a draft, writes .json + .md next to it, master file untouched',
      code == 0 and saved.get('overall', {}).get('score') == 4 and saved.get('master') == 'master_ai_pm.json' and os.path.exists(out[:-5] + '.md')
      and json.load(open(os.path.join(tmp, '2026-11', 'master_ai_pm.json'))) == {'master': MASTER, 'approved': None}, saved)
check('no master → exit 2, nothing written', R.run_direction('data_analyst', ask=lambda s, u: good, resume_dir=tmp, role_path=rp) == 2 and not os.path.exists(os.path.join(tmp, '2026-11', 'recruiter_data_analyst.md')))
print('fails', fails); sys.exit(1 if fails else 0)
