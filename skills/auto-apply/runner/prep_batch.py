#!/usr/bin/env python3
"""Prepare a batch of Greenhouse / Lever / Ashby applications on Joey's Mac (network access needed — run in Terminal with the venv python).

  ~/.job-agent-venv/bin/python prep_batch.py batches/<name>.json

batch file: {"name": "...", "date": "2026-10-28", "jobs": [{"id","company","title","url","track"}]}
Per job:
  - resolves the Greenhouse board + job id (job-boards URL, embed URL or company page with gh_jid=)
  - fetches the public API (questions=true) → <folder>/gh_api.json; JD text → <folder>/jd.md
  - closed posting (404) → status closed; eligibility flags on the JD (same regexes as prefilter.py) → status flagged
  - creates applications/<date>_<Company>_<Title>/ and pins it in iCloud (xattr, Keep Downloaded)
  - writes questions.json (open-ended questions for ds_materials.py) and plan.json (plan_build), url = embed form URL
Writes <batch>.status.json and prints one line per job + every needs_user question.
Tasks only Joey can do (record a video: Loom, HireVue, …; JSA-141, Joey 2026-11-04): in a test batch (`"purpose": "cert"`,
or "cert" in the batch name) the job is skipped (status skipped_joey_task); in a real batch it stays and the row lists
`joey_tasks` — never skipped there, Joey does them.
"""
import html, json, os, re, subprocess, sys, urllib.request
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import plan_build as PB

try:
    from prefilter import RX as FLAGS            # CLEAR / NOSPON / DEG / START … (same rules as the batch pre-filter)
except Exception:
    FLAGS = {}


def gh_ids(url, company):
    m = re.search(r'greenhouse\.io/(?:embed/job_app\?for=)?([\w-]+)(?:/jobs/|&token=)(\d+)', url)
    if m:
        return [(m.group(1), m.group(2))]
    m = re.search(r'gh_jid=(\d+)', url)
    if m:
        base = re.sub(r'[^a-z0-9]', '', company.lower())
        host = re.sub(r'^www\.|\..*$', '', re.sub(r'^https?://', '', url))
        return [(b, m.group(1)) for b in dict.fromkeys([host, base, base + 'llc', base + 'inc'])]
    return []


