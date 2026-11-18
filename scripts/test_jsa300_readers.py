#!/usr/bin/env python3
"""Harness for JSA-300 (rule 13): eligibility_fetch.adp_wfn_api / gh_boards_in_page, wd_search.job_url / parse_tenant,
EF.clearcompany_route / clearcompany_site_id, gate_run.read_ids / pick (--ids), gate_render.page_verdict (closed notice "can't view this job", site-error pages). DeepSeek wrote the cases from
test_cases/jsa300_readers_spec.md; Claude's verdicts on disagreements are in jsa300_readers_verdicts.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import eligibility_fetch as EF, wd_search as W, gate_render as G, gate_run as GR
cases = json.load(open(os.path.join(HERE, 'test_cases', 'jsa300_readers_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'jsa300_readers_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}


def run(c):
    a = dict(c.get('args') or {})
    if 'text_repeat' in a:
        tr = a.pop('text_repeat'); a['text'] = '\n'.join([tr['chunk']] * int(tr['times']))
    f = c['fn']
    if f == 'adp_wfn_api':
        r = EF.adp_wfn_api(a.get('link')); return list(r) if r else None
    if f == 'gh_boards_in_page':
        return EF.gh_boards_in_page(a.get('page'))
    if f == 'job_url':
        return W.job_url(a['host'], a['tenant'], a['site'], a['path'])
    if f == 'parse_tenant':
        r = W.parse_tenant(a.get('url')); return list(r) if r else None
    if f == 'clearcompany_route':
        r = EF.clearcompany_route(a.get('link')); return list(r) if r else None
    if f == 'clearcompany_site_id':
        return EF.clearcompany_site_id(a.get('page'))
    if f == 'read_ids':
        return sorted(GR.read_ids(a.get('text')))
    if f == 'pick':
        due_ids = set(a.get('due_ids') or [])
        ids = set(a['ids']) if a.get('ids') is not None else None
        return [j['id'] for j in GR.pick(a.get('jobs') or [], lambda j: j['id'] in due_ids, ids)]
    if f == 'page_verdict':
        v = G.page_verdict(a.get('url', ''), a.get('final_url', ''), a.get('title', ''), a.get('text', ''), a.get('http', 200) or 200)
        return {'status': v['status']}
    raise ValueError(f)


bad = 0
for c in cases:
    got = run(c)
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1
        print('DISAGREE', c['name'], '| got', json.dumps(got)[:200], '| expect', json.dumps(c['expect'])[:200], '| args', json.dumps(c.get('args'))[:300])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
