#!/usr/bin/env python3
"""Escalation ladder for fields the scripted fill could not get right (Joey's decision 2026-10-28).

  level 1  script        run.py's own widget code (already ran before this module is used)
  level 2  DeepSeek      deepseek-flash gets ONLY this one field: its label, the planned answer, the allowed options and a
                         compacted DOM snippet of the field's container (+ any open dropdown menu). It returns a short list of
                         actions (click / type / press / wait). run.py executes them with real Playwright clicks/keys,
                         then re-checks the field with verify.js. Max 3 tries, each try sees what the last one produced.
  level 3  Claude        handoff.json in the app folder + the tab stays open; Claude in Chrome fixes that field in the same tab,
                         then `run.py <folder> --resume --attach <marker> [--submit]` re-verifies and submits.
  level 4  Joey          CAPTCHA only (queue.md).

The verifier (verify.js) is always the judge. DeepSeek's own description of what it did is never used.
No screenshot is sent (DOM only) — nothing outside the one field leaves the Mac.
"""
import json, os, re, sys, time, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077)

DS_MODEL = os.environ.get('CX_DS_MODEL', 'deepseek-flash')
DS_URL = 'https://api.deepseek.com/chat/completions'
MAX_TRIES = 3
KEY_PATHS = [os.environ.get('DEEPSEEK_KEY_FILE', ''), os.path.expanduser('~/deepseek/api_key'),
             os.path.expanduser('~/mnt/deepseek/api_key')]

# compact DOM of one field: drop svg/script/style, keep only attributes that matter for acting on it
SNIPPET_JS = r'''([sel, key]) => {
  let el = null;
  try { el = document.querySelector(sel); } catch (e) {}
  el = el || document.getElementsByName(key)[0] || document.getElementById(key);
  if (!el) return null;
  // container = the field wrapper (fieldset / question block); never the whole form
  let box = el.closest('fieldset, .field-wrapper, .application-question, [class*="question"], [class*="field"]') || el.parentElement;
  for (let i = 0; i < 3 && box && box.parentElement && box.querySelectorAll('input,select,textarea').length < 1; i++) box = box.parentElement;
  if (!box.id) box.setAttribute('data-cx-box', key);
  const keep = /^(id|name|type|value|for|role|class|placeholder|checked|selected|aria-(checked|selected|expanded|label|controls|activedescendant)|data-cx-box)$/;
  const compact = node => {
    const c = node.cloneNode(true);
    c.querySelectorAll('svg, script, style, path, noscript').forEach(n => n.remove());
    [c, ...c.querySelectorAll('*')].forEach(n => [...n.attributes].forEach(a => {
      if (!keep.test(a.name)) n.removeAttribute(a.name);
      else if (a.name === 'class') n.setAttribute('class', a.value.split(/\s+/).filter(x => !/^(css-|sc-|jsx-)/.test(x)).slice(0, 3).join(' '));
    }));
    // reflect live state the HTML attributes do not show
    const live = node.querySelectorAll('input'), copy = c.querySelectorAll('input');
    live.forEach((x, i) => { if (!copy[i]) return; if (x.checked) copy[i].setAttribute('checked', ''); else copy[i].removeAttribute('checked');
                             if (x.type !== 'checkbox' && x.type !== 'radio') copy[i].setAttribute('value', x.value); });
    return c.outerHTML.replace(/\s+/g, ' ');
  };
  const menus = [...document.querySelectorAll('[role="listbox"], .select__menu, [class*="menu-list"], [role="menu"]')]
    .filter(m => m.getBoundingClientRect().height > 0 && !box.contains(m)).map(compact);
  return { box_sel: box.id ? '[id="' + box.id + '"]' : '[data-cx-box="' + key + '"]', html: compact(box).slice(0, 14000),
           menus: menus.join('\n').slice(0, 6000) };
}'''

