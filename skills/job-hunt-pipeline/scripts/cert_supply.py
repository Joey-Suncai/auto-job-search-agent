#!/usr/bin/env python3
"""Test supply for platform certification (JSA-057, 2026-10-31): internships in OTHER fields, pulled straight from the public
Greenhouse / Lever / Ashby boards of companies already in data/store/jobs.jsonl (Joey 2026-10-31: 「可以用其他的专业的 intern，
因为这只是测试，只要能够证明能在这个平台上跑通即可」).

Never a tier A/B company (a test application there is still a real application — spec docs/specs/runner-platform-expansion.md),
never a company already in the tracker or on the skip list, never a posting already in jobs.jsonl. What is left is checked
offline (title, U.S. location, Summer 2027 season, prefilter flags) and then by the gate's own classifier
(eligibility_classify.js); only 可投 rows are kept.

    python3 cert_supply.py [--platform greenhouse ashby lever] [--write]      # --write appends the rows through store.py
Rows written: tier "D", `cert_supply: "other_field"`, sources ["cert_supply"], elig from the classifier; the 08:45 gate
re-checks them like any row. Spec + DeepSeek-written cases: scripts/test_cases/cert_supply_*; harness scripts/test_cert_supply.py.
"""
import argparse, datetime, html, json, os, re, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'scripts'))
import resolve_builtin as RB  # noqa: E402

CAP = 2                                            # postings per company: spread the test, never flood one employer
INTERN = re.compile(r'\b(intern|interns|internship|internships|co-?op)\b', re.I)
NOT_INTERN = re.compile(r'\b(internal|international|internet)\b', re.I)
STATES = ('AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC '
          'SD TN TX UT VT VA WA WV WI WY DC').split()
STATE_NAMES = ['alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado', 'connecticut', 'delaware', 'florida', 'georgia',
               'hawaii', 'idaho', 'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana', 'maine', 'maryland', 'massachusetts',
               'michigan', 'minnesota', 'mississippi', 'missouri', 'montana', 'nebraska', 'nevada', 'new hampshire', 'new jersey',
               'new mexico', 'new york', 'north carolina', 'north dakota', 'ohio', 'oklahoma', 'oregon', 'pennsylvania', 'rhode island',
               'south carolina', 'south dakota', 'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington', 'west virginia',
               'wisconsin', 'wyoming']
US_RX = re.compile(r'\b(united states|u\.s\.a?\.?|usa|us-remote|remote[ ,(-]*us\b)|\b(' + '|'.join(STATE_NAMES) + r')\b'
                   r'|,\s*(' + '|'.join(STATES) + r')\b|\b(nyc|san francisco|seattle|chicago|boston|austin|los angeles|atlanta|'
                   r'denver|miami|philadelphia|washington,? d\.?c\.?|bay area|silicon valley)\b', re.I)
OTHER_TERM = re.compile(r'\b(fall|autumn|winter|spring|jan(uary)?|feb(ruary)?|march|april|sept?(ember)?|oct(ober)?|nov(ember)?|dec(ember)?)\b', re.I)
NOT_HIM = re.compile(r'\b(ph\.?d|doctoral|undergraduate|undergrad|college fair|career fair|university fair)\b', re.I)
PROF_DEGREE = re.compile(r'\b(legal|law clerk|law student|paralegal|juris|j\.d\.|nursing|pharmacy|medical student|ministry|pastor|dental|veterinary)\b', re.I)


def is_intern(title):
    t = title or ''
    return bool(INTERN.search(NOT_INTERN.sub(' ', t)))


def us_location(loc):
    """True when the location names a U.S. place (a list that also names other countries still counts: he applies for
    the U.S. one). "Remote" alone, or only non-U.S. places, is not enough."""
    return bool(US_RX.search(loc or ''))


