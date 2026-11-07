#!/usr/bin/env python3
"""Eligibility gate, step 2b (JSA-231 phase 2, Joey 2026-11-06 「好的」): rules first, DeepSeek re-reads the soft verdicts.

The rules (eligibility_rules.js) decide the clear cases alone. DeepSeek reads the full JD again only for:
  - 不可投 whose every block reason is a soft one (SOFT: off-cycle term, undergrad-only, no sponsorship, graduation window)
  - 待核实 with a readable JD (review codes, including the self-contradicting ones: SPONSORSHIP_MIXED, GRAD_MIXED)
Outcome (decide(), pure and tested by scripts/test_gate_second_read.py):
  - soft 不可投 + DeepSeek "no"            → stays 不可投 (both agree)
  - soft 不可投 + DeepSeek "yes"/"unclear" → 待核实 with DS_SECOND_READ (never straight to 可投)
  - 待核实 + any answer                     → stays 待核实; the answer is attached for the human check (never 可投 / 不可投)
  - DeepSeek error / no key / over the cap   → the rule verdict, unchanged
Every answer is cached by a hash of (prompt version, model, message), so a re-run over the same JD gives the same result
with no call (data home data/processed/gate_ds_cache.jsonl, git-ignored). Calls per run are capped (--ds-max); the
highest-scored rows are read first and the rest wait for the next check.

Also: weekly_audit() — on the Sunday --all run, a small sample of the hard 不可投 reasons (rules only) is re-read too and
the disagreements are written to data/runner/daily/gate_audit_<date>.md for Claude to check (and to fix the rules).

CLI (one-off / debugging):  python3 gate_second_read.py <jds.jsonl> <gate_results.json> [--ds-max N] [--dry]
"""
import concurrent.futures as cf
import datetime, hashlib, json, os, random, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, 'config'))

PROMPT_VERSION = 'g1'
SOFT = {'OFF_CYCLE', 'UNDERGRAD_ONLY', 'NO_SPONSORSHIP', 'GRAD_WINDOW'}
HARD_AUDIT = ['CITIZEN_OR_CLEARANCE', 'NON_US', 'PHD_ONLY', 'MBA_ONLY', 'TOO_LONG', 'EXPERIENCE_3PLUS']
NO_TEXT = {'UNREADABLE', 'NO_TEXT', 'FETCH_ERROR', 'POSSIBLY_EXPIRED', 'CLOSED'}
DS_CODE = 'DS_SECOND_READ'


