#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/mail_seen_cases.json, from mail_seen_spec.md) against
scripts/daily/email_check.py run_new / save_seen / load_seen (JSA-140). Claude judges every disagreement in
mail_seen_verdicts.json ("case" = the case misread the spec, with the reason).
    python3 scripts/test_mail_seen.py"""
import datetime, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'daily'))
import email_check as EC  # noqa: E402


def run(c):
    f, a = c['fn'], c['args']
    if f == 'run_new':
        called, notes = [], {}
        def apply(m):
            called.append(m['id'])
            if m['id'] in a.get('fallback_ids', []):
                notes.setdefault('fallback', []).append(m['id'])
            return a['results'].get(m['id'])
        seen = json.loads(json.dumps(a.get('seen', {})))
        res, push, n = EC.run_new(a['items'], apply, seen, notes, a['n_apps'], a.get('reread', False),
                                  datetime.date.fromisoformat(a['today']))
        return {'results': res, 'push': push, 'handled': n, 'called': called, 'seen_after': seen}
    if f == 'save_seen':
        p = os.path.join(tempfile.mkdtemp(), 'sub', 'seen.json')
        kept = EC.save_seen(p, dict(a['seen']), datetime.date.fromisoformat(a['today']))
        assert json.load(open(p)) == kept
        return kept
    if f == 'load_seen':
        p = os.path.join(tempfile.mkdtemp(), 'seen.json')
        if a.get('file') is not None:
            open(p, 'w').write(a['file'])
        return EC.load_seen(p)
    raise ValueError(f)


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'mail_seen_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'mail_seen_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        try:
            got = run(c)
        except Exception as e:
            got = f'crash {type(e).__name__}: {e}'
        want = c['expect']
        if isinstance(want, dict) and isinstance(got, dict) and c['fn'] == 'run_new':
            got = {k: v for k, v in got.items() if k in want}
        if got == want:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1
        print('FAIL ', c['name'], f'\n   got  {got!r}\n   want {want!r}')
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
