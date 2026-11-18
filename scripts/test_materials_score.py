#!/usr/bin/env python3
"""Cases for materials_score.score (JSA-194). Expected values derived by hand from the formula in the module docstring;
inputs are shaped like a real folder (Mortaldel AI Engineering Intern: tailored.json terms, materials_manifest.json).
    python3 scripts/test_materials_score.py   → "fails 0" """
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store'))
import materials_score as M

def term(t, truth, before, after, spell=None):
    return {'term': t, 'jd_spelling': spell or t, 'truth': truth, 'before': before, 'after': after}

TERMS = [term('machine learning', 'true', 'other spelling', 'exact', 'ML'), term('LLM', 'true', 'other spelling', 'other spelling', 'LLMs'),
         term('generative AI', 'true', 'exact', 'exact'), term('cross-functional', 'not true', 'no', 'no'),
         term('RAG', 'not true', 'no', 'no'), term('backend', 'not used', 'no', 'no'), term('insights', 'true', 'no', 'exact')]
MAN = {'track': 'AI_Agentic_Engineer', 'company': 'Mortaldel', 'title': 'AI Engineering Intern',
       'resume': {'check': 'pass'}, 'letter': {'fact_check': 'pass', 'words': 311, 'stories': ['M2', 'S1']}}
TAIL = {'direction': 'ai_agentic', 'terms': TERMS, 'tailored': {'entries': [{'entry_id': 'jsa', 'bullets': [{'fact_ids': ['jsa.a', 'jsa.b']}, {'fact_ids': ['jsa.c']}]}]}}
fails = 0
def check(name, cond, detail=''):
    global fails
    if not cond: fails += 1; print('FAIL', name, detail)
    else: print('ok  ', name)

r = M.score(MAN, TAIL, {}, 'I built a tool. It works.')
check('coverage counts: after 4/7, before 3/7, exact 3', r['coverage'] == {'before': 3, 'after': 4, 'total': 7, 'exact_after': 3, 'share': 0.571}, r['coverage'])
check('score = round(100 × 4/7) = 57, no flags', r['score'] == 57 and r['flags'] == [], (r['score'], r['flags']))
check('not-true gaps leave out "not used" (he confirmed not having it — never ask again)', r['gaps_not_true'] == ['cross-functional', 'RAG'], r['gaps_not_true'])
check('phrasing gaps = true but not exact', r['gaps_phrasing'] == ['LLMs'], r['gaps_phrasing'])
check('bullet ids come from the tailored master', r['bullet_ids'] == ['jsa:jsa.a+jsa.b', 'jsa:jsa.c'], r['bullet_ids'])
check('track / direction carried', r['track'] == 'AI_Agentic_Engineer' and r['direction'] == 'ai_agentic')
r2 = M.score(dict(MAN, letter={'fact_check': 'fail', 'words': 300}), TAIL, {}, 'We are a great fit and passionate.')
check('letter fact fail + banned phrases cost 10 each', r2['score'] == 37 and len(r2['flags']) == 2 and r2['letter']['banned_hits'] == ['great fit', 'passionate'], (r2['score'], r2['flags'], r2['letter']))
r3 = M.score(dict(MAN, resume={'check': 'fail'}), TAIL, {}, '')
check('resume check fail costs 10', r3['score'] == 47 and r3['flags'] == ['resume check not pass'], (r3['score'], r3['flags']))
r4 = M.score(MAN, {}, {'data': {'resume': {'exp': {'HP': ['HP07', 'HP08']}, 'projects': {'JSA': ['JSA05']}}}}, '')
check('legacy folder: no terms → score None, bank IDs listed, flagged', r4['score'] is None and r4['bullet_ids'] == ['HP07', 'HP08', 'JSA05'] and any('no JD terms' in f for f in r4['flags']), r4)
check('empty input does not crash', M.score(None, None, None)['score'] is None)
check('banned_hits is whole-word start: "leveraged" hits, "oleverage" does not', M.banned_hits('He leveraged it; oleverage') == ['leverage'])
print('fails', fails); sys.exit(1 if fails else 0)