def fetch(board, job):
    api = f'https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job}?questions=true'
    try:
        with urllib.request.urlopen(urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0'}), timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return PB.gh_fetch(board, job)     # falls back to the job Chrome (CA-cert issues)


def text_of(content):
    t = html.unescape(content or '')
    t = re.sub(r'<(br|/p|/li|/h\d)[^>]*>', '\n', t, flags=re.I)
    t = re.sub(r'<li[^>]*>', '\n- ', t, flags=re.I)
    t = re.sub(r'<[^>]+>', '', t)
    return re.sub(r'\n{3,}', '\n\n', html.unescape(t)).strip()


def slug(s, n=40):
    return re.sub(r'_+', '_', re.sub(r'[^A-Za-z0-9]+', '_', s)).strip('_')[:n]


MOTIVE_RE = re.compile(r'\bwhy\b.{0,60}\b(interest|join|apply|want|role|company|us|position|opportunit|internship|team)|what made you (apply|want|interested|choose)|compelling about|what (excite[sd]?|interest(s|ed)?|draws|drew|attract(s|ed)?) you|interest(s|ed)? you about|motivat', re.I)   # Joey 2026-10-31: always answer "why us" even when optional (an Ashby employer)


LIMIT_RE = re.compile(r'(\d{2,5})\s*(?:-\s*)?(?:char(?:acter)?s?)\b(?:\s*(?:limit|max(?:imum)?))?|(?:limit|max(?:imum)?)(?: of)?\s*(\d{2,5})\s*char', re.I)


def answer_limit(label, ftype=None):
    """Character limit for a drafted answer: a limit stated in the label wins; a single-line text box (Greenhouse
    input_text) holds 255 characters (a Greenhouse employer 2026-10-31: a 600-character answer was cut); otherwise 1200."""
    m = LIMIT_RE.search(label or '')
    if m:
        return int(m.group(1) or m.group(2))
    return 255 if ftype == 'text' else 1200


def optional_essay(f):
    """Pure (tested). An optional free-text question worth answering (Joey 2026-11-04: Pattern's "What is the coolest thing you
    have ever built using AI?" was left blank): a textarea whose label is a question ('?') or starts with Describe / Tell us /
    Share / Explain — never a survey, consent or demographic field, never a referral name. Drafted by ds_materials like the
    "why us" boxes (JSA-144)."""
    lab = f.get('label') or ''
    if f.get('type') != 'textarea' or f.get('survey') or f.get('consent') or f.get('demographic') or f.get('required'):
        return False
    if re.search(r'refer(red|ral)|who referred|pronoun', lab, re.I):
        return False
    return '?' in lab or bool(re.match(r'\s*(describe|tell us|share|explain|walk us through)\b', lab, re.I))


def open_qs(plan):
    """Open questions for ds_materials: required free-text unknowns + optional "why this job / company" boxes."""
    types = {f['key']: f.get('type') for f in plan.get('fields', [])}
    descs = {f['key']: f['description'] for f in plan.get('fields', []) if f.get('description')}   # an option list in the question's description
    qs = [{'id': n['key'], 'label': n['label'], 'limit': answer_limit(n['label'], types.get(n['key']))} for n in plan['needs_user']
          if not n.get('options') and not n.get('survey') and not FACT_FORMAT.search(n['label']) and (OPEN_RE.search(n['label']) or len(n['label']) > 60)]   # survey: Joey's own answer, never drafted (JSA-075)
    have = {q['id'] for q in qs}
    qs += [{'id': f['key'], 'label': f['label'], 'limit': answer_limit(f['label'], f.get('type'))} for f in plan['fields']
           if f['key'] not in have and (f.get('source') == 'open_answers.md' or (f.get('type') in ('text', 'textarea') and not f.get('answer') and (MOTIVE_RE.search(f.get('label') or '') or optional_essay(f))))]   # keep answered ones: a rerun of ds_materials must not lose them
    for q in qs:
        if descs.get(q['id']):
            q['description'] = descs[q['id']]
    return qs


FACT_FORMAT = re.compile(r'\bmm\s*/\s*(dd\s*/\s*)?yyyy\b|\byyyy\b|in (the )?format|\bdate format\b', re.I)   # a fact in a given format, never an essay for DeepSeek (a Lever employer 11-04, JSA-150)
OPEN_RE = re.compile(r'\b(why|describe|tell us|explain|what (excites|interests|makes)|share|cover letter|anything else|additional information)\b', re.I)


JOEY_TASK = re.compile(r'\b(?:video|loom|vimeo|hirevue|vidcruiter|spark ?hire|willo|record(?:ed|ing)? (?:yourself|a|an|your))\b', re.I)


def joey_tasks(plan):
    """Pure (tested). The questions in plan['needs_user'] that ask Joey to record something (a video / Loom link / a
    recorded answer) → their labels. Text answers, file uploads of documents and ratings are not Joey-only tasks here."""
    return [n['label'] for n in plan.get('needs_user') or [] if JOEY_TASK.search(n.get('label') or '')]


def joey_files(reqs, folder):
    """Pure (tested). Required extra Greenhouse file slots (requirements.json, slot 'extra') that only Joey can supply — kind
    other_file / portfolio, or a transcript when the profile has none — and that answers.json does not already name a file
    for → [{key, label}] (JSA-209, Viking 10-31: a research supplement merged with the resume)."""
    import materials_gate
    try:
        answers = json.load(open(os.path.join(folder, 'answers.json'), encoding='utf-8'))
    except (OSError, ValueError):
        answers = {}
    out = []
    for r in reqs or []:
        if r.get('slot') != 'extra' or not r.get('required'):
            continue
        own = r.get('kind') in ('other_file', 'portfolio') or (
            r.get('kind') == 'transcript' and not (materials_gate.TRANSCRIPT and os.path.exists(materials_gate.TRANSCRIPT)))
        if own and not materials_gate.supplied_file(folder, answers if isinstance(answers, dict) else {}, r.get('selector')):
            out.append({'key': r.get('selector'), 'label': r.get('label') or r.get('evidence') or ''})
    return out


def file_requirements(folder, row):
    """Greenhouse: requirements.json from gh_api.json at prep time — every file slot, standard and extra (JSA-209);
    the required ones only Joey can supply go into the row (joey_files) and are printed."""
    try:
        import materials_probe
        _, data = materials_probe.probe(folder)
    except BaseException as e:                     # never break a prep: the runner's material gate probes again
        print(f"    ! requirements.json not written: {type(e).__name__} {str(e)[:80]}"); return row
    grad = [r for r in data.get('requirements') or [] if r.get('kind') == 'grad_transcript']
    if grad:                                       # JSA-216 (Joey 2026-11-05): no graduate transcript yet → skip the job
        row['status'] = 'skipped_grad_transcript'
        print(f"    ⏭ skipped: the form asks for a graduate transcript: {(grad[0].get('label') or '')[:120]}")
        return row
    files = joey_files(data.get('requirements'), folder)
    if files:
        row['joey_files'] = files
        for f in files:
            print(f"    📎 needs a file from Joey (required file slot {f['key']}): {f['label'][:140]}")
    return row


def is_test_batch(batch):
    """Pure (tested). A certification / test batch: purpose 'cert', or 'cert' in its name."""
    return batch.get('purpose') == 'cert' or 'cert' in (batch.get('name') or '').lower()


def joey_gate(row, plan, test):
    """Pure (tested). Adds joey_tasks to the row; in a test batch a row with any becomes skipped_joey_task."""
    t = joey_tasks(plan)
    if t:
        row['joey_tasks'] = t
        if test and row.get('status') in ('ok', 'flagged'):
            row['status'] = 'skipped_joey_task'
    return row


def prep_other(j, url, date, test=False):
    """Lever / Ashby: folder, jd.md, <ats>_job.json, plan.json (url = the apply form), questions.json."""
    row = {'id': j['id'], 'company': j['company'], 'title': j['title']}
    try:
        if 'lever.co' in url:
            ats = 'lever'; site, jid = PB.lever_parse_url(url)
            post = json.loads(PB._get(f'https://api.lever.co/v0/postings/{site}/{jid}'))
            jd = (post.get('descriptionPlain') or '') + '\n\n' + '\n\n'.join(
                f"{l.get('text')}\n" + text_of(l.get('content')) for l in post.get('lists') or []) + '\n\n' + (post.get('additionalPlain') or '')
            title, loc = post.get('text'), (post.get('categories') or {}).get('location')
            apply_url = f'https://jobs.lever.co/{site}/{jid}/apply'
            fields = PB.lever_fields(PB.lever_fetch(site, jid)); src = post
        else:
            ats = 'ashby'; org, jid = PB.ashby_parse_url(url)
            post = PB.ashby_fetch(org, jid)
            title, loc, apply_url = post.get('title'), '', f'https://jobs.ashbyhq.com/{org}/{jid}/application'
            jd = text_of(PB.ashby_description(org, jid))
            fields = PB.ashby_fields(post); src = post
    except BaseException as e:                     # SystemExit from the parsers = posting gone
        row['status'] = 'closed_or_unreadable'; row['why'] = str(e)[:160]; print(f"✗ {j['company']}: {row['why']}"); return row
    flags = [k for k, rx in FLAGS.items() if rx.search(jd)]
    folder = jpaths.apps(f"{date}_{slug(j['company'], 20)}_{slug(j['title'])}")
    os.makedirs(folder, exist_ok=True)
    json.dump(src, open(os.path.join(folder, f'{ats}_job.json'), 'w'), ensure_ascii=False, indent=1)
    open(os.path.join(folder, 'jd.md'), 'w', encoding='utf-8').write(f"# {title} — {j['company']}\nURL: {apply_url}\nLocation: {loc or ''}\n\n{jd.strip()}\n")
    json.dump({'id': j['id'], 'company': j['company'], 'title': title, 'url': apply_url, 'ats': ats, 'track': j.get('track')},
              open(os.path.join(folder, 'job.json'), 'w'), ensure_ascii=False, indent=1)
    plan = PB.build(folder, fields, apply_url, ats)
    qs = open_qs(plan)
    json.dump(qs, open(os.path.join(folder, 'questions.json'), 'w'), ensure_ascii=False, indent=1)
    json.dump(plan, open(os.path.join(folder, 'plan.json'), 'w'), ensure_ascii=False, indent=1)
    row.update(status='flagged' if flags else 'ok', flags=flags, folder=os.path.basename(folder), ats=ats, track=j.get('track'),
               embed=apply_url, needs_user=len(plan['needs_user']), open_questions=len(qs))
    joey_gate(row, plan, test)
    print(f"{'⏭' if row['status'] == 'skipped_joey_task' else '⚠' if flags else '✓'} {j['company']} | {title} | {ats} | flags={flags} | needs_user={len(plan['needs_user'])} (open {len(qs)}) | {os.path.basename(folder)}"
          + (f" | Joey task: {row['joey_tasks'][0][:60]}" + (' — skipped (test batch)' if row['status'] == 'skipped_joey_task' else '') if row.get('joey_tasks') else ''))
    for n in plan['needs_user']:
        print(f"    ? {n['label'][:90]}" + (f"  [{' / '.join(n['options'][:6])}]" if n.get('options') else ''))
    return row


def main():
    bp = sys.argv[1]
    batch = json.load(open(bp))
    date = batch.get('date')
    test = is_test_batch(batch)
    status = []
    for j in batch['jobs']:
        row = {'id': j['id'], 'company': j['company'], 'title': j['title']}
        url = j.get('ats_url') or j['url']
        if re.search(r'lever\.co|ashbyhq\.com', url):        # Lever / Ashby (JSA-004 runner, 2026-10-30)
            status.append(prep_other(j, url, date, test)); continue
        data = board = job = None
        for b, jid in gh_ids(j['url'], j['company']):
            d = fetch(b, jid)
            if d:
                data, board, job = d, b, jid; break
        if not data:
            row['status'] = 'closed_or_not_greenhouse'; status.append(row); print(f"✗ {j['company']}: posting not found (closed?)"); continue
        jd = text_of(data.get('content'))
        flags = [k for k, rx in FLAGS.items() if rx.search(jd)]
        folder = jpaths.apps(f"{date}_{slug(j['company'], 20)}_{slug(j['title'])}")
        os.makedirs(folder, exist_ok=True)
        try: subprocess.run(['xattr', '-w', 'com.apple.fileprovider.pinned#PX', '1', folder], capture_output=True)
        except FileNotFoundError: pass   # not macOS (tests)
        json.dump(data, open(os.path.join(folder, 'gh_api.json'), 'w'), ensure_ascii=False)
        open(os.path.join(folder, 'jd.md'), 'w', encoding='utf-8').write(
            f"# {data.get('title')} — {j['company']}\nURL: {data.get('absolute_url') or j['url']}\nLocation: {(data.get('location') or {}).get('name')}\n\n{jd}\n")
        embed = f'https://job-boards.greenhouse.io/embed/job_app?for={board}&token={job}'
        fields = PB.gh_fields(data)
        plan = PB.build(folder, fields, embed, 'greenhouse')
        qs = open_qs(plan)
        json.dump(qs, open(os.path.join(folder, 'questions.json'), 'w'), ensure_ascii=False, indent=1)
        json.dump(plan, open(os.path.join(folder, 'plan.json'), 'w'), ensure_ascii=False, indent=1)
        row.update(status='flagged' if flags else 'ok', flags=flags, folder=os.path.basename(folder), board=board, job=job,
                   track=j.get('track'), embed=embed, needs_user=len(plan['needs_user']), open_questions=len(qs))
        joey_gate(row, plan, test)
        status.append(row)
        print(f"{'⏭' if row['status'] == 'skipped_joey_task' else '⚠' if flags else '✓'} {j['company']} | {data.get('title')} | flags={flags} | needs_user={len(plan['needs_user'])} (open {len(qs)}) | {os.path.basename(folder)}"
              + (f" | Joey task: {row['joey_tasks'][0][:60]}" + (' — skipped (test batch)' if row['status'] == 'skipped_joey_task' else '') if row.get('joey_tasks') else ''))
        for n in plan['needs_user']:
            print(f"    ? {n['label'][:90]}" + (f"  [{' / '.join(n['options'][:6])}]" if n.get('options') else ''))
        file_requirements(folder, row)            # JSA-209: every file slot into requirements.json; Joey's files listed
    sys.path.append(os.path.join(ROOT, 'skills', 'job-hunt-pipeline', 'scripts')); import form_restrictions   # noqa: E402
    form_restrictions.check_batch(status, jpaths.apps)   # JSA-231: export-control / citizens-only form questions → 不可投
    json.dump(status, open(bp.replace('.json', '.status.json'), 'w'), ensure_ascii=False, indent=1)
    print('status →', bp.replace('.json', '.status.json'))


if __name__ == '__main__':
    main()
