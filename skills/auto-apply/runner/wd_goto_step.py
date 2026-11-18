#!/usr/bin/env python3
"""Go Back (or forward) in an open Workday application until the progress step matches.  wd_goto_step.py <url text> "<step text>" [back|next] [--allow-education-loss]

Going back to (or past) the experience step makes the forward pass save My Experience again, and most tenants then keep
only one education entry (#16 #75, JSA-032). That Back is refused unless --allow-education-loss is given (Joey's call —
e.g. he already chose one school). Steps after My Experience are safe to go back to."""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import sys, time, re
from playwright.sync_api import sync_playwright
EXP = re.compile(r'experience|education|经历|經歷', re.I)


def refuse(names, current, want, way='back', allow=False):
    """True when this Back would make the forward pass save the experience step again (tested in test/t_wd_logic.py)."""
    if way != 'back' or allow:
        return False
    cur = next((i for i, n in enumerate(names) if current and re.search(re.escape(current[:30]), n, re.I)), None)
    tgt = next((i for i, n in enumerate(names) if re.search(want, n, re.I)), None)
    exp = next((i for i, n in enumerate(names) if EXP.search(n)), None)
    if EXP.search(want):
        return True
    if exp is None:
        return False
    if tgt is not None:
        return tgt <= exp
    return cur is None or cur > exp          # target unknown: refuse unless we are still before My Experience


def main():
    args = [x for x in sys.argv[1:] if not x.startswith('--')]; allow = '--allow-education-loss' in sys.argv
    key, want = args[0], args[1]; way = args[2] if len(args) > 2 else 'back'
    btn = {'back': 'pageFooterBackButton', 'next': 'pageFooterNextButton'}[way]
    with sync_playwright() as pw:
        pg = [p for p in cdp_connect.connect(pw, 'http://127.0.0.1:9222').contexts[0].pages if key in p.url][-1]
        step = lambda: (pg.locator('[data-automation-id="progressBarActiveStep"]').first.inner_text() if pg.locator('[data-automation-id="progressBarActiveStep"]').count() else '')
        steps = [x.inner_text() for x in pg.locator('[data-automation-id="progressBar"] li, [data-automation-id^="progressBarStep"]').all()] or []
        names = [re.sub(r'\s+', ' ', x) for x in steps]
        if refuse(names, re.sub(r'\s+', ' ', step()), want, way, allow):
            print(f'refused: going back to "{want}" re-saves My Experience and drops education entries (#75). '
                  'Ask Joey; rerun with --allow-education-loss only after he chose.'); sys.exit(2)
        for _ in range(6):
            if re.search(want, step(), re.I): break
            s = step(); pg.locator(f'button[data-automation-id="{btn}"]').first.click()
            for _ in range(40):
                time.sleep(0.3)
                if step() != s: break
            time.sleep(1)
        print('now at:', step().replace('\n', ' '))


if __name__ == '__main__':
    main()
