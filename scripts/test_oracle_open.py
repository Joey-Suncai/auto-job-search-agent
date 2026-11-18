#!/usr/bin/env python3
"""Harness for run_oracle.py open answers (JSA-298, rule 13): DeepSeek cases for open_drafts (ids written as
"ID(<label>)" — DeepSeek cannot hash — and replaced by open_id here), verdicts in test_cases/oracle_open_verdicts.json;
plus an offline mock of fill_section: a fake Oracle page with a required prose textarea, a folder with / without
open_answers.md → questions.json written, the draft filled and read back."""
import json, os, re, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import run_oracle as R  # noqa: E402


def ids(x):
    if isinstance(x, str):
        m = re.fullmatch(r'ID\((.*)\)', x, re.S)
        return R.open_id(m.group(1)) if m else x
    if isinstance(x, list):
        return [ids(v) for v in x]
    if isinstance(x, dict):
        return {ids(k): ids(v) for k, v in x.items()}
    return x


cases = json.load(open(os.path.join(HERE, 'test_cases', 'oracle_open_cases.json')))
vp = os.path.join(HERE, 'test_cases', 'oracle_open_verdicts.json')
verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
bad = 0
for c in cases:
    try:
        got = list(R.open_drafts(*ids(c['args'])))
        got[1] = [{k: v for k, v in q.items() if k != 'limit_from'} for q in got[1]]   # JSA-312 added limit_from (judged by test_oracle_limits)
    except Exception as e:
        got = f'ERROR {type(e).__name__}: {e}'
    if got != ids(c['expect']) and c['name'] not in verdicts:
        bad += 1; print('DISAGREE', c['name'], '| got', json.dumps(got)[:300], '| expect', json.dumps(ids(c['expect']))[:300])

# ---- offline mock of fill_section (no browser)
Q = "Would you please share some details about your future career aspirations? Anything you'd like the hiring review team to know when reviewing your candidacy? *"
DRAFT = 'My goal is to build analytics that people actually use to decide.'


class FakeOx:
    def __init__(self):
        self.vals = {'blk|Q|textarea|1': '', 'blk|Gpa|text|1': ''}
        self.page = type('P', (), {'keyboard': type('K', (), {'press': lambda *a: None})()})()

    def state(self):
        fs = [{'n': 0, 'key': 'blk|Q|textarea|1', 'block': 'blk', 'label': Q, 'required': True, 'kind': 'textarea', 'options': [],
               'value': self.vals['blk|Q|textarea|1'], 'type': 'textarea', 'maxlength': 1500, 'inputmode': ''},
              {'n': 1, 'key': 'blk|Gpa|text|1', 'block': 'blk', 'label': 'What is your current GPA?', 'required': True, 'kind': 'text',
               'options': [], 'value': self.vals['blk|Gpa|text|1'], 'type': 'text', 'maxlength': None, 'inputmode': ''}]
        return {'fields': fs, 'files': [], 'errors': []}

    def shown(self, key): return True

    def fill_text(self, key, value): self.vals[key] = value


R.time.sleep = lambda s: None
R.answer = lambda qs: {q['key']: ({'status': 'ok', 'value': 'N/A', 'rule': 'gpa_current'} if 'GPA' in q['label'] else {'status': 'unknown'}) for q in qs}
R.related_question = lambda *a: None


def mock(drafts_md):
    d = tempfile.mkdtemp()
    if drafts_md is not None:
        open(os.path.join(d, 'open_answers.md'), 'w').write(drafts_md)
    R.FOLDER = d
    ox = FakeOx()
    rows, problems, unknown, _ = R.fill_section(ox, {}, None, lambda m: None)
    qj = os.path.join(d, 'questions.json')
    return ox, rows, problems, unknown, (json.load(open(qj)) if os.path.exists(qj) else None)


checks = []
ox, rows, problems, unknown, qs = mock(None)                        # no draft: questions.json, needs-user, box empty
checks.append(('no draft → questions.json', qs and qs[0]['id'] == R.open_id(Q) and qs[0]['limit'] == 1500 and qs[0]['label'].endswith('candidacy?')))
checks.append(('no draft → problem + unknown', any('not drafted yet' in p for p in problems) and len(unknown) == 1 and ox.vals['blk|Q|textarea|1'] == ''))
ox, rows, problems, unknown, qs = mock(f'# Open answers\n\n## {R.open_id(Q)} — {R.clean_label(Q)}\nlimit: 1500 characters\n\n{DRAFT}\n')
r = next(x for x in rows if x['kind'] == 'textarea')
checks.append(('draft by id → filled, read back', ox.vals['blk|Q|textarea|1'] == DRAFT and r['ok'] and r['rule'] == 'open_answers' and not problems and not unknown and qs is None))
ox, rows, problems, unknown, qs = mock(f'# Open answers\n\n## vermorgal_q13 — {R.clean_label(Q)}\nlimit: 1500 characters · length: 66\n\n{DRAFT}\n')
checks.append(('draft under another id (VERMORGAL) → by label', ox.vals['blk|Q|textarea|1'] == DRAFT and not problems and not unknown))
ox, rows, problems, unknown, qs = mock(f'## {R.open_id(Q)} — {R.clean_label(Q)}\nASK\n')
checks.append(('ASK draft → still missing', ox.vals['blk|Q|textarea|1'] == '' and qs is not None and unknown))
checks.append(('GPA rule answer untouched', ox.vals['blk|Gpa|text|1'] == 'N/A'))
for name, ok in checks:
    if not ok:
        bad += 1; print('MOCK FAIL', name)
print(f'{len(cases)} cases + {len(checks)} mock checks · disagreements without a verdict: {bad}')
sys.exit(1 if bad else 0)
