#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/gate_render_cases.json, from gate_render_spec.md) against the
JSA-284 pure functions: eligibility_fetch.icims_read_url / wd_page_gone, wellfound_apply.clean_url (iCIMS part),
gate_render.closed_on / page_verdict, gate_run.render_pick / render_merge. Verdicts for disagreements:
gate_render_verdicts.json.    python3 scripts/test_gate_render.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'job-hunt-pipeline', 'scripts'))
import eligibility_fetch as EF, gate_render as GR, gate_run as G, wellfound_apply as WA  # noqa: E402


def call(c):
    f, a = c['fn'], c.get('args') or {}
    if f == 'icims_read_url':
        return EF.icims_read_url(a.get('link'))
    if f == 'wd_page_gone':
        return EF.wd_page_gone(a.get('html'))
    if f == 'clean_url':
        return WA.clean_url(a.get('link'))
    if f == 'closed_on':
        return GR.closed_on(a.get('text'), a.get('today'))
    if f == 'page_verdict':
        t = a.get('text')
        if t is None and a.get('text_repeat'):
            t = '\n'.join([a['text_repeat']['chunk']] * int(a['text_repeat']['times']))
        return {'status': GR.page_verdict(a.get('url'), a.get('final_url'), a.get('title'), t, a.get('http', 200), a.get('today'))['status']}
    if f == 'render_pick':
        return G.render_pick(a.get('lines') or [], a.get('rows') or {}, a.get('cap', 0))
    if f == 'render_merge':
        return G.render_merge(a.get('x') or {}, a.get('v'))
    raise ValueError(f)


def same(got, want, fn):
    if fn == 'render_merge' and isinstance(want, dict):
        return all(got.get(k) == v for k, v in want.items())
    return got == want


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'gate_render_cases.json')))
    vp = os.path.join(HERE, 'test_cases', 'gate_render_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = call(c)
        except Exception as e:
            got = f'error {type(e).__name__}: {e}'
        if same(got, c.get('expect'), c['fn']):
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], f"[{c['fn']}] got {json.dumps(got, ensure_ascii=False)[:300]} want {json.dumps(c.get('expect'), ensure_ascii=False)[:300]}")
    print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
