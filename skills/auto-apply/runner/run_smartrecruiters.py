#!/usr/bin/env python3
"""SmartRecruiters runner (JSA-112 / JSA-153, 2026-11-04). The apply form is SmartRecruiters' "oneclick-ui" (web components
with open shadow roots, DataDome bot protection — read in the job Chrome only, never fetched from a script):

  page 1  name, e-mail (twice), city (autocomplete), phone, LinkedIn / website, résumé, "Message to the Hiring Team"
  page 2  "Preliminary questions": one `sr-question-field-<type>` per question (radio / select / text / textarea /
          checkbox / files / info), the privacy checkbox, then Submit.

Every field is answered with answer_rules.js (config/profile.json) through rules_bridge.js; prose boxes (the message box =
a cover-letter slot, essays) come from the application folder (cover.txt / open_answers.md, same helpers as Workable —
the runner never drafts). Every field is read back from the page; a required field empty on the page always blocks.
Dry-run by default: stops before Submit.

    ~/.job-agent-venv/bin/python run_smartrecruiters.py --url <posting url> [--resume <pdf>] [--out <dir>]
    ~/.job-agent-venv/bin/python run_smartrecruiters.py --folder applications/<folder> [--submit] [--wait-captcha 10]

--submit: only when every field read back, nothing unknown, the folder is in data/runner/approved_batches.json and not
already submitted. Clicks Submit; an e-mailed authentication code (OTP) is read from Gmail (read-only); a CAPTCHA
(DataDome) is Joey's (push, wait). Confirmed by the thank-you page or the receipt e-mail → submitted, tracker row
(sync_results), the posting's tabs closed. Writes <out>/run_log.md, form_check.json, page1.png / page2.png; one line in
data/runner/results.jsonl. Default out (no --folder): data/runner/dryrun/smartrecruiters/<company>_<id>.
"""
import argparse, json, os, re, subprocess, sys, time, urllib.request
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
DATA = os.environ.get('CX_DATA') or jpaths.data('runner')
RULES = os.path.join(HERE, '..', 'scripts', 'answer_rules.js')
COMPANY = ''                                                   # the hiring company (job.json / store row): referral questions check it against the referrer pool (JSA-195)
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36'}
sys.path.insert(0, HERE)
import run_workable as W  # noqa: E402  (confirmed_page, required_empty, read_open_answers, essay_like, N)

N = W.N


def parse_posting(url):
    """Pure (tested). A SmartRecruiters posting URL → {'company', 'id'} (jobs.smartrecruiters.com/<Company>/<digits>[-slug])
    or {'company', 'uuid'} (…/oneclick-ui/company/<Company>/publication/<uuid>); None otherwise."""
    u = str(url or '').strip()
    m = re.match(r'^https?://jobs\.smartrecruiters\.com/oneclick-ui/company/([\w.-]+)/publication/([0-9a-f-]{36})', u, re.I)
    if m:
        return {'company': m.group(1), 'uuid': m.group(2).lower()}
    m = re.match(r'^https?://(?:jobs|careers)\.smartrecruiters\.com/([\w.-]+)/(\d{6,})(?:[-/?#]|$)', u, re.I)
    if m and m.group(1).lower() != 'oneclick-ui':
        return {'company': m.group(1), 'id': m.group(2)}
    return None


def company_id(d, fallback):
    """Pure (tested). The company identifier as the posting API writes it — the oneclick-ui form is case-sensitive
    (`m3usa` opens /expired, `an employer` the live form; an employer / Winsupply1 2026-11-05): company.identifier, else the
    first path part of applyUrl / postingUrl, else the id as written in the store URL."""
    c = ((d or {}).get('company') or {}).get('identifier')
    if not c:
        m = re.match(r'^https?://(?:jobs|careers)\.smartrecruiters\.com/([\w.-]+)/', str((d or {}).get('applyUrl') or (d or {}).get('postingUrl') or ''), re.I)
        c = m.group(1) if m and m.group(1).lower() != 'oneclick-ui' else None
    return c or fallback


def apply_url(p, fetch=None):
    """The oneclick-ui form URL. The public posting API (api.smartrecruiters.com/v1/companies/<c>/postings/<id or uuid>,
    no key, not behind DataDome; the company part is case-insensitive there) gives the uuid and the company identifier in
    the case the form needs. A oneclick-ui URL whose API lookup fails keeps its own uuid and company."""
    fetch = fetch or (lambda u: json.load(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30)))
    try:
        d = fetch(f"https://api.smartrecruiters.com/v1/companies/{p['company']}/postings/{p.get('uuid') or p['id']}") or {}
    except Exception:
        if not p.get('uuid'):
            raise
        d = {'uuid': p['uuid']}
    if not d.get('uuid') or d.get('active') is False:
        return None
    c = company_id(d, p['company'])
    return f"https://jobs.smartrecruiters.com/oneclick-ui/company/{c}/publication/{d['uuid']}?dcr_ci={c}"


def message_text(text):
    """Pure (tested). The "Message to the Hiring Team" box refuses ';' ("This field cannot contain following characters: ;",
    an employer 2026-11-04): every ';' becomes ',' (one space after it, none before); nothing else changes."""
    t = re.sub(r'[ \t]*(?:;[ \t]*)+', ';', str(text or ''))       # a run of ';' (and the spaces around it) → one ';'
    t = re.sub(r';(?=\n|$)', ',', t)                              # before a line break / at the end: no trailing space
    return t.replace(';', ', ')


def city_option(city, state_abbr):
    """Pure (tested). The autocomplete option text for the candidate's city: 'Chicago, IL, US'."""
    return f'{city}, {state_abbr}, US'


