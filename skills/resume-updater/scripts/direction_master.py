#!/usr/bin/env python3
"""Direction master resume (JSA-250, ADR-0010): Claude writes one A-Classic resume per target direction from the
confirmed fact base and the role library; the script checks every sentence against the facts and lays it out.

    ~/.job-agent-venv/bin/python direction_master.py --direction ai_pm            # write + check + build
    ~/.job-agent-venv/bin/python direction_master.py --direction ai_pm --rebuild  # re-lay-out the saved master.json
    ... --summary yes|no     # answer the per-direction summary question (stored in config/profile.json → resume.summary)

Inputs : data home config/facts.json (facts), roles/<direction>.json (+ roles/directions.json), config/resume_content.py
         (contact, education, entry titles / dates), config/profile.json → resume.summary.<direction>.
Writer : Claude (claude-opus-5-5, Keychain jobagent-anthropic; Joey 2026-11-08 「模型的话用 Claude 写」), structured JSON.
Checks : every bullet cites fact ids of its own entry; every number in it is a CURRENT number of a cited fact (history
         numbers are not allowed in new text); no never-phrase of the entry or a cited fact; fact "pairs" ([a, b]: a
         needs b, e.g. "70%" needs "workflow"); skills only from facts.skills.true or a resume_ok fact's skills, never
         from skills.not_true; the summary's numbers from resume_ok facts; check_bullets.py (bullet formula, ≤ 5 per
         entry, varied verbs). One retry with the problems listed; still failing → exit 1, nothing built.
Layout : ds_materials.build_docx (A-Classic), spacing / font from loose to tight until one page with fill bottom
         730–756 and check_resume.py passing; under-filled → add the next reserve bullet; overflow → drop the bullet
         worth least to the direction (lowest competency weight; never an entry's first bullet).
Output : data home resume/<YYYY-MM>/master_<direction>.json · <Prefix>_Resume_<Direction>_Master_A-Classic.docx/.pdf ·
         master_<direction>.md (bullets with fact ids, keyword coverage vs. the current role version, changes).
The user approves the master once (decisions-log); approved bullets then go into bullet-bank.md with their fact ids.
Exit 0 built · 1 checks failed · 2 missing input · 4 a question for the user: the summary (--summary yes|no) or STAR
parts missing in the facts (--star-gaps lists them; a bullet whose cited facts lack S, T, A or R is never written —
Joey 2026-11-08: 「如果 star 法则里缺少任意一项，就问我」).
"""
import argparse
import copy
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SKILL))
ROLES = os.path.join(SKILL, 'roles')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import paths  # noqa: E402  (generated role library: data home first, JSA-377)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, 'config'))
import facts_check as FC  # noqa: E402
import check_bullets as CB  # noqa: E402
from role_library import matcher  # noqa: E402

MODEL = os.environ.get('JOBAGENT_MASTER_MODEL', 'claude-opus-5-5')
def is_core(i, b):
    """A bullet no JD tailoring or layout drop may remove: an entry's first (outcome first) or one the user marked
    core ("core": true — what the project is and what it achieved; Joey 2026-11-09 「一定要放的」)."""
    return i == 0 or bool(b.get('core'))


MAX_PER_ENTRY = {'jsa': 5, 'hp': 3, 'stock': 2, 'fs': 2, 'voice': 3}
SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['headline', 'summary', 'skills', 'entries', 'reserve', 'notes'],
    'properties': {
        'headline': {'type': 'string'},
        'summary': {'type': 'string'},
        'skills': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['label', 'items'],
                                              'properties': {'label': {'type': 'string'}, 'items': {'type': 'array', 'items': {'type': 'string'}}}}},
        'entries': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['entry_id', 'bullets'],
                    'properties': {'entry_id': {'type': 'string'},
                                   'bullets': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False,
                                               'required': ['text', 'fact_ids', 'competencies', 'bold'],
                                               'properties': {'text': {'type': 'string'},
                                                              'bold': {'type': 'array', 'items': {'type': 'string'}},
                                                              'fact_ids': {'type': 'array', 'items': {'type': 'string'}},
                                                              'competencies': {'type': 'array', 'items': {'type': 'string'}}}}}}}},
        'reserve': {'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['entry_id', 'text', 'fact_ids', 'bold'],
                    'properties': {'entry_id': {'type': 'string'}, 'text': {'type': 'string'},
                                   'bold': {'type': 'array', 'items': {'type': 'string'}},
                                   'fact_ids': {'type': 'array', 'items': {'type': 'string'}}}}},
        'notes': {'type': 'string'},
    },
}