def _merge_reasons():
    import importlib.util
    spec = importlib.util.spec_from_file_location('eligibility_merge', os.path.join(HERE, 'eligibility_merge.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m.REASON


BLOCK = {c for c, (lv, _) in _merge_reasons().items() if lv == 'block'}   # the merge step's table = one source of truth

MONTH = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def _ym(s, default):
    m = re.match(r'^(\d{4})-(\d{2})$', str(s or ''))
    return f"{MONTH[int(m.group(2)) - 1]} {m.group(1)}" if m else default


def candidate_text(el):
    """The candidate paragraph of the prompt, built from config/profile.json → eligibility (no facts in code, JSA-077)."""
    el = el or {}
    deg = {'bachelors': "a bachelor's", 'phd': 'a PhD', 'masters': "a master's"}.get(str(el.get('degree_level', 'masters')).lower(), "a master's")
    grad = _ym(el.get('grad'), 'December 2027')
    summer = el.get('intern_summer') or 2027
    ft = _ym(el.get('fulltime_from'), 'January 2028')
    if el.get('citizen_or_pr'):
        auth = 'U.S. citizen or permanent resident; needs no visa sponsorship. No security clearance.'
    elif el.get('needs_sponsorship', True):
        auth = ('F-1 international student, not a U.S. citizen or permanent resident, no security clearance. A summer internship '
                'runs on CPT (no employer sponsorship needed for the internship itself); full-time work will need H-1B '
                'sponsorship later. A posting that will not consider candidates who need sponsorship now OR IN THE FUTURE, or '
                'that requires permanent work authorization for any employer, excludes the candidate; a posting that only '
                "says 'must be authorized to work in the US' does not.")
    else:
        auth = 'Not a U.S. citizen; authorized to work without sponsorship. No security clearance.'
    prior = " Already holds a bachelor's degree." if deg != "a bachelor's" else ''
    return (f"{auth} Currently enrolled in {deg} program, graduating {grad}.{prior} Wants: Summer {summer} internships "
            f"(roughly May-September {summer}, about 10-14 weeks, full-time) or full-time jobs starting {ft} or later. "
            "Has 0-1 years of full-time experience. U.S. locations only.")


SYSTEM = """You screen job postings for ONE candidate. Read the whole posting and decide if the candidate may apply.
Candidate: {cand}
Decide each check from the posting text only (quote it). 'unclear' when the posting does not settle it.
Return JSON: {{"eligible": "yes"|"no"|"unclear", "blocking": [ {{"check": one of sponsorship|citizenship_clearance|location|term_not_summer|too_long|degree_level|grad_date|experience|mba_only|phd_only|other, "quote": "..."}} ],
 "notes": "one sentence"}}. 'no' only when a quoted sentence clearly excludes the candidate; mere preferences are not blocks."""


def message(x):
    text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', x.get('text') or '')).strip()
    return f"TITLE: {x.get('title')}\nLOCATION: {x.get('loc')}\nLEVEL: {x.get('level')}\nPOSTING:\n{text[:14000]}"


def cache_key(system, msg, model):
    return hashlib.sha256(f"{PROMPT_VERSION}\x00{model}\x00{system}\x00{msg}".encode('utf-8')).hexdigest()[:32]


def codes_of(r):
    return [c for c in (r.get('c') or '').split(',') if c]


def pick(r):
    """Which second read a gate result needs: 'soft_block', 'review' or None (pure)."""
    codes = codes_of(r)
    if any(c in NO_TEXT for c in codes):
        return None
    if r.get('v') == 'Ineligible':
        blocks = [c for c in codes if c in BLOCK]
        return 'soft_block' if blocks and all(c in SOFT for c in blocks) else None
    if r.get('v') == 'Review':
        return 'review'
    return None


def decide(r, kind, ans):
    """New gate result from the rule result r, the pick() kind and DeepSeek's answer (None = no answer). Pure."""
    if not kind or not isinstance(ans, dict) or ans.get('eligible') not in ('yes', 'no', 'unclear'):
        return r
    out = dict(r)
    out['ds'] = {'eligible': ans['eligible'], 'notes': str(ans.get('notes') or '')[:240],
                 'checks': sorted({str(b.get('check')) for b in (ans.get('blocking') or []) if isinstance(b, dict)}),
                 'v': PROMPT_VERSION}
    if kind == 'soft_block' and ans['eligible'] != 'no':
        out['v'] = 'Review'
        out['c'] = ','.join(codes_of(r) + [DS_CODE])
        out['e'] = ('DeepSeek: ' + out['ds']['notes'] + ' | rule: ' + (r.get('e') or ''))[:300]
    return out


class Reader:
    """DeepSeek with a JSONL cache. ask(msg) -> answer dict or None. Thread-safe enough for appends (one line per write)."""

    def __init__(self, cache_path, system, ask=None, model=None):
        self.path, self.system, self.cache = cache_path, system, {}
        self.usage = {'calls': 0, 'prompt': 0, 'out': 0, 'cached': 0, 'errors': 0}
        if ask is None:
            sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
            import ladder  # noqa: E402  (DeepSeek chat API, JSON mode, temperature 0)
            if not ladder._key():   # no key here (the claude.ai cloud routine): rules only, no failed calls
                raise RuntimeError('no DeepSeek key (DEEPSEEK_KEY_FILE / ~/deepseek/api_key)')
            self.model = model or ladder.DS_MODEL
            self._ask = lambda m: ladder.ask_deepseek(m, self.usage, system=self.system)
        else:
            self.model, self._ask = model or 'test', ask
        if cache_path and os.path.exists(cache_path):
            for line in open(cache_path, encoding='utf-8'):
                try:
                    x = json.loads(line); self.cache[x['k']] = x['a']
                except Exception:
                    pass

    def ask(self, msg):
        k = cache_key(self.system, msg, self.model)
        if k in self.cache:
            self.usage['cached'] += 1
            return self.cache[k]
        try:
            a = self._ask(msg)
        except Exception:
            self.usage['errors'] += 1
            return None
        if not isinstance(a, dict) or a.get('eligible') not in ('yes', 'no', 'unclear'):
            self.usage['errors'] += 1
            return None
        self.cache[k] = a
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'k': k, 'a': a, 'at': datetime.date.today().isoformat()}, ensure_ascii=False) + '\n')
        return a

    def cached(self, msg):
        return cache_key(self.system, msg, self.model) in self.cache


def default_reader(ask=None):
    import paths as jpaths
    try:
        import jsa_profile
        el = jsa_profile.load().get('eligibility') or {}
    except Exception:
        el = {}
    return Reader(jpaths.data('processed', 'gate_ds_cache.jsonl'), SYSTEM.format(cand=candidate_text(el)), ask=ask)


