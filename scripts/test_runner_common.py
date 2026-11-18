#!/usr/bin/env python3
"""Harness for runner_common.py (JSA-187, rule 13): DeepSeek wrote the run scenarios from
test_cases/runner_common_spec.md; each scenario runs through the REAL main() of every runner it applies to — with a fake
browser, a stubbed page loop (`run`) and stubbed button press (`submit`), in a throw-away data home. Claude's verdicts on
disagreements: test_cases/runner_common_verdicts.json ("<case>" or "<case>|<ats>").

  presses_inside = false → run_workable, run_smartrecruiters, run_successfactors (the main() presses after the gate)
  presses_inside = true  → run_oracle, run_icims (the page loop presses; runner_common.gate_inside() runs before it)

    python3 scripts/test_runner_common.py      # exit 0 = no disagreement without a verdict
"""
import contextlib, importlib, io, json, os, shutil, sys, tempfile, types

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..'))
HOME = tempfile.mkdtemp(prefix='rc_home_')
DATA = os.path.join(HOME, 'data', 'runner')
os.makedirs(DATA); os.makedirs(os.path.join(HOME, 'applications')); os.makedirs(os.path.join(HOME, 'data', 'store'))
open(os.path.join(HOME, 'data', 'store', 'jobs.jsonl'), 'w').close()
os.environ.update(JSA_HOME=HOME, CX_DATA=DATA, JSA_NO_PUSH='1')
RUNNER = os.path.join(REPO, 'skills', 'auto-apply', 'runner')
sys.path[:0] = [RUNNER, os.path.join(REPO, 'skills', 'auto-apply', 'scripts'), os.path.join(REPO, 'config')]

# ---- fakes: playwright, sync_results, push
EVENTS = {}


class Page:
    def __init__(self): self.closed = False; self.url = 'about:blank'
    def screenshot(self, path=None, **k): open(path, 'wb').write(b'png')
    def is_closed(self): return self.closed
    def close(self): self.closed = True
    def set_viewport_size(self, *a, **k): pass
    def set_default_timeout(self, *a, **k): pass
    def inner_text(self, *a, **k): return ''
    def goto(self, *a, **k): EVENTS['form_opened'] = True


class Ctx:
    def __init__(self): self.pages = []
    def new_page(self): p = Page(); self.pages.append(p); return p


class PW:
    def __enter__(self):
        ns = types.SimpleNamespace(); ns.chromium = types.SimpleNamespace(connect_over_cdp=lambda *a, **k: types.SimpleNamespace(contexts=[Ctx()]))
        return ns
    def __exit__(self, *a): return False


pw_mod = types.ModuleType('playwright'); pw_sync = types.ModuleType('playwright.sync_api')
pw_sync.sync_playwright = lambda: PW(); pw_mod.sync_api = pw_sync
sys.modules['playwright'] = pw_mod; sys.modules['playwright.sync_api'] = pw_sync
sr_mod = types.ModuleType('sync_results'); sr_mod.sync_folder = lambda folder, log=None: EVENTS.__setitem__('synced', True)
sys.modules['sync_results'] = sr_mod

import canon  # noqa: E402
import run_form as RF  # noqa: E402
from materials_check import sha256  # noqa: E402
RF.push = lambda title, body: EVENTS.__setitem__('pushed', True)
RF.close_posting_tabs = lambda ctx, url: 0

URLS = {'workable': 'https://apply.workable.com/acme/j/ABCDEF1234/',
        'smartrecruiters': 'https://jobs.smartrecruiters.com/Acme/7441234567890-data-intern',
        'successfactors': 'https://jobs.acme.com/job/Chicago-Data-Intern-IL-60601/1234567890/',
        'oracle': 'https://acme.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/job/123456',
        'icims': 'https://careers-acme.icims.com/jobs/12345/data-intern/job'}
