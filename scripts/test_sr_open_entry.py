#!/usr/bin/env python3
"""Runs the DeepSeek-written cases (scripts/test_cases/sr_open_entry_cases.json, spec sr_open_entry_spec.md) against
run_smartrecruiters.open_entry on a headless page: an "Add education entry" button inside a shadow root at a given
height of a 700-pixel window, which reveals an Institution spl-autocomplete after N clicks (NevFengal 11-05: the
button sat below the fold, the click landed nowhere and the runner waited 30 s — JSA-221). Verdicts in
sr_open_entry_verdicts.json.
    ~/.job-agent-venv/bin/python scripts/test_sr_open_entry.py"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
os.environ.setdefault('JSA_ALLOW_REPO_HOME', '1')
try:
    import run_smartrecruiters as R  # noqa: E402
    from playwright.sync_api import sync_playwright  # noqa: E402
except ImportError as e:
    print(f'skip test_sr_open_entry ({e})'); sys.exit(0)


def page_html(a):
    y, hidden, n = a.get('button_y'), a.get('hidden'), a.get('opens_after_clicks')
    host = '' if y is None else f'<div id="host" style="position:absolute;top:{y}px;left:40px"></div>'
    return f'''<html><body style="margin:0;height:6000px">{host}<div id="form"></div><script>
const h = document.getElementById('host'); let clicks = 0; const need = {json.dumps(n)};
if (h) {{ const r = h.attachShadow({{mode: 'open'}});
  r.innerHTML = '<button aria-label="Add education entry" style="{'width:0;height:0;padding:0;border:0;overflow:hidden' if hidden else 'width:70px;height:30px'}">{'' if hidden else 'Add'}</button>';
  r.querySelector('button').addEventListener('click', () => {{ clicks++; if (need !== null && clicks >= need && !document.querySelector('spl-autocomplete'))
    document.getElementById('form').innerHTML = '<spl-autocomplete label="Institution"><input></spl-autocomplete>'; }}); }}
</script></body></html>'''


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'sr_open_entry_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'sr_open_entry_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad = 0
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel='chrome')   # the installed Chrome; never the job Chrome
        except Exception:
            b = p.chromium.launch(headless=True)
        for c in cases:
            pg = b.new_page(viewport={'width': 1000, 'height': 700}); pg.set_content(page_html(c['args']))
            t = time.time()
            got = R.open_entry(pg, 'Add education entry', pg.locator('spl-autocomplete[label="Institution"] input').first, wait_ms=1500)
            took = time.time() - t; pg.close()
            if got == c['expect'] and took < 8:
                print(f'PASS  {c["name"]} ({took:.1f}s)'); continue
            v = verdicts.get(c['name'])
            if v and v.get('verdict') == 'case':
                print('CASE ', c['name'], '—', v['why']); continue
            bad += 1; print('FAIL ', c['name'], 'got', got, f'{took:.1f}s', 'want', c['expect'])
        b.close()
    print(f'{len(cases) - bad}/{len(cases)} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
