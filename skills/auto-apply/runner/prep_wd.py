#!/usr/bin/env python3
"""Prepare Workday applications (Mac, venv python): folder + pin, wd_job.json, jd.md (public Workday CXS API), eligibility flags.

  ~/.job-agent-venv/bin/python prep_wd.py ../../../data/runner/batches/<name>.json
batch: {"name","date","jobs":[{"id","company","title","url","track"}]}  (Workday URLs: *.myworkdayjobs.com / myworkdaysite.com)
Questions are not public on Workday → run_wd.py reads them page by page and stops with wd_needs.json for anything unknown.
"""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import json, os, re, subprocess, sys, urllib.request
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', 'config'))   # the repo's config/ (JSA-184: '..' alone = skills/auto-apply/config, missing in the release)
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
from prep_batch import text_of, slug, ROOT
import posting as PO  # noqa: E402  (JSA-331: look jobs up by ats_url first)
import app_folder as AF  # noqa: E402  (JSA-319: one folder per job — found by job id first)
try:
    from prefilter import RX as FLAGS
except Exception:
    FLAGS = {}


def cxs_url(url):
    u = re.sub(r'\?.*$', '', url)
    m = re.match(r'https://([\w.-]+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?([^/]+)/(job/.+)$', u)
    if m:
        host, site, rest = m.groups(); tenant = host.split('.')[0]
        return f'https://{host}/wday/cxs/{tenant}/{site}/{rest}'
    m = re.match(r'https://([\w.-]+\.myworkdaysite\.com)/(?:[a-z]{2}-[A-Z]{2}/)?recruiting/([^/]+)/([^/]+)/(job/.+)$', u)
    if m:
        host, tenant, site, rest = m.groups()
        return f'https://{host}/wday/cxs/{tenant}/{site}/{rest}'
    return None


def fetch(api):
    req = urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code in (404, 410): return None
        return via_chrome(api)                          # 403 etc.: some tenants refuse scripts → ask through the job Chrome
    except Exception:
        return via_chrome(api)


def via_chrome(api):
    try:                                   # CA-cert issue on python.org builds → read it through the job Chrome
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            page = cdp_connect.connect(pw, 'http://127.0.0.1:9222').contexts[0].new_page()
            r = page.request.get(api, headers={'Accept': 'application/json'}); page.close()
            return r.json() if r.ok else None
    except Exception:
        return None


def resolve(url):
    """Aggregator links (zapply.jobs, simplify …) → the real Workday URL by following redirects."""
    if 'myworkday' in url: return url
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=30) as r:
            final = r.geturl(); body = r.read(200000).decode('utf-8', 'ignore')
        if 'myworkday' in final: return final
        m = re.search(r'https://[\w.-]+\.myworkday(?:jobs|site)\.com/[^"\'<> ]+', body)
        return m.group(0) if m else url
    except Exception:
        return url


def main():
    bp = sys.argv[1]; batch = json.load(open(bp)); status = []
    for j in batch['jobs']:
        row = {'id': j['id'], 'company': j['company'], 'title': j['title'], 'ats': 'workday'}
        try:
            j['url'] = resolve(PO.posting_url(j)); api = cxs_url(j['url'])   # JSA-331: ats_url first
            data = fetch(api) if api else None
        except Exception as e:
            api, data = None, None; print(f"✗ {j['company']}: {type(e).__name__} {str(e)[:80]}")
        info = (data or {}).get('jobPostingInfo')
        if not info:
            row['status'] = 'closed_or_unreadable'; status.append(row); print(f"✗ {j['company']}: posting not found ({api})"); continue
        jd = text_of(info.get('jobDescription'))
        flags = [k for k, rx in FLAGS.items() if rx.search(jd)]
        folder = AF.for_job(j['id'], batch['date'], j['company'], j['title'], jpaths.apps(), AF.submitted_fn())   # JSA-319
        try: subprocess.run(['xattr', '-w', 'com.apple.fileprovider.pinned#PX', '1', folder], capture_output=True)
        except FileNotFoundError: pass
        json.dump({'url': j['url'], 'api': api, 'id': j['id'], 'company': j['company'], 'title': info.get('title'), 'track': j.get('track'),
                   'location': info.get('location'), 'timeType': info.get('timeType'), 'startDate': info.get('startDate'),
                   'jobReqId': info.get('jobReqId')}, open(os.path.join(folder, 'wd_job.json'), 'w'), ensure_ascii=False, indent=1)
        open(os.path.join(folder, 'jd.md'), 'w', encoding='utf-8').write(
            f"# {info.get('title')} — {j['company']}\nURL: {j['url']}\nLocation: {info.get('location')}\nTime type: {info.get('timeType')}\n\n{jd}\n")
        if not os.path.exists(os.path.join(folder, 'questions.json')):
            json.dump([], open(os.path.join(folder, 'questions.json'), 'w'))
        row.update(status='flagged' if flags else 'ok', flags=flags, folder=os.path.basename(folder), track=j.get('track'))
        status.append(row)
        print(f"{'⚠' if flags else '✓'} {j['company']} | {info.get('title')} | {info.get('location')} | flags={flags} | {os.path.basename(folder)}")
    json.dump(status, open(bp.replace('.json', '.status.json'), 'w'), ensure_ascii=False, indent=1)
    print('status →', bp.replace('.json', '.status.json'))


if __name__ == '__main__':
    main()
