#!/usr/bin/env python3
"""Fill (and, only when every gate passes, submit) one application from its plan.json.

  python3 run.py "<app folder>"                 # dry-run: fill + verify, never submits (default)
  python3 run.py "<app folder>" --submit        # submits only if ALL gates pass (see gate())
  python3 run.py "<app folder>" --launch        # tests: launch a local Chromium instead of attaching to the job Chrome
  python3 run.py "<app folder>" --attach <m>    # work in an existing tab of the job Chrome whose URL contains <m> (a Claude in Chrome tab)
  python3 run.py "<app folder>" --resume --attach <m> [--submit]   # after Claude fixed a handed-off field: re-verify (+ submit), no refill

Escalation ladder (ladder.py, Joey 2026-10-28): script fill → DeepSeek per failed field (max 3 tries, verify.js judges) →
handoff.json for Claude in Chrome in the same tab → CAPTCHA to Joey. verify.js is the only judge.

Browser: attaches over CDP to the dedicated job Chrome (start_chrome.sh, port 9222, profile ~/.job-agent-chrome),
so every click and keystroke is a real, trusted browser event (react-select, phone country, location lookups, custom checkboxes).

Writes into the app folder: run_log.md (appended), verify.json, filled_check.png, and on success submitted_confirmation.png.
Writes to <job search agent>/data/runner/: results.jsonl (one line per run) and queue.md (everything that needs Joey).
Gates for --submit: batch approved (data/runner/approved_batches.json lists the folder) · plan.ready · verify.pass ·
no CAPTCHA on the page · no unknown/new required field on the live page. Any failure → no submit, reason queued.
JSA-209: a required extra file slot with no file on hand → STATUS needs-user before filling (slot label queued); after
the click, the form's own validation errors → STATUS failed with the field names (nothing was submitted), not unconfirmed.
"""
import argparse, json, os, re, sys, time
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
import ladder, canon, materials_gate, decide, human_check
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))          # <job search agent>
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
DATA = os.environ.get('CX_DATA') or jpaths.data('runner')
VERIFY_SRC = open(os.path.join(HERE, 'verify.js'), encoding='utf-8').read()
CONFIRM_RE = re.compile(r"(thank you for (applying|your application|your interest)|application (has been |was )?(submitted|received)|"
                        r"we('| ha)ve received your application|successfully submitted|application submitted)", re.I)
CODE_RE = re.compile(r'(security|verification|confirmation) code', re.I)
CAPTCHA_SEL = 'iframe[src*="hcaptcha"], iframe[src*="recaptcha"][src*="bframe"], iframe[title*="challenge" i], div.h-captcha:not(:empty)'


def now():
    return datetime.now().isoformat(timespec='seconds')


def launch_browser(pw):
    """Headless browser for --launch (tests): Playwright's Chromium if installed, else the system Chrome."""
    try:
        return pw.chromium.launch()
    except Exception as e:
        ch = os.environ.get('CX_CHANNEL', 'chrome')
        print(f"playwright chromium unavailable ({str(e).splitlines()[0][:70]}) → launching {ch}")
        return pw.chromium.launch(channel=ch, headless=True)


def company_hint(folder):
    """Company name as the code mail names it (Greenhouse: "…your application to <Company>"), from job.json."""
    try:
        name = json.load(open(os.path.join(folder, 'job.json'), encoding='utf-8')).get('company') or ''
    except Exception:
        return None
    words = [w for w in re.findall(r"[A-Za-z0-9&']+", name) if w.lower() not in ('the', 'a', 'an', 'inc', 'llc') and len(w) >= 2]
    return words[0] if words else None          # first real word: "a Greenhouse employer" → "Walleye" (the mail may shorten the name)


def used_codes():
    p = os.path.join(DATA, 'used_codes.json')
    return set(json.load(open(p))) if os.path.exists(p) else set()


def remember_code(code):
    p = os.path.join(DATA, 'used_codes.json')
    os.makedirs(DATA, exist_ok=True)
    json.dump(sorted(used_codes() | {code})[-200:], open(p, 'w'))


def code_boxes(inputs, n):
    """Pure (tested): which page inputs take an n-character e-mail security code, in typing order. Greenhouse (2026-10-31):
    n one-character boxes id security-input-0..n-1. Else one box marked as a one-time code / named or labelled "security
    code", "verification code" or "code". Never a ZIP / postal / promo / referral / country / area / discount code field."""
    excl = re.compile(r'zip|postal|post code|promo|referral|coupon|discount|country|area|phone|invite', re.I)
    multi = sorted((i for i in inputs if re.fullmatch(r'security-input-\d+', i.get('id') or '')), key=lambda i: int(i['id'].rsplit('-', 1)[1]))
    if multi:
        return [i['id'] for i in multi]
    def text(i): return ' '.join(str(i.get(k) or '') for k in ('id', 'name', 'label'))
    ok = [i for i in inputs if i.get('id') and not excl.search(text(i)) and (i.get('auto') == 'one-time-code'
          or re.search(r'(security|verification|one[- ]time|confirmation|access)[ _-]?code|\botp\b', text(i), re.I)
          or any(str(i.get(k) or '').strip().lower() == 'code' for k in ('id', 'name', 'label')))]
    return [ok[0]['id']] if ok else []