SYSTEM = """You write one-page resumes for a candidate from a confirmed fact base. You are writing the candidate's
DIRECTION MASTER for one target direction: the version he approves once and later tailors per job.

Truth rules (hard — a sentence that breaks one is rejected by a checker and you will be asked to rewrite):
- Use only what the cited facts say. Every bullet lists the fact ids it rests on (ids of its own entry only).
- Every number you write must appear in a cited fact's current A / R / numbers exactly (formatting like 1,886 kept).
  Never use a number from a fact's history. Never round, add or combine numbers.
- Keep ownership exactly: respect each fact's "ownership", "must_keep" and "never" phrases. Team work stays team work
  ("led the code and analysis for a team of 3", "co-built with a consultant"). For the personal agent project
  the candidate designed, set rules and operates; Claude Code wrote the code — use "designed / set / specified /
  operate / runs", never "coded / wrote the code / built the scripts".
- A fact's "pairs" [a, b]: if your sentence contains a it must also contain b.
- Skills lines: only items from skills.true or from the skills of a resume_ok fact; never anything in skills.not_true.
  Do not list spoken languages. Group the lines by what they are (e.g. AI product practice, AI tools, product tools,
  analytics, data platforms) — a tool never goes under a wrong label.
- No visa or work-authorization words. No school name for the club (it is written as given). Banned words: {banned}.

Writing rules:
- Every bullet rests on complete STAR facts: each part must come from the cited facts' S / T / A / R — never invent a
  situation, task or result; if the cited facts lack one, cite another fact of the same entry that has it, or leave the
  bullet out (the checker rejects a bullet whose cited facts have no S, T, A or R).
- How a bullet reads (the candidate's rule, from a peer resume he liked):
  * with a number: WHAT was done (action verb + what + tool) + WHY (the purpose or situation, from S / T) + IMPACT (the
    number, and where the facts allow, what it led to);
  * without a number: the PROBLEM (from S) + HOW it was solved (A).
  * The bullet's FIRST WORD is an action verb (the peer resume: all bullets verb-first). Never open with a context
    phrase ("To …, ", "Because …, ", "When …, ", "Asked by …, "): the purpose goes after the action as " to …", the
    result at the end. Never a causal clause — no "because", "since", "due to" (Joey 2026-11-09): say the purpose
    (" to …", "so …") or let the result show why.
  * Vary the shape in the middle and the end, not the start — mix: verb … ", <result>ing …" participle clause
    ("…, cutting review time by 70%"); verb … " to <purpose>" … result; two actions joined by ";"; two actions joined
    by "and" then the result; a comparison with a baseline. No shape on more than 40 % of the bullets; at least 3
    shapes. No verb opens more than 2 bullets.
  * ≤ 220 characters per bullet.
- Bold 1–2 key terms per bullet in "bold": the tool, method or product term a recruiter scans for (a skill of a cited
  fact or one of the direction's JD words), written exactly as in the text; never a number or a filler word.
- Outcome first (the candidate's rule, 2026-11-09): the FIRST bullet of each entry states what the whole experience
  achieved — its overall result, quantified when the facts hold a number (scale, speed, quality, what it led to),
  chosen for the direction's highest-weight competency. The bullets after it each take one problem: what was wrong
  or needed (S / T), what was done about it (A), and the effect (R).
- Use the competency "angle" given for the direction to decide which part of a fact leads.
- Max bullets per entry: {max_per_entry}. Aim for about {target} bullets on the page in total, plus 2–3 reserve
  bullets (true, ranked) the layout may add if the page is short.
- Headline: follow the pattern, with the direction's title in place of the exact job title.
- Summary (only if asked): 2 sentences, ≤ 300 characters, built only from facts; no adjectives about personality.
- Return JSON matching the schema. "notes": one or two sentences on choices the reviewer should know."""


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def fact_skill_pool(fb):
    pool = {}
    for g, v in ((fb.get('skills') or {}).get('true') or {}).items():
        if g.lower() == 'languages':   # spoken languages stay off resumes (Joey 2026-11-08)
            continue
        for x in v:
            pool[x.lower()] = x
    for f in fb['facts']:
        if f.get('resume_ok', True) is not False:
            for x in f.get('skills') or []:
                pool.setdefault(x.lower(), x)
    return pool


