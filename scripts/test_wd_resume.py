#!/usr/bin/env python3
"""JSA-392: Workday checkpoint + resume — run_wd.norm_step / checkpoint_update / resume_target (DeepSeek-written cases
scripts/test_cases/wd_resume_cases.json; a case judged wrong goes into wd_resume_verdicts.json with its source) and the jump on a fake page.
    python3 scripts/test_wd_resume.py"""
import copy, json, os, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_wd  # noqa: E402

cases = json.load(open(os.path.join(HERE, 'test_cases', 'wd_resume_cases.json')))
cases = cases['cases'] if isinstance(cases, dict) else cases
vp = os.path.join(HERE, 'test_cases', 'wd_resume_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
def T(name, ok, info=''):
    global bad
    v = verdicts.get(name)
    if not ok and v and v.get('verdict') == 'case':
        print(f'SKIP {name}  (case judged wrong: {v["why"][:80]})'); return
    print(('PASS ' if ok else 'FAIL ') + name + ('' if ok else f'  {info}')); bad += not ok

for c in cases:
    if c['fn'] == 'norm_step': got = run_wd.norm_step(c['value'])
    elif c['fn'] == 'checkpoint_update':
        cp = copy.deepcopy(c.get('cp')); got = run_wd.checkpoint_update(cp, c['step'], c['at'])
        if cp != c.get('cp'): got = 'MUTATED'
    else: got = run_wd.resume_target(c['done'], c['bar'])
    T(c['name'], got == c['expect'], f"got {got!r} want {c['expect']!r}")

BAR = ['My Information', 'My Experience', 'Application Questions', 'Voluntary Disclosures', 'Self Identify', 'Review']
T('vanguard: My Information + My Experience saved → jump to Application Questions, My Experience is not re-saved',
  run_wd.resume_target(['My Information', 'My Experience'], BAR) == 'Application Questions')

# the jump itself on a fake page: the bar item is clicked, the active step changes → True; an item that cannot be clicked → False
class Item:
    def __init__(s, page, name): s.page, s.name = page, name
    def inner_text(s, **k): return s.name
    def click(s, **k):
        if s.page.clickable: s.page.active = s.name
class Loc:
    def __init__(s, page, sel): s.page, s.sel = page, sel
    def all(s): return [Item(s.page, n) for n in s.page.bar]
    def count(s): return 1 if 'ActiveStep' in s.sel else len(s.page.bar)
    @property
    def first(s): return s
    def inner_text(s, **k): return 'current step 3 of 6 ' + s.page.active
class FakePage:
    def __init__(s, clickable): s.bar, s.active, s.clickable = BAR, 'My Information', clickable
    def locator(s, sel): return Loc(s, sel)
logs = []
fp = FakePage(True)
T('jump_to_step: clicks the bar item and reads the new active step', run_wd.jump_to_step(fp, 'Application Questions', logs.append, wait=1) is True and fp.active == 'Application Questions')
fp2 = FakePage(False)
T('jump_to_step: an item that does not move the page → False (full pass)', run_wd.jump_to_step(fp2, 'Application Questions', logs.append, wait=1) is False)
T('bar_steps: the names in bar order', run_wd.bar_steps(FakePage(True)) == BAR)
# checkpoint file round trip
d = tempfile.mkdtemp()
run_wd.save_checkpoint(d, run_wd.checkpoint_update(None, 'My Information', '2026-11-17T10:00:00-06:00'))
run_wd.save_checkpoint(d, run_wd.checkpoint_update(run_wd.load_checkpoint(d), 'My Experience', '2026-11-17T10:01:00-06:00'))
T('checkpoint file: saved pages accumulate across saves', run_wd.load_checkpoint(d)['done'] == ['my information', 'my experience'])
T('checkpoint file: a missing or broken file reads as empty', run_wd.load_checkpoint(tempfile.mkdtemp()) == {} and (open(os.path.join(d, 'checkpoint.json'), 'w').write('{broken') and run_wd.load_checkpoint(d) == {}))
# review (JSA-392): the jump is forward only — hand-derived from the JSA-032 loss: going back to a saved My Experience re-saves it
T('should_jump: forward to Application Questions from My Information', run_wd.should_jump('My Information', 'Application Questions', BAR) is True)
T('should_jump: never back (the tab is already past the target)', run_wd.should_jump('Voluntary Disclosures', 'Application Questions', BAR) is False)
T('should_jump: never to the page it is on', run_wd.should_jump('My Experience', 'My Experience', BAR) is False)
T('should_jump: screen-reader prefix on the current page is read', run_wd.should_jump('current step 1 of 6 My Information', 'My Experience', BAR) is True)
T('should_jump: an unknown name → no jump', run_wd.should_jump('My Information', 'Nope', BAR) is False and run_wd.should_jump('', 'Review', BAR) is False)
# answers survive a stop before Review (a resume skips those pages; Review checks them against wd_answered.json)
d2 = tempfile.mkdtemp()
run_wd.merge_answered(d2, {('Education 1', 'School'): 'University of Illinois Urbana-Champaign', ('', 'First Name'): 'Alex'})
merged = run_wd.merge_answered(d2, {('Education 2', 'School'): 'University of Chicago'})
T('merge_answered: earlier pages stay, new ones are added, file readable', merged == json.load(open(os.path.join(d2, 'wd_answered.json'))) and set(merged) == {'Education 1||School', '||First Name', 'Education 2||School'}, merged)
T('merge_answered: a broken file is replaced, not fatal', (open(os.path.join(d2, 'wd_answered.json'), 'w').write('[1') and run_wd.merge_answered(d2, {('', 'x'): 'y'}) == {'||x': 'y'}))
run_wd.save_checkpoint(d2, {'done': ['my information']}); run_wd.clear_checkpoint(d2)
T('clear_checkpoint removes it (and is harmless when absent)', run_wd.load_checkpoint(d2) == {} and run_wd.clear_checkpoint(d2) is None)
T('resume_target: a "Sign-In" bar entry is not an application page', run_wd.resume_target(['my information'], ['Sign-In', 'My Information', 'My Experience']) == 'My Experience')
T('load_checkpoint: a done that is not a list is ignored', (open(os.path.join(d2, 'checkpoint.json'), 'w').write('{"done": "abc"}') and run_wd.load_checkpoint(d2) == {}))
sys.exit(1 if bad else 0)