def clean_label(text):
    """Pure (tested). A question wrapper's text → its label: the leading required star and the trailing counter
    ('0 / 200') and '(definitions)' link text dropped."""
    t = N(text)
    t = re.sub(r'^\*\s*', '', t)
    t = re.sub(r'\s*\d+\s*/\s*\d+\s*$', '', t)
    t = re.sub(r'\s*\(definitions?\)\s*', ' ', t)
    return N(t)


# Reads every question wrapper on page 2 (shadow DOM walk): type, label (the slot "label-content" text, else the wrapper
# text before the options), required, the control id, radio options.
READ_Q = r"""() => {
  const all=[]; const walk=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) walk(e.shadowRoot); }); }; walk(document);
  const deep=(e)=>{ let t=''; const w=(n)=>{ if(n.nodeType===3) t+=n.textContent+' '; else if(n.nodeType===1){ if(n.shadowRoot) w(n.shadowRoot); n.childNodes.forEach(w);} else if(n.nodeType===11) n.childNodes.forEach(w); }; w(e); return t.replace(/\s+/g,' ').trim(); };
  return all.filter(e=>/^sr-question-field-/.test(e.tagName.toLowerCase())).map((e,i)=>{
    const type=e.tagName.toLowerCase().replace('sr-question-field-','');
    const slot=e.querySelector('[slot=label-content]');
    const ctl=e.querySelector('spl-radio-group,spl-autocomplete,spl-input,spl-textarea,spl-checkbox,spl-checkbox-group,spl-select');
    const radios=[...e.querySelectorAll('spl-radio')].map(x=>x.getAttribute('label')||deep(x));
    const boxes=[...e.querySelectorAll('spl-checkbox')].map(x=>x.getAttribute('label')||deep(x));
    return {idx:i, type, label: slot?deep(slot):deep(e), text: deep(e).slice(0,600), id: ctl?ctl.id:'', tag: ctl?ctl.tagName.toLowerCase():'',
            required: !!(ctl && ctl.hasAttribute('required')) || /^\*/.test(deep(e)), radios, boxes,
            subs: [...e.querySelectorAll('spl-autocomplete')].map(x=>x.id).filter(Boolean)};
  });
}"""

# The privacy / consent checkbox outside the question wrappers (page 2 footer).
READ_CONSENT = r"""() => {
  const all=[]; const walk=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) walk(e.shadowRoot); }); }; walk(document);
  const deep=(e)=>{ let t=''; const w=(n)=>{ if(n.nodeType===3) t+=n.textContent+' '; else if(n.nodeType===1){ if(n.shadowRoot) w(n.shadowRoot); n.childNodes.forEach(w);} else if(n.nodeType===11) n.childNodes.forEach(w); }; w(e); return t.replace(/\s+/g,' ').trim(); };
  const inQuestion=(e)=>{ let a=e; for(let i=0;i<40 && a;i++){ if(/^sr-question-field-/.test((a.tagName||'').toLowerCase())) return true; a=a.parentElement || (a.getRootNode && a.getRootNode().host) || null; } return false; };
  return all.filter(e=>e.tagName.toLowerCase()==='spl-checkbox' && !inQuestion(e))
            .map(e=>({id:e.id, label: e.getAttribute('label')||deep(e), required: e.hasAttribute('required')}));
}"""


def plan_questions(raw):
    """Pure (tested). READ_Q output → the questions to answer: [{key, label, type, required, options}] — info blocks and
    file slots are left out; key = the control id (question_<uuid> / spl-form-element_<n>); type radio / select / text /
    textarea / checkbox."""
    out = []
    for q in raw or []:
        t = q.get('type')
        if t in ('info', 'files', 'file'):
            continue
        if t == 'eeo':                                            # one block, two lists: <id>_gender and <id>_ethnicity (Bosch 11-04)
            for sid in q.get('subs') or []:
                lab = 'What is your gender?' if sid.endswith('_gender') else 'What is your race/ethnicity?' if re.search(r'_(ethnicity|race)$', sid) else None
                if lab:
                    out.append({'key': sid, 'label': lab, 'type': 'select', 'required': bool(q.get('required')), 'options': [], 'tag': 'spl-autocomplete'})
            continue
        typ = {'radio': 'radio', 'select': 'select', 'text': 'text', 'textarea': 'textarea', 'checkbox': 'checkbox',
               'multiselect': 'select', 'number': 'text', 'date': 'text'}.get(t, 'text')
        opts = q.get('radios') or q.get('boxes') or []
        label = clean_label(q.get('label') or q.get('text') or '')
        for o in opts:                                            # the slot text may end with the option texts
            label = re.sub(r'\s+' + re.escape(o) + r'$', '', label)
        out.append({'key': q.get('id') or f"q{q.get('idx')}", 'label': N(label), 'type': typ, 'required': bool(q.get('required')),
                    'options': opts, 'tag': q.get('tag')})
    return out


def answer(fields, jd='', company=None):
    qs = [{'key': f['key'], 'label': f['label'], 'type': f['type'], 'options': f['options']} for f in fields]
    q = {'fields': qs, 'jd': jd, 'company': COMPANY if company is None else company}   # company: referrer pool (JSA-195)
    r = subprocess.run(['node', os.path.join(HERE, 'rules_bridge.js'), os.path.abspath(RULES)], input=json.dumps(q),
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout or '{}')