MOD = {'workable': 'run_workable', 'smartrecruiters': 'run_smartrecruiters', 'successfactors': 'run_successfactors',
       'oracle': 'run_oracle', 'icims': 'run_icims'}
want_future = canon.SPEC['fields']['sponsorship_future'].get('want', 'Yes')
WRONG = 'No' if str(want_future).lower().startswith('y') else 'Yes'


def make_folder(name, ats, c):
    d = os.path.join(HOME, 'applications', name); os.makedirs(d)
    json.dump({'company': 'Acme', 'title': 'Data Intern', 'url': URLS[ats], 'track': 'Data_Analyst'}, open(os.path.join(d, 'job.json'), 'w'))
    res = 'Alex_Doe_Resume_Acme_Data_Intern_A-Classic.pdf'
    open(os.path.join(d, res), 'wb').write(b'%PDF tailored')
    if c.get('materials_ok', True):
        json.dump({'resume': {'file': res, 'sha256': sha256(os.path.join(d, res)), 'check': 'pass'},
                   'letter': {'decision': 'not_accepted_by_form'}}, open(os.path.join(d, 'materials_manifest.json'), 'w'))
    if c.get('approved'):
        p = os.path.join(DATA, 'approved_batches.json')
        b = json.load(open(p)) if os.path.exists(p) else {'batches': []}
        b['batches'].append({'name': name, 'folders': [name]}); json.dump(b, open(p, 'w'))
    if c.get('already_submitted'):
        open(os.path.join(DATA, 'results.jsonl'), 'a').write(json.dumps({'folder': name, 'status': 'submitted'}) + '\n')
    return d


def platform_result(c, inside):
    pl = c.get('platform') or {}
    fields = [] if pl.get('no_fields') else [
        {'label': 'First name', 'want': 'Alex', 'page': 'Alex', 'type': 'text', 'required': True, 'ok': True},
        {'label': 'Will you now or in the future require visa sponsorship?', 'want': WRONG if pl.get('canon_mismatch') else want_future,
         'page': WRONG if pl.get('canon_mismatch') else want_future, 'type': 'radio', 'required': True, 'ok': True},
        {'label': 'Phone', 'want': '1', 'page': '' if pl.get('fields_ok') is False else '1', 'type': 'text', 'required': True,
         'ok': pl.get('fields_ok', True) is not False}]
    r = {'status': pl.get('status', 'dry-run'), 'problems': list(pl.get('problems') or []), 'unknown': list(pl.get('unknown') or [])}
    if inside:
        r[('sections' if inside == 'oracle' else 'steps')] = [{'fields': fields, 'problems': [], 'unknown': []}]
    else:
        r['fields'] = fields
    return r


