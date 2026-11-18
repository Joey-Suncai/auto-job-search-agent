#!/usr/bin/env python3
"""JSA-245 (rule 13): DeepSeek-written cases from scripts/test_cases/audit_sample_spec.md (audit_sample_cases.json,
verdicts in audit_sample_verdicts.json) for the independent audit's pure parts; plus fixed checks: judge() writes the
judgment and a confirmed wrong answer into wrong_answers.jsonl; platform_scorecard.audit_rows; session_mode.audit_note.
Offline, temp folders only.   python3 scripts/test_audit_sample.py"""
import json, os, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp(prefix='jsa_audit_')
os.environ['JSA_HOME'] = TMP
os.environ['JSA_AUDIT_DIR'] = os.path.join(TMP, 'audit')
sys.path.insert(0, HERE)
import audit_sample as A  # noqa: E402
import ops_session as SM  # noqa: E402  (ADR-0011 step 5: the using session's start note; audit_rows is tested in the dev repo)

PROF = {"name": {"first": "Alex", "last": "Rivera", "full": "Alex Rivera", "preferred": "Al", "signature": "Alex (Al) Rivera"},
        "contact": {"email": "alex@example.com", "secondary_email": "a.r@example.org", "phone": "312-555-0142",
                    "linkedin": "linkedin.com/in/alexrivera", "website": "github.com/alexr"},
        "answers": {"has_preferred": {"yes": True}, "phone_device": {"text": "Mobile"}, "city": {"text": "Chicago"},
                    "state": {"text": "Illinois", "pick": ["/^illinois$/i", "/^il$/i"]}, "zip": {"text": "60601"},
                    "country": {"text": "United States", "pick": ["/^united states( of america)?$/i"]},
                    "address": {"text": "1200 S Sample Ave"}, "permanent_address": {"text": "12 Calle Sol, Madrid"},
                    "county": {"text": "Cook"}, "gender": {"pick": ["/^male$/i", "/^man$/i"], "text": "Male"},
                    "race": {"pick": ["/asian/i"], "text": "Asian"},
                    "hispanic": {"yes": False, "text": "No", "pick": ["/^no\\b/i", "/^(i am )?not hispanic/i"]},
                    "veteran": {"pick": ["/^i am not a (protected )?veteran/i"]},
                    "disability": {"pick": ["/^no,? i do(n't| not) have a disability/i"]}, "transgender": {"yes": False},
                    "orientation": {"pick": ["/heterosexual|straight/i"], "text": "Heterosexual"},
                    "pronouns": {"pick": ["/he\\s*\\/\\s*him/i"], "text": "He/Him"}}}