def ids_with_text(ids, code):
    """One character per box when there is one box per character, else the whole code into the single box."""
    return list(zip(ids, code)) if len(ids) > 1 else [(ids[0], code)]


# ---------- extra file slots and the after-submit outcome (JSA-209, Viking 10-31; spec scripts/test_cases/gh_file_slots_spec.md) ----------
def file_slots(plan, folder, transcript_name=None):
    """Pure (tested). The plan's extra file slots (type file, not resume / cover_letter), each with the file on hand:
    Joey's file named in answers.json → the tailored resume / cover letter PDF for a slot that asks only for that →
    the transcript for a transcript-only slot → else None (only Joey can supply it)."""
    import materials_probe
    tname = transcript_name or materials_gate.TRANSCRIPT_NAME
    try:
        answers = json.load(open(os.path.join(folder, 'answers.json'), encoding='utf-8'))
    except (OSError, ValueError):
        answers = {}
    names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    pdf = lambda word: next((x for x in names if x.lower().endswith('.pdf') and word in x.lower()), None)
    out = []
    for f in plan.get('fields') or []:
        if f.get('type') != 'file' or f.get('key') in ('resume', 'cover_letter'):
            continue
        kind = materials_probe.slot_kind(f['key'], f.get('label') or '')
        got = materials_gate.supplied_file(folder, answers if isinstance(answers, dict) else {}, f['key'])
        if not got:
            got = (pdf('resume') if kind == 'resume' else pdf('cover_letter') if kind == 'cover_letter'
                   else tname if kind == 'transcript' and tname in names else None)   # exact name (macOS paths ignore case)
        out.append({'key': f['key'], 'label': f.get('label') or '', 'required': bool(f.get('required')), 'kind': kind, 'file': got})
    return out


def ensure_transcript(plan, folder):
    """A transcript-only extra slot gets the profile's official transcript, copied into the folder (Walleye 2026-10-31)."""
    import materials_probe
    if not any(f.get('type') == 'file' and f.get('key') not in ('resume', 'cover_letter')
               and materials_probe.slot_kind(f['key'], f.get('label') or '') == 'transcript' for f in plan.get('fields') or []):
        return
    dst = os.path.join(folder, materials_gate.TRANSCRIPT_NAME)
    if not os.path.exists(dst) and materials_gate.TRANSCRIPT and os.path.exists(materials_gate.TRANSCRIPT):
        import shutil; shutil.copyfile(materials_gate.TRANSCRIPT, dst)


def grad_transcript_stop(folder, plan, url, log):
    """A graduate-transcript file slot (required or optional) → the job is skipped: he has no graduate transcript yet and the
    undergraduate one never goes there (Joey 2026-11-05 「研究生成绩单目前还没有，那这种问题的岗位就先跳过去」, JSA-216)."""
    import materials_probe
    hits = [f for f in plan.get('fields') or [] if f.get('type') == 'file' and f.get('key') not in ('resume', 'cover_letter')
            and materials_probe.slot_kind(f['key'], f.get('label') or '') == 'grad_transcript']
    if not hits:
        return None
    what = '; '.join(f"\"{f.get('label', '')[:120]}\" ({f['key']})" for f in hits)
    queue(folder, f'skipped: the form asks for a graduate transcript ({what}) — none yet (Joey 2026-11-05: skip these jobs)', url)
    log(f'skipped before filling: graduate transcript slot → {what}')
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, 'results.jsonl'), 'a') as out:
        out.write(json.dumps({'at': now(), 'folder': os.path.basename(folder), 'url': url, 'status': 'skipped',
                              'problems': [f"graduate transcript slot: {f['key']}: {f.get('label', '')[:200]}" for f in hits],
                              'mode': 'gate'}) + '\n')
    return hits


NEEDS_USER_RX = re.compile(r'^plan not ready\b|required fields? not in (the )?plan', re.I)


def stop_status(reasons, submit):
    """Pure (JSA-235). The status of a run the gates stopped: 'dry-run' without --submit; on a submit 'needs-user' when
    a reason is a question Joey has to answer first (plan not ready / a required field the plan does not know — met only
    on the live form), else 'blocked'. Either way nothing was submitted and the folder is queued."""
    if not submit:
        return 'dry-run'
    return 'needs-user' if any(NEEDS_USER_RX.search(str(r)) for r in reasons or []) else 'blocked'


def file_slot_stop(folder, plan, url, log):
    """A required extra file slot with no file → needs-user for Joey with the slot's label, before anything is filled."""
    miss = missing_file_slots(plan, folder)
    if not miss:
        return None
    what = '; '.join(f"\"{s['label'][:160]}\" ({s['key']})" for s in miss)
    queue(folder, f'needs a file from Joey — required file slot: {what} — put the file in the folder and name it in '
                  f'answers.json ({{"{miss[0]["key"]}": "<file name>"}}), then rerun', url)
    log(f'stopped before filling: required file slot without a file → Joey: {what}')
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, 'results.jsonl'), 'a') as out:
        out.write(json.dumps({'at': now(), 'folder': os.path.basename(folder), 'url': url, 'status': 'needs-user',
                              'problems': [f"required file slot without a file: {s['key']}: {s['label'][:200]}" for s in miss],
                              'mode': 'gate'}) + '\n')
    return miss