def season_ok(title, text):
    """A Summer 2027 internship: "2027" in the title or text, no 2026-only term in the title, and no fall / winter /
    spring term or January–April / September–December month in the title unless the title also says summer."""
    t, x = title or '', text or ''
    if re.search(r'\b2026\b', t) and not re.search(r'\b2027\b', t):
        return False
    if OTHER_TERM.search(t) and not re.search(r'\bsummer\b', t, re.I):
        return False
    return bool(re.search(r'\b2027\b', t + ' ' + x))


def track_of(title):
    t = (title or '').lower()
    if re.search(r'\b(ai|machine learning|ml|agents?|agentic|llm|genai)\b', t) and re.search(r'\b(product manag\w*|product owner|apm|associate product)\b', t): return 'AI Product Manager', 'Product_Manager'
    if re.search(r'\b(ai|machine learning|ml|agent|llm|software|engineer)', t): return 'AI Agentic Eng', 'AI_Agentic_Engineer'
    if re.search(r'\bproduct\b', t): return 'Product Manager', 'Product_Manager'
    if re.search(r'data engineer|pipeline|etl', t): return 'Data Engineer', 'Data_Engineer'
    return 'Data Sci / Analytics', 'Data_Analyst'


def squash(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def near_blocked(post, blocked):
    """A raw board token like "doordashusa" / "optiverprivate" / "thenewyorktimes" names a blocked company without matching
    its key: blocked when a blocked name (squashed, ≥ 4 characters) is inside the company name or token, or the other way."""
    names = {squash(post.get('company')), squash(post.get('board'))} - {''}
    for b in blocked:
        sb = squash(b)
        if len(sb) >= 4 and any(sb in n or (len(n) >= 4 and n in sb) for n in names):
            return True
    return False


def select(post, ctx):
    """Pure (tested). post = {company, title, location, text, url, key, board}; ctx = {blocked: set of company keys,
    blocked_boards: set of board tokens already used (tracker / runner results),
    known: set of posting keys / urls already in the store, flags: callable(post) → list of prefilter flags}.
    → (keep: bool, reason: str)."""
    ck = RB.company_key(post.get('company'))
    if ck in ctx['blocked'] or (post.get('board') and post['board'] in ctx.get('blocked_boards', ())) or near_blocked(post, ctx['blocked']):
        return False, 'company blocked (tier A/B, tracker or skip list)'
    if post.get('key') in ctx['known'] or post.get('url') in ctx['known']:
        return False, 'already in the store'
    if not is_intern(post.get('title')):
        return False, 'not an internship'
    if NOT_HIM.search(post.get('title') or ''):
        return False, 'not open to him (PhD / undergraduate only / one school\'s fair)'
    if PROF_DEGREE.search(post.get('title') or ''):
        return False, 'needs a professional degree (law / medicine / ministry)'
    if not us_location(post.get('location')):
        return False, 'not a U.S. location'
    if not season_ok(post.get('title'), post.get('text')):
        return False, 'not Summer 2027'
    fl = ctx['flags'](post)
    bad = [f for f in ('CLEAR', 'NOSPON', 'DEG', 'START', 'STALE', 'DEF') if f in fl]
    if bad:
        return False, 'flags ' + ', '.join(bad)
    return True, 'ok'


# ---------- network + store (not part of the pure step) ----------
def strip(h):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', html.unescape(h or '')))).strip()


def postings(ats, token, company):
    out = []
    try:
        if ats == 'greenhouse':
            d = json.loads(RB.get(f'https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true', tries=2))
            for j in d.get('jobs', []):
                out.append(dict(company=company, title=j.get('title'), location=(j.get('location') or {}).get('name'),
                                text=strip(j.get('content')), url=f'https://job-boards.greenhouse.io/{token}/jobs/{j["id"]}',
                                key=f'gh:{j["id"]}', ats='greenhouse', board=token, posted=(j.get('first_published') or j.get('updated_at') or '')[:10]))
        elif ats == 'lever':
            d = json.loads(RB.get(f'https://api.lever.co/v0/postings/{token}?mode=json', tries=2))
            for j in d if isinstance(d, list) else []:
                c = j.get('categories') or {}
                out.append(dict(company=company, title=j.get('text'), location=c.get('location') or ', '.join(c.get('allLocations') or []),
                                text=(j.get('descriptionPlain') or '') + ' ' + ' '.join(strip(x.get('content')) for x in j.get('lists') or []),
                                url=j.get('hostedUrl'), key=f'lv:{j.get("id")}', ats='lever', board=token,
                                posted=datetime.date.fromtimestamp((j.get('createdAt') or 0) / 1000).isoformat()))
        elif ats == 'ashby':
            d = json.loads(RB.get(f'https://api.ashbyhq.com/posting-api/job-board/{token}', tries=2))
            for j in d.get('jobs', []):
                if j.get('isListed') is False:
                    continue
                loc = ', '.join([j.get('location') or ''] + [s.get('location', '') for s in j.get('secondaryLocations') or []])
                out.append(dict(company=company, title=j.get('title'), location=loc, text=j.get('descriptionPlain') or '',
                                url=j.get('jobUrl'), key=f'ab:{j.get("id")}', ats='ashby', board=token, posted=(j.get('publishedAt') or '')[:10]))
    except Exception:
        return []
    return out


def raw_boards():
    """(ats, token) → company name guess for every Greenhouse / Lever / Ashby board linked from data/raw (the source lists
    in every field). The name is the token, title-cased, unless the same record names the company."""
    out = {}
    for dp, _, fs in os.walk(jpaths.data('raw')):
        for f in fs:
            try:
                txt = open(os.path.join(dp, f), encoding='utf-8', errors='replace').read()
            except Exception:
                continue
            for ats, rx in RB.BOARD_RX:
                for m in re.finditer(rx, txt):
                    tok = m.group(1)
                    if tok not in ('embed', 'jobs') and (ats, tok) not in out:
                        out[(ats, tok)] = re.sub(r'[-_.]+', ' ', tok).title()
    return out


def classify(rows):
    """The gate's classifier on the posting text → {key: verdict code}."""
    import tempfile
    d = tempfile.mkdtemp()
    src, res = os.path.join(d, 'in.jsonl'), os.path.join(d, 'out.json')
    with open(src, 'w', encoding='utf-8') as fh:
        for r in rows:
            fh.write(json.dumps({'id': r['key'], 'level': 'Internship', 'status': 'ok', 'key': r['key'], 'title': r['title'],
                                 'text': r['text'], 'loc': r['location']}, ensure_ascii=False) + '\n')
    subprocess.run(['node', os.path.join(HERE, 'eligibility_classify.js'), src, res], check=True, stdout=subprocess.DEVNULL)
    return json.load(open(res))


def main():
    import store, prefilter
    ap = argparse.ArgumentParser()
    ap.add_argument('--platform', nargs='*', default=['greenhouse', 'ashby', 'lever'])
    ap.add_argument('--write', action='store_true'); ap.add_argument('--out')
    a = ap.parse_args()
    jobs, apps = store.load('jobs'), store.load('applications')
    blocked = {RB.company_key(j.get('company')) for j in jobs if j.get('tier') in ('A', 'B')}
    blocked |= {RB.company_key(x.get('company')) for x in apps}
    sk = jpaths.data('dashboard', 'skip_companies.txt')
    if os.path.exists(sk):
        blocked |= {RB.company_key(l.split('#')[0].strip()) for l in open(sk, encoding='utf-8') if l.split('#')[0].strip()}
    used = [x.get('url') for x in apps] + [json.loads(l).get('url') for l in open(jpaths.data('runner', 'results.jsonl'), encoding='utf-8') if l.strip()]
    blocked_boards = {m.group(1) for u in used if u for _, rx in RB.BOARD_RX for m in [re.search(rx, u)] if m}
    blocked_boards |= {m.group(1) for f in os.listdir(jpaths.apps()) for p in [jpaths.apps(f, 'plan.json')]
                       if os.path.exists(p) for _, rx in RB.BOARD_RX for m in [re.search(rx, json.load(open(p)).get('url') or '')] if m}
    known = {j.get('url') for j in jobs} | {j.get('ats_url') for j in jobs} | {prefilter.posting_key(j.get('url') or '') for j in jobs}
    known.discard(None); known.discard('')
    known |= {f'{pre}:{k}' for k in list(known) for pre in ('gh', 'lv', 'ab')}   # postings are keyed "lv:<id>"; the store has the bare id (a Lever employer 2026-10-31)
    known |= {prefilter.posting_key(j.get('ats_url') or '') for j in jobs} - {None, ''}
    boards = {}
    for j in jobs:
        for ats, tok in RB.known_boards([j]).get(RB.company_key(j.get('company')), []):
            if ats in a.platform and RB.company_key(j.get('company')) not in blocked:
                boards.setdefault((ats, tok), j.get('company'))
    for (ats, tok), name in raw_boards().items():      # boards seen in the raw source lists (all fields, data/raw) — more Ashby / Lever
        ck = RB.company_key(name)
        if ats in a.platform and (ats, tok) not in boards and ck not in blocked and RB.company_key(tok) not in blocked:
            boards[(ats, tok)] = name
    print(f'{len(boards)} boards to read', file=sys.stderr)
    with ThreadPoolExecutor(12) as ex:
        allp = [p for lst in ex.map(lambda b: postings(b[0], b[1], boards[b]), boards) for p in lst]
    ctx = {'blocked': blocked, 'blocked_boards': blocked_boards, 'known': known,
           'flags': lambda p: prefilter.flags_of({'title': p['title'], 'level': 'Internship', 'company': p['company'], 'posted': p.get('posted') or '9999'},
                                                  {'status': 'ok', 'text': p['text']}, set(), set())}
    from collections import Counter
    why, keep = Counter(), []
    for p in allp:
        k, r = select(p, ctx)
        why[r] += 1
        if k: keep.append(p)
    seen, uniq, per = set(), [], Counter()
    for p in keep:                                  # same company + title in several cities → one row; at most CAP per company
        t = (RB.company_key(p['company']), p['title'].lower())
        if t not in seen and per[t[0]] < CAP: seen.add(t); per[t[0]] += 1; uniq.append(p)
    verdicts = classify(uniq) if uniq else {}
    ok = [p for p in uniq if (verdicts.get(p['key']) or {}).get('v') == 'Eligible']
    print(json.dumps({'postings': len(allp), 'reasons': dict(why), 'after_filters': len(uniq), 'eligible': len(ok),
                      'by_platform': dict(Counter(p['ats'] for p in ok))}, indent=1))
    if a.out:
        json.dump(ok, open(a.out, 'w'), ensure_ascii=False, indent=1)
    if a.write and ok:
        today = datetime.date.today().isoformat()
        nid = max([int(j['id'][1:]) for j in jobs if re.match(r'J\d+$', j.get('id') or '')] or [0]) + 1
        for p in ok:
            lbl, _ = track_of(p['title'])
            jobs.append({'id': f'J{nid:05d}', 'company': p['company'], 'title': p['title'], 'track': lbl, 'level': 'Internship',
                         'location': p['location'], 'url': p['url'], 'posted': p.get('posted') or '', 'tier': 'D', 'tier_orig': 'D',
                         'score': 0, 'sources': ['cert_supply'], 'cert_supply': 'other_field', 'added': today,
                         'elig': '可投', 'elig_base': '可投', 'elig_checked': today, 'elig_key': p['key'],
                         'elig_reason': 'cert_supply: offline filters + eligibility_classify.js 可投', 'referral': 'Cold',
                         'notes': 'platform certification test (other field, Joey 2026-10-31)'})
            nid += 1
        store.save('jobs', jobs)
        print(f'written: {len(ok)} rows (J… ids, cert_supply=other_field)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
