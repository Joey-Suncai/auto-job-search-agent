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
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import argparse, json, os, re, subprocess, sys, time, urllib.request
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
import jsa_profile  # noqa: E402  (JSA-403: the user's own values come from the profile)
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
    const ctl=e.querySelector('spl-radio-group,spl-autocomplete,spl-multiselect-autocomplete,spl-input,spl-textarea,spl-checkbox,spl-checkbox-group,spl-select');
    const radios=[...e.querySelectorAll('spl-radio')].map(x=>x.getAttribute('label')||deep(x));
    const boxes=[...e.querySelectorAll('spl-checkbox')].map(x=>x.getAttribute('label')||deep(x));
    return {idx:i, type, label: slot?deep(slot):deep(e), text: deep(e).slice(0,600), id: ctl?ctl.id:'', tag: ctl?ctl.tagName.toLowerCase():'',
            required: !!(ctl && ctl.hasAttribute('required')) || /^\*/.test(deep(e)), radios, boxes,
            subs: [...e.querySelectorAll('spl-autocomplete')].map(x=>x.id).filter(Boolean)};
  });
}"""

# The markup of the idx-th question wrapper (shadow roots serialised inline, trimmed) — kept in the row when a control cannot be
# found, so the next fix reads the real structure instead of guessing (JSA-387).
DUMP_Q = r"""(idx) => {
  const all=[]; const walk=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) walk(e.shadowRoot); }); }; walk(document);
  const q=all.filter(e=>/^sr-question-field-/.test(e.tagName.toLowerCase()))[idx]; if(!q) return '';
  const ser=(n)=>{ if(n.nodeType===3) return n.textContent.replace(/\s+/g,' '); if(n.nodeType!==1) return '';
    const a=[...n.attributes].filter(x=>/^(id|class|name|label|role|type|aria-label|multiple|required)$/.test(x.name)).map(x=>x.name+'="'+x.value.slice(0,60)+'"').join(' ');
    let inner=''; if(n.shadowRoot) inner+='#shadow{'+[...n.shadowRoot.childNodes].map(ser).join('')+'}'; inner+=[...n.childNodes].map(ser).join('');
    return '<'+n.tagName.toLowerCase()+(a?' '+a:'')+'>'+inner+'</'+n.tagName.toLowerCase()+'>'; };
  return ser(q).slice(0,6000); }"""

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


DECLARATIONS = (   # (rule, pattern) — Joey agreed to tick these three (JSA-326 acceptance, Arista 11-11)
    ('background_release', re.compile(r'\bgrant permission to any person, firm or corporation to release\b[^.]{0,200}\b(information|employment)\b', re.I)),
    ('at_will', re.compile(r'\bi understand\b[^.]{0,120}\b(application|interview)\b[^.]{0,200}\bemployment contract\b.{0,600}\bat-will\b', re.I | re.S)),
    ('i9_verify', re.compile(r'\bi understand that all persons hired (will be required to|must|are required to|need to) verify identity and eligibility to work in the united states\b', re.I)),
)
NEGATED = re.compile(r"\b(do not|don't|cannot|can't|never|not) (grant|understand|agree)\b", re.I)


def declaration_rule(label):
    """Pure (tested, JSA-326). The employment declaration a required checkbox asks for — background_release / at_will /
    i9_verify — or None. These are acknowledgements of the hiring process, not facts about the user; Joey agreed to tick the
    three (Arista 11-11). Anything else (marketing, certify, convictions, a negated sentence) stays with the rules."""
    t = re.sub(r'\s+', ' ', re.sub(r'^\*\s*', '', str(label or ''))).strip()
    if NEGATED.search(t):
        return None
    for rule, pat in DECLARATIONS:
        if pat.search(t):
            return rule
    return None


def apply_declarations(fields, ans):
    """Pure (tested, JSA-326). Adds an 'ok' answer for a required single-option checkbox the rules left unanswered when it is
    one of the three declarations; returns the answers dict (a new one)."""
    out = dict(ans)
    for f in fields:
        opts = f.get('options') or []
        if f.get('type') != 'checkbox' or not f.get('required') or len(opts) != 1 or (out.get(f['key']) or {}).get('status') == 'ok':
            continue
        rule = declaration_rule(f.get('label')) or declaration_rule(opts[0])
        if rule:
            out[f['key']] = {'status': 'ok', 'label': f['label'], 'rule': 'declaration:' + rule, 'value': opts[0]}
    return out


def answer(fields, jd='', company=None):
    qs = [{'key': f['key'], 'label': f['label'], 'type': f['type'], 'options': f['options']} for f in fields]
    q = {'fields': qs, 'jd': jd, 'company': COMPANY if company is None else company}   # company: referrer pool (JSA-195)
    r = subprocess.run(['node', os.path.join(HERE, 'rules_bridge.js'), os.path.abspath(RULES)], input=json.dumps(q),
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout or '{}')


OPTS_JS = r"""([key, want]) => { const all=[]; const walk=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) walk(e.shadowRoot); }); }; walk(document);
  const ac=all.find(e=>/^spl-(multiselect-)?autocomplete$/.test(e.tagName.toLowerCase()) && e.id===key); if(!ac) return {err:'no autocomplete'};
  const opts=[]; const w2=(r)=>{ r.querySelectorAll('*').forEach(e=>{ if(e.tagName.toLowerCase()==='spl-select-option') opts.push(e); if(e.shadowRoot) w2(e.shadowRoot); }); }; w2(ac); if(ac.shadowRoot) w2(ac.shadowRoot);
  const n=s=>(s||'').replace(/\s+/g,' ').trim();
  if(want===null) return {opts: opts.map(e=>n(e.textContent)).filter(Boolean)};
  const o=opts.find(e=>n(e.textContent).toLowerCase()===n(want).toLowerCase()); if(!o) return {opts: opts.map(e=>n(e.textContent))};
  o.scrollIntoView({block:'center'}); const b=o.getBoundingClientRect(); return {xy:[b.x+b.width/2, b.y+b.height/2]}; }"""


def select_options(page, key):
    """Opens an autocomplete and returns its option texts (the list lives in the autocomplete's shadow root)."""
    inp = page.locator(f'{AC}#{css_id(key)} input').first
    inp.scroll_into_view_if_needed(); inp.click(); time.sleep(1.2)
    opts = (page.evaluate(OPTS_JS, [key, None]) or {}).get('opts') or []
    page.keyboard.press('Escape'); time.sleep(0.3)
    return opts


AC = ':is(spl-autocomplete, spl-multiselect-autocomplete)'   # "select all that apply" lists are spl-multiselect-autocomplete (Arista 11-11, JSA-387)
TAGS_JS = r"""(id) => { const all=[]; const walk=(r)=>{ r.querySelectorAll('*').forEach(e=>{ all.push(e); if(e.shadowRoot) walk(e.shadowRoot); }); }; walk(document);
  const h=all.find(e=>e.tagName.toLowerCase()==='spl-multiselect-autocomplete' && e.id===id); if(!h) return '';
  const t=[]; const txt=(n)=>{ if(n.nodeType===3){ const x=n.textContent.replace(/\s+/g,' ').trim(); if(x) t.push(x); } else if(n.nodeType===1){ if(n.shadowRoot) txt(n.shadowRoot); n.childNodes.forEach(txt);} else if(n.nodeType===11) n.childNodes.forEach(txt); };
  const find=(n)=>{ if(n.nodeType===1 && n.tagName.toLowerCase()==='spl-tags-list') { txt(n); return; } if(n.nodeType===1 && n.shadowRoot) find(n.shadowRoot); n.childNodes.forEach(find); };
  find(h); return t.join(', '); }"""


def multi_has(got, want):
    """Pure (tested). A multi-select's read-back (its tags joined by ', ') holds the wanted option as one whole tag."""
    tags = [re.sub(r'\s+', ' ', x).strip().lower() for x in str(got or '').split(',')]
    w = re.sub(r'\s+', ' ', str(want or '')).strip().lower()
    return bool(w) and w in tags


def css_id(k):
    return re.sub(r'([^\w-])', r'\\\1', k)


def fill_select(page, key, want):
    """Open the list, find the option whose whole text is `want` (case-insensitive) and click it with the mouse; a long
    list that shows only the first options gets the answer typed first."""
    if multi_has(page.evaluate(TAGS_JS, key), want):
        return                                               # already picked: a second click could toggle it off
    inp = page.locator(f'{AC}#{css_id(key)} input').first
    inp.scroll_into_view_if_needed(); inp.click(); time.sleep(1.0)
    r = page.evaluate(OPTS_JS, [key, want]) or {}
    if not r.get('xy'):
        inp.fill(str(want)[:40]); time.sleep(1.2)
        r = page.evaluate(OPTS_JS, [key, want]) or {}
    if not r.get('xy'):
        raise ValueError(f'no option {want!r}')
    page.mouse.click(*r['xy']); time.sleep(0.6)
    if page.locator(f'spl-multiselect-autocomplete#{css_id(key)}').count():
        page.keyboard.press('Escape'); time.sleep(0.3)   # a multi-select stays open after a pick


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


MONTHS_FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
               'November', 'December']