def relevance(role, fb):
    """{fact id: [(competency id, weight)]} — the role competencies each fact's skills prove (for the prompt)."""
    out = {}
    for f in fb['facts']:
        hits = []
        for c in role['competencies']:
            if c['weight'] <= 0:
                continue
            for k in c['keywords']:
                sp = [k['term']] + k.get('synonyms', [])
                ms = [matcher(x) for x in sp]
                if any(any(m.search(s) for m in ms) or s.lower() in {x.lower() for x in sp} for s in f.get('skills') or []):
                    hits.append((c['id'], c['weight']))
                    break
        out[f['id']] = hits
    return out


def prompt(direction, role, dconf, fb, want_summary):
    rel = relevance(role, fb)
    keep = resume_entries(fb)
    ents = [e for e in fb['entries'] if e['id'] in keep]
    facts = [{k: f.get(k) for k in ('id', 'entry', 'S', 'T', 'A', 'R', 'numbers', 'skills', 'ownership', 'must_keep',
                                      'never', 'pairs')} | {'proves': [c for c, _ in rel.get(f['id'], [])]}
             for f in fb['facts'] if bullet_ok(f) and f['entry'] in keep]
    comps = [{'id': c['id'], 'label': c['label'], 'weight': c['weight'], 'jd_words': [k['term'] for k in c['keywords'][:6] if k['df'] > 0],
              'angle': c.get('angle', '')} for c in role['competencies'] if c['weight'] >= 0.03]
    return json.dumps({
        'direction': {'id': direction, 'title': role['label'], 'headline_pattern': role.get('headline_pattern'),
                      'section_order': role.get('section_order'), 'n_jds': role['n_jds'],
                      'competencies_by_weight': comps,
                      'top_jd_keywords': [k['term'] for k in role['top_keywords'][:20]]},
        'summary_wanted': bool(want_summary),
        'entries': [{'id': e['id'], 'kind': e['kind'], 'org': e['org'], 'role': e['role'], 'never': e.get('never', []),
                     'ownership': e.get('ownership', ''), 'note': e.get('note', '')} for e in ents],
        'facts': facts,
        'skills': {'true': fb['skills']['true'], 'not_true': fb['skills']['not_true']},
    }, ensure_ascii=False, indent=1)


def call_claude(user, system, history=None):
    sys.path.insert(0, os.path.join(REPO, 'scripts', 'daily'))
    from claude_reader import api_key
    import anthropic
    key = api_key()
    if not key:
        raise SystemExit('no Anthropic API key in the Keychain (service jobagent-anthropic)')
    client = anthropic.Anthropic(api_key=key, max_retries=3)
    msgs = (history or []) + [{'role': 'user', 'content': user}]
    r = client.beta.messages.create(
        model=MODEL, max_tokens=16000,
        betas=['server-side-fallback-2026-07-01'], fallbacks='default',
        output_config={'effort': 'high', 'format': {'type': 'json_schema', 'schema': SCHEMA}},
        system=system, messages=msgs)
    if r.stop_reason == 'refusal':
        raise SystemExit(f'Claude declined: {getattr(r.stop_details, "category", None)}')
    text = ''.join(b.text for b in r.content if b.type == 'text')
    usage = {'input': r.usage.input_tokens, 'output': r.usage.output_tokens}
    return json.loads(text), text, msgs, usage


STAR_PARTS = ('S', 'T', 'A', 'R')


def bullet_ok(f):
    return f.get('resume_ok', True) is not False and f.get('bullet_ok', True) is not False


def resume_entries(fb):
    """Entry ids that get bullets: on_resume, not education, and at least one fact that may be a bullet."""
    have = {f['entry'] for f in fb['facts'] if bullet_ok(f)}
    return {e['id'] for e in fb['entries'] if e.get('on_resume') and e['kind'] != 'education' and e['id'] in have}


def star_missing(facts):
    """STAR parts (S, T, A, R) that none of the given facts provides — the bullet cannot be written in STAR without
    inventing them (Joey 2026-11-08: 「如果 star 法则里缺少任意一项，就问我」)."""
    return [p for p in STAR_PARTS if not any(str(f.get(p) or '').strip() for f in facts)]


