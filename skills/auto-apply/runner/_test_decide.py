#!/usr/bin/env python3
"""Offline tests for decide.py (event -> action). Run: python3 _test_decide.py  -> must print "fails 0"."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import decide as D

fails = []


def check(name, cond, detail=''):
    if not cond:
        fails.append('%s: %s' % (name, detail))


def fake(action, reason='ok'):
    return lambda msg, system: {'action': action, 'reason': reason}


def folder():
    return tempfile.mkdtemp()


EV = {'event': 'requirement_appeared', 'kind': 'cover_letter', 'required': True, 'generatable': True,
      'page': 'Application Questions', 'evidence': "file slot 'Cover Letter'"}

# 1. the model's valid choice is taken and logged
f = folder()
r = D.decide(EV, f, ask=fake('generate_material'))
check('valid action accepted', r['action'] == 'generate_material' and r['source'] == 'model', str(r))
check('decision logged', len(D._read_log(f)) == 1, str(D._read_log(f)))

# 2. an action outside the menu is refused
f = folder()
r = D.decide(EV, f, ask=fake('click_submit'))
check('out-of-menu refused', r['action'] == 'pause_for_joey' and r['source'] == 'invalid_action', str(r))

# 3. generate_material is refused when the event says it is not generatable
f = folder()
r = D.decide(dict(EV, generatable=False), f, ask=fake('generate_material'))
check('not generatable refused', r['action'] == 'pause_for_joey' and 'not generatable' in r['reason'], str(r))

# 4. skip_if_optional is refused for a required field
f = folder()
r = D.decide(EV, f, ask=fake('skip_if_optional'))
check('required field cannot be skipped', r['action'] == 'pause_for_joey', str(r))
r2 = D.decide(dict(EV, required=False), folder(), ask=fake('skip_if_optional'))
check('optional field may be skipped', r2['action'] == 'skip_if_optional', str(r2))

# 5. the same event is decided once
f = folder()
a = D.decide(EV, f, ask=fake('generate_material'))
b = D.decide(EV, f, ask=fake('pause_for_joey'))
check('second call cached', b['source'] == 'cached' and b['action'] == 'generate_material', str(b))
check('one log line only', len(D._read_log(f)) == 1, str(D._read_log(f)))

# 6. the per-application decision cap
f = folder()
for i in range(3):
    D.decide(dict(EV, evidence='slot %d' % i), f, ask=fake('generate_material'))
r = D.decide(dict(EV, evidence='slot 9'), f, ask=fake('generate_material'))
check('cap enforced', r['source'] == 'cap' and r['action'] == 'pause_for_joey', str(r))

# 7. unknown event types never reach the model
f = folder()
r = D.decide({'event': 'meteor_strike'}, f, ask=fake('abort'))
check('unknown event falls back', r['source'] == 'unknown_event' and r['action'] == 'pause_for_joey', str(r))

# 8. retry budget on unknown_widget
spec = {'event': 'unknown_widget', 'required': True, 'retries_used': 1}
f = folder()
r = D.decide(spec, f, ask=fake('classify_and_retry'))
check('retry budget enforced', r['action'] == 'pause_for_joey', str(r))
r2 = D.decide(dict(spec, retries_used=0), folder(), ask=fake('classify_and_retry'))
check('first retry allowed', r2['action'] == 'classify_and_retry', str(r2))

# 9. a failing model call degrades safely
f = folder()
def boom(msg, system):
    raise RuntimeError('api down')
r = D.decide(EV, f, ask=boom)
check('model failure degrades', r['action'] == 'pause_for_joey' and r['source'] == 'model_error', str(r))

print('fails', len(fails))
for x in fails:
    print(' FAIL', x)
sys.exit(1 if fails else 0)