OPTS_JS = r"""([key, want]) => { const all=[]; const walk=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) walk(e.shadowRoot); }); }; walk(document);
  const ac=all.find(e=>e.tagName.toLowerCase()==='spl-autocomplete' && e.id===key); if(!ac) return {err:'no autocomplete'};
  const opts=[]; const w2=(r)=>{ r.querySelectorAll('*').forEach(e=>{ if(e.tagName.toLowerCase()==='spl-select-option') opts.push(e); if(e.shadowRoot) w2(e.shadowRoot); }); }; w2(ac); if(ac.shadowRoot) w2(ac.shadowRoot);
  const n=s=>(s||'').replace(/\s+/g,' ').trim();
  if(want===null) return {opts: opts.map(e=>n(e.textContent)).filter(Boolean)};
  const o=opts.find(e=>n(e.textContent).toLowerCase()===n(want).toLowerCase()); if(!o) return {opts: opts.map(e=>n(e.textContent))};
  o.scrollIntoView({block:'center'}); const b=o.getBoundingClientRect(); return {xy:[b.x+b.width/2, b.y+b.height/2]}; }"""


def select_options(page, key):
    """Opens an autocomplete and returns its option texts (the list lives in the autocomplete's shadow root)."""
    inp = page.locator(f'spl-autocomplete#{css_id(key)} input').first
    inp.scroll_into_view_if_needed(); inp.click(); time.sleep(1.2)
    opts = (page.evaluate(OPTS_JS, [key, None]) or {}).get('opts') or []
    page.keyboard.press('Escape'); time.sleep(0.3)
    return opts


def css_id(k):
    return re.sub(r'([^\w-])', r'\\\1', k)


def fill_select(page, key, want):
    """Open the list, find the option whose whole text is `want` (case-insensitive) and click it with the mouse; a long
    list that shows only the first options gets the answer typed first."""
    inp = page.locator(f'spl-autocomplete#{css_id(key)} input').first
    inp.scroll_into_view_if_needed(); inp.click(); time.sleep(1.0)
    r = page.evaluate(OPTS_JS, [key, want]) or {}
    if not r.get('xy'):
        inp.fill(str(want)[:40]); time.sleep(1.2)
        r = page.evaluate(OPTS_JS, [key, want]) or {}
    if not r.get('xy'):
        raise ValueError(f'no option {want!r}')
    page.mouse.click(*r['xy']); time.sleep(0.6)


BTN_JS = r"""(want) => { const all=[]; const walk=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) walk(e.shadowRoot); }); }; walk(document);
  const n=s=>(s||'').replace(/\s+/g,' ').trim().toLowerCase();
  const b=all.filter(e=>e.tagName.toLowerCase()==='spl-button' && new RegExp(want,'i').test(n(e.textContent)) && e.getBoundingClientRect().width>0).pop();
  if(!b) return null; b.scrollIntoView({block:'center'}); const r=b.getBoundingClientRect(); return [r.x+r.width/2, r.y+r.height/2]; }"""


def click_button(page, pattern):
    """Click the visible spl-button whose whole text matches `pattern` (a JS regex source, e.g. '^next$') with the mouse;
    False when there is none. Playwright's has_text does not see the text inside these components."""
    xy = page.evaluate(BTN_JS, pattern)
    if not xy:
        return False
    page.mouse.click(*xy); return True


VIS_JS = r"""(txt) => { const out=[]; const w=(r)=>{ r.querySelectorAll('*').forEach(e=>{ const t=(e.textContent||'').replace(/\s+/g,' ').trim(); const b=e.getBoundingClientRect(); if(t===txt && b.width>0 && b.height>0 && e.children.length===0) out.push([b.x+b.width/2,b.y+b.height/2]); if(e.shadowRoot) w(e.shadowRoot); }); }; w(document); return out; }"""
ARIA_JS = r"""(lab) => { const out=[]; const w=(r)=>{ r.querySelectorAll('[aria-label]').forEach(e=>{ const b=e.getBoundingClientRect(); if(e.getAttribute('aria-label')===lab && b.width>0) out.push([b.x+b.width/2,b.y+b.height/2]); }); r.querySelectorAll('*').forEach(e=>{ if(e.shadowRoot) w(e.shadowRoot); }); }; w(document); return out; }"""
# The same lookup, but the element is scrolled to the middle of the viewport first: the coordinates are viewport
# coordinates, and a button below the fold (an employer's collapsed Education "Add" at y 944 of a 900-pixel window)
# took a mouse click that landed nowhere — the runner then waited 30 s for the Institution box (JSA-221).
ARIA_SCROLL_JS = r"""(lab) => { let hit=null; const w=(r)=>{ r.querySelectorAll('[aria-label]').forEach(e=>{ if(!hit && e.getAttribute('aria-label')===lab && e.getBoundingClientRect().width>0) hit=e; }); r.querySelectorAll('*').forEach(e=>{ if(e.shadowRoot) w(e.shadowRoot); }); }; w(document);
  if(!hit) return null; hit.scrollIntoView({block:'center'}); const b=hit.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]; }"""
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']


def month_value(ym):
    """Pure (tested). '2026-09' → '09/2026' (the value the month picker shows); None for anything else."""
    m = re.fullmatch(r'(\d{4})-(\d{1,2})', str(ym or '').strip())
    return f'{int(m.group(2)):02d}/{m.group(1)}' if m and 1 <= int(m.group(2)) <= 12 else None