def month_value(ym):
    """Pure (tested). '2026-09' → '09/2026' (the old way of writing the month); None for anything else."""
    m = re.fullmatch(r'(\d{4})-(\d{1,2})', str(ym or '').strip())
    return f'{int(m.group(2)):02d}/{m.group(1)}' if m and 1 <= int(m.group(2)) <= 12 else None


def picker_ym(value):
    """Pure (tested). What a month picker box holds → 'YYYY-MM'; None when it holds no month. The box holds an ISO date
    ('2026-09-01', SyngentaGroup 2026-11-10 — the reason "From month not set" was logged on every run: the runner only
    knew '09/2026'); 'MM/YYYY' and 'YYYY-MM' are read too."""
    v = str(value or '').strip()
    m = re.fullmatch(r'(\d{4})-(\d{1,2})(?:-\d{1,2})?', v) or None
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
    else:
        m = re.fullmatch(r'(\d{1,2})/(\d{4})', v)
        if not m:
            return None
        y, mo = int(m.group(2)), int(m.group(1))
    return f'{y:04d}-{mo:02d}' if 1 <= mo <= 12 else None


def ym_of(v):
    """Pure (tested). A profile date ('2025-08', '08/2025', '2025-08-01') → 'YYYY-MM'; None otherwise."""
    return picker_ym(v)


