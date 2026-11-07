#!/usr/bin/env python3
"""Identity restrictions that only show up in the application FORM (JSA-231; Joey 2026-11-06, e.g. Divergent: the JD says
nothing, the Greenhouse form asks "This position requires access to information and technology that is subject to US
export controls. Are you any of the following 'protected individuals' …").

find(plan)                -> the restriction questions in a plan.json (pure, tested: scripts/test_form_restrictions.py)
applies(hits, candidate)  -> True when they exclude this candidate (a non-citizen / non-permanent-resident)
check_batch(status, apps) -> called once by prep_batch.py after every plan is built: a restricted job's prep row becomes
                             status 'ineligible_form' (batch_apply.py then skips it) and its store row 不可投 with
                             elig_form, which eligibility_merge.py keeps on later gate runs (the JD alone would pass it).
A question that only ASKS ("Are you a U.S. citizen?", "Will you require sponsorship?") is not a restriction; the form
must say the position requires it (export control / ITAR / U.S. person / citizenship / security clearance).
"""
import datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))

EXPORT = re.compile(r"\bexport[- ](?:control\w*|compliance)|(?-i:\bITAR\b|\bEAR\b)|\bdeemed export|\bInternational Traffic in Arms", re.I)
IDENTITY = re.compile(r"\bU\.?S\.? (?:citizen|person|national)s?\b|\bUnited States (?:citizen|person|national)s?\b|\bcitizenship\b|"
                      r"\bpermanent resident|\bgreen card|\bprotected individual|\brefugee|\basylee|\b8 ?U\.?S\.?C\.? ?1324b", re.I)
REQUIRE = re.compile(r"\b(?:requires?|required|must (?:be|have|hold|possess)|only (?:be )?(?:open|available) to|limited to|restricted to|"
                     r"is contingent (?:up)?on|eligib\w+ (?:is )?(?:limited|restricted))\b", re.I)
# "may require access …", "must be a U.S. person or otherwise eligible for deemed export licensing", "committed to
# compliance with export control laws": the company may still hire with a licence — a person decides, no automatic block
MAYBE = re.compile(r"\bmay (?:also )?require\b|\botherwise eligible for (?:a )?(?:deemed[- ])?export licen|\bcommitted to compliance\b|"
                   r"\bassess\w* (?:its |our |their )?export compliance|\b(?:licen[cs]e|authori[sz]ation) (?:may|might|could) be (?:required|needed|obtained)", re.I)
CITIZEN_REQ = re.compile(r"\b(?:requires?|required|must be|only|limited to|restricted to)\b[^?.]{0,80}\b(?:U\.?S\.?|United States) "
                         r"(?:citizen(?:ship)?s?|persons?)\b|\b(?:U\.?S\.?|United States) citizens? only\b", re.I)
CLEARANCE_REQ = re.compile(r"\b(?:requires?|required|must (?:have|hold|possess|be able to obtain|obtain))\b[^?.]{0,80}\b(?:security|secret|top secret|TS/SCI|DoD|government|federal|public trust) clearance\b|"
                           r"\b(?:active|current) (?:security |secret |top secret |TS/SCI )?clearance (?:is )?required\b", re.I)


# a sanctions screen ("… compliance with U.S. sanctions and export controls. Select all that apply: Citizen or permanent
# resident of Cuba, Iran, North Korea, or Syria / … / None of the above" — a Greenhouse employer 11-06, JSA-237 smoke run) asks about
# embargoed countries, not for U.S. citizenship: no restriction for this candidate (the answer is "None of the above")
# a question that ASKS (JSA-237 full prefetch 2026-11-06: a Greenhouse employer "Would you require an export license …", Zoox "list any
# countries of which you are a citizen … export licensing", TRM "If this role requires a security clearance, do you …",
# ERG "Some of the work … requires a DoD Secret clearance. Are you eligible …") is a question for Joey, not a block
LICENSE_ASK = re.compile(r"\bwould you (?:\w+ )?require (?:an? )?(?:export )?licen|\bfor the (?:sole )?purpose of determining (?:export )?licens|"
                         r"\bwould you meet the requirements for (?:an? )?(?:deemed )?export licen|\bplease list any countries\b", re.I)
COND_ASK = re.compile(r"\bif (?:this|the|your) (?:role|position|job|work)\b[^?.]{0,30}\brequires?\b|\bsome of the (?:work|roles|positions)\b|"
                      r"\bcertain (?:positions|roles|contracts|projects)\b|\bin which you required\b|\bmay be required\b", re.I)
STATEMENT = re.compile(r"\b(?:involves?|will (?:have|require)|requires?|needs?) (?:access|work)\b|\binvolves? work with\b|\bsubject to\b", re.I)
SANCTIONS = re.compile(r"\bsanction|\b(?:Cuba|Iran|North Korea|Syria|Crimea|Donetsk|Luhansk)\b", re.I)
US_IDENTITY = re.compile(r"\bU\.?S\.? (?:citizen|person|national)s?\b|\bUnited States (?:citizen|person|national)s?\b|\bprotected individual|"
                         r"\bgreen card|\b8 ?U\.?S\.?C", re.I)


def _text(f):
    return ' '.join(str(x) for x in [f.get('label') or '', f.get('description') or ''] if x)