def star_gaps(fb, ids=None):
    """[(fact id, entry, [missing parts])] for resume facts (or the given ids) whose own S / T / A / R is incomplete —
    the questions to ask the user."""
    out = []
    edu = {e['id'] for e in fb['entries'] if e.get('kind') == 'education' or not e.get('on_resume')}   # not bullets
    for f in fb['facts']:
        if not bullet_ok(f) or f['entry'] in edu or (ids is not None and f['id'] not in ids):
            continue
        miss = [p for p in STAR_PARTS if not str(f.get(p) or '').strip()]
        if miss:
            out.append((f['id'], f['entry'], miss))
    return out


def check(m, fb, direction):
    """Problems (list of strings) for a master dict."""
    errs = []
    F = {f['id']: f for f in fb['facts']}
    E = {e['id']: e for e in fb['entries']}
    pool = fact_skill_pool(fb)
    not_true = {x.lower() for x in fb['skills']['not_true']}

    role_words = set()
    if direction:
        rp = paths.role_file(f'{direction}.json')
        if os.path.exists(rp):
            for c in load_json(rp)['competencies']:
                for k in c['keywords']:
                    role_words |= {x.lower() for x in [k['term']] + k.get('synonyms', [])}

    def bold_check(where, text, bold, ids):
        bold = bold or []
        if len(bold) > 2:
            errs.append(f'{where}: bold_too_many — {len(bold)} bold terms (max 2) — {text[:50]}')
        known = role_words | set(pool)
        for i in ids or []:
            if i in F:
                known |= {x.lower() for x in F[i].get('skills') or []}
        for t in bold:
            if not t or t not in text:
                errs.append(f'{where}: bold_missing — "{t}" is not written exactly in the bullet — {text[:50]}')
            elif re.search(r'\d', t) or t.lower() not in known:
                errs.append(f'{where}: bold_unknown — "{t}" is not a skill of a cited fact or a direction keyword — {text[:50]}')

    def sentence(where, text, ids, entry_id):
        if not ids:
            errs.append(f'{where}: no fact ids — {text[:60]}')
        cited = []
        for i in ids:
            f = F.get(i)
            if not f:
                errs.append(f'{where}: unknown fact id {i}')
            elif f['entry'] != entry_id:
                errs.append(f'{where}: fact {i} belongs to {f["entry"]}, not {entry_id}')
            elif f.get('resume_ok', True) is False:
                errs.append(f'{where}: fact {i} is kept off the resume')
            elif f.get('bullet_ok', True) is False:
                errs.append(f'{where}: fact {i} is not a resume bullet (bullet_ok false) — {text[:50]}')
            else:
                cited.append(f)
        now = set()   # numbers come from every cited fact that exists (a wrong-entry / off-resume id is reported above);
        for i in ids or []:   # no existing cited fact → every number in the sentence is unsupported
            if i in F:
                now |= FC._nums(F[i])
        for n in FC.numbers_in(text):
            if n not in now:
                errs.append(f'{where}: number {n} is not a current number of {[f["id"] for f in cited]} — {text[:60]}')
        if all(i in F for i in ids or []):   # no cited fact at all → every STAR part is missing
            miss = star_missing([F[i] for i in ids or []])
            if miss:
                errs.append(f'{where}: star_missing {",".join(miss)} — the cited facts {list(ids)} have no '
                            f'{"/".join(miss)}; ask the user, do not invent — {text[:50]}')
        for p in FC.never_hits(text, E[entry_id], cited):
            errs.append(f'{where}: never-phrase "{p}" — {text[:60]}')
        low = text.lower()
        for f in cited:
            for a, b in f.get('pairs') or []:
                if a.lower() in low and b.lower() not in low:
                    errs.append(f'{where}: "{a}" needs "{b}" in the same sentence (fact {f["id"]}) — {text[:60]}')

    allowed = resume_entries(fb)
    seen = set()
    for e in m.get('entries') or []:
        eid = e.get('entry_id')
        if eid not in allowed:
            errs.append(f'entry {eid}: not a resume entry')
            continue
        seen.add(eid)
        if len(e.get('bullets') or []) > MAX_PER_ENTRY.get(eid, 5):
            errs.append(f'entry {eid}: {len(e["bullets"])} bullets > {MAX_PER_ENTRY.get(eid, 5)}')
        for b in e.get('bullets') or []:
            sentence(f'{eid}', b['text'], b.get('fact_ids'), eid)
            bold_check(f'{eid}', b['text'], b.get('bold'), b.get('fact_ids'))
    for b in m.get('reserve') or []:
        if b.get('entry_id') in allowed:
            sentence(f'reserve {b["entry_id"]}', b['text'], b.get('fact_ids'), b['entry_id'])
            bold_check(f'reserve {b["entry_id"]}', b['text'], b.get('bold'), b.get('fact_ids'))
    missing = allowed - seen
    if missing:
        errs.append(f'entries missing: {sorted(missing)}')
    for s in m.get('skills') or []:
        for it in s.get('items') or []:
            if it.lower() in not_true:
                errs.append(f'skills: "{it}" is confirmed NOT used')
            elif it.lower() not in pool:
                errs.append(f'skills: "{it}" is not in skills.true or any fact\'s skills')
    summ = m.get('summary') or ''
    if summ:
        alln = set()
        for f in fb['facts']:
            if f.get('resume_ok', True) is not False:
                alln |= FC._nums(f)
        for n in FC.numbers_in(summ):
            if n not in alln:
                errs.append(f'summary: number {n} is not in any resume fact')
        nev = [p for e in fb['entries'] for p in e.get('never') or []] + [p for f in fb['facts'] for p in f.get('never') or []]
        for p in sorted(set(nev)):
            if re.search(r'(?<![a-z])' + re.escape(p.lower()) + r'(?![a-z])', summ.lower()):
                errs.append(f'summary: never-phrase "{p}"')
        if len(summ) > 320:
            errs.append(f'summary: {len(summ)} characters > 320')
    cm = {'entries': [{'name': e.get('entry_id'), 'bullets': e.get('bullets') or []} for e in m.get('entries') or []]}
    errs += CB.check_master(cm)
    for w in CB.BANNED:
        if re.search(rf'\b{re.escape(w)}\b', (summ + ' ' + (m.get('headline') or '')).lower()):
            errs.append(f'banned word in summary / headline: {w}')
    return errs


