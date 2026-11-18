"""The shared essay-box step (JSA-318): every runner that fills text boxes gets its prose answers one known way, and
skills/auto-apply/runner/essay_step.py does what the runners rely on.

1. Coverage. Every runner (skills/auto-apply/runner/run*.py) that touches a textarea either imports essay_step, or is
   listed in OTHER_PATH with the call that brings its drafts in. That call must still be in the file. A new runner with
   neither fails here. That is the miss this test exists for: SuccessFactors and iCIMS never read open_answers.md.
2. The Harwynpell replay (SF, 2026-11-11). The approved answer, filed under the page id '162:_txtArea', is filled into a box
   whose page id has moved. With no draft, the box goes to questions.json with the page's limit. A draft over that limit
   is sent back for a rewrite.
3. Rule answers win, cover-letter boxes are skipped, and Oracle's older 'label:' keys still match.

DeepSeek cases (rule 13) are not in this file yet: the DeepSeek balance was empty on 2026-11-11 (402). Add them as
test_cases/essay_step_cases.json once it is topped up.
"""
import json
import os
import re
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
RUNNER = os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner')
sys.path.insert(0, RUNNER)
import essay_step as ES  # noqa: E402

# runner → (the call that brings its prose drafts in, why it is not essay_step)
OTHER_PATH = {
    'run.py': ('plan_build', 'Greenhouse: prep_batch / plan_build put open_answers.md into plan.json before the run'),
    'run_form.py': ('plan_build', 'Ashby / Lever: prep_batch / plan_build put open_answers.md into plan.json before the run'),
    'run_wd.py': ('plan_build', 'Workday: plan_build.build reads open_answers.md by label'),
    'run_workable.py': ('apply_drafts(', 'Workable: apply_drafts by the stable schema field id'),
    'run_smartrecruiters.py': ('apply_drafts(', 'SmartRecruiters: W.apply_drafts by the stable field id'),
    'run_tiktok.py': (None, 'TikTok / ByteDance: dry run only; Joey reviews and submits every form himself'),
}

checks = []


def check(name, ok, info=''):
    checks.append((name, bool(ok)))
    print(('PASS  ' if ok else 'FAIL  ') + name + (f'  — {info}' if info and not ok else ''))


# 1. coverage
for fn in sorted(os.listdir(RUNNER)):
    if not re.fullmatch(r'run(_\w+)?\.py', fn):
        continue
    src = open(os.path.join(RUNNER, fn), encoding='utf-8').read()
    if 'textarea' not in src:
        continue
    if re.search(r'^import essay_step\b', src, re.M):
        check(f'coverage: {fn} uses essay_step', 'ES.step(' in src or 'ES.fill(' in src, 'imported but never called')
    elif fn in OTHER_PATH:
        token, why = OTHER_PATH[fn]
        check(f'coverage: {fn} — {why}', token is None or token in src, f'{token!r} no longer in the file')
    else:
        check(f'coverage: {fn} fills text boxes without the essay step', False,
              'import essay_step and call ES.step, or add it to OTHER_PATH with its own draft path')

# 2. the Harwynpell replay
Q = 'What interests you most about Machine Learning?'
A = 'What interests me most about machine learning is testing whether a model has really learned something.'
d = tempfile.mkdtemp()
open(os.path.join(d, 'open_answers.md'), 'w').write(f'# Open answers\n\n## 162:_txtArea — {Q}\n{A}\n')
ans, prob = ES.step([{'key': '171:_txtArea', 'label': Q + ' *', 'kind': 'textarea'}], {}, d, prefix='sf_')
check('Harwynpell: approved draft found by its question after the page id moved', (ans.get('171:_txtArea') or {}).get('value') == A and prob is None, repr(ans))
ans, _ = ES.step([{'key': '162:_txtArea', 'label': Q, 'kind': 'textarea'}], {}, d, prefix='sf_')
check('Harwynpell: draft found by the page id', (ans.get('162:_txtArea') or {}).get('value') == A)

d2 = tempfile.mkdtemp()
ans, prob = ES.step([{'key': '162:_txtArea', 'label': Q, 'kind': 'textarea', 'maxlength': 500}], {}, d2, prefix='sf_')
qs = json.load(open(os.path.join(d2, 'questions.json'))) if os.path.exists(os.path.join(d2, 'questions.json')) else []
check('no draft → questions.json with the page limit', qs and qs[0]['id'] == ES.prose_id(Q, 'sf_') and qs[0]['limit'] == 500
      and qs[0]['limit_from'] == 'the box' and prob and prob.startswith('not drafted yet'), repr(qs))
check('no draft → the box stays unanswered', '162:_txtArea' not in ans)

out, miss = ES.fill([{'key': 'k', 'label': Q, 'kind': 'textarea', 'maxlength': 40}], {}, {'label:' + ES.key_label(Q): A})
check('draft over the page limit → sent back for a rewrite', 'k' not in out and miss and miss[0].get('redraft') and miss[0]['limit'] == 40, repr(miss))

# 3. what the step leaves alone
rule = {'status': 'ok', 'value': 'University of Chicago', 'rule': 'school'}
out, miss = ES.fill([{'key': 'k', 'label': Q, 'kind': 'textarea'}], {'k': rule}, {'label:' + ES.key_label(Q): A})
check('a rule answer is never replaced', out['k'] == rule and not miss)
out, miss = ES.fill([{'key': 'cover_letter', 'label': 'Cover letter', 'kind': 'textarea'}], {}, {})
check('the cover-letter box is not an essay box', not miss and 'cover_letter' not in out)
out, miss = ES.fill([{'key': 'k', 'label': 'Comments', 'kind': 'textarea'}], {'k': {'status': 'unknown', 'leave': True}}, {})
check("a box left empty on purpose ('leave') stays empty", not miss)
out, miss = ES.fill([{'key': 'k', 'label': 'Phone', 'kind': 'text'}], {}, {})
check('a one-line text box is not an essay box', not miss)
out, _ = ES.fill([{'key': 'k', 'label': 'Why do you want this job?', 'kind': 'textarea'}], {}, {'label:why do you want this job?': 'Old key'})
check("Oracle's older 'label:' key still matches", (out.get('k') or {}).get('value') == 'Old key')
check('prose ids are stable and prefixed', ES.prose_id(Q + ' *', 'sf_') == ES.prose_id(Q, 'sf_') and ES.prose_id(Q, 'ic_').startswith('ic_'))

bad = [n for n, ok in checks if not ok]
print(f'{len(checks)} checks · failed: {len(bad)}')
sys.exit(1 if bad else 0)