def pick_month(page, label, ym):
    """The education From / To month picker: open it, click the month, then step the year with Previous / Next year until
    the box shows MM/YYYY."""
    want = month_value(ym)
    box = page.locator(f'input[aria-label="{label}"]').first
    for _ in range(6):
        box.click(); time.sleep(0.8)
        xy = page.evaluate(VIS_JS, MONTHS[int(ym[5:7]) - 1])
        if not xy:
            return False
        page.mouse.click(*xy[0]); time.sleep(0.6)
        got = box.input_value()
        if got == want:
            return True
        m = re.match(r'(\d{2})/(\d{4})', got or '')
        if not m:
            return False
        step = 'Previous year' if int(m.group(2)) > int(ym[:4]) else 'Next year'
        box.click(); time.sleep(0.6)
        for _ in range(abs(int(m.group(2)) - int(ym[:4]))):
            b = page.evaluate(ARIA_JS, step)
            if not b:
                return False
            page.mouse.click(*b[0]); time.sleep(0.3)
        xy = page.evaluate(VIS_JS, MONTHS[int(ym[5:7]) - 1])
        if xy:
            page.mouse.click(*xy[0]); time.sleep(0.6)
        if box.input_value() == want:
            return True
    return box.input_value() == want


def pick_option_text(page, want):
    xy = page.evaluate(OPTS_ANY_JS, want)
    if xy:
        page.mouse.click(*xy); time.sleep(0.8)
    return bool(xy)


OPTS_ANY_JS = r"""(want) => { const all=[]; const w=(r)=>{ r.querySelectorAll('*').forEach(e=>{ if(e.tagName.toLowerCase()==='spl-select-option' && e.getBoundingClientRect().width>0) all.push(e); if(e.shadowRoot) w(e.shadowRoot); }); }; w(document);
  const o=all.find(e=>(e.textContent||'').replace(/\s+/g,' ').trim()===want); if(!o) return null; o.scrollIntoView({block:'center'}); const b=o.getBoundingClientRect(); return [b.x+b.width/2,b.y+b.height/2]; }"""


def open_entry(page, label, first_box, tries=2, wait_ms=6000):
    """Click a section's "Add" button (found by aria-label, scrolled into view) and wait for the entry form's first box;
    one more click when it did not open. True when the box is there, False after `tries` clicks (never a 30 s hang)."""
    for _ in range(tries):
        xy = page.evaluate(ARIA_SCROLL_JS, label)
        if not xy:
            return False
        time.sleep(0.4)
        xy = page.evaluate(ARIA_SCROLL_JS, label) or xy             # after the scroll settled
        page.mouse.click(*xy)
        try:
            first_box.wait_for(state='visible', timeout=wait_ms)
            return True
        except Exception:
            continue
    return False


def add_education(page, edu, log):
    """Page 1 "Education → Add": the current school (config education, first entry) — institution and school location from
    the autocomplete, major, degree, From month and "I currently attend" (else To). Returns the saved entry's text or ''."""
    inst = page.locator('spl-autocomplete[label="Institution"] input').first
    if not open_entry(page, 'Add education entry', inst):
        log('education: the entry form did not open after "Add"'); return ''
    inst.click(timeout=10000); inst.press_sequentially(edu['school'], delay=50); time.sleep(2.5)
    if not pick_option_text(page, edu['school']):
        log(f"education: no institution option '{edu['school']}'"); return ''
    page.locator('input[id^="edu-major-"]').first.fill(edu.get('major') or '')
    page.locator('input[id^="edu-degree-"]').first.fill(edu.get('degree_full') or edu.get('degree') or '')
    loc = page.locator('spl-autocomplete[label="School location"] input').first
    loc.click(); loc.press_sequentially(edu.get('city') or '', delay=50); time.sleep(2.5)
    pick_option_text(page, city_option(edu.get('city') or '', edu.get('state') or ''))
    if edu.get('start') and not pick_month(page, 'From', edu['start']):
        log('education: From month not set')
    if edu.get('current'):
        xy = page.evaluate(VIS_JS, 'I currently attend')
        if xy: page.mouse.click(*xy[0]); time.sleep(0.6)
    elif edu.get('end'):
        pick_month(page, 'To', edu['end'])
    sv = page.evaluate(ARIA_SCROLL_JS, 'Save education entry')
    if not sv:
        return ''
    time.sleep(0.4); sv = page.evaluate(ARIA_SCROLL_JS, 'Save education entry') or sv
    page.mouse.click(*sv); time.sleep(2)
    t = deep_text(page)
    i = t.find('Education')
    return t[i:i + 200] if edu['school'] in t[i:i + 300] else ''


def fill_radio(page, key, want):
    page.locator(f'spl-radio-group#{css_id(key)} spl-radio[label="{want}"]').first.click(); time.sleep(0.4)


