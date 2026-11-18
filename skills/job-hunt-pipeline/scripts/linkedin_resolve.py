#!/usr/bin/env python3
"""LinkedIn job page → the company's apply link (JSA-178, 2026-11-05; Joey 「现在做」 after the JSA-176 survey).

Most LinkedIn internship listings send the applicant to the company's site (JSA-176: Easy Apply 11 / 292), and the link
is in the page without a click: `a[aria-label="Apply on company website"]` → linkedin.com/safety/go/?url=<company URL>.
This script loads each row's LinkedIn job page ONCE in the job Chrome (CDP 9222, Joey signed in), reads the apply
control and writes, through store.py:
  - linkedin_url (the job page), li_apply ('external' | 'easy' | 'closed' | 'unknown'), li_apply_reason, li_apply_on;
  - external: apply_url = the company link (cleaned: LinkedIn redirect unwrapped, tracking parameters dropped); and
    ats_url when that link is one posting on a known ATS (same rule as wellfound_apply.pick_external) and the row has
    no ats_url yet → the existing runners take it;
  - closed ("No longer accepting applications", or "Not currently accepting applications" in the top card without a
    visible apply control — JSA-313): elig = 已关闭 with the reason (the gate's own value for a closed posting).
Never clicks, types, saves, follows or applies. 8–15 s between page loads; a sign-in page, a security check / CAPTCHA
or "unusual activity" stops the run at once — nothing is solved or signed in. One tab of its own, closed at the end.

Rows: store rows whose url is a LinkedIn job page and that have no ats_url, plus (--wellfound <method B .json>) the
Wellfound rows whose "Apply on website" opened a LinkedIn job page (JSA-171).
usage:
  ~/.job-agent-venv/bin/python linkedin_resolve.py [--wellfound <json>] [--ids J1,J2] [--limit N] [--save pages.json]
  python3 linkedin_resolve.py --json pages.json [--wellfound <json>] [--write]     # saved records, no browser
Without --write: counts and one line per row only. Tests (rule 13): scripts/test_linkedin_resolve.py.
"""
import json, os, random, re, sys, time, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from linkedin_search import job_id  # noqa: E402
import linkedin_survey as LS  # noqa: E402  (APPLY_JS, classify_button, SIGNIN / BLOCK)
from wellfound_apply import clean_url, posting_like  # noqa: E402
from platform_counts import platform_of  # noqa: E402

PAUSE = (8, 15)
REMOVED = re.compile(r'job id provided may not be valid|job posting has been removed|this job is no longer available|not currently accepting applications', re.I)   # live 11-05 (the last one: 51 of 54 unread pages)


# ---------- pure (tested) ----------
def company_link(href):
    """Pure (tested). An apply control's href → the company URL: LinkedIn's redirect (/safety/go/?url=…,
    /redir/redirect?url=…) unwrapped, tracking parameters dropped (wellfound_apply.clean_url). '' when the href is empty,
    not http(s), or still a linkedin.com page."""
    u = clean_url(href)
    if not u:
        return ''
    h = (re.match(r'https?://([^/?#]+)', u, re.I).group(1) or '').lower().split(':')[0]
    if h == 'linkedin.com' or h.endswith('.linkedin.com'):
        return ''
    return u


NOT_ACCEPTING = re.compile(r'(?:not currently|no longer) accepting applications', re.I)   # JSA-313: top-card closed note


def _pick(ctls, visible_only):
    """The first control (visible ones only when visible_only) whose text, else aria-label, reads Easy Apply / Apply →
    ('easy' | 'external', control), or (None, None)."""
    for c in ctls:
        if visible_only and not c.get('visible'):
            continue
        k = LS.classify_button(c.get('text') or '')
        if k == 'unknown':
            k = LS.classify_button(c.get('aria') or '')
        if k in ('easy', 'external'):
            return k, c
    return None, None