# ------------------------------------------------------------------------------------------------ layout
def role_dict(m, fb, C, order, cfg, extra=()):
    """ds_materials.build_docx role dict from a master; extra = reserve bullets added (index list)."""
    E = {e['id']: e for e in fb['entries']}
    base = C.ROLES.get('Product_Manager') or next(iter(C.ROLES.values()))
    meta = {}
    for j in base.get('exp', []):
        meta[j['org']] = dict(title=j['title'], date=j['date'])
    for p in base.get('projects', []):
        meta[p['title']] = dict(tag=p['tag'], date=p['date'])
    bl = {e['entry_id']: [dict(text=b['text'], bold=b.get('bold') or []) for b in e['bullets']] for e in m['entries']}
    for i in extra:
        r = m['reserve'][i]
        bl.setdefault(r['entry_id'], []).append(dict(text=r['text'], bold=r.get('bold') or []))
    exp, proj, lead = [], [], False   # False = no Leadership section
    for eid, bullets in bl.items():
        e = E[eid]
        mt = meta.get(e['org'], {})
        if e['kind'] == 'experience':
            exp.append(dict(org=e['org'], title=mt.get('title', e['role']), date=mt.get('date', e['dates']), bullets=bullets))
        elif e['kind'] == 'project':
            proj.append(dict(title=e['org'], tag=mt.get('tag', e['role']), date=mt.get('date', e['dates']), bullets=bullets,
                             url=e.get('url')))
        elif e['kind'] == 'leadership':
            lead = dict(org=C.LEAD['org'], title=C.LEAD['title'], date=C.LEAD['date'], bullets=bullets)
    sz, ba, sb = cfg
    return dict(skills=[(s['label'], ', '.join(s['items'])) for s in m['skills']], exp=exp, projects=proj, lead=lead,
                lead_short=False, summary=m.get('summary') or '', a_sz=sz, a_bullet_after=ba, a_section_before=sb)


CFGS = [(22, 40, 140), (22, 34, 120), (22, 28, 100), (21, 40, 140), (21, 34, 120), (21, 28, 100), (21, 22, 80)]