def read_value(page, f):
    k = css_id(f['key'])
    if f['type'] == 'radio':
        return page.evaluate("""(id) => { const all=[]; const walk=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) walk(e.shadowRoot); }); }; walk(document);
          const g=all.find(e=>e.id===id && e.tagName.toLowerCase()==='spl-radio-group'); if(!g) return '';
          const r=[...g.querySelectorAll('spl-radio')].find(x=>x.hasAttribute('checked') || (x.shadowRoot && x.shadowRoot.querySelector('input:checked')));
          return r ? (r.getAttribute('label')||'') : ''; }""", f['key'])
    if f['type'] == 'select':
        loc = page.locator(f'spl-autocomplete#{k} input')
        return loc.first.input_value() if loc.count() else ''
    if f['type'] == 'checkbox':
        return 'checked' if page.locator(f'spl-checkbox#{k} input').first.is_checked() else ''
    loc = page.locator(f'spl-input#{k} input, spl-textarea#{k} textarea, input#{k}, textarea#{k}')
    return loc.first.input_value() if loc.count() else ''


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def run(page, form_url, resume, log, out, folder=None, jd=''):
    res = {'status': 'blocked', 'problems': [], 'fields': [], 'unknown': []}
    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import jsa_profile
    page.goto(form_url, wait_until='domcontentloaded', timeout=60000)
    time.sleep(8)
    body = page.inner_text('body') + ' ' + deep_text(page)
    if '/expired' in page.url or re.search(r'no longer (available|accepting)|job (is )?(not found|closed)|temporarily unavailable|job ad (has )?expired|招聘广告已过期', body, re.I):
        res['status'] = 'closed'; res['problems'].append('posting closed / form unavailable'); return res
    if W.captcha_up(page) or [f for f in page.frames if 'captcha-delivery.com' in (f.url or '')]:
        res['problems'].append('DataDome / CAPTCHA on load — Joey'); return res
    # ---- page 1
    p1 = [{'key': 'first-name-input', 'label': 'First name', 'type': 'text', 'required': True, 'options': []},
          {'key': 'last-name-input', 'label': 'Last name', 'type': 'text', 'required': True, 'options': []},
          {'key': 'email-input', 'label': 'Email', 'type': 'text', 'required': True, 'options': []},
          {'key': 'phone', 'label': 'Phone number', 'type': 'text', 'required': True, 'options': []},
          {'key': 'city', 'label': 'City', 'type': 'text', 'required': True, 'options': []},
          {'key': 'linkedin-input', 'label': 'LinkedIn', 'type': 'text', 'required': False, 'options': []},
          {'key': 'website-input', 'label': 'Website', 'type': 'text', 'required': False, 'options': []}]
    a1 = answer(p1, jd)
    a1['state'] = answer([{'key': 'state', 'label': 'State', 'type': 'text', 'options': []}], jd).get('state') or {}
    rows = []
    v = lambda k: (a1.get(k) or {}).get('value') if (a1.get(k) or {}).get('status') == 'ok' else None
    for k in ('first-name-input', 'last-name-input', 'email-input', 'linkedin-input', 'website-input'):
        if v(k) and page.locator(f'input#{k}').count():
            page.locator(f'input#{k}').first.fill(v(k))
    if v('email-input') and page.locator('input#confirm-email-input').count():
        page.locator('input#confirm-email-input').first.fill(v('email-input'))
    if v('phone'):
        page.locator('input[type=tel]').first.fill(re.sub(r'\D', '', v('phone'))[-10:])
    st_abbr = {'illinois': 'IL'}.get(str(v('state') or 'Illinois').lower(), 'IL')
    want_city = city_option(v('city') or 'Chicago', st_abbr)
    city = page.locator('spl-autocomplete[label="City"] input').first if page.locator('spl-autocomplete[label="City"] input').count() else page.locator('input#spl-form-element_10').first   # the City id moves (an employer _8, Intuitive _10)
    try:
        city.click(); city.fill(''); city.press_sequentially(v('city') or 'Chicago', delay=80); time.sleep(2.5)
        page.locator('spl-select-option').filter(has_text=want_city).first.click(); time.sleep(1)
    except Exception as e:
        res['problems'].append(f'city autocomplete: {type(e).__name__}')
    if resume:
        page.locator('input#spl-dropzone-file-input-1').first.set_input_files(resume); time.sleep(6)
    if page.evaluate(ARIA_JS, 'Add education entry') and 'Edit education' not in deep_text(page):   # some companies require it (an employer 11-04)
        edus = jsa_profile.get('education') or []
        if edus:
            saved = add_education(page, edus[0], log)
            rows.append({'key': 'education', 'label': 'Education entry', 'type': 'text', 'required': False, 'want': edus[0]['school'],
                         'page': edus[0]['school'] if saved else '', 'ok': bool(saved), 'step': 1})
            if not saved:
                res['problems'].append('Education entry: not saved')
    cover = None
    if folder and os.path.exists(os.path.join(folder, 'cover.txt')):
        cover = open(os.path.join(folder, 'cover.txt'), encoding='utf-8').read().strip() or None
    msg = page.locator('textarea#hiring-manager-message-input')
    if msg.count():
        if cover:
            msg.first.fill(message_text(cover))
        else:
            res['problems'].append('Message to the Hiring Team (a cover-letter slot) — needs cover.txt in the application folder (ds_materials)')
    # page 1 read-back
    back = {'First name': page.locator('input#first-name-input').first.input_value(), 'Last name': page.locator('input#last-name-input').first.input_value(),
            'Email': page.locator('input#email-input').first.input_value(), 'Confirm email': page.locator('input#confirm-email-input').first.input_value() if page.locator('input#confirm-email-input').count() else v('email-input'),
            'Phone number': page.locator('input[type=tel]').first.input_value(), 'City': city.input_value(),
            'LinkedIn': page.locator('input#linkedin-input').first.input_value() if page.locator('input#linkedin-input').count() else ''}
    wants = {'First name': v('first-name-input'), 'Last name': v('last-name-input'), 'Email': v('email-input'), 'Confirm email': v('email-input'),
             'Phone number': v('phone'), 'City': want_city, 'LinkedIn': v('linkedin-input')}
    for lab, got in back.items():
        w = wants[lab]
        ok = (N(got).lower() == N(w).lower()) or (lab == 'Phone number' and re.sub(r'\D', '', got)[-10:] == re.sub(r'\D', '', str(w))[-10:])
        rows.append({'key': lab, 'label': lab, 'type': 'text', 'required': lab != 'LinkedIn', 'want': w, 'page': got, 'ok': ok, 'step': 1})
        if not ok:
            res['problems'].append(f'{lab}: want {w!r}, page {got!r}')
    if resume:
        shown = os.path.splitext(os.path.basename(resume))[0][:30].lower() in ' '.join(page.locator('body').all_inner_texts()).lower() or \
                page.evaluate("(n) => document.body.innerHTML.includes(n) || [...document.querySelectorAll('*')].some(e => e.shadowRoot && e.shadowRoot.innerHTML.includes(n))", os.path.basename(resume)[:30])
        rows.append({'key': 'resume', 'label': 'Resume', 'type': 'file', 'required': False, 'want': os.path.basename(resume), 'page': os.path.basename(resume) if shown else '', 'ok': bool(shown), 'step': 1})
        if not shown:
            res['problems'].append('Resume: not shown on the page after upload')
    try: page.screenshot(path=os.path.join(out, 'page1.png'), full_page=True)
    except Exception: pass
    if [x for x in res['problems'] if not x.startswith('Message to the Hiring Team')]:   # page 1 itself is wrong: never press Next
        res['fields'] = rows; res['status'] = 'needs-user'; return res
    single = False
    if not click_button(page, '^next$'):
        if page.evaluate(BTN_JS, '^submit$'):                     # a one-page form: no screening questions (Huck 11-04)
            single = True
        else:
            res['problems'].append('no Next button on page 1'); res['fields'] = rows; return res
    for _ in range(0 if single else 15):                          # page 2 must really be there: never call an empty page clean
        time.sleep(1)
        if page.locator('sr-screening-questions-form').count() or re.search(r'thank you|application (was )?(sent|submitted)', page.inner_text('body'), re.I):
            break
    if not single and not page.locator('sr-screening-questions-form').count():
        err = page.evaluate("() => { let t=''; const w=(r)=>{ r.querySelectorAll('*').forEach(e=>{ if(e.shadowRoot) w(e.shadowRoot); }); r.querySelectorAll('[class*=error],[role=alert]').forEach(e=>{ t+=' '+(e.textContent||''); }); }; w(document); return t.replace(/\\s+/g,' ').trim().slice(0,300); }")
        res['problems'].append('page 2 (Preliminary questions) did not open after Next' + (f' — page says: {err}' if err else ''))
        res['fields'] = rows; return res
    # ---- page 2
    done = set(); allans = {}
    for _round in range(4):                                     # an answer can open a follow-up question (export control → country list,
                                                                # an employer 11-04): read again until nothing new appears
        plan_all = plan_questions(page.evaluate(READ_Q))
        fields = [f for f in plan_all if f['key'] not in done]
        if not fields:
            break
        for f in fields:
            if f['type'] == 'select':
                try: f['options'] = select_options(page, f['key'])
                except Exception as e: f['options'] = []; f['error'] = f'options: {type(e).__name__}'
        ans = answer(fields, jd)
        for f in fields:                                              # "If you selected Other …, enter it below": only for "Other"
            if not f['required'] and IF_OTHER.search(f['label']):
                ans[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'if_followup', 'value': '', 'leave': True}   # 'ok' keeps it out of the drafts
        allans.update(ans)
        new = {f['key'] for f in fields}
        prev = None
        for f in plan_all:                                        # "Other (free text)" right after a list answered Other: the fact as text
            if f['key'] in new and prev and f['type'] == 'text' and OTHER_TEXT.search(f['label']) and str((allans.get(prev['key']) or {}).get('value') or '').lower().startswith('other'):
                t = answer([{'key': 'x', 'label': prev['label'], 'type': 'text', 'options': []}], jd).get('x') or {}
                if t.get('status') == 'ok' and t.get('value'):
                    ans[f['key']] = allans[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'other_text:' + str(t.get('rule')), 'value': t['value']}
            prev = f if f['type'] in ('select', 'radio') else (prev if f['type'] == 'text' and OTHER_TEXT.search(f['label']) else None)
        ans = W.guard_short_answers(fields, ans)
        ans, missing = W.apply_drafts(fields, ans, W.read_open_answers(folder), cover)
        if missing:
            names = ' | '.join(q['label'][:70] for q in missing)
            if folder:
                W.write_questions(folder, missing)
                res['problems'].append(f'not drafted yet: {names} — questions.json written; run scripts/ds_materials.py on the folder, then rerun')
            else:
                res['problems'].append(f'prose boxes need an application folder: {names}')
        missing_ids = {q['id'] for q in missing}
        for f in fields:
            row = dict(f); a = ans.get(f['key']) or {}; row['step'] = 2
            try:
                if a.get('status') != 'ok':
                    row['want'] = None; row['why'] = a.get('why')
                    if f['required'] and f['key'] not in missing_ids:
                        res['unknown'].append(f['label'] + (f" (options: {' / '.join(f['options'][:6])})" if f['options'] else ''))
                    rows.append(row); continue
                want = a.get('value'); row['want'] = want; row['rule'] = a.get('rule')
                if a.get('leave'):
                    row['want'] = None; rows.append(row); continue
                if f['type'] == 'radio':
                    fill_radio(page, f['key'], want)
                elif f['type'] == 'select':
                    fill_select(page, f['key'], want)
                elif f['type'] == 'checkbox':
                    cb = page.locator(f'spl-checkbox#{css_id(f["key"])} input').first
                    if not cb.is_checked(): cb.check(force=True)
                    row['want'] = 'checked'
                else:
                    page.locator(f'spl-input#{css_id(f["key"])} input, spl-textarea#{css_id(f["key"])} textarea').first.fill(str(want))
            except Exception as e:
                row['error'] = f'{type(e).__name__}: {str(e)[:120]}'
            rows.append(row)
        done |= {f['key'] for f in fields}
        time.sleep(1.5)
    for c in page.evaluate(READ_CONSENT):                         # the privacy notice checkbox
        a = answer([{'key': 'c', 'label': c['label'], 'type': 'checkbox', 'options': [c['label']]}], jd).get('c') or {}
        row = {'key': c['id'], 'label': N(c['label'])[:200], 'type': 'checkbox', 'required': c['required'], 'options': [], 'step': 2}
        if a.get('status') == 'ok' and a.get('rule') in ('data_consent', 'terms', 'privacy'):
            cb = page.locator(f'spl-checkbox#{css_id(c["id"])} input').first
            if not cb.is_checked(): cb.check(force=True)
            row['want'] = 'checked'; row['rule'] = a.get('rule')
        else:
            row['want'] = None
            if c['required']: res['unknown'].append(row['label'])
        rows.append(row)
    time.sleep(1.5)
    for row in rows:                                              # read back (page 2)
        if row.get('step') != 2:
            continue
        got = read_value(page, row) if row['type'] != 'file' else ''
        row['page'] = got
        w = row.get('want')
        row['ok'] = (w is None and not row['required']) or (w is not None and bool(N(got)) and (N(got).lower() == N(w).lower() or (row['type'] == 'checkbox' and got == 'checked')))
        if not row['ok'] and w is not None:
            res['problems'].append(f"{row['label'][:80]}: want {str(w)[:40]!r}, page {str(got)[:40]!r}" + (f" ({row['error']})" if row.get('error') else ''))
    said = ' '.join(res['problems'] + res['unknown'])
    for lab in W.required_empty(rows):
        if lab[:60] not in said:
            res['problems'].append(f'required field empty on the page: {lab[:100]}')
    res['fields'] = rows
    try: page.screenshot(path=os.path.join(out, 'page2.png'), full_page=True)
    except Exception: pass
    res['status'] = 'dry-run' if not res['problems'] and not res['unknown'] else 'needs-user'
    log(f'all fields filled and read back — {sum(1 for r in rows if r.get("ok"))}/{len(rows)} read back')
    return res