CASES = os.path.join(HERE, 'test_cases')
vp = os.path.join(CASES, 'audit_sample_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0


def check(name, ok, *info):
    global bad
    if not ok and name not in verdicts:
        bad += 1
        print('FAIL', name, *info)


def close(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(close(a[k], b[k]) for k in a)
    if isinstance(a, float) or isinstance(b, float):
        return a is not None and b is not None and abs(a - b) < 0.0006
    return a == b


cases = json.load(open(os.path.join(CASES, 'audit_sample_cases.json')))
for c in cases:
    n, fn, g = c['name'], c['fn'], c.get('args') or {}
    try:
        if fn == 'submitted_by_platform':
            got = A.submitted_by_platform(g['results'], lambda r: r.get('ats') or 'other')
            check(n, got == c['expect'], got)
        elif fn == 'sample':
            got = A.sample(g['folders'], g.get('audited'), g['n'], g['seed'])
            pool = set(g['folders']) - set(g.get('audited') or ())
            ok = got == sorted(set(got)) and set(got) <= pool and len(got) == c.get('expect_len', len(got))
            check(n, ok, got)
        elif fn == 'answers_of':
            # the spec names the output but not the corpus line fields: a case's line "answer" is the read-back "page"
            lines = [dict(l, page=l['answer']) if 'answer' in l and 'page' not in l and 'planned' not in l else l for l in g['lines']]
            got = A.answers_of(lines, g['folder'])
            exp = c['expect']
            ok = [{k: x.get(k) for k in ('question', 'answer', 'options', 'type', 'at')} for x in got] == \
                 [{k: (x.get(k) if k != 'options' else x.get(k) or []) for k in ('question', 'answer', 'options', 'type', 'at')} for x in exp]
            check(n, ok, json.dumps(got)[:400])
        elif fn == 'norm_answer':
            got = A.norm_answer(g['a'])
            check(n, got == c['expect'], repr(got))
        elif fn == 'contact_check':
            got = A.contact_check(g['question'], g['answer'], PROF)
            check(n, got == c['expect'], got)
        elif fn == 'eeo_key':
            got = A.eeo_key(g['q'], g['a'])
            check(n, got == c['expect'], got)
        elif fn == 'eeo_check':
            got = A.eeo_check(g['question'], g['answer'], PROF)
            check(n, got == c['expect'], got)
        elif fn == 'date_check':
            got = A.date_check(g['question'], g['answer'], g['at'])
            check(n, got == c['expect'], got)
        elif fn == 'summary':
            got = A.summary(g['items'])
            check(n, close(got, c['expect']), json.dumps(got)[:400])
        else:
            check(n, False, 'unknown fn ' + fn)
    except Exception as e:
        check(n, False, f'{type(e).__name__}: {e}')

# ----------------------------------------------------------------------------- fixed checks
d = os.environ['JSA_AUDIT_DIR']
os.makedirs(d)
os.makedirs(os.path.join(TMP, 'data', 'runner'), exist_ok=True)
it = {'key': 'k1', 'platform': 'greenhouse', 'folder': '2026-11-01_X', 'question': 'Consent: marketing', 'answer': 'Yes',
      'check': 'wrong', 'judged': None, 'cls': 'non-critical'}
open(os.path.join(d, 'items.jsonl'), 'w').write(json.dumps(it) + '\n')
check('fixed: pending lists it', [x['key'] for x in A.pending_items()] == ['k1'])
A.judge('k1', 'wrong', 'his rule: marketing opt-in No')
items = A.jsonl(os.path.join(d, 'items.jsonl'))
check('fixed: judged wrong', items[0]['judged'] == 'wrong' and A.pending_items() == [], items)
wa = A.jsonl(A.jpaths.data('runner', 'wrong_answers.jsonl'))
check('fixed: wrong_answers line', len(wa) == 1 and wa[0]['folder'] == '2026-11-01_X' and wa[0]['class'] == 'non-critical', wa)
check('fixed: unknown key', A.judge('nope', 'right', '') == 1)
A.judge('k1', 'wrong', 'again')                       # judging wrong twice never adds a second line
check('fixed: no duplicate line', len(A.jsonl(A.jpaths.data('runner', 'wrong_answers.jsonl'))) == 1)
open(A.jpaths.data('runner', 'wrong_answers.jsonl'), 'a').write(json.dumps({'folder': '2026-11-01_X', 'field': 'Consent: marketing', 'note': 'found by the replay'}) + '\n')
A.judge('k1', 'right', 'Joey: his rule allows it')   # reversal withdraws only the audit's own line
wa = A.jsonl(A.jpaths.data('runner', 'wrong_answers.jsonl'))
check('fixed: reversal withdraws the audit line only', len(wa) == 1 and wa[0]['note'] == 'found by the replay', wa)
check('fixed: audit note', SM.audit_note('using', 3).startswith('AUDIT (JSA-245): 3') and SM.audit_note('release', 3) == ''
      and SM.audit_note('using', 0) == '')

print(f'audit_sample: {len(cases)} DeepSeek cases ({len(verdicts)} verdicts) + fixed checks — fails {bad}')
sys.exit(1 if bad else 0)