def run_case(c, ats):
    for k in list(EVENTS):
        del EVENTS[k]
    name = f"2026-11-05_{c['name'][:40]}_{ats}".replace(' ', '_').replace('/', '_')
    folder = make_folder(name, ats, c)
    inside = ats in ('oracle', 'icims')
    m = importlib.import_module(MOD[ats])

    def stub_run(page, *a, **k):
        EVENTS['form_opened'] = True
        r = platform_result(c, ats if inside else False)
        if inside:                                      # the real page loop reaches the button only when its own checks pass
            pl = c.get('platform') or {}
            clean = (r['status'] == 'dry-run' and not r['problems'] and not r['unknown'] and not pl.get('no_fields')
                     and pl.get('fields_ok', True) is not False)
            if pl.get('fields_ok') is False:
                r['status'] = 'needs-user'; r['problems'].append('section 1: Phone not confirmed')
            if clean and m.SUBMIT:
                if m.RUN.gate_inside(r):
                    EVENTS['pressed'] = True
                    r['status'] = c.get('press_outcome') or 'submitted'
                    if r['status'] == 'submitted': r['confirmed_by'] = 'page'
        return r

    def stub_submit(*a, **k):
        EVENTS['pressed'] = True
        out = c.get('press_outcome') or 'submitted'
        return out, ('page' if out == 'submitted' else None)

    m.run = stub_run
    if hasattr(m, 'submit'):
        m.submit = stub_submit
    if hasattr(m, 'apply_url'):
        m.apply_url = lambda p, fetch=None: 'https://jobs.smartrecruiters.com/oneclick-ui/company/Acme/publication/x'
    if hasattr(m, 'wait_token'):
        m.wait_token = lambda page, secs: False
    if hasattr(m, 'by_email'):
        m.by_email = lambda *a, **k: None
    q0 = open(os.path.join(DATA, 'queue.md')).read().count(name) if os.path.exists(os.path.join(DATA, 'queue.md')) else 0
    argv = ['x', '--folder', folder] + (['--submit'] if c.get('mode') == 'submit' else [])
    sys.argv = argv
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try:
            m.main()
        except SystemExit:
            pass
    lines = [json.loads(l) for l in open(os.path.join(DATA, 'results.jsonl')) if l.strip()] if os.path.exists(os.path.join(DATA, 'results.jsonl')) else []
    mine = [l for l in lines if l.get('folder') == name and 'mode' in l]
    q = (open(os.path.join(DATA, 'queue.md')).read().count(name) if os.path.exists(os.path.join(DATA, 'queue.md')) else 0) - q0
    last = mine[-1] if mine else {}
    got = {'results_lines': len(mine), 'status': last.get('status'), 'stopped_at': last.get('stopped_at'),
           'pressed': bool(EVENTS.get('pressed')), 'queued': q, 'pushed': bool(EVENTS.get('pushed')),
           'synced': bool(EVENTS.get('synced')), 'form_opened': bool(EVENTS.get('form_opened'))}
    # every line keeps the old keys + the new ones
    if mine:
        for k in ('at', 'folder', 'url', 'ats', 'status', 'mode', 'problems', 'fields', 'bad', 'secs', 'by', 'phases', 'stopped_at', 'tenant'):
            if k not in last:
                got['missing_key'] = k
    if got['status'] == 'submitted' and not os.path.exists(os.path.join(folder, 'submitted_confirmation.png')):
        got['no_screenshot'] = True
    if got['stopped_at'] and ('停在' not in buf.getvalue()):
        got['no_layer_line'] = True
    return got, buf.getvalue()


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'runner_common_cases.json'), encoding='utf-8'))
    vp = os.path.join(HERE, 'test_cases', 'runner_common_verdicts.json')
    verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    bad = runs = 0
    for c in cases:
        targets = ('oracle', 'icims') if c.get('presses_inside') else ('workable', 'smartrecruiters', 'successfactors')
        for ats in targets:
            runs += 1
            got, out = run_case(c, ats)
            exp = c.get('expect') or {}
            diff = {k: (got.get(k), exp[k]) for k in exp if k in got and got.get(k) != exp[k]}
            for k in ('missing_key', 'no_screenshot', 'no_layer_line'):
                if got.get(k):
                    diff[k] = got[k]
            if diff and c['name'] not in verdicts and f"{c['name']}|{ats}" not in verdicts:
                bad += 1
                print('DISAGREE', c['name'], ats, diff)
                if os.environ.get('RC_VERBOSE'):
                    print(out[-1500:])
    # risk 3 in the spec: no platform name inside the common module (code or comments) — differences come in as parameters
    import re
    src = open(os.path.join(RUNNER, 'runner_common.py'), encoding='utf-8').read()
    names = re.findall(r'(?i)\b(greenhouse|lever|ashby|workday|icims|jibe|oracle|workable|smartrecruiters|successfactors|tiktok|bytedance)\b', src)
    if names:
        bad += 1; print('PLATFORM NAME in runner_common.py:', sorted(set(n.lower() for n in names)))
    shutil.rmtree(HOME, ignore_errors=True)
    print(f'{len(cases)} DeepSeek cases · {runs} runs through the real main() · disagreements without a verdict: {bad}')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