def missing_file_slots(plan, folder, transcript_name=None):
    """Pure (tested). Required extra file slots with no file on hand → the job stops before Submit, handed to Joey."""
    return [s for s in file_slots(plan, folder, transcript_name) if s['required'] and not s['file']]


def after_submit(confirmed, code_page, before, after):
    """Pure (tested). The outcome once Submit was pressed: confirmed → submitted; a security-code step → unconfirmed;
    validation errors that were not there before the click → failed (the form refused it, nothing was sent), with the
    fields; else unconfirmed."""
    if confirmed:
        return {'status': 'submitted', 'fields': []}
    if code_page:
        return {'status': 'unconfirmed', 'fields': []}
    seen = {e.get('field') for e in before or []}
    new = []
    for e in after or []:
        if e.get('field') not in seen and e.get('field') not in new:
            new.append(e.get('field'))
    return {'status': 'failed', 'fields': new} if new else {'status': 'unconfirmed', 'fields': []}


SUBMIT_ERRORS_JS = r'''(plan) => {
  const N = s => String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
  const scope = document.querySelector('form') || document.body;
  const visible = el => { const cs = getComputedStyle(el); const r = el.getBoundingClientRect();
    return cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0; };
  const matches = (el, f) => { if (el.id === f.key || el.getAttribute('name') === f.key) return true;
    try { return !!f.sel && el.matches(f.sel); } catch (e) { return false; } };
  const planOf = el => plan.find(f => matches(el, f));
  const errRe = /(this field is required|is required\.?$|please (enter|select|fill|provide|complete|upload|attach)|is invalid|invalid (email|phone|format|value)|can't be blank|cannot be blank)/i;
  const legendRe = /indicates a required field|required fields are marked/i;
  const cls = el => String((el && el.className && el.className.baseVal !== undefined ? el.className.baseVal : (el && el.className)) || '');
  const fieldOf = n => {
    for (let a = n; a && a !== scope.parentElement; a = a.parentElement) {
      const hit = new Set();
      a.querySelectorAll('input, textarea, select').forEach(c => { const f = planOf(c); if (f) hit.add(f); });
      if (hit.size === 1) return [...hit][0].label;
      if (hit.size > 1) break;
      if (a === scope) break;
    }
    const box = n.closest('[class*="field"], .application-question, fieldset, li');
    const lab = box && box.querySelector('label');
    return lab ? N(lab.textContent) : N(n.textContent);
  };
  const out = [], seen = new Set();
  scope.querySelectorAll('*').forEach(n => {
    const t = N(n.textContent);
    if (n.children.length || !t || t.length > 160 || !visible(n) || legendRe.test(t)) return;
    const styled = /error|invalid/i.test(cls(n) + ' ' + cls(n.parentElement)) || n.getAttribute('role') === 'alert';
    if (!errRe.test(t) && !styled) return;
    if (n.closest('label') && !/error|invalid|helper/i.test(cls(n))) return;
    if (!styled && n.closest('[id$="-description"], .question-description, [class*="description"]')) return;
    const field = fieldOf(n);
    if (!seen.has(field)) { seen.add(field); out.push({ field, msg: t }); }
  });
  scope.querySelectorAll('[aria-invalid="true"]').forEach(el => {
    if (!visible(el)) return;
    const f = planOf(el); const field = f ? f.label : (el.id || el.getAttribute('name') || '');
    if (!seen.has(field)) { seen.add(field); out.push({ field, msg: 'aria-invalid' }); }
  });
  return out; }'''


