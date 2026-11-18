#!/usr/bin/env python3
"""learn triage (JSA-400, design learn-model-triage.md approved by Joey 2026-11-17): DeepSeek decides each problem candidate's CATEGORY and
which candidates are the same problem. The model only classifies — it never changes an answer, a rule, a saved answer or a fact, and it is
never sent a fact's content (only whether a fact / rule / saved answer for the question exists, by key name).

  fact    answering needs a fact of Joey's that the fact library lacks → the morning question sheet asks him
  rule    the fact exists but the rules did not answer or answered wrong → a developer row
  qtype   the rules took the question for another type (a country list read as citizen_pr) → a developer row (JSA-361 class)
  page    question / options not read completely, read-back differs, a special control → a developer row (platform runner / ats skill)
  runner  timeout, a click that failed, a stuck flow → a developer row
  ignore  voluntary, may be declined, a fixed way to answer exists, or one-off noise → counted on the card, not listed
  unsure  the program's own bucket: bad JSON, evidence not in the material, a 'fact' the second read did not confirm

Honesty guards (pure, tested): validate_item (evidence must be quoted from the material), combine_reads (a 'fact' needs two agreeing reads),
merge_groups (the model's grouping claims → groups), trial_folder (dry runs and folders that are not applications never count).
"""
import hashlib, json, os, random, re, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
CATEGORIES = ('fact', 'rule', 'qtype', 'page', 'runner', 'ignore')
BATCH = 10


def trial_folder(name, existing=None):
    """Pure (tested). A trial / test folder or one that is not an application: never evidence."""
    n = str(name or '').strip()
    if not n or n.startswith(('dry_', 'test_')) or n == 'out':
        return True
    return existing is not None and n not in existing