def layout(m, fb, out_docx, order, wt=None):
    """wt = {competency id: weight} of the direction (decides which bullet is dropped when the page is long)."""
    wt = wt or {}
    sys.path.insert(0, os.path.join(REPO, 'skills', 'auto-apply', 'scripts'))
    import ds_materials as D
    D.BUDGET = 10 ** 9
    tp = D.Tpl()
    tmp = tempfile.mkdtemp(prefix='master_')
    extra, dropped, log = [], [], []
    last_check = ''
    mm = copy.deepcopy(m)
    for _ in range(8):
        under = over = False
        for cfg in CFGS:
            r = role_dict(mm, fb, D.C, order, cfg, extra)
            docx = os.path.join(tmp, os.path.basename(out_docx))
            D.build_docx(tp, r, mm['headline'], order, docx)
            pdf = D.to_pdf(docx, tmp)
            n = D.pages_of(pdf)
            top, bot = D.fill_bottom(pdf) if n == 1 else (0, 9999)
            log.append((cfg, len(extra), n, bot))
            if n == 1 and bot < 730:
                under = True
                break
            if n == 1 and 730 <= bot <= 756:
                cp = subprocess.run([sys.executable, os.path.join(HERE, 'check_resume.py'), docx], capture_output=True, text=True)
                if cp.returncode == 0:
                    return dict(docx=docx, pdf=pdf, cfg=cfg, top=top, bottom=bot, extra=extra, dropped=dropped, master=mm, log=log,
                                check=cp.stdout), None
                last_check = ' | '.join(l.strip() for l in cp.stdout.splitlines() if '✗' in l)
                continue   # e.g. a one-word last line at this font / spacing: the next setting may wrap differently
        else:
            over = not last_check
        if last_check and not under and not over:
            return None, 'check_resume failed at every setting that fits: ' + last_check
        if under:
            nxt = len(extra)
            if nxt >= len(mm.get('reserve') or []):
                return None, f'page under-filled (bottom {bot}) and no reserve bullet left'
            extra.append(nxt)
        elif over:
            # drop the bullet worth least to this direction: lowest best competency weight among the bullets that are
            # not core (an entry's first, or marked core); ties → the longer entry, then the later bullet
            cand = [(max([wt.get(c, 0) for c in b.get('competencies') or []] or [0]), -len(e['bullets']), -i, e, i)
                    for e in mm['entries'] for i, b in enumerate(e['bullets']) if not is_core(i, b)]
            if not cand:
                return None, 'does not fit on one page'
            _, _, _, e, i = min(cand, key=lambda x: x[:3])
            dropped.append(e['bullets'].pop(i)['text'])
    return None, 'layout did not settle: ' + '; '.join(map(str, log[-4:]))


# ------------------------------------------------------------------------------------------------ report
def coverage(text, role):
    hit = []
    for k in role['top_keywords']:
        c = next(c for c in role['competencies'] if c['id'] == k['competency'])
        kw = next(x for x in c['keywords'] if x['term'] == k['term'])
        if any(matcher(s).search(text) for s in [kw['term']] + kw.get('synonyms', [])):
            hit.append(k['term'])
    return hit


def master_text(m, extra=()):
    parts = [m.get('headline', ''), m.get('summary', '')]
    parts += [', '.join(s['items']) for s in m.get('skills') or []]
    parts += [b['text'] for e in m.get('entries') or [] for b in e['bullets']]
    parts += [m['reserve'][i]['text'] for i in extra]
    return '\n'.join(parts)


def old_text(C, key='Product_Manager'):
    r = C.ROLES[key]
    parts = [x for _, x in r['skills'] + r.get('skills_a', [])]
    parts += [b for j in r['exp'] for b in j['bullets']] + [b for p in r['projects'] for b in p['bullets']]
    return '\n'.join(parts)