def find(plan):
    """Every form question that states an identity restriction: [{key, label, kind}] with kind export_control |
    citizenship | clearance (these block — the form states the position REQUIRES it) or export_control_maybe /
    citizenship_maybe / clearance_maybe (the form only ASKS — a question for the person, no block; JSA-237). Pure."""
    out, seen = [], set()
    for f in (plan or {}).get('fields') or []:
        t = _text(f)
        opts = ' '.join(str(o) for o in f.get('options') or [])
        kind = None
        if SANCTIONS.search(t + ' ' + opts) and not US_IDENTITY.search(t + ' ' + opts):
            continue                                       # an embargoed-country screen, not a U.S.-person requirement
        asks = bool(COND_ASK.search(t))
        if LICENSE_ASK.search(t):
            kind = 'export_control_maybe'                  # a license question for the person, whatever else it says
        elif EXPORT.search(t) and (IDENTITY.search(t) or IDENTITY.search(opts)):
            stated = REQUIRE.search(t) or STATEMENT.search(t)
            kind = 'export_control_maybe' if (MAYBE.search(t) or LICENSE_ASK.search(t) or asks or not stated) else 'export_control'
        elif CITIZEN_REQ.search(t):
            kind = 'citizenship_maybe' if asks else 'citizenship'
        elif CLEARANCE_REQ.search(t):
            kind = 'clearance_maybe' if asks else 'clearance'
        if kind and f.get('key') not in seen:
            seen.add(f.get('key'))
            out.append({'key': f.get('key'), 'label': (f.get('label') or '')[:300], 'kind': kind})
    return out


HARD = ('export_control', 'citizenship', 'clearance')


def applies(hits, candidate):
    """These restrictions exclude the candidate: always for a non-citizen / non-permanent resident; a citizen passes
    citizenship and export-control questions (clearance is left to a person: not blocked here)."""
    hard = [h for h in hits or [] if h['kind'] in HARD]
    return bool(hard) and not (candidate or {}).get('citizen_or_pr')


def candidate():
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    try:
        import jsa_profile
        return jsa_profile.load().get('eligibility') or {}
    except Exception:
        return {}


def mark_store(job_id, hits, today=None, store=None):
    """The job's store row → 不可投 with elig_form (kept by eligibility_merge.py). Returns True when a row changed."""
    if store is None:
        sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
        import store  # noqa: E402
    today = today or datetime.date.today().isoformat()
    rows = store.load('jobs')
    for j in rows:
        if j.get('id') != job_id:
            continue
        form = {'kind': hits[0]['kind'], 'label': hits[0]['label'][:200], 'at': today}
        if j.get('elig_form') == form and j.get('elig') == '不可投':
            return False
        j['elig_form'] = form
        apply_form(j)
        store.save('jobs', rows)
        return True
    return False


REASON = '申请表要求美国公民/绿卡、安全许可或出口管制身份（JD 没写，表单里才出现）'


def apply_form(j):
    """Pure: a row with elig_form is 不可投 (unless already closed / not eligible). Used by mark_store and the merge step."""
    f = j.get('elig_form')
    if not isinstance(f, dict) or j.get('elig') in ('不可投', '已关闭'):
        return j
    codes = [c for c in str(j.get('elig_codes') or '').split(',') if c and c != 'FORM_RESTRICTION']
    j.update(elig='不可投', elig_reason=REASON, elig_codes=','.join(codes + ['FORM_RESTRICTION']),
             elig_evidence=('form: ' + f.get('label', ''))[:180])
    j['elig_base'] = '不可投'
    if 'tier_orig' not in j:
        j['tier_orig'] = j.get('tier')
    j['tier'] = 'Blocked'
    return j


def check_batch(status, apps, cand=None, mark=None, log=print):
    """prep_batch.py's one call. status: the prep rows; apps(folder) -> path. A restricted row: status 'ineligible_form',
    why, form_restriction; the store row is marked (mark(job_id, hits); failures are logged, never raised)."""
    cand = candidate() if cand is None else cand
    mark = mark or mark_store
    for row in status:
        if row.get('status') not in ('ok', 'flagged') or not row.get('folder'):
            continue
        try:
            plan = json.load(open(os.path.join(apps(row['folder']), 'plan.json')))
        except Exception:
            continue
        hits = find(plan)
        if not applies(hits, cand):
            if hits and not cand.get('citizen_or_pr'):
                row['form_note'] = hits
                log(f"⚠ {row.get('company')} | {row.get('title')} | export-control question that may allow a licence — read it before applying: {hits[0]['label'][:100]}")
            continue
        hits = [h for h in hits if h['kind'] in HARD]
        row.update(status='ineligible_form', form_restriction=hits,
                   why=f"form: {hits[0]['kind']} question — {hits[0]['label'][:120]} → 不可投")
        try:
            changed = mark(row.get('id'), hits)
        except Exception as e:
            changed = f'store not updated ({type(e).__name__}: {str(e)[:80]})'
        log(f"⛔ {row.get('company')} | {row.get('title')} | form restriction ({hits[0]['kind']}): {hits[0]['label'][:100]} → 不可投"
            + ('' if changed is True else f' [{changed}]' if isinstance(changed, str) else ' [store already 不可投]'))
    return status


if __name__ == '__main__':   # python3 form_restrictions.py <plan.json> …: print the hits (no store change)
    for p in sys.argv[1:]:
        print(p, json.dumps(find(json.load(open(p))), ensure_ascii=False))