# The open picker's month cells carry aria-label "<Month> 1, <year>"; the year it shows = the year in those labels.
PICKER_YEAR_JS = r"""() => { let y=null; const w=(r)=>{ r.querySelectorAll('[aria-label]').forEach(e=>{ const m=/^[A-Z][a-z]+ 1, (\d{4})$/.exec(e.getAttribute('aria-label')||''); if(!y && m && e.getBoundingClientRect().width>0) y=+m[1]; }); r.querySelectorAll('*').forEach(e=>{ if(e.shadowRoot) w(e.shadowRoot); }); }; w(document); return y; }"""


def pick_month(page, label, ym):
    """A From / To month picker (education and experience entries): open the visible box with that aria-label, step the
    year with Previous / Next year until the cell "<Month> 1, <year>" is there, click it; True when the box then holds
    that month (read with picker_ym)."""
    want = ym_of(ym)
    if not want:
        return False
    y, mo = int(want[:4]), int(want[5:7])
    box = page.locator(f'input[aria-label="{label}"]:visible').first
    for _ in range(3):
        box.click(); time.sleep(0.8)
        for _ in range(15):
            cell = page.evaluate(ARIA_JS, f'{MONTHS_FULL[mo - 1]} 1, {y}')
            if cell:
                page.mouse.click(*cell[0]); time.sleep(0.6)
                break
            shown = page.evaluate(PICKER_YEAR_JS)
            b = page.evaluate(ARIA_JS, 'Previous year' if (shown or 0) > y else 'Next year') if shown else None
            if not b:
                break
            page.mouse.click(*b[0]); time.sleep(0.3)
        if picker_ym(box.input_value()) == want:
            return True
    return picker_ym(box.input_value()) == want