IF_OTHER = re.compile(r'^if (you )?(selected|chose|picked|answered)?\s*["“]?other\b|^if other\b|^if (your (selection|answer|response)|you (selected|chose|picked|answered)|yes|no)\b', re.I)   # an optional follow-up of another answer (an employer 11-04)
FIELD_ERRORS = r"""() => { const all=[]; const w=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) w(e.shadowRoot); }); }; w(document);
  const deep=(e)=>{ let t=''; const ww=(n)=>{ if(n.nodeType===3) t+=n.textContent+' '; else if(n.nodeType===1){ if(n.shadowRoot) ww(n.shadowRoot); n.childNodes.forEach(ww);} else if(n.nodeType===11) n.childNodes.forEach(ww); }; ww(e); return t.replace(/\s+/g,' ').trim(); };
  const out=[]; for(const e of all){ const t=(e.textContent||'').trim(); if(e.children.length===0 && /^(this field is required|this field cannot contain|please (provide|select|enter))/i.test(t)){ let a=e; for(let i=0;i<30&&a;i++){ if(/^sr-question-field-|^spl-checkbox$|form-section/.test(((a.tagName||'')+' '+(a.className||'')).toLowerCase())) break; a=a.parentElement||(a.getRootNode&&a.getRootNode().host)||null; } out.push(t+' — '+(a?deep(a).replace(t,'').slice(0,90):'')); } } return [...new Set(out)].slice(0,6); }"""


