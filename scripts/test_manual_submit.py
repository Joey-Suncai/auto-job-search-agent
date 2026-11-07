#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/manual_submit_cases.json, from manual_submit_spec.md) against
skills/auto-apply/runner/manual_submit.py (should_write, sheet) and scripts/store/sync_results.manual_line (JSA-042).
Claude judges every disagreement in scripts/test_cases/manual_submit_verdicts.json ("code" = fixed / "case" = the case
misread the spec, with the reason). A disagreement without a verdict fails.    python3 scripts/test_manual_submit.py"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')); sys.path.insert(0, os.path.join(HERE, 'store'))
import manual_submit as M  # noqa: E402
import sync_results as S  # noqa: E402


def parse(text):
    rows = []
    for line in text.split('\n'):
        m = re.match(r'^\| (\d+) \| (.*) \| (.*) \|$', line)
        if m:
            ans = m.group(3)
            f = re.match(r'^upload `(.*)`$', ans)
            rows.append([m.group(2), f.group(1) if f else ('LONG' if re.match(r'^see answer \d+ below$', ans) else ans)])
    sec = lambda h: re.findall(r'^- `?(.*?)`?$', (text.split(f'## {h}\n\n', 1) + [''])[1].split('\n\n')[0], re.M) if f'## {h}\n' in text else []
    longs = [{'n': int(n), 'text': t} for n, t in re.findall(r'^## Answer (\d+) — .*\n\n```\n(.*?)\n```', text, re.M | re.S)]
    cmd = re.search(r'--manual "([^"]+)"', text)
    return rows, sec('Leave blank'), sec('Files'), longs, cmd.group(1) if cmd else None


def run(c):
    k = c['kind']
    if k == 'should_write':
        return M.should_write(c['ats'], c.get('problems') or [], c.get('results') or [], c['status']), c['expect']
    if k == 'manual_line':
        return S.manual_line(c['folder'], c.get('results') or [], c.get('url', ''), c.get('ats', ''), c.get('at', ''), c.get('note') or ''), c['expect']
    t = M.sheet({'url': 'https://jobs.lever.co/x/apply', 'fields': c.get('plan_fields') or []}, c['results'], c['folder'], {}, '2026-10-31')
    rows, blank, files, longs, cmd = parse(t)
    ok_static = 'https://jobs.lever.co/x/apply' in t and 'error verifying' in t and 'Gmail' in t
    got = {'rows': rows, 'blank': blank, 'files': files, 'long': longs, 'cmd': cmd, 'static': ok_static}
    want = {'rows': c.get('expect_rows') or [], 'blank': c.get('expect_blank') or [], 'files': c.get('expect_files') or [],
            'long': c.get('expect_long') or [], 'cmd': c.get('expect_command_folder') or os.path.basename(c['folder'].rstrip('/')), 'static': True}
    return got, want


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'manual_submit_cases.json')))
    vp = os.path.join(HERE, 'test_cases', 'manual_submit_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got, want = run(c)
        if got == want:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1
        print('FAIL ', c['name'], '\n   got ', json.dumps(got, ensure_ascii=False)[:600], '\n   want', json.dumps(want, ensure_ascii=False)[:600])
    print(f'{len(cases)} cases · disagreements without a verdict: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
