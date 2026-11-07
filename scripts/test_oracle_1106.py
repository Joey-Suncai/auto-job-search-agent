#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/oracle_1106_cases.json, spec oracle_1106_spec.md) against the
JSA-226 Oracle helpers: degree_option (OSTMORFEN / Fensevpell / Harmorquin card Degree lists), tenant_id + code_mail_ok (BraRoskel got
OSTMORFEN's code a minute earlier), box_fit (Harmorquin's Salary Expectations cut to "Open / per interns") and edu_fill's fallback
(a card with no school, letters split by a resume parse). Verdicts in oracle_1106_verdicts.json.
    python3 scripts/test_oracle_1106.py"""
import json, os, sys
from datetime import date
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
import run_oracle as R  # noqa: E402


def run_case(c):
    a = c['args']
    try:
        if c['fn'] == 'degree_option':
            return R.degree_option(a['want'], a['options'])
        if c['fn'] == 'tenant_id':
            return R.tenant_id(a['url'])
        if c['fn'] == 'code_mail_ok':
            return R.code_mail_ok(a['sender'], a['body'], a['tenant'], a.get('company'))
        if c['fn'] == 'blank_card':
            return R.blank_card(a.get('title'))
        if c['fn'] == 'box_fit':
            return R.box_fit(a['label'], a['kind'], a.get('value'), a.get('box') or {})
        return R.edu_fill(a['school'], a['education'], date.fromisoformat(a['today']))
    except Exception as e:
        return f'RAISES {type(e).__name__}: {e}'


def page_check():
    """Headless page: a Fensevpell-style timeline card with the red "!" and a OSTMORFEN-style hidden "Fields to fix" tile on an
    earlier section — fix_tiles finds both (visible only → the timeline one), refusal_issues names them."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        print(f'skip page check ({e})'); return 0
    html = ('<html><body><div style="display:none"><div class="apply-flow-profile-item-tile">Economics UIUC Fields to fix: 1</div></div>'
            '<div class="beautiful-timeline-item"><div class="beautiful-timeline-item--invalid-block icon-alert-error"></div>'
            '<div class="beautiful-timeline-item__content">Data Science THE UNIVERSITY OF CHICAGO</div></div>'
            '<div class="beautiful-timeline-item"><div class="beautiful-timeline-item__content">Economics UIUC</div></div>'
            '<div class="input-row input-row--invalid">Degree The Degree field is required.</div></body></html>')
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel='chrome')   # the installed Chrome; never the job Chrome
        except Exception:
            b = p.chromium.launch(headless=True)
        pg = b.new_page(); pg.set_content(html)
        vis, allt, issues = R.fix_tiles(pg).count(), R.fix_tiles(pg, visible_only=False).count(), R.refusal_issues(pg)
        pg2 = b.new_page(); pg2.set_content(          # a blank card whose Delete icon lies under a popup (Harmorquin 11-06)
            '<article class="apply-flow-profile-item-tile"><div class="apply-flow-profile-item-tile__summary-title">Unnamed License</div>'
            'Fields to fix: 1<button class="apply-flow-profile-item-tile__delete-icon" onclick="this.closest(\'article\').remove()">x</button></article>'
            '<div style="position:fixed;inset:0;z-index:9;background:rgba(0,0,0,.1)">popup</div>')
        deleted = R.delete_card(pg2, R.fix_tiles(pg2, visible_only=False).first, lambda m: None)
        b.close()
    print(('PASS ' if deleted else 'FAIL ') + 'page: delete_card removes a blank card under a popup')
    ok = vis == 1 and allt == 2 and any(i.startswith('timeline card: Data Science') for i in issues) and any('Degree field is required' in i for i in issues)
    print(('PASS ' if ok else 'FAIL ') + f'page: fix_tiles visible {vis} / all {allt}, issues {issues}')
    return 0 if ok and deleted else 1


def main():
    cases = []
    for f in ('oracle_1106_cases.json', 'oracle_blank_cases.json'):   # + blank cards (Harmorquin 11-06)
        c = json.load(open(os.path.join(HERE, 'test_cases', f)))
        cases += c['cases'] if isinstance(c, dict) else c
    vp = os.path.join(HERE, 'test_cases', 'oracle_1106_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    for c in cases:
        got = run_case(c)
        if got == c['expect']:
            print('PASS ', c['name']); continue
        v = verdicts.get(c['name'])
        if v and v.get('verdict') == 'case':
            print('CASE ', c['name'], '—', v['why']); continue
        bad += 1; print('FAIL ', c['name'], 'got', json.dumps(got, default=str)[:300], 'want', json.dumps(c['expect'])[:300])
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if (bad or page_check()) else 0


if __name__ == '__main__':
    sys.exit(main())