def apply(res, jds, reader, ds_max=400, score=None, workers=8):
    """res: {id: gate result} (changed in place and returned); jds: {id: fetched JD row}; score: {id: score} for the order.
    Cached answers are free and always used; new calls stop at ds_max."""
    score = score or {}
    todo = [(i, pick(r)) for i, r in res.items() if pick(r) and i in jds and (jds[i].get('text') or '')]
    todo.sort(key=lambda t: (-float(score.get(t[0]) or 0), t[0]))
    msgs = {i: message(jds[i]) for i, _ in todo}
    # one call per distinct message: two rows with the same JD (a posting listed twice) always get the same answer
    uniq = list(dict.fromkeys(msgs[i] for i, _ in todo if not reader.cached(msgs[i])))[:max(0, ds_max)]
    with cf.ThreadPoolExecutor(workers) as ex:
        got = dict(zip(uniq, ex.map(reader.ask, uniq)))
    answers = {i: got[msgs[i]] for i, _ in todo if msgs[i] in got}
    allowed = set(answers) | {i for i, _ in todo if reader.cached(msgs[i])}
    stats = {'candidates': len(todo), 'read': 0, 'skipped_cap': 0, 'to_review': 0, 'confirmed': 0, 'by_code': {}}
    for i, kind in todo:
        if i not in allowed:
            stats['skipped_cap'] += 1
            continue
        ans = answers.get(i) if i in answers else reader.ask(msgs[i])
        new = decide(res[i], kind, ans)
        if 'ds' in new:
            stats['read'] += 1
            if kind == 'soft_block':
                key = '+'.join(sorted(c for c in codes_of(res[i]) if c in BLOCK))
                b = stats['by_code'].setdefault(key, {'read': 0, 'to_review': 0})
                b['read'] += 1
                if new['v'] == 'Review':
                    stats['to_review'] += 1; b['to_review'] += 1
                else:
                    stats['confirmed'] += 1
        res[i] = new
    stats['usage'] = dict(reader.usage)
    return res, stats


def weekly_audit(res, jds, reader, out_md, per_code=5, seed=None, titles=None):
    """Sunday sample: per_code rows per hard block reason (rules only, not re-read above), DeepSeek reads them; every
    'yes' / 'unclear' is listed for Claude to check. Returns the per-code counts."""
    rnd = random.Random(seed if seed is not None else datetime.date.today().isoformat())
    titles = titles or {}
    by = {}
    for i, r in res.items():
        if r.get('v') != 'Ineligible' or i not in jds or not jds[i].get('text'):
            continue
        blocks = sorted({c for c in codes_of(r) if c in BLOCK})
        if len(blocks) == 1 and blocks[0] in HARD_AUDIT:
            by.setdefault(blocks[0], []).append(i)
    counts, lines = {}, []
    for code in HARD_AUDIT:
        ids = sorted(by.get(code, []))
        pickd = rnd.sample(ids, min(per_code, len(ids)))
        n_dis = 0
        for i in pickd:
            a = reader.ask(message(jds[i]))
            if isinstance(a, dict) and a.get('eligible') in ('yes', 'unclear'):
                n_dis += 1
                lines.append(f"| {i} | {code} | {a['eligible']} | {(titles.get(i) or jds[i].get('title') or '')[:60]} | "
                             f"{(res[i].get('e') or '')[:140]} | {str(a.get('notes') or '')[:160]} |")
        counts[code] = {'sampled': len(pickd), 'disagree': n_dis}
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, 'w', encoding='utf-8') as f:
        f.write(f"# Gate audit {datetime.date.today().isoformat()} (JSA-231 weekly sample, hard reasons, rules only)\n\n")
        f.write('Check every row below by reading the JD: a real false kill → fix eligibility_rules.js + a case in '
                'eligibility_rules_test.js; a DeepSeek misread → nothing to do.\n\n')
        f.write('| code | sampled | DeepSeek disagrees |\n| --- | --- | --- |\n')
        for c, v in counts.items():
            f.write(f"| {c} | {v['sampled']} | {v['disagree']} |\n")
        f.write('\n| id | code | DeepSeek | title | rule evidence | DeepSeek note |\n| --- | --- | --- | --- | --- | --- |\n')
        f.write('\n'.join(lines) + ('\n' if lines else ''))
        # the soft verdicts DeepSeek moved to 待核实 this run: the rule may need a fix (Claude checks a sample)
        soft = sorted(i for i, r in res.items() if DS_CODE in codes_of(r))
        f.write(f"\n## Soft 不可投 → 待核实 this run ({len(soft)}; a sample of 20)\n\n| id | codes | title | DeepSeek + rule evidence |\n| --- | --- | --- | --- |\n")
        for i in rnd.sample(soft, min(20, len(soft))):
            f.write(f"| {i} | {res[i].get('c')} | {(titles.get(i) or (jds.get(i) or {}).get('title') or '')[:60]} | {(res[i].get('e') or '')[:220]} |\n")
    return counts


def main(a):
    jds = {}
    for line in open(a[0], encoding='utf-8'):
        if line.strip():
            x = json.loads(line); jds[x['id']] = x
    res = json.load(open(a[1]))
    ds_max = int(a[a.index('--ds-max') + 1]) if '--ds-max' in a else 400
    if '--dry' in a:
        kinds = {}
        for r in res.values():
            k = pick(r); kinds[k] = kinds.get(k, 0) + 1
        print(json.dumps(kinds)); return 0
    res, stats = apply(res, jds, default_reader(), ds_max=ds_max)
    json.dump(res, open(a[1], 'w'), ensure_ascii=False)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
