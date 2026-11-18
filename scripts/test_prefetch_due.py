#!/usr/bin/env python3
"""JSA-243 (rule 13): DeepSeek-written cases from scripts/test_cases/prefetch_due_spec.md (prefetch_due_cases.json,
verdicts in prefetch_due_verdicts.json) for prefetch_due.answer_of / pending / line, form_prefetch.recheck / push_line and
session_mode.due_note; plus fixed checks: mark() + load_handled() round trip, collect_batch --apply marks a prefetch sheet.
Offline, temp folders only.   python3 scripts/test_prefetch_due.py"""
import copy, json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TMP = tempfile.mkdtemp(prefix='jsa_due_')
os.environ['JSA_HOME'] = TMP
os.environ['JSA_FORMS_DIR'] = os.path.join(TMP, 'forms')
os.environ['JSA_NO_PUSH'] = '1'
for p in (os.path.join(HERE, 'store'), HERE, os.path.join(ROOT, 'skills', 'auto-apply', 'runner')):
    sys.path.insert(0, p)
import prefetch_due as PD  # noqa: E402
import ops_session as SM  # noqa: E402  (ADR-0011 step 5: the using session start note)
import form_prefetch as FP  # noqa: E402

bad = 0
CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'prefetch_due_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}


def check(name, ok, *info):
    global bad
    if not ok:
        if name in verdicts:
            return
        bad += 1
        print('FAIL', name, *info)


def run_case(c):
    n, fn = c['name'], c['fn']
    if fn == 'answer_of':
        got = PD.answer_of(c['sheet'], c['q'])
        check(n, got == c.get('expect'), got)
    elif fn == 'pending':
        got = PD.pending(c['sheet'], c.get('handled'))
        check(n, got == c['expect'], got)
    elif fn == 'line':
        got = PD.line(c['sheet'], c['ids'])
        if 'expect_exact' in c and c['expect_exact'] is not None:
            check(n, got == c['expect_exact'], repr(got))
        else:
            check(n, got.startswith(c['expect_prefix']), repr(got))
    elif fn == 'recheck':
        recs = copy.deepcopy(c['recs'])
        calls, items = [], []

        def answer(qs):
            calls.append(1); items.extend(qs)
            return {q['key']: c['answers_by_label'].get(q['label'], {'status': 'unknown'}) for q in qs}
        got = FP.recheck(recs, answer, c.get('today', '2026-11-07'))
        check(n + ' [changed]', got == c['expect_changed'], got)
        if 'expect_recs' in c:
            check(n + ' [recs]', recs == c['expect_recs'], json.dumps(recs, ensure_ascii=False)[:600])
        if 'expect_calls' in c:
            check(n + ' [calls]', len(calls) == c['expect_calls'], len(calls))
        if c.get('expect_items') is not None and calls:
            check(n + ' [items]', len(items) == c['expect_items'], len(items))
    elif fn == 'push_line':
        got = FP.push_line(c['summary'])
        e = c.get('expect')
        if e is None:
            check(n, got is None, got)
        else:
            ok = got is not None and got[0] == e['title'] and all(s in got[1] for s in e.get('body_contains') or [])
            check(n, ok, got)
    elif fn == 'due_note':
        got = SM.due_note(c['mode'], c['status_line'])
        ok = (got == '') if c.get('expect_empty') else (bool(got) and (not c.get('expect_prefix') or got.startswith(c['expect_prefix'])))
        ok = ok and all(s in got for s in c.get('contains') or []) and not any(s in got for s in c.get('not_contains') or [])
        check(n, ok, repr(got[:200]))
    else:
        check(n, False, 'unknown fn ' + fn)


cases = json.load(open(os.path.join(CASES, 'prefetch_due_cases.json')))
for c in cases:
    try:
        run_case(c)
    except Exception as e:
        check(c['name'], False, f'{type(e).__name__}: {e}')

# ----------------------------------------------------------------------------- fixed checks
d = os.environ['JSA_FORMS_DIR']
sheet = {'name': 'prefetch-2026-11-07', 'summary': {'jobs': 10, 'ready_now': 2, 'ready_after': 7, 'questions': 2},
         'accept_derived': False, 'questions': [{'id': 'P1', 'question': 'Q one', 'answer': None},
                                                 {'id': 'P2', 'question': 'Q two', 'answer': None}]}
os.makedirs(d, exist_ok=True)
json.dump(sheet, open(os.path.join(d, 'questions.json'), 'w'))
s, ids = PD.status()
check('fixed: status waits', ids == ['P1', 'P2'], ids)
PD.mark('prefetch-2026-11-07', 'deferred', None)
check('fixed: handled after mark', PD.status()[1] == [], PD.status())
check('fixed: other sheet still waits', PD.pending(dict(sheet, name='prefetch-2026-11-08'), PD.load_handled()) == ['P1', 'P2'])
open(os.path.join(d, 'asked.jsonl'), 'a').write('not json\n{"x": 1}\n')
check('fixed: bad lines ignored', PD.load_handled() == {'prefetch-2026-11-07': None}, PD.load_handled())

# collect_batch --apply on a prefetch sheet with no answers: no qa_add call, sheet marked handled
d2 = os.path.join(TMP, 'forms2')
os.makedirs(d2)
json.dump(dict(sheet, name='prefetch-2026-11-09'), open(os.path.join(d2, 'questions.json'), 'w'))
r = subprocess.run([sys.executable, os.path.join(ROOT, 'skills', 'auto-apply', 'runner', 'collect_batch.py'), '--apply',
                    os.path.join(d2, 'questions.json'), '--source', 'test'], capture_output=True, text=True,
                   env=dict(os.environ, JSA_FORMS_DIR=d2))
check('fixed: collect_batch exit 0', r.returncode == 0, r.stderr[-400:])
check('fixed: collect_batch marked the sheet', 'prefetch-2026-11-09' in PD.load_handled(d2), PD.load_handled(d2))

print(f'prefetch_due: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) + fixed checks — fails {bad}')
sys.exit(1 if bad else 0)