def report(direction, role, res, fb, C, usage, retries):
    m = res['master']
    new_hit = coverage(master_text(m, res['extra']), role)
    old_hit = coverage(old_text(C), role)
    top = [k['term'] for k in role['top_keywords']]
    L = [f"# Direction master — {role['label']}", '',
         f"Built {datetime.date.today().isoformat()} by {MODEL} from config/facts.json and roles/{direction}.json "
         f"({role['n_jds']} JDs). Layout: font {res['cfg'][0] / 2} pt, bullet spacing {res['cfg'][1]}, section {res['cfg'][2]}, "
         f"bottom {res['bottom']}. Tokens: in {usage['input']}, out {usage['output']} (0 = written in a session from the same prompt, --draft); checker retries {retries}.", '',
         f"**Headline:** {m['headline']}", '']
    if m.get('summary'):
        L += [f"**Summary:** {m['summary']}", '']
    L += ['**Skills**', ''] + [f"- {s['label']}: {', '.join(s['items'])}" for s in m['skills']] + ['']
    E = {e['id']: e for e in fb['entries']}
    for e in m['entries']:
        L += [f"**{E[e['entry_id']]['org']}**", '']
        for b in e['bullets']:
            L.append(f"- {b['text']}  \n  *facts: {', '.join(b['fact_ids'])} · proves: {', '.join(b['competencies'])} · "
                     f"bold: {', '.join(b.get('bold') or []) or '—'} · shape: {CB.shape(b['text'])}*")
        for i in res['extra']:
            r = m['reserve'][i]
            if r['entry_id'] == e['entry_id']:
                L.append(f"- {r['text']}  \n  *facts: {', '.join(r['fact_ids'])} · added to fill the page*")
        L.append('')
    if res['dropped']:
        L += ['**Dropped to fit one page:** ' + ' / '.join(res['dropped']), '']
    L += ['## Keyword coverage vs. the current Product Manager version', '',
          f"Top {len(top)} keywords of {role['n_jds']} {role['label']} JDs (the role library):", '',
          f"- New master: **{len(new_hit)} / {len(top)}** — {', '.join(new_hit)}",
          f"- Current PM version: **{len(old_hit)} / {len(top)}** — {', '.join(old_hit)}",
          f"- Gained: {', '.join(x for x in new_hit if x not in old_hit) or '—'}",
          f"- Lost: {', '.join(x for x in old_hit if x not in new_hit) or '—'}", '']
    if m.get('notes'):
        L += [f"**Writer's notes:** {m['notes']}", '']
    L += ['*Every sentence traces to the fact ids shown; the checker verified numbers, ownership and never-phrases. '
          'Approve once → the bullets go into bullet-bank.md with their fact ids.*', '']
    return '\n'.join(L), new_hit, old_hit


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--direction', required=True)
    ap.add_argument('--summary', choices=['yes', 'no'])
    ap.add_argument('--rebuild', action='store_true', help='lay out the saved master_<direction>.json again (no Claude call)')
    ap.add_argument('--draft', help='a master JSON written outside the API (e.g. by Claude in a session when the API key has '
                                    'no credit); it gets the same checks and layout')
    ap.add_argument('--prompt-out', help='write the writer prompt (system + user) to this file and stop')
    ap.add_argument('--core', help='mark core bullets in the saved master, e.g. "jsa:0,1,2,4" (0-based; the rest of the '
                                   'entry\'s bullets lose the mark), then lay it out again like --rebuild')
    ap.add_argument('--star-gaps', action='store_true', help='list resume facts missing S / T / A / R (questions for the user) and stop')
    a = ap.parse_args(argv)
    import paths
    import content as C
    rp = paths.role_file(f'{a.direction}.json')
    if not os.path.exists(rp):
        print(f'no {rp} — run role_library.py --direction {a.direction}')
        return 2
    role = load_json(rp)
    dconf = load_json(os.path.join(ROLES, 'directions.json'))['directions'].get(a.direction, {})
    fb = load_json(paths.config('facts.json'))
    prof_p = paths.config('profile.json')
    prof = load_json(prof_p)
    summ = ((prof.get('resume') or {}).get('summary') or {}).get(a.direction)
    if a.summary:
        summ = a.summary == 'yes'
        prof.setdefault('resume', {}).setdefault('summary', {})[a.direction] = summ
        json.dump(prof, open(prof_p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    if summ is None:
        print(f'ask the user: a 2-line summary at the top of the {role["label"]} master? then rerun with --summary yes|no')
        return 4
    if a.star_gaps:
        gaps = star_gaps(fb)
        for fid, ent, miss in gaps:
            print(f'{fid:18} ({ent}) missing {", ".join(miss)}')
        print(f'star gaps: {len(gaps)} fact(s) — ask the user for the missing parts, then add them to config/facts.json')
        return 4 if gaps else 0
    month = datetime.date.today().strftime('%Y-%m')
    out_dir = paths.resume(month)
    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, f'master_{a.direction}.json')
    usage, retries = {'input': 0, 'output': 0}, 0
    if a.prompt_out:
        system = SYSTEM.format(banned=', '.join(CB.BANNED), max_per_entry=json.dumps(MAX_PER_ENTRY), target=16 if summ else 17)
        open(a.prompt_out, 'w', encoding='utf-8').write(system + '\n\n=== USER ===\n' + prompt(a.direction, role, dconf, fb, summ)
                                                        + '\n\n=== SCHEMA ===\n' + json.dumps(SCHEMA))
        print(f'prompt → {a.prompt_out}')
        return 0
    if a.core:
        m = load_json(jpath)['master']
        for part in a.core.split(';'):
            eid, idx = part.split(':')
            e = next(e for e in m['entries'] if e['entry_id'] == eid.strip())
            keep = {int(x) for x in idx.split(',') if x.strip()}
            for i, b in enumerate(e['bullets']):
                if i in keep:
                    b['core'] = True
                else:
                    b.pop('core', None)
        errs = check(m, fb, a.direction)
        if errs:
            print('\n'.join(errs))
            return 1
    elif a.rebuild:
        m = load_json(jpath)['master']
    elif a.draft:
        m = load_json(a.draft)
        m = m.get('master', m)
        if not summ:
            m['summary'] = ''
        errs = check(m, fb, a.direction)
        if errs:
            print('\n'.join(errs))
            if all('star_missing' in e for e in errs):
                print('direction_master: STAR parts missing in the facts — ask the user (exit 4)')
                return 4
            print(f'direction_master: draft failed the checks ({len(errs)})')
            return 1
        usage = {'input': 0, 'output': 0}
    else:
        system = SYSTEM.format(banned=', '.join(CB.BANNED), max_per_entry=json.dumps(MAX_PER_ENTRY),
                               target=16 if summ else 17)
        user = prompt(a.direction, role, dconf, fb, summ)
        t0 = time.time()
        m, raw, msgs, u = call_claude(user, system)
        usage = {k: usage[k] + u[k] for k in usage}
        if not summ:
            m['summary'] = ''
        errs = check(m, fb, a.direction)
        if errs and all('star_missing' in e for e in errs):
            print('\n'.join(errs))
            print('direction_master: STAR parts missing in the facts — ask the user (exit 4)')
            return 4
        if errs:
            retries = 1
            fix = ('The checker rejected these points. Rewrite the whole JSON so none of them remain, changing nothing '
                   'else that passed:\n- ' + '\n- '.join(errs))
            m, raw, msgs, u = call_claude(fix, system, msgs + [{'role': 'assistant', 'content': raw}])
            usage = {k: usage[k] + u[k] for k in usage}
            if not summ:
                m['summary'] = ''
            errs = check(m, fb, a.direction)
        print(f'claude: {time.time() - t0:.0f}s, tokens in {usage["input"]} out {usage["output"]}, retries {retries}')
        if errs:
            json.dump({'master': m, 'errors': errs}, open(jpath + '.rejected', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            print('\n'.join(errs))
            print(f'direction_master: checks failed ({len(errs)}); draft saved to {jpath}.rejected')
            return 1
    so = role.get('section_order') or []
    order = ['projects', 'exp'] if ('Projects' in so and 'Experience' in so and so.index('Projects') < so.index('Experience')) else ['exp', 'projects']
    prefix = getattr(C, 'FILE_PREFIX', 'Candidate')
    name = f"{prefix}_Resume_{a.direction.upper().replace('_', '-')}_Master_A-Classic"
    res, err = layout(m, fb, os.path.join(out_dir, name + '.docx'), order, {c['id']: c['weight'] for c in role['competencies']})
    if err:
        json.dump({'master': m, 'layout_error': err}, open(jpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'direction_master: layout failed — {err}')
        return 1
    import shutil
    shutil.copy(res['docx'], os.path.join(out_dir, name + '.docx'))
    shutil.copy(res['pdf'], os.path.join(out_dir, name + '.pdf'))
    md, new_hit, old_hit = report(a.direction, role, res, fb, C, usage, retries)
    open(os.path.join(out_dir, f'master_{a.direction}.md'), 'w', encoding='utf-8').write(md)
    json.dump({'master': res['master'], 'extra': res['extra'], 'dropped': res['dropped'], 'cfg': res['cfg'],
               'bottom': res['bottom'], 'model': MODEL, 'built': datetime.date.today().isoformat(),
               'approved': None}, open(jpath, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'direction_master: {a.direction} built → {os.path.join(out_dir, name + ".pdf")} · bottom {res["bottom"]} · '
          f'keywords {len(new_hit)} (current PM version {len(old_hit)}) of {len(role["top_keywords"])}')
    try:   # JSA-252: the simulated recruiter's scores (advice only) land next to the draft, so Joey sees them when he approves
        import recruiter_review
        recruiter_review.run_direction(a.direction)
    except Exception as e:
        print(f'direction_master: recruiter review skipped — {type(e).__name__}: {str(e)[:100]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