SYSTEM = """You operate ONE field of a job application web form with a real mouse and keyboard.
You get: the field's label, the exact answer that must end up selected/typed, the allowed options, and the compacted HTML of
the field's container (and any open dropdown menu). Return JSON only:
{"actions": [ ... ], "note": "<10 words>"}
Allowed actions (executed in order, all scoped to the container unless "global": true):
  {"do": "click", "css": "<CSS selector>"}            real click on the element (for a checkbox/radio, the label or the input)
  {"do": "click_text", "text": "<exact visible text>"}  real click on the smallest element whose text equals this
  {"do": "type", "text": "<text>"}                      types into the focused element
  {"do": "press", "key": "Enter|Tab|Escape|ArrowDown|ArrowUp|Backspace|Meta+A"}
  {"do": "wait", "ms": 300}
Rules: the final state must show EXACTLY the answer (for several answers separated by " | ", every one of them and no others).
Uncheck boxes that are checked but not in the answer. Use ids/for attributes from the HTML when possible; escape [ ] in CSS
ids by using attribute selectors like [id="a[]_1"]. For a dropdown: click it, type a few letters, then click the option.
Never click a submit button. Never type anything other than the answer. If the answer cannot be produced, return
{"actions": [], "note": "impossible: <why>"}."""


def _key():
    for p in KEY_PATHS:
        if p and os.path.exists(p):
            return open(p).read().strip()
    raise RuntimeError('DeepSeek API key not found (~/deepseek/api_key)')


def ask_deepseek(user_msg, usage, system=None):
    body = json.dumps(dict(model=DS_MODEL, temperature=0, response_format={'type': 'json_object'},
                           messages=[{'role': 'system', 'content': system or SYSTEM}, {'role': 'user', 'content': user_msg}])).encode()
    req = urllib.request.Request(DS_URL, data=body, method='POST', headers={
        'Content-Type': 'application/json', 'Authorization': 'Bearer ' + _key()})
    out = json.loads(urllib.request.urlopen(req, timeout=90).read())
    u = out.get('usage', {})
    usage['calls'] += 1; usage['prompt'] += u.get('prompt_tokens', 0); usage['out'] += u.get('completion_tokens', 0)
    return json.loads(out['choices'][0]['message']['content'])


def execute(page, box_sel, actions, log):
    box = page.locator(box_sel).first
    for a in (actions or [])[:25]:
        d = a.get('do')
        scope = page if a.get('global') else box
        try:
            if d == 'click':
                loc = scope.locator(a['css']).first
                if loc.count() == 0 and not a.get('global'): loc = page.locator(a['css']).first
                loc.scroll_into_view_if_needed(timeout=3000); loc.click(timeout=4000)
            elif d == 'click_text':
                t = a['text']
                loc = scope.get_by_text(t, exact=True)
                if loc.count() == 0: loc = page.get_by_text(t, exact=True)
                loc.last.scroll_into_view_if_needed(timeout=3000); loc.last.click(timeout=4000)
            elif d == 'type':
                page.keyboard.type(str(a['text']), delay=30)
            elif d == 'press':
                page.keyboard.press(a['key'])
            elif d == 'wait':
                time.sleep(min(int(a.get('ms', 300)), 3000) / 1000)
            time.sleep(0.15)
        except Exception as e:
            log(f'    action {json.dumps(a)[:120]} failed: {type(e).__name__}: {str(e)[:100]}')
            return f'action {json.dumps(a)[:120]} failed: {type(e).__name__}'
    return None


def check_field(run, f):
    """verify.js on this one field only → (ok, what the page shows). A runner with its own check (run_wd.py) provides check_one."""
    if hasattr(run, 'check_one'):
        return run.check_one(f)
    plan = dict(run.plan); plan['fields'] = [f]
    res = run.page.evaluate('([src, plan]) => { eval(src); return __cxVerify(plan); }', [run.VERIFY_SRC, plan])
    bad = res.get('bad') or []
    return (not bad), (bad[0] if bad else {})