def experience_required(cfg):
    """Pure (tested). The form config (GET …/publication/<uuid>/config) → True when its Experience section is visible and
    required (SyngentaGroup: "Please provide at least one work experience entry" blocked Next, JSA-233)."""
    e = ((cfg or {}).get('fieldSets') or {}).get('experience') or {}
    return bool(e.get('required')) and e.get('visible') is not False


def exp_entries(work):
    """Pure (tested). config/wd_profile.json `work` (the entries Workday already uses: Job Title, Company, Location
    "City, State", From / To "MM/YYYY", current, Description) → the experience entries to add, most recent first:
    {'title', 'company', 'city', 'description', 'start', 'end', 'current'}. An entry without a title, a company or a
    start month is left out (never guessed)."""
    out = []
    for w in work or []:
        t, c, st = N((w or {}).get('Job Title')), N((w or {}).get('Company')), ym_of((w or {}).get('From'))
        if not (t and c and st):
            continue
        cur = bool(w.get('current'))
        out.append({'title': t, 'company': c, 'city': N(str(w.get('Location') or '').split(',')[0]),
                    'description': str(w.get('Description') or '').strip(), 'start': st,
                    'end': None if cur else ym_of(w.get('To')), 'current': cur})
    return sorted(out, key=lambda e: e['start'], reverse=True)


def location_option(city, options):
    """Pure (tested). The Office location / School location option for a city: the first option whose text starts with
    "<city>," (case and spaces ignored) — never the "Cannot find your city?" entry; None when none matches."""
    c = N(city).lower()
    if not c:
        return None
    for o in options or []:
        t = N(o)
        if t.lower().startswith(c + ',') and not t.lower().startswith('cannot find'):
            return t
    return None


def validation_text(page):
    """The page's own validation messages (error elements and the validation summary list, through the shadow roots)."""
    return page.evaluate("() => { let t=''; const w=(r)=>{ r.querySelectorAll('*').forEach(e=>{ if(e.shadowRoot) w(e.shadowRoot); }); r.querySelectorAll('[class*=error],[class*=validation-summary-entry],[role=alert]').forEach(e=>{ if(e.getBoundingClientRect().width>0) t+=' '+(e.textContent||''); }); }; w(document); return t.replace(/\\s+/g,' ').trim().slice(0,300); }")


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


OPTS_TEXT_JS = r"""() => { const all=[]; const w=(r)=>{ r.querySelectorAll('*').forEach(e=>{ if(e.tagName.toLowerCase()==='spl-select-option' && e.getBoundingClientRect().width>0) all.push((e.textContent||'').replace(/\s+/g,' ').trim()); if(e.shadowRoot) w(e.shadowRoot); }); }; w(document); return all; }"""


def type_pick(page, label, text, choose=None):
    """An entry autocomplete (Title / Company / Office location): type `text`, then click the option `choose(options)`
    picks (default: the option that is the typed text itself — the box empties again when no option is clicked).
    Returns the option clicked or None."""
    box = page.locator(f'spl-autocomplete[label="{label}"] input:visible').first
    box.click(); box.fill(''); box.press_sequentially(text, delay=50); time.sleep(2.5)
    opts = page.evaluate(OPTS_TEXT_JS)
    want = choose(opts) if choose else next((o for o in opts if N(o).lower() == N(text).lower()), None)
    if want and pick_option_text(page, want):
        return want
    box.press('Escape')
    return None


