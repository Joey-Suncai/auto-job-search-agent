#!/usr/bin/env python3
"""Find out what material THIS form actually asks for, and write requirements.json.

    python3 materials_probe.py "<app folder>"                 # offline (Greenhouse API dump)
    python3 materials_probe.py "<app folder>" --live [--url U] # enumerate the open page over CDP (any ATS)

Output (requirements.json): every requirement carries the evidence that produced it, so "why does this need a
cover letter" is auditable instead of being a model's impression.
    {"ats": "greenhouse|workday|other", "source": "gh_api|live_form", "checked_at": "...",
     "requirements": [{"kind": "resume", "required": true, "evidence": "...", "selector": "...", "source": "gh_api"}]}

Kinds: resume · cover_letter · essay · transcript · portfolio · other_file · unknown.
"""
import argparse, json, os, re, sys, time

KINDS = [
    ('resume', r'\bresume\b|\bcv\b|curriculum vitae'),
    ('cover_letter', r'cover letter|covering letter|letter of interest'),
    ('transcript', r'transcript|academic record|grade report'),
    ('portfolio', r'portfolio|github|website|personal site'),
    ('essay', r'why (do|are) you|tell us|describe|essay|statement|in \d+ words'),
]


def classify(label, ftype=''):
    low = (label or '').lower()
    for kind, rx in KINDS:
        if re.search(rx, low, re.I):
            return kind
    if ftype in ('input_file', 'file'):
        return 'other_file'
    if ftype in ('textarea',):
        return 'essay' if len(low) > 24 else 'other_file'
    return 'unknown'


# Greenhouse file slots (JSA-209, Viking 10-31): an extra slot whose label merely MENTIONS the resume ("upload your resume
# and brief research supplement — as a single PDF") is not the resume slot. Spec: scripts/test_cases/gh_file_slots_spec.md.
SLOT_DOCS = [
    ('resume', r'\bresum[eé]s?\b|r[eé]sum[eé]|\bcv\b|curriculum vitae'),
    ('cover_letter', r'cover(ing)? letter|letter of interest|motivation letter'),
    ('transcript', r'transcript|academic record|grade report'),
]
SLOT_OTHER = re.compile(r'supplement|writing sample|work sample|code sample|portfolio|project|research|\bpapers?\b|publication|'
                        r'essay|statement|certificate|recommendation|reference letter|case stud', re.I)
# a GRADUATE transcript slot ("Graduate Transcript", "Transcript (Graduate, if applicable)", "Master's transcript"): he has
# none yet (M.S. in progress) — never the undergraduate transcript there; Joey 2026-11-05: skip such jobs (JSA-216)
GRAD_TRANSCRIPT = re.compile(r"(?<!under)(?<!under-)(?<!under )\b(graduate|grad school|master'?s|m\.s\.|ms|post[- ]?graduate)(?!\w)[^?!]{0,25}\btranscripts?\b"
                             r"|\btranscripts?\b[^.?!]{0,10}\(\s*(graduate|grad)\b", re.I)
SLOT_COMBINE = re.compile(r'\bmerge[ds]?\b|\bcombine[ds]?\b|\b(single|one) (pdf|file|document)\b|\btogether\b', re.I)


def slot_kind(name, label):
    """Pure (tested). The kind of one Greenhouse file slot: the standard `resume` / `cover_letter` fields by name; any other
    (a posting's own input_file question) from its label — exactly one of resume / cover letter / transcript and no other
    document or combine wording → that kind, else other_file (only the candidate can supply it)."""
    if name in ('resume', 'cover_letter'):
        return name
    low = label or ''
    if GRAD_TRANSCRIPT.search(low):
        return 'grad_transcript'
    hits = [k for k, rx in SLOT_DOCS if re.search(rx, low, re.I)]
    if len(hits) == 1 and not SLOT_OTHER.search(low) and not SLOT_COMBINE.search(low):
        return hits[0]
    return 'other_file'