def deepseek_fix(run, f, log, usage):
    """Level 2. Returns True when verify.js accepts the field."""
    history = []
    for attempt in range(1, MAX_TRIES + 1):
        snip = run.page.evaluate(SNIPPET_JS, [f['sel'], f['key']])
        if not snip:
            log(f"  L2 {f['key']}: field not found on the page"); return False
        msg = {'label': f.get('label'), 'answer': f['answer'], 'type_in_plan': f.get('type'),
               'allowed_options': (f.get('options') or [])[:150], 'container_css': snip['box_sel'],
               'container_html': snip['html'], 'open_menus_html': snip['menus'] or None,
               'previous_attempts': history or None}
        try:
            reply = ask_deepseek(json.dumps(msg, ensure_ascii=False), usage)
        except Exception as e:
            log(f"  L2 {f['key']}: DeepSeek call failed: {type(e).__name__}: {str(e)[:120]}"); return False
        acts = reply.get('actions') or []
        log(f"  L2 {f['key']} try {attempt}: {len(acts)} actions — {str(reply.get('note'))[:80]}")
        if not acts:
            return False
        err = execute(run.page, snip['box_sel'], acts, log)
        run.page.mouse.click(2, 2); time.sleep(0.4)
        ok, seen = check_field(run, f)
        if ok:
            log(f"  L2 {f['key']}: verify OK after try {attempt}"); return True
        history.append({'actions': acts, 'error': err, 'verify_saw_on_page': seen.get('page'),
                        'verify_saw_in_react': seen.get('framework')})
    log(f"  L2 {f['key']}: still wrong after {MAX_TRIES} tries")
    return False


def write_handoff(run, fields, url, marker):
    items = []
    for f in fields:
        ok, seen = check_field(run, f)
        items.append({'key': f['key'], 'label': f.get('label'), 'sel': f['sel'], 'want': f['answer'],
                      'options': (f.get('options') or [])[:150], 'page_now': seen.get('page'), 'react_now': seen.get('framework')})
    h = {'created': time.strftime('%Y-%m-%dT%H:%M:%S'), 'url': url, 'tab_marker': marker, 'page_url': run.page.url,
         'fields': items,
         'how': 'Claude in Chrome: open the tab whose URL/marker matches (or rerun run.py --attach in a Claude tab), set ONLY '
                'these fields, touch nothing else, then: run.py "<folder>" --resume --attach <marker> [--submit]'}
    json.dump(h, open(os.path.join(run.folder, 'handoff.json'), 'w'), indent=1, ensure_ascii=False)
    return h


# ---------------------------------------------------------------------------------------------------------------------------
# B. DeepSeek picks ONE option from the REAL list (handoff 2026-10-28b). No click actions: the runner clicks the returned option.
PICK_SYSTEM = """You choose ONE option for one job-application form field for the candidate.
You get: the field label, whether it is required, the candidate's TRUE facts for this field, an ordered preference list
(most preferred first) and the COMPLETE list of options the form offers. Return JSON only:
{"option": "<one option copied EXACTLY from the list>" | "NONE", "why": "<10 words>"}
Rules: answer only with an option that is in the list, character for character. The option must describe the candidate's
real situation (for a field of study: his real study area). Walk the preference list in order and take the first that exists
(exact or the clearly same subject with tiny wording differences, e.g. "Data Science & Analytics"). Never pick a different
subject, a degree level, "Other", "None", "Undecided" or a placeholder unless the preference list names it.
If nothing in the list fits, return "NONE" — an empty field is better than a wrong one."""

# C. DeepSeek maps an unknown question to an answer Joey has ALREADY given (saved facts). Never invents.
TRIAGE_SYSTEM = """You map job-application questions to answers the candidate has ALREADY given.
You get: SAVED_FACTS (his confirmed answers and facts, one per line) and QUESTIONS (label, type, options if any).
For each question return either an answer that follows DIRECTLY from one saved fact, or UNKNOWN. Return JSON only:
{"answers": [{"i": <question index>, "answer": "<exact option text if options are given, else short text>" | "UNKNOWN",
              "source_fact": "<the saved fact line you used, copied>"}]}
Rules: never invent or guess a personal fact, number, date, name, motivation or opinion. Essay / "why" / describe questions
→ UNKNOWN. If options are given, the answer must be one option copied exactly. If two facts conflict or the question asks
something slightly different from the fact (other time frame, other employer, other country), → UNKNOWN.
Work-authorization questions: F-1 student; CPT for the internship is not yet effective → "authorized as of today / effective
now / for any employer" = No; generic "legally authorized to work in the US" = Yes; sponsorship now No (internship) only if
asked separately from future, future Yes; asked together → Yes."""

PROFILE_MD = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '_shared', 'candidate-profile.md')
FACT_SECTIONS = ('Identity & contact', 'Standard application-form answers', 'Additional answers', 'Education')