class Run:
    def __init__(self, folder, page, log):
        self.folder, self.page, self.log = folder, page, log
        self.plan = json.load(open(os.path.join(folder, 'plan.json'), encoding='utf-8'))
        self.problems = []          # general problems (block the gate)
        self.field_problems = {}    # key → message (the ladder may clear them)
        self.VERIFY_SRC = VERIFY_SRC
        self.absent = []            # optional / generic-profile fields this form does not have

    # ---------- widgets (all real clicks / keys) ----------
    def combo(self, f):
        p, sel, want = self.page, f['sel'], str(f['answer'])
        loc = p.locator(sel).first
        loc.scroll_into_view_if_needed()
        loc.click()
        p.keyboard.press('Control+A') if sys.platform != 'darwin' else p.keyboard.press('Meta+A')
        p.keyboard.press('Backspace')
        wants = [want] + [x for x in (f.get('alts') or []) if x != want]
        queries = wants if f['key'] not in ('location',) else [want.split(',')[0], ', '.join(want.split(',')[:2]), want]
        if f['key'] == 'country':
            queries = ['United States']
        for q in queries:
            p.keyboard.type(q, delay=25)
            try:
                p.wait_for_selector('.select__option', timeout=4000)
            except Exception:
                p.keyboard.press('Meta+A' if sys.platform == 'darwin' else 'Control+A'); p.keyboard.press('Backspace')
                continue
            time.sleep(0.3)
            opts = p.locator('.select__option')
            texts = [t.strip() for t in opts.all_inner_texts()]
            idx = next((i for i, t in enumerate(texts) if t == q or t == want), None) if f['key'] != 'location' else None
            if idx is None and f['key'] in ('country',):
                idx = next((i for i, t in enumerate(texts) if t.startswith('United States')), None)
            if idx is None and f['key'] == 'location':
                idx = next((i for i, t in enumerate(texts) if t.lower().startswith(want.lower())), None)
            if idx is not None:
                opts.nth(idx).click()
                return True
            p.keyboard.press('Meta+A' if sys.platform == 'darwin' else 'Control+A'); p.keyboard.press('Backspace')
        p.keyboard.press('Escape')
        self.problems.append(f"{f['key']}: option '{want}' not offered")
        return False

    def text(self, f):
        loc = self.page.locator(f['sel']).first
        loc.scroll_into_view_if_needed()
        loc.fill(str(f['answer']))          # Playwright fill = focus + input events → React sees it
        return True

    def native_select(self, f):
        self.page.locator(f['sel']).first.select_option(label=str(f['answer']))
        return True

    def radio(self, f):
        name = f['key']
        loc = self.page.locator(f'input[type=radio][name="{name}"][value="{f["answer"]}"]')
        if loc.count() == 0:
            loc = self.page.get_by_role('radio', name=str(f['answer']))
        loc.first.check(force=True)
        return True

    def checkbox(self, f):
        loc = self.page.locator(f['sel']).first
        want = f['answer'] in (True, 'Yes', 'yes', 'checked', 'true')
        if loc.is_checked() != want:
            box = loc.locator('xpath=ancestor::label[1]')
            (box if box.count() else loc).first.click()      # a real click on the visible label/box
        if loc.is_checked() != want:
            loc.check(force=True) if want else loc.uncheck(force=True)
        return True

    def checkbox_group(self, f):
        want = [w.strip() for w in str(f['answer']).split(' | ')]
        ids = self.page.locator(f['sel']).first.evaluate('''(el, want) => {
            const box = el.closest('fieldset, [role="group"], .checkbox-group, [class*="field"]') || document;
            const out = [];
            box.querySelectorAll('input[type=checkbox]').forEach((x, i) => {
              if (!x.id) x.id = 'cxcb_' + i + '_' + Math.random().toString(36).slice(2, 7);
              const l = document.querySelector('label[for="' + CSS.escape(x.id) + '"]') || x.closest('label');
              const t = (l ? l.textContent : x.value).replace(/\\s+/g, ' ').trim();
              if (want.includes(t) !== x.checked) out.push(x.id);
            });
            return out; }''', want)
        for i in ids:
            cb = self.page.locator(f'[id="{i}"]')
            lab = self.page.locator(f'label[for="{i}"]')
            (lab if lab.count() else cb).first.click()
        return True

    def upload_resume(self):
        pdfs = [x for x in os.listdir(self.folder) if x.lower().endswith('.pdf') and 'resume' in x.lower()]
        if not pdfs:
            self.problems.append('no resume PDF in the folder'); return
        fin = self.page.locator('input[type=file]#resume, input[type=file][name="resume"]').first
        if fin.count() == 0: fin = self.page.locator('input[type=file]').first
        if fin.count() == 0:
            self.problems.append('no file input for the resume'); return
        fin.set_input_files(os.path.join(self.folder, sorted(pdfs)[0]))
        self.log(f'resume uploaded: {sorted(pdfs)[0]}')
        cl = [x for x in os.listdir(self.folder) if x.lower().endswith('.pdf') and 'cover_letter' in x.lower()]
        cin = self.page.locator('input[type=file]#cover_letter, input[type=file][name="cover_letter"]')
        if cl and cin.count():
            cin.first.set_input_files(os.path.join(self.folder, sorted(cl)[0])); self.log(f'cover letter uploaded: {sorted(cl)[0]}')
        self.upload_extra()

    def upload_extra(self):
        """Every extra file slot (JSA-209): the file on hand (file_slots) goes into its input; a transcript-only slot gets the
        profile's official transcript (Walleye / TransMarket 2026-10-31). A required slot left without a file is a problem."""
        ensure_transcript(self.plan, self.folder)
        for s in file_slots(self.plan, self.folder):
            fin = self.page.locator(f'input[type=file][id="{s["key"]}"], input[type=file][name="{s["key"]}"]')
            if s['file'] and fin.count():
                fin.first.set_input_files(os.path.join(self.folder, s['file'])); self.log(f'{s["kind"]} uploaded: {s["file"]} → {s["key"]}')
            elif s['required']:
                self.problems.append(f'required file slot {s["key"]} not filled: {s["label"][:80]}')

    def submit_errors(self):
        """The form's visible validation errors as [{field, msg}] (SUBMIT_ERRORS_JS; spec gh_submit_errors_spec.md)."""
        try:
            return self.page.evaluate(SUBMIT_ERRORS_JS, [{'key': f['key'].replace('[]', ''), 'label': f.get('label') or f['key'],
                                                          'sel': f.get('sel') or ''} for f in self.plan['fields']])
        except Exception:
            return []

    # ---------- steps ----------
    def fill_one(self, f, el_tag):
        if el_tag.endswith('|checkbox') and (f['type'] == 'multi' or f['key'].endswith('[]')):
            self.checkbox_group(f)
        elif el_tag.startswith('COMBO') or (f['type'] in ('combo', 'multi') and not el_tag.startswith('SELECT')):
            if not self.combo(f): self.field_problems[f['key']] = self.problems.pop()
        elif el_tag.startswith('SELECT'):
            self.native_select(f)
        elif f['type'] == 'radio' or el_tag.endswith('|radio'):
            self.radio(f)
        elif f['type'] == 'checkbox' or el_tag.endswith('|checkbox'):
            self.checkbox(f)
        else:
            self.text(f)

    def tag_of(self, f):
        loc = self.page.locator(f['sel'])
        if not loc.count(): return ''
        return loc.first.evaluate(
            'e => (e.closest(".select__control") || e.getAttribute("role") === "combobox" ? "COMBO" : e.tagName) + "|" + (e.type||"")')

    def fill(self):
        """Level 1 (script). Per-field failures go to self.field_problems for the ladder; nothing here is the judge."""
        fields = [f for f in self.plan['fields'] if f.get('status') == 'ok']
        order = lambda f: 0 if (f['type'] in ('combo', 'multi', 'select', 'radio', 'checkbox') or f['key'] in ('location', 'country')) else 1   # widgets first, text last
        later = []
        for rnd, todo in ((1, sorted(fields, key=order)), (2, later)):
            for f in list(todo):
                try:
                    el_tag = self.tag_of(f)
                    if not el_tag and f['type'] != 'radio':
                        if rnd == 1:            # may appear after another answer (race after ethnicity) → second pass
                            later.append(f); continue
                        generic = str(f.get('source') or '').startswith('rules:') and re.search(r'--\d+$', f['key'])
                        if not f.get('required') or generic:
                            f['status'] = 'absent'; self.absent.append(f['key'])
                            self.log(f"{f['key']}: not on this form — skipped ({'optional' if not f.get('required') else 'generic profile field'})")
                        else:
                            self.field_problems[f['key']] = 'not on the page'
                        continue
                    self.fill_one(f, el_tag)
                except Exception as e:
                    self.field_problems[f['key']] = f"{type(e).__name__}: {str(e)[:120]}"
            self.page.mouse.click(2, 2)
            time.sleep(0.5)

    def verify(self):
        res = self.page.evaluate('([src, plan]) => { eval(src); return __cxVerify(plan); }', [VERIFY_SRC, self.plan])
        json.dump(res, open(os.path.join(self.folder, 'verify.json'), 'w'), indent=1, ensure_ascii=False)
        return res

    def captcha(self):
        try:
            return any(l.is_visible() for l in self.page.locator(CAPTCHA_SEL).all())
        except Exception:
            return False

    def unplanned_required(self):
        """Required fields on the live page that the plan does not cover (form changed since the plan was built) — required
        file uploads included (Viking 10-31: a required document the plan had no file for was submitted empty)."""
        known = [f['key'].replace('[]', '') for f in self.plan['fields']] + [f['sel'].lstrip('#') for f in self.plan['fields']]
        return self.page.evaluate('''(known) => {
          const out = [];
          document.querySelectorAll('form input, form textarea, form select').forEach(el => {
            if (el.type === 'hidden' || el.disabled) return;
            const req = el.required || el.getAttribute('aria-required') === 'true'
              || (el.type === 'file' && /\\*|required/i.test(((el.closest('.field, .application-question, div') || {}).innerText || '').slice(0, 200)));   // a required upload the plan has no file for (Viking 10-31)
            if (!req || !el.id) return;
            const id = el.id.replace('[]', '');
            if (known.some(k => id === k || id.startsWith(k + '_') || id.startsWith(k + '[]'))) return;
            if (/^(country|react-select|iti)/.test(el.id)) return;
            out.push(el.id);
          });
          return out; }''', known)