def deep_text(page):
    """The page text including every open shadow root (scripts and styles left out)."""
    return page.evaluate("() => { let t=''; const w=(n)=>{ if(n.nodeType===3 && !(n.parentElement && /^(SCRIPT|STYLE)$/.test(n.parentElement.tagName))) t+=n.textContent+' '; else if(n.nodeType===1){ if(n.shadowRoot) w(n.shadowRoot); n.childNodes.forEach(w);} else if(n.nodeType===11) n.childNodes.forEach(w); }; w(document.body); return t.replace(/\\s+/g,' ').trim(); }")


OTHER_TEXT = re.compile(r'^other\b.{0,30}(free text|specify|please|describe)|^if other\b|^please specify\b', re.I)
OTP_RE = re.compile(r'authentication code', re.I)


def submit(page, company, wait_captcha, log, push):
    """Click Submit and confirm. An e-mailed authentication code is typed from Gmail (read-only). Returns (status, by)."""
    from datetime import timedelta
    import gmail_code
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    if not click_button(page, '^submit$'):
        log('no Submit button'); return 'blocked', None
    log('submit clicked')
    t_end = time.time() + 30
    otp_done = False
    while time.time() < t_end:
        time.sleep(2)
        txt = ' '.join(page.locator('body').all_inner_texts())
        if W.confirmed_page(page.url, txt) or W.confirmed_page(page.url, deep_text(page)):
            return 'submitted', 'page'
        errs = page.evaluate(FIELD_ERRORS)
        if errs:                                                  # the site refused the form: nothing went in
            log('Submit refused by the page: ' + ' | '.join(errs)[:300]); return 'refused', None
        if not otp_done and OTP_RE.search(deep_text(page)):
            log('authentication code asked — reading it from Gmail (read-only)')
            code = gmail_code.find_code(sender='smartrecruiters', since=since)
            if not code:
                time.sleep(20); code = gmail_code.find_code(sender='smartrecruiters', since=since)
            if not code:
                log('no authentication code in Gmail'); return 'unconfirmed', None
            box = page.locator('input[autocomplete="one-time-code"], input[name*=otp i], input[id*=otp i], spl-input input').last
            box.fill(str(code)); time.sleep(0.5)
            click_button(page, '^(submit|verify|confirm)')
            otp_done = True; t_end = time.time() + 30
        if W.captcha_up(page) or [f for f in page.frames if 'captcha-delivery.com' in (f.url or '')]:
            log('CAPTCHA after submit → Joey (never answered by the runner)')
            push('求职 runner：人机验证', f'{company} SmartRecruiters — job Chrome 里的页面等你过验证')
            t_end = time.time() + wait_captcha * 60
    log('no thank-you page — waiting up to 180 s for the receipt e-mail (Gmail read-only)')
    subj = gmail_code.wait_for_mail(since, company, timeout=180)
    if subj:
        log(f'company e-mail: {subj[:100]}'); return 'submitted', 'email'
    return 'unconfirmed', None


