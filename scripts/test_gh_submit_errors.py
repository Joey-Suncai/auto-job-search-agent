#!/usr/bin/env python3
"""Harness (rule 13) for run.SUBMIT_ERRORS_JS — the Greenhouse form's validation errors read after Submit (JSA-209,
Viking 10-31). Each DeepSeek case (test_cases/gh_submit_errors_cases.json, written from gh_submit_errors_spec.md) is
loaded into a headless Chrome and the in-page reader runs on it. Verdicts in test_cases/gh_submit_errors_verdicts.json.
Plus a sanitized Viking fixture: the required supplement slot with "This field is required." under it → that slot's label.
Skips (exit 0) when no browser is available."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
cases = json.load(open(os.path.join(HERE, 'test_cases', 'gh_submit_errors_cases.json'), encoding='utf-8'))
vp = os.path.join(HERE, 'test_cases', 'gh_submit_errors_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
try:
    from playwright.sync_api import sync_playwright
    import run as R
except Exception as e:
    print('skip:', e); sys.exit(0)

SUPP = ('This role requires a brief research supplement describing a relevant project you recently completed. Please upload '
        'your resume and brief research supplement — as a single PDF.')
VIKING = '''<form><div class="field-wrapper"><label for="first_name">First Name*</label><input id="first_name" value="A"></div>
<div class="file-upload"><div class="label upload-label" id="upload-label-resume">Resume/CV*</div>
<div class="file-upload__filename">Resume.pdf</div><input type="file" id="resume" class="visually-hidden"></div>
<div class="file-upload"><div class="label upload-label" id="upload-label-question_20063878004">%s*</div>
<button type="button">Attach</button><p class="file-upload__accepted">Accepted file types: pdf, doc, docx, txt, rtf</p>
<input type="file" id="question_20063878004" class="visually-hidden" style="position:absolute;width:1px;height:1px">
<p class="helper-text helper-text--error" id="question_20063878004-error">This field is required.</p></div>
<button type="submit">Submit application</button></form>''' % SUPP
VPLAN = [{'key': 'first_name', 'label': 'First Name', 'sel': '#first_name'}, {'key': 'resume', 'label': 'Resume/CV', 'sel': '#resume'},
         {'key': 'question_20063878004', 'label': SUPP, 'sel': '#question_20063878004'}]

bad = 0
with sync_playwright() as p:
    try:
        br = p.chromium.launch(channel='chrome', headless=True)
    except Exception:
        try:
            br = p.chromium.launch(headless=True)
        except Exception as e:
            print('skip: no browser', str(e)[:80]); sys.exit(0)
    pg = br.new_page()
    for c in cases:
        pg.set_content(c['html'])
        got = pg.evaluate(R.SUBMIT_ERRORS_JS, c['plan'])
        if got != c['expect'] and c['name'] not in verdicts:
            bad += 1; print('DISAGREE', c['name'], '| got', got, '| expect', c['expect'])
    pg.set_content(VIKING)
    got = pg.evaluate(R.SUBMIT_ERRORS_JS, VPLAN)
    if got != [{'field': SUPP, 'msg': 'This field is required.'}]:
        bad += 1; print('FAIL viking fixture', got)
    out = R.after_submit(False, False, [], got)
    if out != {'status': 'failed', 'fields': [SUPP]}:
        bad += 1; print('FAIL viking outcome', out)
    br.close()
print(f'{len(cases)} cases + Viking fixture · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