def add_experience(page, e, log):
    """Page 1 "Experience → Add" (only where the form requires it, JSA-233): title, company, office location, description,
    From / To months (or "I currently work here"), Save. Returns the problems ([] = saved and both title and company are
    on the page in the saved entry)."""
    title = page.locator('spl-autocomplete[label="Title"] input').first
    if not open_entry(page, 'Add experience entry', title):
        return ['the experience entry form did not open after "Add"']
    probs = []
    if not type_pick(page, 'Title', e['title']):
        probs.append(f"no Title option {e['title']!r}")
    if not type_pick(page, 'Company', e['company']):
        probs.append(f"no Company option {e['company']!r}")
    if e.get('city') and not type_pick(page, 'Office location', e['city'], lambda o: location_option(e['city'], o)):
        probs.append(f"no Office location option for {e['city']!r}")
    d = page.locator('textarea[id^="exp-desc-"]:visible')
    if e.get('description') and d.count():
        d.first.fill(message_text(e['description']))
    if not pick_month(page, 'From', e['start']):
        probs.append(f"From month {e['start']} not set")
    if e.get('current'):
        xy = page.evaluate(VIS_JS, 'I currently work here')
        if xy: page.mouse.click(*xy[0]); time.sleep(0.6)
    elif e.get('end') and not pick_month(page, 'To', e['end']):
        probs.append(f"To month {e['end']} not set")
    if probs:                                                   # never save a half-filled entry: cancel it
        xy = page.evaluate(ARIA_SCROLL_JS, 'Cancel adding experience entry')
        if xy: time.sleep(0.4); page.mouse.click(*(page.evaluate(ARIA_SCROLL_JS, 'Cancel adding experience entry') or xy)); time.sleep(1)
        return probs
    sv = page.evaluate(ARIA_SCROLL_JS, 'Save experience entry')
    if not sv:
        return ['no "Save experience entry" button']
    time.sleep(0.4); page.mouse.click(*(page.evaluate(ARIA_SCROLL_JS, 'Save experience entry') or sv)); time.sleep(2)
    if page.locator('spl-autocomplete[label="Title"] input:visible').count():
        return [f"not saved — page says: {validation_text(page) or '(nothing)'}"]
    t = deep_text(page)
    i, j = t.find('Experience'), t.find('Education')
    seg = t[i:j if j > i else i + 2000]
    return [] if (N(e['title']).lower() in seg.lower() and N(e['company']).lower() in seg.lower()) else ['saved entry not found on the page']


