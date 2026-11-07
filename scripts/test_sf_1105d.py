#!/usr/bin/env python3
"""SuccessFactors 2026-11-05 fourth round (JSA-092 types AE / AF): education-row From / To Date boxes
(sf_combo_edu.edu_date_want), what covers the final Apply button (run_successfactors.cover_action) and the outcome wording
after pressing it (press_result — a click that never landed is never "pressed the final button"). DeepSeek wrote the cases
from scripts/test_cases/sf_1105d_spec.md (rule 13); disagreements judged in sf_1105d_verdicts.json. Prints `N/M ok`.
    python3 scripts/test_sf_1105d.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
RUN = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUN)
import run_successfactors as R  # noqa: E402
import sf_combo_edu as CE  # noqa: E402


def got(c):
    a = c['args']
    if c['fn'] == 'edu_date_want':
        return CE.edu_date_want(a['label'], a.get('edu'), a.get('required'), a.get('fmt'))
    if c['fn'] == 'cover_action':
        return R.cover_action(a.get('el'))
    if c['fn'] == 'press_result':
        st, note = R.press_result(a['clicked'], a.get('confirmed_by'), a['button_left'])
        return st, note


def same(c, g):
    if c['fn'] != 'press_result':
        return g == c['expect']
    st, note = g
    e = c['expect']
    pre = e.get('note_prefix')
    if st != e['status'] or (note is None) != (pre is None) or (pre is not None and not note.startswith(pre)):
        return False
    return c['args']['clicked'] or not note or 'pressed the final button' not in note      # a click that never landed never says "pressed"


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sf_1105d_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sf_1105d_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    ok = bad = 0
    for c in cases:
        g = got(c)
        if same(c, g):
            ok += 1
        elif c['name'] in verdicts:
            ok += 1; print('VERDICT', c['name'], '—', verdicts[c['name']][:150])
        else:
            bad += 1; print('FAIL', c['name'], c['fn'], json.dumps(c['args'])[:200], '| want', repr(c['expect']), '| got', repr(g))
    # fixed checks from the live pages (Danfoss / Newell 11-05, read-only DOM)
    danfoss = {'self': False, 'tag': 'div', 'id': '', 'cls': 'cookiePolicy cookiemanager ', 'role': 'region', 'title': '', 'name': '', 'src': '',
               'text': 'We use cookies to offer you the best possible website experience. Your cookie preferences will be stored in your browser', 'fixed': True}
    uchicago = {'school': 'University of Chicago', 'start': '2026-09', 'end': '2027-12'}
    uiuc = {'school': 'University of Illinois Urbana-Champaign', 'end': '2026-05'}
    live = [('danfoss cookie banner over #fbqa_apply → hide_banner', R.cover_action(danfoss) == 'hide_banner'),
            ('danfoss inner div.centered without the fixed root → stop (never hide a page element)', R.cover_action(dict(danfoss, cls='centered', role='', fixed=False)) == 'stop'),
            ('phenom chat iframe → hide_chat', R.cover_action({'tag': 'iframe', 'id': 'phenomChatbotIframe', 'title': 'Phenom Career Bot', 'fixed': True}) == 'hide_chat'),
            ('newell UChicago From Date (required, MM/dd/yyyy) → 09/01/2026', CE.edu_date_want('From Date', uchicago, True, 'MM/dd/yyyy') == '09/01/2026'),
            ('newell UChicago To Date (optional) → left empty', CE.edu_date_want('To Date', uchicago, False, 'MM/dd/yyyy') is None),
            ('newell UIUC From Date: no start on file → None (ask Joey)', CE.edu_date_want('From Date', uiuc, True, 'MM/dd/yyyy') is None),
            ('a failed click with the button still there is blocked, not "pressed"', R.press_result(False, None, False)[0] == 'blocked'
             and 'pressed the final button' not in R.press_result(False, None, False)[1]),
            ('a failed click is never the pressed wording, button gone either', 'pressed the final button' not in R.press_result(False, None, True)[1])]
    for name, cond in live:
        ok += cond; bad += (not cond); print(('ok   ' if cond else 'FAIL ') + name)
    print(f"{ok}/{len(cases) + len(live)} ok")
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