def resolve(info):
    """Pure (tested). What the job page showed {controls: [{text, aria, href, visible}], closed: bool, head: str} →
    {'li_apply', 'reason', 'apply_url', 'ats_url'}. Order:
      0. no controls and the head says the posting was removed ("Job id provided may not be valid", "job posting has
         been removed", "This job is no longer available", "Not currently accepting applications") → 'closed';
      1. closed (APPLY_JS: "No longer accepting applications" anywhere in the page) → 'closed';
      2. the first VISIBLE control whose text, else aria-label, reads Easy Apply → 'easy', or Apply → 'external' with
         its company link (apply_url) and, when that link is one posting on a known ATS, ats_url;
      3. the head says "Not currently accepting applications" / "No longer accepting applications" → 'closed', even
         when the page has other, non-apply controls ("Tailor my resume", "Show match details"; JSA-313, J02867).
         A visible apply control (step 2) wins over this note: wrongly closing an open job drops it from every batch,
         while a wrongly open one is caught later by the gate / the runner reading the live form;
      4. the same as step 2 for hidden controls;
      5. nothing readable → 'unknown'."""
    out = {'li_apply': 'unknown', 'reason': 'no apply control on the page', 'apply_url': '', 'ats_url': ''}
    head = str(info.get('head') or '')
    if REMOVED.search(head) and not info.get('controls'):
        out.update(li_apply='closed', reason='LinkedIn: the job posting has been removed')
        return out
    if info.get('closed'):
        out.update(li_apply='closed', reason='LinkedIn: No longer accepting applications')
        return out
    ctls = info.get('controls') or []
    k, c = _pick(ctls, True)
    if not k:
        m = NOT_ACCEPTING.search(head)
        if m:
            out.update(li_apply='closed', reason=f'LinkedIn: {m.group(0)[0].upper()}{m.group(0)[1:].lower()}')
            return out
        k, c = _pick(ctls, False)
    if k == 'easy':
        out.update(li_apply='easy', reason='LinkedIn Easy Apply (applied inside LinkedIn)')
    elif k == 'external':
        u = company_link(c.get('href'))
        if not u:
            out.update(li_apply='external', reason='Apply goes to the company site; its link was not in the page')
            return out
        plat = platform_of(u)
        ats = u if plat and posting_like(u) else ''
        out.update(li_apply='external', apply_url=u, ats_url=ats,
                   reason=f'apply link → {plat}' if ats else (f'apply link → {plat} (not one posting)' if plat else 'apply link → company site'))
    return out


def apply_row(row, res, li_url, today):
    """Pure (tested). Write one resolve() result onto a store row. Always: linkedin_url, li_apply, li_apply_reason,
    li_apply_on. external: apply_url (when the row has none or it is a linkedin.com link); ats_url + ats_resolved /
    ats_resolved_on only when the row has no ats_url yet. closed: elig = 已关闭, elig_reason, elig_checked = today. Returns
    the row."""
    row.update(linkedin_url=li_url, li_apply=res['li_apply'], li_apply_reason=res['reason'], li_apply_on=today)
    if res['li_apply'] == 'external' and res.get('apply_url'):
        cur = str(row.get('apply_url') or '')
        if not cur or 'linkedin.com' in cur.lower():
            row['apply_url'] = res['apply_url']
        if res.get('ats_url') and not row.get('ats_url'):
            row.update(ats_url=res['ats_url'], ats_resolved='linkedin apply link (JSA-178)', ats_resolved_on=today)
            row.pop('ats_unresolved', None)
    if res['li_apply'] == 'closed':
        row.update(elig='已关闭', elig_reason=res['reason'], elig_checked=today)
    return row


def targets(rows, wellfound_pages=None, redo=False):
    """Pure (tested). [(row id, LinkedIn job id)] in store order, each row once: rows whose url is a LinkedIn job page,
    plus rows named in the Wellfound method B pages (pages[].id) whose opened URLs include a LinkedIn job page. Rows
    with an ats_url, or (without redo) a li_apply value already, are skipped; rows that are 不可投 / 已关闭 / 重复 too.
    Order (most useful first; a run is capped with --limit): 可投 rows before the rest, then tier A, B, C, D, other;
    then internships before other levels; ties keep store order."""
    wf = {}
    for pg in wellfound_pages or []:
        for u in pg.get('opened') or []:
            j = job_id(u)
            if j:
                wf.setdefault(pg.get('id'), j)
                break
    out = []
    for r in rows:
        j = job_id(r.get('url')) or wf.get(r.get('id'))
        if not j or r.get('ats_url') or (r.get('li_apply') and not redo):
            continue
        if (r.get('elig') or '') in ('不可投', '已关闭', '重复'):
            continue
        out.append((r, j))
    tier = {'A': 0, 'B': 1, 'C': 2, 'D': 3}
    key = lambda x: ((x[1][0].get('elig') or '') != '可投', tier.get(x[1][0].get('tier'), 4),
                     not re.match(r'intern', str(x[1][0].get('level') or ''), re.I), x[0])
    return [(r['id'], j) for _, (r, j) in sorted(enumerate(out), key=key)]


# ---------- browser (job Chrome; not part of the pure step) ----------
class Stop(Exception):
    pass