def _squash(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip().lower()


def validate_item(item, material_text, ids):
    """Pure (tested). The model's answer for one candidate, made honest: a bad category or evidence that is not in the material → 'unsure'."""
    if not isinstance(item, dict):
        return {'category': 'unsure', 'group_with': [], 'evidence': '', 'confidence': 'low', 'reason': 'not an object'}
    cat, ev = item.get('category'), str(item.get('evidence') or '').strip()
    gw = item.get('group_with'); own = item.get('id')
    out_gw = []
    for g in gw if isinstance(gw, list) else []:
        if g in ids and g != own and g not in out_gw: out_gw.append(g)
    conf = item.get('confidence') if item.get('confidence') in ('high', 'medium', 'low') else 'low'
    res = {'category': cat, 'group_with': out_gw, 'evidence': ev, 'confidence': conf, 'reason': ''}
    if cat not in CATEGORIES:
        res.update(category='unsure', reason='bad category')
    elif (len(ev) < MIN_EVIDENCE and _squash(ev) != _squash(material_text)) or _squash(ev) not in _squash(material_text):   # a short quote counts only when it IS the whole text (a question like "Extra")
        res.update(category='unsure', reason='evidence not in the material')
    return res


def combine_reads(first, second):
    """Pure (tested). A 'fact' needs two agreeing reads; every other first read stands."""
    if first != 'fact': return first
    return 'fact' if second == 'fact' else 'unsure'


def merge_groups(items):
    """Pure (tested). The model's grouping claims → sorted groups of ids (links in either direction, transitive)."""
    ids = list(dict.fromkeys(i['id'] for i in items))     # a candidate named twice is one candidate
    parent = {i: i for i in ids}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    for it in items:
        for g in it.get('group_with') or []:
            if g in parent and g != it['id']:
                parent[find(g)] = find(it['id'])
    groups = {}
    for i in ids: groups.setdefault(find(i), []).append(i)
    return sorted((sorted(g) for g in groups.values()), key=lambda g: g[0])


# ---------------------------------------------------------------- the model call (not pure; the tests use a fake `ask`)
SYSTEM = """You sort problems found while an agent fills in job application forms for ONE candidate. You get {"profile_fact_keys": [...names of the fact
library's entries — no contents...], "candidates": [...]}; each candidate has an "id", "found_by" (how the problem was found) and its material.
Decide for each candidate:
category — exactly one of:
  fact    a REAL personal question about the candidate whose answer needs a fact that is NOT in the fact library (no matching profile_fact_keys entry,
          fact_library "none") — the agent must ask him. Only when found_by says the rules left it unanswered. Never for conditional follow-ups.
  rule    the fact EXISTS (a profile_fact_keys entry covers it: name, contact, address / city / state, school, degree, major, GPA, graduation, high school,
          employers, work authorization / visa / sponsorship, dates, saved answers) but the rules left the question empty or answered it wrong / in the wrong format
  qtype   the rules took the question for another TYPE of question (a country list read as a citizenship question, a keyword that misfired: "criminal",
          "housing"), or put one question's answer into another's box
  page    page problem: label or options not read completely, the page's read-back differs from what was filled, a control that does not take the value
  runner  program problem: timeout, a click that failed, a stuck flow, a page that refused the submit
  ignore  nothing to fix or ask: voluntary self-identification (race, gender, disability, veteran, marketing opt-in), CONDITIONAL follow-ups ("If yes ...",
          "If other, please specify", "Other URL", "details" boxes), optional free text, essays / opinions the candidate writes himself, a CAPTCHA (Joey's by design)
Rules of thumb: found_by "the rules answered WRONGLY" is never fact and never ignore — it is rule, qtype or page. found_by "left unanswered" + optional
follow-up / free text / voluntary question → ignore. A required real question about the candidate with no matching key → fact.
group_with — ids of OTHER candidates in this list that are the SAME underlying problem (the same question worded differently, the same error on the same
platform); [] if none. Do not group things that are only similar in kind.
evidence — an exact phrase copied from that candidate's material (a few words) that supports the category
confidence — high | medium | low
Never invent facts. Answer with JSON only: {"items": [{"id": "...", "category": "...", "group_with": [], "evidence": "...", "confidence": "..."}]}"""


class ModelUnavailable(Exception):
    pass


def ask_model(system, user, temperature=0.0, usage=None):
    """One DeepSeek call (JSON mode). Raises ModelUnavailable on a missing key / network / parse failure."""
    sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
    try:
        import ladder, urllib.request
        body = json.dumps({'model': ladder.DS_MODEL, 'temperature': temperature, 'response_format': {'type': 'json_object'},
                           'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}).encode()
        req = urllib.request.Request(ladder.DS_URL, data=body, method='POST', headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + ladder._key()})
        out = json.loads(urllib.request.urlopen(req, timeout=120).read())
        if usage is not None:
            u = out.get('usage', {}); usage['calls'] = usage.get('calls', 0) + 1
            usage['prompt'] = usage.get('prompt', 0) + u.get('prompt_tokens', 0); usage['out'] = usage.get('out', 0) + u.get('completion_tokens', 0)
        return json.loads(out['choices'][0]['message']['content'])
    except Exception as e:
        raise ModelUnavailable(f'{type(e).__name__}: {str(e)[:100]}')


EVIDENCE_KEYS = ('question', 'options', 'what_went_wrong', 'problems', 'stopped_at')
MIN_EVIDENCE = 8


def material_text(m):
    """The part of the material a quoted `evidence` phrase is looked up in: the question, options, notes and errors as plain text — never the
    program's own words (found_by, fact_library, key names), which would make any quote 'valid'."""
    def flat(v):
        if isinstance(v, dict): return ' ; '.join(flat(x) for x in v.values())
        if isinstance(v, (list, tuple)): return ' | '.join(flat(x) for x in v)
        return '' if v is None else str(v)
    return ' ; '.join(flat(m[k]) for k in EVIDENCE_KEYS if k in m)


def material_hash(m):
    return hashlib.sha1(json.dumps(m, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()[:12]


def classify_batch(cands, ask, temperature=0.0, shuffle=None, index=None):
    """cands = [{'id', 'material'}] → {id: validated item}. A batch the model could not answer / returned as junk → every item 'unsure'."""
    order = list(cands)
    if shuffle is not None: random.Random(shuffle).shuffle(order)
    ids = {c['id'] for c in cands}
    user = json.dumps({'profile_fact_keys': index or [], 'candidates': [{'id': c['id'], **c['material']} for c in order]}, ensure_ascii=False)
    out = {}
    try:
        resp = ask(SYSTEM, user, temperature)
        by = {i.get('id'): i for i in (resp.get('items') if isinstance(resp, dict) and isinstance(resp.get('items'), list) else []) if isinstance(i, dict)}
    except ModelUnavailable:
        raise
    except Exception:
        by = {}
    for c in cands:
        out[c['id']] = validate_item(by.get(c['id']), material_text(c['material']), ids)
    return out


GROUP_SYSTEM = """You get a list of problem candidates found while an agent fills in job application forms, each with an "id" and a short "text". Find the ones that are
the SAME underlying problem: the same question worded differently, or the same error on the same platform. Do not group things that are only similar in kind.
Answer with JSON only: {"groups": [["id1", "id2"], ...]} — only groups of two or more; every id at most once."""


def group_all(cands, ask, cache, ids_per_call=150, cats=None):
    """One grouping pass over ALL candidates (a batch of 10 cannot see a wording in another batch). → list of groups (lists of ids), cached by content."""
    items = [{'id': c['id'], 'category': (cats or {}).get(c['id']), 'platform': c['material'].get('platform') or ','.join(c['material'].get('platforms') or []) or None,
              'text': (material_text(c['material']) or str(c['id']))[:240]} for c in cands]
    out = []
    for i in range(0, len(items), ids_per_call):
        chunk = items[i:i + ids_per_call]
        k = 'groups:' + hashlib.sha1(json.dumps(chunk, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()[:16]
        if k in cache: out += cache[k]; continue
        try:
            resp = ask(GROUP_SYSTEM, json.dumps(chunk, ensure_ascii=False), 0.0)
            valid = {c['id'] for c in chunk}; seen = set(); gs = []
            for g in (resp.get('groups') if isinstance(resp, dict) and isinstance(resp.get('groups'), list) else []):
                g = [x for x in (g if isinstance(g, list) else []) if x in valid and x not in seen]
                if len(g) >= 2: gs.append(g); seen.update(g)
            cache[k] = gs; out += gs
        except ModelUnavailable:
            raise
        except Exception:
            pass                                                   # no grouping today; nothing is cached, tried again next run
    return out


def triage(cands, ask, cache=None, usage=None, index=None, on_batch=None):
    """cands = [{'id', 'material'}] → ({id: {'category', 'group_with', 'evidence', 'confidence', 'reason', 'read2'}}, groups).
    `id` must be STABLE across days. Cached per (id, material hash); only new candidates are sent; a 'fact' is read a second time (temperature 0.7,
    shuffled order). Model / format failures are not cached (tried again next run). `on_batch()` is called after every batch (save the cache)."""
    cache = cache if cache is not None else {}
    res, todo = {}, []
    for c in cands:
        k = c['id'] + ':' + material_hash(c['material'])
        if k in cache: res[c['id']] = cache[k]
        else: todo.append(c)
    for i in range(0, len(todo), BATCH):
        b = todo[i:i + BATCH]
        first = classify_batch(b, ask, 0.0, index=index)
        facts = [c for c in b if first[c['id']]['category'] == 'fact']
        second = classify_batch(facts, ask, 0.7, shuffle=i + 1, index=index) if facts else {}
        for c in b:
            r = dict(first[c['id']]); s = second.get(c['id'])
            r['read2'] = s['category'] if s else None
            r['category'] = combine_reads(r['category'], r['read2']) if r['category'] == 'fact' else r['category']
            if r['category'] == 'unsure' and not r.get('reason'): r['reason'] = 'the second read did not confirm "fact"'
            res[c['id']] = r
            if r.get('reason') not in ('not an object',): cache[c['id'] + ':' + material_hash(c['material'])] = r
        if on_batch: on_batch()
    cat = {c['id']: res[c['id']]['category'] for c in cands}
    ok = lambda a, b: cat[a] == cat[b] or 'fact' not in (cat[a], cat[b])      # a confirmed fact is never swallowed by another category's group
    claims = [{'id': c['id'], 'group_with': [g for g in res[c['id']]['group_with'] if g in cat and ok(c['id'], g)]} for c in cands]
    for g in group_all(cands, ask, cache, cats=cat):              # the global pass adds links the batches could not see
        for x in g[1:]:
            if ok(g[0], x): claims.append({'id': g[0], 'group_with': [x]})
    if on_batch: on_batch()
    return res, merge_groups(claims)