# Joey 2026-10-27: contact details never go to the DeepSeek API. The Identity section holds them because the
# runner needs them to FILL the form (from wd_profile.json), not because a model should see them.
CONTACT_RE = re.compile(r'[\w.+-]+@[\w-]+\.[\w.]+|\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b|https?://|'
                        r'\b\d{2,5}\s+[A-Z][\w.]*(\s+[A-Z][\w.]*)*\s+(Ave|Avenue|St|Street|Rd|Road|Blvd|Dr|Drive|Ln|Way|Ct|Pl)\b', re.I)


def strip_contact(lines):
    """Drop phone / email / URL / street-address lines before anything is sent to a third-party API."""
    return [l for l in lines if not CONTACT_RE.search(l)]


def saved_facts(path=PROFILE_MD):
    """Compact fact lines from candidate-profile.md: table rows + bullets of the sections that hold confirmed answers.
    Contact details are stripped (see CONTACT_RE) — they are filled by rules, never by a model."""
    try: txt = open(path, encoding='utf-8').read()
    except Exception: return []
    out, on = [], False
    for line in txt.splitlines():
        if line.startswith('#'):
            on = any(k in line for k in FACT_SECTIONS); continue
        if not on: continue
        l = re.sub(r'\*\*|`', '', line).strip()
        if l.startswith('|'):
            cells = [c.strip() for c in l.strip('|').split('|')]
            if len(cells) >= 2 and not re.match(r'^-+$', cells[0]) and cells[0].lower() not in ('question', 'school', 'field'):
                out.append(' — '.join(c for c in cells if c)[:260])
        elif l.startswith('- '):
            out.append(l[2:][:260])
    if jsa_profile.get('education_note'):
        out.append(jsa_profile.get('education_note'))
    return strip_contact(out)


def ds_pick(label, required, facts, prefs, options, usage, log=print):
    """→ exact option text or None. Validates that the answer is in the list."""
    opts = [o for o in dict.fromkeys(options) if o and not re.match(r'^select one$', o, re.I)]
    if not opts: return None
    msg = {'label': label, 'required': bool(required), 'true_facts': facts, 'preference_order': prefs, 'options': opts[:400]}
    try: r = ask_deepseek(json.dumps(msg, ensure_ascii=False), usage, PICK_SYSTEM)
    except Exception as e:
        log(f'  DS pick {label[:40]}: call failed {type(e).__name__}: {str(e)[:80]}'); return None
    o = str(r.get('option') or 'NONE').strip()
    hit = next((x for x in opts if x == o), None) or next((x for x in opts if x.strip().lower() == o.lower()), None)
    log(f"  DS pick {label[:40]}: {o!r} ({r.get('why', '')[:60]}) from {len(opts)} options → {'OK' if hit else 'NONE/invalid'}")
    return hit


def ds_triage(questions, usage, facts=None, log=print):
    """questions = [{label, type, options}] → {index: (answer, source_fact)} for the ones DeepSeek could map; rest = Joey."""
    facts = facts if facts is not None else saved_facts()
    if not questions or not facts: return {}
    qs = [{'i': i, 'label': q['label'], 'type': q.get('type'), 'options': (q.get('options') or [])[:120]} for i, q in enumerate(questions)]
    try: r = ask_deepseek(json.dumps({'SAVED_FACTS': facts, 'QUESTIONS': qs}, ensure_ascii=False), usage, TRIAGE_SYSTEM)
    except Exception as e:
        log(f'  DS triage: call failed {type(e).__name__}: {str(e)[:80]}'); return {}
    out = {}
    for a in r.get('answers') or []:
        try: i = int(a.get('i'))
        except Exception: continue
        if not 0 <= i < len(questions): continue
        ans, src = str(a.get('answer') or '').strip(), str(a.get('source_fact') or '').strip()
        if not ans or ans.upper() == 'UNKNOWN' or not src: continue
        opts = questions[i].get('options') or []
        if opts:
            ans = next((o for o in opts if o == ans), None) or next((o for o in opts if o.strip().lower() == ans.lower()), None)
            if not ans: continue                                   # not an exact option → Joey
        elif len(ans) > 200: continue                              # long free text is never a saved fact
        out[i] = (ans, src)
    log(f'  DS triage: {len(out)}/{len(questions)} mapped to saved facts')
    return out
