"""The shared essay-box step for every runner (JSA-318).

A prose box (a textarea no rule answers: "What interests you most about Machine Learning?", "Why this company?") is never
written by a runner. ds_materials.py drafts it into <folder>/open_answers.md ('## <id> — <label>' + the answer, Joey's
approved text), and the runner fills it from there. A box with no draft yet goes into <folder>/questions.json, with the
page's own limit, so that ds_materials can write it.

JSA-298 built this path inside run_oracle.py (and Workable / SmartRecruiters had their own by field id). The
SuccessFactors and iCIMS runners never had it. an employer (SF, 2026-11-11) stopped at 49/50 with Joey's approved ML answer
sitting unread in open_answers.md. So the step lives here now, and `scripts/test_essay_step.py` checks that every runner
filling text boxes either calls it or is listed there with the reason it gets its essays another way.

fields = [{'key', 'label', 'kind' | 'type', 'maxlength'?, 'minlength'?, 'limits'?}]. Pure functions apart from
read_drafts / write_questions (files).
"""
import hashlib
import os
import re

import field_limits as FL
import run_workable as W

GUESS_LIMIT = 1500                     # no limit known from the page: ds_materials' default
FIXED_BOXES = ('cover_letter', 'summary')


def key_label(label):
    """A label as a lookup key (case, punctuation, the required '*' and spacing ignored)."""
    return FL.norm_prompt(label)


def prose_id(label, prefix='eq_'):
    """Pure (tested). A stable id for a prose question: prefix + 8 hex of its key_label. Page ids shift on some
    platforms (Oracle data-ox numbers, SF '162:_txtArea'); the label does not."""
    return prefix + hashlib.sha1(key_label(label).encode('utf-8')).hexdigest()[:8]


def read_drafts(folder):
    """Pure-ish (tested). <folder>/open_answers.md → {id: answer}, each answer also under 'label:' + its heading's
    key_label. A draft written under another id (an employer 11-11: 'mapei_q13'; an employer 11-11: the page id '162:_txtArea')
    is still found by its question."""
    by_id = W.read_open_answers(folder)
    out = dict(by_id)
    p = os.path.join(folder or '', 'open_answers.md')
    if by_id and os.path.exists(p):
        for m in re.finditer(r'^## (\S+) — (.+)$', open(p, encoding='utf-8').read(), re.M):
            if m.group(1) in by_id:
                out['label:' + key_label(m.group(2))] = by_id[m.group(1)]
    return out


def is_prose(f, answer=None):
    """Pure (tested). A box this step fills: a textarea (never the fixed cover-letter / summary boxes) that no rule
    answered and that is not deliberately left empty ('leave'). A rule answer always wins (status ok)."""
    kind = f.get('kind') or f.get('type')
    if f.get('key') in FIXED_BOXES or kind != 'textarea':
        return False
    a = answer or {}
    return a.get('status') != 'ok' and not a.get('leave')


def fill(fields, ans, drafts, prefix='eq_', id_of=None, clean=None):
    """Pure (tested). Each prose box (is_prose) gets its open_answers.md draft, found by its prose id, then its page key,
    then its label. Returns (answers, missing). missing = [{id, label, limit, min?, limit_from, redraft?}] for
    questions.json: the limit is the page's (maxlength, minlength, `limits` from the platform data), else GUESS_LIMIT
    with limit_from 'guess'. A draft that breaks the page's limit (an employer 11-11: 1086 characters in a 200-character box)
    is not used. It goes back to missing with the real limit, so ds_materials writes it again. A rule answer is never
    replaced. `clean` = the platform's own label cleaner, applied before the label is used; `id_of` = the platform's id
    function (Oracle keeps its 'oq_' ids so the drafts already on disk still match)."""
    clean = clean or (lambda s: re.sub(r'\s+', ' ', str(s or '')).strip())
    id_of = id_of or (lambda lab: prose_id(lab, prefix))
    out, missing = dict(ans), []
    for f in fields:
        a = out.get(f['key']) or {}
        if not is_prose(f, a):
            continue
        lab = clean(f.get('label'))
        lim = FL.merge({'max': f.get('maxlength'), 'min': f.get('minlength'), 'source': 'the box'}
                       if (f.get('maxlength') or f.get('minlength')) else None, f.get('limits'))
        oid = id_of(lab)
        d = (drafts.get(oid) or drafts.get(str(f['key'])) or drafts.get('label:' + key_label(lab))
             or drafts.get('label:' + lab.lower()))                # Oracle's older 'label:' keys (cleaned label, lower case)
        q = {'id': oid, 'label': lab, 'limit': lim['max'] or GUESS_LIMIT, 'limit_from': lim['source'] or 'guess'}
        if lim['min']:
            q['min'] = lim['min']
        cap = dict(lim, max=lim['max'] or GUESS_LIMIT)          # no page limit: the fallback cap ds_materials was given
        bad = FL.check(d, cap) if d else None
        if d and not bad:
            out[f['key']] = {'status': 'ok', 'label': f.get('label'), 'rule': 'open_answers', 'value': d}
        else:
            if bad:
                q['redraft'] = FL.why(bad, d, cap)
            missing.append(q)
    return out, missing


def problem(missing, folder):
    """Pure (tested). The one problem line for the run log / result when prose boxes still wait for a draft."""
    names = ' | '.join(q['label'][:70] + (f" (draft breaks the page's limit: {q['redraft']})" if q.get('redraft') else '') for q in missing)
    if folder:
        return f'not drafted yet: {names} — questions.json written (limits from the page); run scripts/ds_materials.py on the folder, then rerun'
    return f'prose boxes need an application folder (open_answers.md): {names}'


def step(fields, ans, folder, prefix='eq_', id_of=None, clean=None):
    """The whole step for a runner: drafts in, missing questions out to questions.json. Returns (answers, problem|None)."""
    out, missing = fill(fields, ans, read_drafts(folder) if folder else {}, prefix, id_of, clean)
    if not missing:
        return out, None
    if folder:
        W.write_questions(folder, missing)
    return out, problem(missing, folder)
