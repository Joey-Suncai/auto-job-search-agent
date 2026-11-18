#!/usr/bin/env python3
"""JSA-406: the "Give up" button of the Waiting-for-you table. Cases written by DeepSeek from test_cases/give_up_spec.md:
action_done.decline, pref_server.validate('/decline'), joey_todo.tracker_actions, echo_funnel.records."""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'store')); sys.path.insert(0, os.path.join(HERE, 'scoring'))
import action_done, pref_server, joey_todo, echo_funnel  # noqa: E402
TC = os.path.join(HERE, 'test_cases')
cases = json.load(open(os.path.join(TC, 'give_up_cases.json'), encoding='utf-8'))
vp = os.path.join(TC, 'give_up_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = []
for c in cases:
    if c['name'] in verdicts:
        continue
    if c['fn'] == 'decline':
        before = copy.deepcopy(c['row'])
        row, err = action_done.decline(c['row'], c['give_up'], c['today'])
        ok = row == c['expect_row'] and err == c['expect_error'] and c['row'] == before
        got = {'row': row, 'error': err}
    elif c['fn'] == 'validate':
        code, out = pref_server.validate(c['method'], c['path'], c['headers'], c['body'].encode('utf-8'))
        ok = code == c['expect_code'] and (code != 200 or out == c.get('expect_payload', out))
        got = {'code': code, 'out': out}
    elif c['fn'] == 'todo':
        got = [r['job_id'] for r in joey_todo.tracker_actions(c['apps'], c['today'])]
        ok = got == c['expect_job_ids']
    else:
        got = {r['job_id']: r['declined'] for r in echo_funnel.records(c['apps'], [], [])}
        ok = got == c['expect']
    if not ok:
        bad.append(f"{c['name']}: got {json.dumps(got, ensure_ascii=False)[:300]} | want {json.dumps({k: v for k, v in c.items() if k.startswith('expect')}, ensure_ascii=False)[:300]}")
print(f'give up: {len(bad)} failure(s) in {len(cases)} cases')
for b in bad:
    print('FAIL', b)
sys.exit(1 if bad else 0)
