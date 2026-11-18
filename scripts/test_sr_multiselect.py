#!/usr/bin/env python3
"""JSA-387 (Arista 11-11): the "select all that apply" list is spl-multiselect-autocomplete.
  1. DeepSeek cases (rule 13) for multi_has: test_cases/sr_multi_cases.json, verdicts in test_cases/sr_multi_verdicts.json;
  2. headless mock (runner/test/sr_multiselect_mock.html): select_options lists the options, fill_select picks one, read_value
     returns its tag, multi_has accepts it; READ_Q-style detection of the control tag is covered by the live dry run.
Run with the venv python (Playwright; part 2 skipped without it). Exit 1 on any failure."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUNNER)
import run_smartrecruiters as SR  # noqa: E402
cases = json.load(open(os.path.join(HERE, 'test_cases', 'sr_multi_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'sr_multi_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    got = SR.multi_has(*c['args'])
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print(f'{len(cases)} cases · part 2 skipped (no Playwright) · disagreements: {bad}'); sys.exit(1 if bad else 0)
with sync_playwright() as pw:
    br = None
    for kw in ({'channel': 'chrome', 'headless': True}, {'headless': True}):
        try:
            br = pw.chromium.launch(**kw); break
        except Exception:
            continue
    if br is None:
        print('no headless Chrome; part 2 skipped')
    else:
        page = br.new_page(); page.goto('file://' + os.path.abspath(os.path.join(RUNNER, 'test', 'sr_multiselect_mock.html')))
        opts = SR.select_options(page, 'question_x1')
        if 'Online job board' not in opts or len(opts) != 5:
            bad += 1; print('DISAGREE select_options', opts)
        SR.fill_select(page, 'question_x1', 'Online job board')
        got = SR.read_value(page, {'key': 'question_x1', 'type': 'select'})
        if not SR.multi_has(got, 'Online job board') or SR.multi_has(got, 'LinkedIn'):
            bad += 1; print('DISAGREE read_value after pick', repr(got))
        br.close()
print(f'{len(cases)} cases + mock · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