def probe_greenhouse(folder):
    path = os.path.join(folder, 'gh_api.json')
    if not os.path.exists(path):
        return None
    d = json.load(open(path, encoding='utf-8'))
    reqs = []
    for q in d.get('questions') or []:
        for f in (q.get('fields') or []):
            ftype = f.get('type') or ''
            if ftype in ('input_file', 'file'):          # every file slot, standard or extra (JSA-209)
                name = f.get('name') or ''
                reqs.append({'kind': slot_kind(name, q.get('label')), 'required': bool(q.get('required')),
                             'evidence': "%s (%s)" % (q.get('label'), ftype), 'selector': name, 'source': 'gh_api',
                             'slot': 'standard' if name in ('resume', 'cover_letter') else 'extra',
                             'label': (q.get('label') or '')[:300]})
                continue
            kind = classify(q.get('label'), ftype)
            if kind in ('unknown', 'other_file'):
                continue
            reqs.append({'kind': kind, 'required': bool(q.get('required')),
                         'evidence': "%s (%s)" % (q.get('label'), ftype or 'field'),
                         'selector': f.get('name') or '', 'source': 'gh_api'})
    return {'ats': 'greenhouse', 'source': 'gh_api', 'version': GH_VERSION, 'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'requirements': reqs}


GH_VERSION = 2      # 2 = file slots classified by slot_kind (JSA-209); an older gh_api requirements.json is re-probed


JS_ENUM = """() => {
  const out = [];
  document.querySelectorAll('input[type=file]').forEach(el => {
    const lab = el.closest('label') || document.querySelector('label[for="' + el.id + '"]');
    const box = el.closest('[data-automation-id^="formField-"], fieldset, div');
    const txt = (lab && lab.innerText || (box && box.innerText) || el.name || '').trim().slice(0, 120);
    out.push({tag: 'file', label: txt, id: el.name || el.id || ''});
  });
  document.querySelectorAll('textarea').forEach(el => {
    const lab = el.closest('label') || document.querySelector('label[for="' + el.id + '"]');
    const box = el.closest('[data-automation-id^="formField-"], fieldset, div');
    const txt = (lab && lab.innerText || (box && box.innerText) || '').trim().slice(0, 200);
    out.push({tag: 'textarea', label: txt, id: el.name || el.id || ''});
  });
  return out;
}"""


def probe_live(folder, url=None, cdp='http://127.0.0.1:9222'):
    from playwright.sync_api import sync_playwright
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'runner'))
    import cdp_connect                                        # JSA-386: opens a tab when the job Chrome has none
    with sync_playwright() as pw:
        b = cdp_connect.connect(pw, cdp)
        ctx = b.contexts[0]
        page = None
        if url:
            page = next((p for p in ctx.pages if url[:60] in p.url), None)
            if page is None:
                page = ctx.new_page(); page.goto(url, wait_until='domcontentloaded'); page.wait_for_timeout(2500)
        else:                                  # prefer the ATS tab, never whatever happens to be first
            page = (next((x for x in ctx.pages if 'myworkday' in x.url), None)
                    or next((x for x in ctx.pages if 'greenhouse' in x.url), None)
                    or ctx.pages[0])
        items = page.evaluate(JS_ENUM)
        ats = 'workday' if 'myworkday' in page.url else ('greenhouse' if 'greenhouse' in page.url else 'other')
    reqs = []
    for it in items:
        kind = classify(it.get('label'), 'input_file' if it['tag'] == 'file' else 'textarea')
        if kind == 'unknown':
            continue
        reqs.append({'kind': kind, 'required': None, 'evidence': it.get('label', '')[:120],
                     'selector': it.get('id', ''), 'source': 'live_form'})
    return {'ats': ats, 'source': 'live_form', 'url': page.url, 'checked_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'requirements': reqs}


def probe(folder, live=False, url=None, cdp='http://127.0.0.1:9222'):
    data = probe_live(folder, url, cdp) if live else probe_greenhouse(folder)
    if data is None:
        raise SystemExit('nothing to probe: no gh_api.json (use --live)')
    out = os.path.join(folder, 'requirements.json')
    json.dump(data, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return out, data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--live', action='store_true')
    ap.add_argument('--url'); ap.add_argument('--cdp', default='http://127.0.0.1:9222')
    a = ap.parse_args()
    out, data = probe(a.folder, a.live, a.url, a.cdp)
    print('wrote', out)
    for r in data['requirements']:
        print("  %-13s required=%-5s %s" % (r['kind'], r['required'], r['evidence'][:80]))


if __name__ == '__main__':
    main()
