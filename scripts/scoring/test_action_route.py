#!/usr/bin/env python3
"""Harness for the tracker Done button (rule 13, JSA-125): action_done.mark + pref_server.validate('/action');
DeepSeek cases in test_cases/action_route_cases.json, verdicts in action_route_verdicts.json."""
import copy, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
TC = os.path.join(HERE, '..', 'test_cases')
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'store'))
import action_done, pref_server  # noqa: E402
cases = json.load(open(os.path.join(TC, 'action_route_cases.json'), encoding='utf-8'))
vp = os.path.join(TC, 'action_route_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    if c['fn'] == 'mark':
        before = copy.deepcopy(c['row'])
        row, err = action_done.mark(c['row'], c['done'], c['today'])
        ok = row == c['expect_row'] and err == c['expect_error'] and c['row'] == before
        got = {'row': row, 'error': err}
    else:
        code, out = pref_server.validate(c['method'], c['path'], c['headers'], c['body'].encode('utf-8'))
        # error payloads are {"error": text}; the spec fixes keys / payload only for 200
        ok = code == c.get('expect_code') and (code != 200 or (sorted(out) == sorted(c.get('expect_payload_keys', sorted(out)))
                                                             and out == c.get('expect_payload', out)))
        got = {'code': code, 'out': out}
    if not ok and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got, ensure_ascii=False)[:300], '| case', json.dumps({k: v for k, v in c.items() if k.startswith('expect')}, ensure_ascii=False)[:300])
print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