def add_experiences(page, log, rows, res):
    """Every wd_profile.json work entry; one read-back row per entry. Added oldest first: the page lists the entry added
    last on top, so the most recent job ends up first (entry 1 = the most recent)."""
    import jsa_profile
    work = json.load(open(jsa_profile.data_file('wd_profile.json', 'JSA_WD_PROFILE'), encoding='utf-8')).get('work') or []
    entries = exp_entries(work)
    if not entries:
        res['problems'].append('Experience is required here but config/wd_profile.json has no work entry'); return
    for n, e in reversed(list(enumerate(entries, 1))):
        want = f"{e['title']} · {e['company']} · {e['start']}–{'now' if e['current'] else e['end']}"
        probs = add_experience(page, e, log)
        for pr in probs:
            log(f'experience {n}: {pr}')
        rows.append({'key': f'experience-{n}', 'label': f'Experience entry {n}', 'type': 'text', 'required': n == 1,
                     'want': want, 'page': '' if probs else want, 'ok': not probs, 'step': 1})
        if probs:
            res['problems'].append(f"Experience entry {n} ({e['company']}): {probs[0]}")


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
        loc = page.locator(f'{AC}#{k} input')
        tags = page.evaluate(TAGS_JS, f['key'])               # a multi-select shows its picks as tags (JSA-387); typed filter text is not a pick
        return tags or (loc.first.input_value() if loc.count() and not f.get('tag') == 'spl-multiselect-autocomplete' else '')
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
    cfg = {}
    def on_resp(r):                                             # the form config: which page-1 sections are required (JSA-233)
        if not cfg and re.search(r'/oneclick-ui/api/company/[^/]+/publication/[^/]+/config', r.url) and r.status == 200:
            try: cfg.update(r.json() or {})
            except Exception: pass
    page.on('response', on_resp)
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
    exp_done = False
    if experience_required(cfg) and page.evaluate(ARIA_JS, 'Add experience entry'):   # "Please provide at least one work
        add_experiences(page, log, rows, res); exp_done = True                       # experience entry" (SyngentaGroup 11-10)
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
    def page2_wait():
        for _ in range(0 if single else 15):                      # page 2 must really be there: never call an empty page clean
            time.sleep(1)
            if page.locator('sr-screening-questions-form').count() or re.search(r'thank you|application (was )?(sent|submitted)', page.inner_text('body'), re.I):
                break
    page2_wait()
    if not single and not page.locator('sr-screening-questions-form').count() and not exp_done \
            and re.search(r'work experience entry', validation_text(page), re.I) and page.evaluate(ARIA_JS, 'Add experience entry'):
        log('experience: required by the page (config not read) — adding the entries, then Next again')   # JSA-233 fallback
        n0 = len(res['problems']); add_experiences(page, log, rows, res); exp_done = True
        if len(res['problems']) > n0:
            res['fields'] = rows; res['status'] = 'needs-user'; return res
        click_button(page, '^next$'); page2_wait()
    if not single and not page.locator('sr-screening-questions-form').count():
        err = validation_text(page)
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
        ans = apply_declarations(fields, answer(fields, jd))
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
                if re.fullmatch(r'q\d+', str(f['key'])):             # no control id was found: keep the wrapper's markup (JSA-387)
                    try: row['dom'] = page.evaluate(DUMP_Q, int(str(f['key'])[1:]))
                    except Exception: pass
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
        row['ok'] = (w is None and not row['required']) or (w is not None and bool(N(got)) and (N(got).lower() == N(w).lower() or (row['type'] == 'checkbox' and got == 'checked') or (row.get('tag') == 'spl-multiselect-autocomplete' and multi_has(got, w))))
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
    import confirm_page as CP
    since = datetime.now(timezone.utc) - timedelta(minutes=1)
    before = sr_snap(page)
    if not click_button(page, '^submit$'):
        log('no Submit button'); return 'blocked', None
    log('submit clicked')
    t_end = time.time() + 30
    otp_done, why = False, ''
    while time.time() < t_end:
        time.sleep(2)
        ok, why = W.page_done(before, sr_snap(page))              # JSA-299: the page must have changed, not just thank him
        if ok:
            log(f'confirmation page: {why}'); CP.settle(page)
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
    log(f'no thank-you page ({why}) — waiting up to 180 s for the receipt e-mail (Gmail read-only)')
    subj = gmail_code.wait_for_mail(since, company, timeout=180)
    if subj:
        log(f'company e-mail: {subj[:100]}'); return 'submitted', 'email'
    return 'unconfirmed', None


def sr_snap(page):
    """{'url', 'text', 'form'} for confirm_page.judge: the text includes the shadow roots; form = a visible Submit
    button (spl-button, found through the shadow roots)."""
    try:
        form = bool(page.evaluate(BTN_JS, '^submit$'))
    except Exception:
        form = None
    try:
        text = ' '.join(page.locator('body').all_inner_texts()) + ' ' + deep_text(page)
    except Exception:
        text = ''
    return {'url': page.url, 'text': text[:40000], 'form': form}


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
    resume = a.resume or jpaths.resume('2026-10', jsa_profile.resume_file('Data_Analyst_A-Classic.pdf'))
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
        ctx = cdp_connect.connect(pw, a.cdp).contexts[0]
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