def read_pages(todo, cdp='http://127.0.0.1:9222', save=None):
    from playwright.sync_api import sync_playwright
    recs = []
    with sync_playwright() as p:
        ctx = p.chromium.connect_over_cdp(cdp).contexts[0]
        pg = ctx.new_page(); pg.set_viewport_size({'width': 1300, 'height': 900})
        try:
            for n, (rid, jid) in enumerate(todo):
                if n:
                    time.sleep(random.uniform(*PAUSE))
                url = f'https://www.linkedin.com/jobs/view/{jid}/'
                t0 = time.time()
                pg.goto(url, wait_until='domcontentloaded', timeout=60000)
                pg.wait_for_timeout(4500)
                body, title = pg.inner_text('body')[:4000], pg.title()
                if LS.SIGNIN.search(pg.url) or (re.search(r'\bjoin now\b', body[:800], re.I) and re.search(r'\bsign in\b', body[:800], re.I)):
                    raise Stop(f'sign-in page at {pg.url[:140]}')
                if LS.BLOCK.search(title) or (len(body) < 1500 and LS.BLOCK.search(body)) or re.search(r'unusual activity|quick security check|complete (?:a|this) security check', body[:2000], re.I):
                    raise Stop(f'security check / unusual activity at {pg.url[:140]}')
                info = {'controls': [], 'closed': False, 'head': ''}
                for wait in (8000, 5000):                  # the top card's Apply loads late on some pages (live 11-05: 50 / 160)
                    try:
                        pg.wait_for_selector('.jobs-apply-button, button[aria-label*="pply"], a[aria-label*="pply"], '
                                             'button:has-text("Apply"), a:has-text("Apply")', timeout=wait)
                    except Exception:
                        pass
                    info = pg.evaluate(LS.APPLY_JS)
                    if info['controls'] or info['closed'] or REMOVED.search(info['head'] or ''):
                        break
                    pg.mouse.wheel(0, 400); pg.wait_for_timeout(1500)
                rec = {'id': rid, 'job_id': jid, 'url': url, 'final_url': pg.url[:300], 'controls': info['controls'],
                       'closed': info['closed'], 'head': info['head'][:600], 'secs': round(time.time() - t0, 1)}
                recs.append(rec)
                res = resolve(rec)
                print(f"  {rid} {jid} {res['li_apply']:8} | {res['reason'][:70]} | {rec['secs']} s", flush=True)
                if save:
                    json.dump({'pages': recs}, open(save, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
        except Stop as e:
            print('STOPPED:', e, '— nothing solved; sign in / clear it, then run again', flush=True)
        finally:
            try:
                pg.close()
            except Exception:
                pass
    return recs


def main(a):
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store'))
    import store
    from collections import Counter
    jobs = store.load('jobs')
    wfp = json.load(open(a[a.index('--wellfound') + 1], encoding='utf-8')).get('pages') if '--wellfound' in a else []
    todo = targets(jobs, wfp, '--redo' in a)
    if '--ids' in a:
        want = a[a.index('--ids') + 1].split(',')
        todo = [t for t in todo if t[0] in want]
    if '--limit' in a:
        todo = todo[:int(a[a.index('--limit') + 1])]
    if '--json' in a:
        recs = json.load(open(a[a.index('--json') + 1], encoding='utf-8')).get('pages') or []
        print(f'{len(recs)} saved pages')
    else:
        print(f'{len(todo)} rows with a LinkedIn job page to read (job Chrome, one tab, {PAUSE[0]}–{PAUSE[1]} s apart)', flush=True)
        recs = read_pages(todo, save=a[a.index('--save') + 1] if '--save' in a else None)
    results = [(r, resolve(r)) for r in recs]
    c = Counter(res['li_apply'] for _, res in results)
    plats = Counter(platform_of(res['ats_url']) for _, res in results if res['ats_url'])
    print('li_apply: ' + ' · '.join(f'{k} {v}' for k, v in c.most_common()) +
          ('  |  ats_url: ' + ' · '.join(f'{k} {v}' for k, v in plats.most_common()) if plats else ''))
    if '--write' not in a:
        return 0
    by_id, today = {j['id']: j for j in jobs}, dt.date.today().isoformat()
    n = 0
    for rec, res in results:
        if rec['id'] in by_id:
            apply_row(by_id[rec['id']], res, rec['url'], today); n += 1
    store.save('jobs', jobs)
    print(f"written: {n} rows · {sum(1 for _, r in results if r['ats_url'])} ats_url · {c.get('closed', 0)} → 已关闭")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