def gate(r, res, submit, approved):
    reasons = []
    if not submit: reasons.append('dry-run')
    if not approved: reasons.append('batch not approved')
    if not r.plan.get('ready'): reasons.append('plan not ready: ' + ', '.join(n['key'] for n in r.plan.get('needs_user', [])))
    if not res.get('pass'): reasons.append(f"verify failed: bad={[b['key'] for b in res.get('bad', [])]} errors={[e['key'][:30] for e in res.get('errors', [])]}")
    if r.problems: reasons.append('fill problems: ' + '; '.join(r.problems[:6]))
    if r.field_problems: reasons.append('field problems: ' + '; '.join(f'{k}: {v}' for k, v in list(r.field_problems.items())[:6]))
    return reasons


def approved_for(folder):
    p = os.path.join(DATA, 'approved_batches.json')
    if not os.path.exists(p): return False
    name = os.path.basename(os.path.abspath(folder))
    return any(name in b.get('folders', []) for b in json.load(open(p)).get('batches', []))


def queue(folder, reason, url):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, 'queue.md'), 'a', encoding='utf-8') as q:
        q.write(f"- [ ] {now()} **{os.path.basename(os.path.abspath(folder))}** — {reason} — {url}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('folder'); ap.add_argument('--submit', action='store_true'); ap.add_argument('--launch', action='store_true')
    ap.add_argument('--url', help='override plan url (tests)'); ap.add_argument('--cdp', default='http://127.0.0.1:9222')
    ap.add_argument('--keep-open', action='store_true')
    ap.add_argument('--attach', help='use the existing job-Chrome tab whose URL contains this text (a Claude in Chrome tab)')
    ap.add_argument('--resume', action='store_true', help='no navigation/upload/fill: re-verify the tab (after a Claude fix) and gate/submit')
    ap.add_argument('--no-ladder', action='store_true', help='script only (tests)')
    ap.add_argument('--materials-gate', choices=materials_gate.MODES, default=materials_gate.DEFAULT_MODE,
                    help='material gate before filling: block (default: stop unless decide.py says skip) | warn (log only) | off')
    a = ap.parse_args()
    import chrome_lock; chrome_lock.hold(f'run.py {os.path.basename(os.path.normpath(a.folder))}')   # JSA-236: one driver of the job Chrome
    t0 = time.time()
    from playwright.sync_api import sync_playwright
    folder = jpaths.folder(a.folder)   # as typed, else under the data home (ADR-0008)
    if a.submit and os.path.exists(os.path.join(folder, 'submitted_confirmation.png')):
        print('already submitted (submitted_confirmation.png exists) — skipped'); print('STATUS already-submitted'); return
    logf = open(os.path.join(folder, 'run_log.md'), 'a', encoding='utf-8')
    def log(m): logf.write(f'- {now()} {m}\n'); logf.flush(); print(m)
    gate_mode = 'off' if a.resume else a.materials_gate      # resume = re-verify only, nothing is filled or uploaded
    try:
        plan0 = json.load(open(os.path.join(folder, 'plan.json'), encoding='utf-8'))
    except Exception:
        plan0 = {}
    if plan0.get('fields'):                                   # JSA-209: a required extra file slot needs Joey's file first
        grad = grad_transcript_stop(folder, plan0, a.url or plan0.get('url', ''), log)
        if grad:
            print('STATUS skipped'); return
        ensure_transcript(plan0, folder)
        if a.submit and file_slot_stop(folder, plan0, a.url or plan0.get('url', ''), log):
            print('STATUS needs-user'); return
        for s in missing_file_slots(plan0, folder):
            log(f"dry-run: required file slot without a file (a submit would stop for Joey): {s['key']}: {s['label'][:100]}")
    ask = None if a.no_ladder else decide.deepseek_ask        # problems go through decide.py (JSA-002 slice 2)
    mg = materials_gate.run_gate(folder, log, gate_mode, ask=ask, ats=plan0.get('ats'))
    if gate_mode == 'block' and not mg['ok']:
        url0 = a.url or plan0.get('url', '')
        queue(folder, 'materials incomplete: ' + '; '.join((mg['next'] or mg['problems'])[:4]), url0)
        log('stopped before filling: materials gate (block)')
        os.makedirs(DATA, exist_ok=True)                  # a results line for every run, so the scorecard sees gate stops too (a Greenhouse employer 2026-10-31)
        with open(os.path.join(DATA, 'results.jsonl'), 'a') as out:
            out.write(json.dumps({'at': now(), 'folder': os.path.basename(folder), 'url': url0, 'status': 'blocked',
                                  'problems': ['materials gate: ' + '; '.join((mg['next'] or mg['problems'])[:4])[:300]], 'mode': 'gate'}) + '\n')
        print('STATUS blocked'); return
    import chrome_guard                                       # JSA-227: no autofill / password extension in the job Chrome
    if chrome_guard.stop(folder, a.url or plan0.get('url', ''), log, queue, DATA, 'greenhouse'): return
    with sync_playwright() as pw:
        if a.launch:
            br = launch_browser(pw); ctx = br.new_context(); page = ctx.new_page()
        else:
            br = pw.chromium.connect_over_cdp(a.cdp); ctx = br.contexts[0]
            plan_url = json.load(open(os.path.join(folder, 'plan.json'), encoding='utf-8'))['url']
            if a.attach or a.resume:
                cands = [p for p in ctx.pages if (a.attach and a.attach in p.url)] or [p for p in ctx.pages if p.url.split('#')[0] == plan_url]
                if not cands:
                    print('no tab found for --attach/--resume', a.attach, plan_url); print('STATUS no-tab'); return
                page = cands[-1]
            else:
                page = ctx.new_page()
        page.set_default_timeout(8000)          # a blocked click (overlay, hidden widget) fails fast → ladder, not a 30 s hang
        r = Run(folder, page, log)
        url = a.url or r.plan['url']
        rt_path = os.path.join(folder, 'runtime.json')
        usage = {'calls': 0, 'prompt': 0, 'out': 0}
        log(f'start {"SUBMIT" if a.submit else "dry-run"}{" RESUME" if a.resume else ""} {url}')
        if a.resume:
            rt = json.load(open(rt_path)) if os.path.exists(rt_path) else {}
            for f in r.plan['fields']:
                if f['key'] in rt.get('absent', []): f['status'] = 'absent'
            r.absent = rt.get('absent', [])
            if os.path.exists(os.path.join(folder, 'handoff.json')):
                os.rename(os.path.join(folder, 'handoff.json'), os.path.join(folder, f'handoff_done_{int(time.time())}.json'))
        else:
            page.goto(url, wait_until='domcontentloaded'); page.wait_for_selector('form', timeout=30000); time.sleep(1.5)
            if r.plan.get('ats') == 'greenhouse' and not a.url:
                r.upload_resume()
            r.fill()                                                   # level 1: script
            json.dump({'absent': r.absent, 'at': now()}, open(rt_path, 'w'))
        handoff = []
        if not a.resume and not a.no_ladder:                           # level 2: DeepSeek, one field at a time
            res0 = r.verify()
            bad = {b['key'] for b in res0.get('bad', [])} | set(r.field_problems)
            targets = [f for f in r.plan['fields'] if f.get('status') == 'ok' and f['key'] in bad]
            if targets: log(f'ladder: {len(targets)} field(s) → DeepSeek: ' + ', '.join(f['key'] for f in targets))
            for f in targets:
                if ladder.deepseek_fix(r, f, log, usage):
                    r.field_problems.pop(f['key'], None)
                else:
                    handoff.append(f)
            if usage['calls']:
                log(f"DeepSeek usage: {usage['calls']} calls, {usage['prompt']} prompt + {usage['out']} output tokens")
        extra = r.unplanned_required()
        if extra: r.problems.append('required fields not in plan: ' + ', '.join(extra[:8]))
        res = r.verify()
        page.screenshot(path=os.path.join(folder, 'filled_check.png'), full_page=True)
        cap = r.captcha()
        # canonical audit: the page against Joey's facts, independent of the plan (canon.py).
        # verify.js compares page vs plan; this catches a plan that is itself wrong.
        try:
            cbad = canon.audit(page.evaluate(canon.probe_src() + '; __cxCanonProbe()'), canon.tenant_of(url))
        except Exception as e:
            cbad = []
            r.problems.append(f'canonical audit unavailable: {type(e).__name__}: {str(e)[:80]}')
        json.dump(cbad, open(os.path.join(folder, 'canon.json'), 'w'), indent=1, ensure_ascii=False)
        if cbad:
            r.problems.extend(canon.block(cbad))
            log('canonical audit FAILED: ' + '; '.join(f"{m['key']}={m['value']!r}" for m in cbad))
        if handoff:                                                    # level 3: Claude in Chrome, same tab
            h = ladder.write_handoff(r, handoff, url, a.attach)
            r.problems.append('handed to Claude: ' + ', '.join(x['key'] for x in h['fields']))
        reasons = gate(r, res, a.submit, approved_for(folder))
        if r.problems: log('problems: ' + '; '.join(r.problems))
        log(f"verify pass={res.get('pass')} counts={res.get('counts')} bad={[b['key'] for b in res.get('bad', [])]} errors={len(res.get('errors', []))} captcha={cap}")
        status = 'filled'
        if handoff:
            log('HANDOFF to Claude in Chrome (handoff.json); tab kept open: ' + page.url)
            status = 'handoff'
        elif reasons:
            log('NOT submitted: ' + ' | '.join(reasons))
            if a.submit: queue(folder, 'not submitted: ' + ' | '.join(reasons), url)
            status = stop_status(reasons, a.submit)          # JSA-235: an answer Joey owes → needs-user
        elif cap:
            log('CAPTCHA present → hand-off'); queue(folder, 'CAPTCHA — solve it, then the runner finishes (or click Submit)', url); status = 'captcha'
            human_check.park(folder, 'greenhouse', page.url, [{}])    # JSA-106: push + open-check list, the batch moves on
        else:
            btn = page.get_by_role('button', name=re.compile(r'^\s*submit( application)?\s*$', re.I)).first
            pre_txt = page.inner_text('body')[:20000]; pre_hit = bool(CONFIRM_RE.search(pre_txt)); pre_url = page.url
            pre_errs = r.submit_errors()                 # JSA-209: errors after the click count only when they are new
            btn.click(); log('submit clicked')
            ok, t_submit, code_done, err_polls, txt = False, datetime.now().astimezone(), False, 0, ''
            for _ in range(80):
                time.sleep(0.5)
                txt = page.inner_text('body')[:20000]
                if 'confirmation' in page.url.lower() and page.url != pre_url: ok = True; break     # Greenhouse /confirmation page
                if CONFIRM_RE.search(txt) and not pre_hit: ok = True; break                         # thank-you text that was not there before
                if r.captcha(): break
                if not code_done and not CODE_RE.search(txt):   # the form refused it (Viking 10-31: "This field is required")
                    err_polls = err_polls + 1 if after_submit(False, False, pre_errs, r.submit_errors())['fields'] else 0
                    if err_polls >= 2: break                    # seen on two polls in a row: client-side validation, nothing sent
                if not code_done and CODE_RE.search(txt):            # e.g. Greenhouse "enter the security code sent to your email"
                    code_done = True
                    log('email security code requested → reading Gmail (read-only)')
                    try:
                        from gmail_code import wait_for_code
                        used = used_codes()
                        code = wait_for_code(sender=None, since=t_submit - timedelta(seconds=30), timeout=150,
                                             hint=company_hint(folder), exclude=used)
                        if code: remember_code(code)
                    except BaseException as e:                     # SystemExit or an IMAP error: never crash without a result line
                        code = None; log(f'code read failed: {type(e).__name__} {str(e)[:120]}')
                    if not code:
                        log('no code found'); break
                    inputs = page.evaluate('''() => [...document.querySelectorAll('input')].filter(e => e.offsetParent !== null && e.type !== 'hidden' && e.type !== 'file')
                        .map(e => ({id: e.id, name: e.name, label: e.getAttribute('aria-label') || '', auto: e.autocomplete || '', maxlength: e.maxLength}))''')
                    ids = code_boxes(inputs, len(code))
                    if not ids:
                        log('no security-code box found on the page'); break
                    for sel, part in ids_with_text(ids, code):
                        page.locator(f'[id="{sel}"]').fill(part)
                    log(f'code entered ({len(ids)} box(es))')
                    sub = page.get_by_role('button', name=re.compile(r'submit|verify|continue|confirm', re.I)).first
                    try:
                        if sub.count(): sub.click(timeout=15000)
                    except Exception as e:
                        log(f'submit after code not clickable: {str(e)[:80]}')
            if ok:
                page.screenshot(path=os.path.join(folder, 'submitted_confirmation.png'), full_page=True)
                m = CONFIRM_RE.search(txt); log('CONFIRMED: ' + (m.group(0) if m else '') + ' | ' + page.url); status = 'submitted'
                with open(os.path.join(folder, 'application_record.md'), 'a', encoding='utf-8') as rec:
                    rec.write(f"\n## Submitted by runner {now()}\n- URL: {url}\n- verify.json: pass (nonce {r.plan.get('nonce')})\n- Confirmation: submitted_confirmation.png\n")
            else:
                code_page = code_done or bool(CODE_RE.search(txt))
                post_errs = [] if code_page else r.submit_errors()
                out = after_submit(False, code_page, pre_errs, post_errs)
                status = out['status']
                page.screenshot(path=os.path.join(folder, 'after_submit.png'), full_page=True)
                if status == 'failed':                    # validation errors on the page: nothing was submitted
                    msgs = {e['field']: e['msg'] for e in post_errs}
                    what = '; '.join(f"{fld[:90]}: {msgs.get(fld, '')[:60]}" for fld in out['fields'][:6])
                    r.problems.append('form refused the submit (validation errors, nothing submitted): ' + what)
                    json.dump(post_errs, open(os.path.join(folder, 'submit_errors.json'), 'w'), indent=1, ensure_ascii=False)
                    queue(folder, 'form refused the submit — validation errors, nothing was submitted: ' + what + ' — see after_submit.png', url)
                    log('FAILED: the form refused the submit (validation errors): ' + what)
                else:
                    queue(folder, 'clicked Submit but no confirmation seen (CAPTCHA / email code / error?) — see after_submit.png', url)
                    log('no confirmation seen')
        os.makedirs(DATA, exist_ok=True)
        with open(os.path.join(DATA, 'results.jsonl'), 'a') as out:
            out.write(json.dumps({'at': now(), 'folder': os.path.basename(folder), 'url': url, 'status': status,
                                  'verify_pass': res.get('pass'), 'problems': r.problems[:8],
                                  'field_problems': r.field_problems, 'deepseek': usage,
                                  'secs': round(time.time() - t0, 1), 'mode': 'resume' if a.resume else 'full'}) + '\n')
        if status == 'submitted':        # JSA-014: Applied row in data/store + queue lines ticked, no hand edit
            sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'scripts', 'store'))
            import sync_results; sync_results.sync_folder(folder, log)
        if status != 'captcha': human_check.resolve(folder, status)
        print('STATUS', status)
        if a.attach and a.attach.startswith('cx=') and status != 'handoff':
            try: page.goto('https://example.com/?' + a.attach)        # hand the Claude tab back for the next job of the batch
            except Exception: pass
        print(f'TIME {round(time.time() - t0, 1)}s')
        import tab_policy                                     # Joey 2026-11-05: close the tab when the run ends; a CAPTCHA hand-off / --keep-open / attach stays
        if not (a.keep_open or a.attach or a.resume or handoff or tab_policy.keep_open(status)) and not page.is_closed(): page.close()
        if a.launch: br.close()


if __name__ == '__main__':
    main()