def write_form_check(r, out, posting, form_url, a):
    """form_check.json (the results line is written by runner_common.Run.finish, JSA-187)."""
    n, ok = len(r['fields']), sum(1 for f in r['fields'] if f.get('ok'))
    json.dump({'at': now(), 'posting': posting, 'form': form_url, 'job': a.job, **r, 'readback': f'{ok}/{n}'},
              open(os.path.join(out, 'form_check.json'), 'w'), indent=1, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url'); ap.add_argument('--job'); ap.add_argument('--resume'); ap.add_argument('--out')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222')
    ap.add_argument('--folder'); ap.add_argument('--submit', action='store_true'); ap.add_argument('--wait-captcha', type=float, default=10)
    a = ap.parse_args()
    import run_form as RF
    folder = jpaths.folder(a.folder) if a.folder else None   # as typed, else under the data home (ADR-0008)
    jd = ''
    if folder:
        fj = json.load(open(os.path.join(folder, 'job.json')))
        a.job = a.job or fj.get('id'); a.url = a.url or fj.get('url')
        pdfs = sorted(x for x in os.listdir(folder) if x.lower().endswith('.pdf') and 'resume' in x.lower())
        a.resume = a.resume or (os.path.join(folder, pdfs[0]) if pdfs else None); a.out = folder
        if os.path.exists(os.path.join(folder, 'jd.md')):
            jd = open(os.path.join(folder, 'jd.md'), encoding='utf-8').read()
        if RF.already_submitted(folder):
            print(f'{os.path.basename(folder)}: already submitted — nothing to do'); print('STATUS already-submitted'); return
    if a.submit and not folder:
        sys.exit('--submit needs --folder (approval, tailored resume and the tracker row come from it)')
    job = {}
    if a.job:
        for line in open(jpaths.data('store', 'jobs.jsonl'), encoding='utf-8'):
            r = json.loads(line)
            if r.get('id') == a.job:
                job = r; break
    posting = a.url or job.get('ats_url') or job.get('url')
    p = parse_posting(posting)
    if not p:
        sys.exit(f'not a SmartRecruiters posting: {posting}')
    global COMPANY
    COMPANY = (fj.get('company') if folder else '') or job.get('company') or ''   # referral questions (JSA-195)
    form_url = apply_url(p)
    resume = a.resume or jpaths.resume('2026-10', 'Alex_Rivera_Resume_Data_Analyst_A-Classic.pdf')
    out = os.path.abspath(a.out or os.path.join(DATA, 'dryrun', 'smartrecruiters', f"{p['company']}_{p.get('id') or p.get('uuid')[:8]}"))
    os.makedirs(out, exist_ok=True)
    logf = open(os.path.join(out, 'run_log.md'), 'a')
    def log(m): logf.write(f'- {now()} {m}\n'); logf.flush(); print(m)
    import runner_common as RC                                   # JSA-187: opening checks · submit gate · closing books
    R = RC.Run('smartrecruiters', posting, folder, out, submit=a.submit, log=log, label='SmartRecruiters', data_dir=DATA)
    if not form_url:
        r = {'status': 'closed', 'problems': ['posting API: not active / no uuid'], 'fields': [], 'unknown': []}
        log('posting closed (API)')
        R.stopped_at = RC.PAGE
        write_form_check(r, out, posting, form_url, a)
        R.finish(r)
        return
    from playwright.sync_api import sync_playwright
    log(f'start smartrecruiters {"submit" if a.submit else "dry-run"} {form_url} (resume {os.path.basename(resume)})')
    if not R.opening(resume):                                    # submit + materials problem: stopped before filling
        return
    with sync_playwright() as pw:
        ctx = pw.chromium.connect_over_cdp(a.cdp).contexts[0]
        page = ctx.new_page(); page.set_viewport_size({'width': 1300, 'height': 900})
        R.mark('page')
        try:
            r = run(page, form_url, resume, log, out, folder, jd)
        except Exception as e:
            r = {'status': 'blocked', 'problems': [f'runner error {type(e).__name__}: {str(e)[:200]}'], 'fields': [], 'unknown': []}
        decision = R.gate(r)
        confirmed_by = None
        if decision == 'press':
            R.mark('submit')
            company = job.get('company') or json.load(open(os.path.join(folder, 'job.json'))).get('company') or p['company']
            try:
                r['status'], confirmed_by = submit(page, company, a.wait_captcha, log, RF.push)
            except Exception as e:                                    # never crash after a possible click: queue it for Joey
                log(f'submit step error {type(e).__name__}: {str(e)[:160]}'); r['status'], confirmed_by = 'unconfirmed', None
            r['confirmed_by'] = confirmed_by
            if r['status'] == 'submitted':
                log(f'CONFIRMED by {confirmed_by}')
            elif r['status'] == 'refused':
                r['problems'].append('the page refused Submit (see run_log) — nothing went in'); r['status'] = 'blocked'
                R.stopped_at = RC.PAGE
                R._q('SmartRecruiters refused Submit (a field the runner did not see) — rerun after the fix')
        write_form_check(r, out, posting, form_url, a)
        R.finish(r, ctx=ctx, page=page, confirmed_by=confirmed_by)

if __name__ == '__main__':
    main()
