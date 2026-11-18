#!/usr/bin/env python3
"""TikTok / ByteDance runner (JSA-047, 2026-11-03): DRY-RUN ONLY. Opens the apply form in the job Chrome, signs in with the
Keychain password, uploads the resume, corrects what the resume parser got wrong from config/, answers the questions with
answer_rules.js, reads every field back and stops. There is no submit code path: the limit is 2 early-career applications per
half-year (TikTok + ByteDance together, no withdrawal) and Submit always shows a CAPTCHA, so the candidate submits by hand
after reading form_check.json (skills/ats-tiktok/SKILL.md).

    ~/.job-agent-venv/bin/python run_tiktok.py --job J02045 [--resume <pdf>] [--out <dir>] [--wait-captcha 5]
    ~/.job-agent-venv/bin/python run_tiktok.py --url https://lifeattiktok.com/search/<id> --track Data_Engineer

Writes <out>/run_log.md, form_check.json (every field: want / page / ok; slots; parsed entries for review), filled_check.png;
one line in data/runner/results.jsonl (status dry-run | blocked | captcha | no-slot). Default out: data/runner/tiktok/<job id>.
Slot guard (JSA-097): before Chrome is touched, the tracker is counted (skills/auto-apply/scripts/tiktok_slots.py); a counted
role whose program has used its 2 slots in this half-year is refused (status no-slot), so the form is never put in front of
the candidate. The form's own banner is compared with the tracker afterwards (fewer left on the page = a missing tracker row).
"""
import cdp_connect  # JSA-386: opens a tab when the job Chrome has none
import argparse, json, os, re, subprocess, sys, time
if __name__ == '__main__':   # live runs only (a test that imports this module never turns it on)
    os.environ.setdefault('CX_SECOND_OPINION', '1')   # uncertain rule answers get a second opinion (JSA-202)
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as jpaths  # noqa: E402  (data home: $JSA_HOME, else this repo — ADR-0008)
import jsa_profile  # noqa: E402  (JSA-403: the user's own values come from the profile)
DATA = os.environ.get('CX_DATA') or jpaths.data('runner')
RULES = os.path.join(HERE, '..', 'scripts', 'answer_rules.js')
COMPANY = ''                                                   # the hiring company (job.json / store row): referral questions check it against the referrer pool (JSA-195)
sys.path.insert(0, os.path.join(HERE, '..', 'scripts'))
import tiktok_slots  # noqa: E402

SLOTS = re.compile(r'submit up to (\d+) job applications?.*?within the [“"](.+?)[”"] recruitment project\.\s*You currently have (\d+) application', re.S | re.I)
CAPTCHA_TEXT = re.compile(r'select \d+ objects|drag the (slider|puzzle)|verify you are human|security check', re.I)
TT_DEGREE = {'phd': 'PhD', 'mba': 'MBA', 'master': "Master's degree", 'bachelor': "Bachelor's degree", 'associate': 'Associate degree'}
PRESENT = 'Present'                                            # the end-month panel's "ongoing" item (data-cy="-")
TRACKS = {'Data Engineer': 'Data_Engineer', 'Data Sci / Analytics': 'Data_Analyst', 'Product Manager': 'Product_Manager',
          'AI Agentic Eng': 'AI_Agentic_Engineer', 'AI Product Manager': 'Product_Manager'}


# ---------- pure helpers (tested: test/t_tiktok.py) ----------
def N(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def apply_url(url):
    """Posting URL → apply-form URL, or None when it is not a TikTok / ByteDance posting."""
    u = str(url or '').strip()
    m = re.match(r'https?://(?:www\.)?(?:lifeattiktok\.com|careers\.tiktok\.com)/(?:search|position|resume)/(\d{10,})', u)
    if m:
        return f'https://lifeattiktok.com/resume/{m.group(1)}/apply'
    m = re.match(r'https?://(?:www\.)?(?:jobs\.bytedance\.com/(?:en/)?(?:position|resume)|joinbytedance\.com/(?:search|position))/(\d{10,})', u)
    if m:
        return f'https://jobs.bytedance.com/en/resume/{m.group(1)}/apply'
    return None


def parse_slots(text):
    """The form's banner → {'limit', 'project', 'remaining'}; None when the banner is not on the page."""
    m = SLOTS.search(N(text))
    return {'limit': int(m.group(1)), 'project': m.group(2).strip(), 'remaining': int(m.group(3))} if m else None


def field_of(degree):
    """'M.S. Applied Data Science' → 'Applied Data Science' (profile degree string → TikTok's free-text field of study)."""
    return re.sub(r'^\s*(?:[A-Z][A-Za-z]{0,3}\.){1,3}\s*', '', str(degree or '')).strip()


def month(s):
    """'08/2025' · '2025-08' · '2025.8' → '2025-08'; anything else → ''."""
    s = str(s or '')
    m = re.search(r'(\d{4})\D(\d{1,2})\b', s) or None
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}'
    m = re.search(r'\b(\d{1,2})/(\d{4})\b', s)
    return f'{m.group(2)}-{int(m.group(1)):02d}' if m else ''


def edu_plan(entries, education, wd_education):
    """entries = the education blocks on the page [{'idx', 'school'}]; education = config/profile.json education;
    wd_education = config/wd_profile.json education (From_month / To_month). Each profile school is used once, in the order of
    the page. Returns (plan, problems): plan = [{'idx', 'degree', 'field', 'start', 'end'}] for matched blocks; a block whose
    school is not in the profile (e.g. a school kept off applications) and a profile school missing from the page → problems."""
    plan, problems, used = [], [], set()
    for e in entries:
        school = N(e.get('school')).lower()
        hit = None
        for i, p in enumerate(education):
            if i in used or not school:
                continue
            if re.search(p.get('match_re') or re.escape(p['school'].lower()), school, re.I):
                if p.get('level') == 'master' and re.search(r'illinois|urbana|uiuc', school) and not re.search(r'illinois', p['school'], re.I):
                    continue
                hit = i
                break
        if hit is None:
            problems.append(f"education block {e.get('idx')}: school {e.get('school')!r} is not in the profile — delete the block by hand")
            continue
        used.add(hit)
        p = education[hit]
        wd = next((w for w in wd_education if re.search(w.get('match', '^$'), p['school'], re.I)), {})
        plan.append({'idx': e.get('idx'), 'school': p['school'], 'degree': TT_DEGREE.get(p.get('level'), ''),
                     'field': field_of(p.get('degree')), 'start': wd.get('From_month', ''), 'end': wd.get('To_month', '')})
    for i, p in enumerate(education):
        if i not in used:
            problems.append(f"{p['school']} is not on the form — add the education block by hand")
    return plan, problems


def lang_plan(entries, languages):
    """entries = [{'idx', 'language'}]; languages = config/wd_profile.json languages (match regex + 'tiktok' level)."""
    plan, problems = [], []
    for e in entries:
        name = N(e.get('language'))
        w = next((l for l in languages if re.search(l['match'], name, re.I) or (re.search(r'mandarin|cantonese', name, re.I) and 'chinese' in l['match'])), None)
        if not w or not w.get('tiktok'):
            problems.append(f"language block {e.get('idx')}: {name!r} has no TikTok level in config/wd_profile.json")
        else:
            plan.append({'idx': e.get('idx'), 'language': name, 'proficiency': w['tiktok']})
    return plan, problems


def work_plan(entries, work):
    """Parsed internship / work blocks [{'idx', 'kind', 'company'}] vs config/wd_profile.json work → title and period to set."""
    plan, problems = [], []
    for e in entries:
        w = next((x for x in work if re.search(x['match'], N(e.get('company')), re.I)), None)
        if not w:
            problems.append(f"{e.get('kind')} block {e.get('idx')}: company {e.get('company')!r} is not in config/wd_profile.json work")
            continue
        plan.append({'idx': e.get('idx'), 'kind': e.get('kind'), 'title': w['Job Title'], 'start': month(w['From']), 'end': month(w['To'])})
    return plan, problems


def project_plan(entries, projects):
    """entries = the project blocks on the page [{'idx', 'name'}]; projects = config/profile.json projects (name, match_re,
    role, start, end — end None = ongoing — description). Each config project is used once, in page order. Returns
    (plan, problems): plan = [{'idx', 'name', 'role', 'start', 'end', 'desc'}] — idx None = not on the page, add a block;
    a parsed block that matches no config project (e.g. a club role read as a project) → a problem, and the block is removed."""
    plan, problems, used = [], [], set()
    for e in entries:
        name = N(e.get('name'))
        hit = next((i for i, p in enumerate(projects) if i not in used and name
                    and re.search(p.get('match_re') or re.escape(p['name']), name, re.I)), None)
        if hit is None:
            problems.append(f"project block {e.get('idx')}: {e.get('name')!r} is not in config/profile.json projects")
            continue
        used.add(hit)
        plan.append(dict(_proj(projects[hit]), idx=e.get('idx')))
    plan += [dict(_proj(p), idx=None) for i, p in enumerate(projects) if i not in used]
    return plan, problems


def _proj(p):
    return {'name': p['name'], 'role': p.get('role', ''), 'start': month(p.get('start')),
            'end': month(p.get('end')) if p.get('end') else PRESENT, 'desc': p.get('description', '')}


def same(want, got):
    w, g = N(want).lower(), N(got).lower()
    if re.fullmatch(r'[\d\s()+.-]{7,}', w):                     # phone: compare the last 10 digits
        return re.sub(r'\D', '', g)[-10:] == re.sub(r'\D', '', w)[-10:]
    if ' | ' in w or ' | ' in g:
        return sorted(x.strip() for x in w.split('|')) == sorted(x.strip() for x in g.split('|'))
    return w == g


def answer(questions):
    """[{key, label, type, options}] → {key: answerFor result} through rules_bridge.js (the shared answer rules)."""
    r = subprocess.run(['node', os.path.join(HERE, 'rules_bridge.js'), RULES], input=json.dumps({'fields': questions, 'jd': '', 'company': COMPANY}),   # company: referrer pool (JSA-195)
                       capture_output=True, text=True, timeout=60)
    return json.loads(r.stdout or '{}')


# ---------- page ----------
def now():
    return datetime.now().isoformat(timespec='seconds')


class TT:
    def __init__(self, page, log):
        self.p, self.log = page, log

    def item(self, key):
        return self.p.locator('.atsx-form-item').filter(has=self.p.locator(f'label[for="{key}"]')).first

    def keys(self, pat):
        return [k for k in self.p.evaluate("() => [...document.querySelectorAll('.atsx-form-item-label label[for]')].map(l => l.getAttribute('for'))")
                if re.match(pat, k or '')]

    def _dropdown(self, cls):
        for _ in range(10):
            d = [x for x in self.p.locator(cls).all() if x.is_visible()]
            if d:
                return d[-1]
            time.sleep(0.3)
        return None

    # text / atsx select / period / formily select
    def read(self, key):
        it = self.item(key)
        if not it.count():
            return None
        return it.evaluate("""e => {
          const per = e.querySelectorAll('.atsx-date-picker-period-month-label'); if (per.length) return [...per].map(x => x.innerText.replace(/\\s+/g, '')).join(' ');
          const inp = [...e.querySelectorAll('input:not([type=file]):not([type=checkbox]):not(.atsx-select-search__field):not(.atsx-date-picker-period-hidden-input), textarea')];
          const v = inp.map(i => i.value).filter(Boolean).join(' ');
          if (v) return v;                                    // text, and the number box of the phone field (the +1 code is a select beside it)
          const sel = e.querySelector('.atsx-select-selection-selected-value'); if (sel) return sel.innerText.trim();
          const combo = e.querySelector('.atsx-select-combobox .atsx-select-search__field'); if (combo) return combo.value.trim();   // school: a search box
          return '';
        }""")

    def set_text(self, key, value):
        box = self.item(key).locator('input:not(.atsx-select-search__field), textarea').last
        box.fill(value)

    def set_select(self, key, value):
        it = self.item(key); it.scroll_into_view_if_needed()
        it.locator('.atsx-select-selection').first.click()
        d = self._dropdown('.atsx-select-dropdown')
        if not d:
            raise RuntimeError('dropdown did not open')
        d.locator('li[role=option]', has_text=re.compile(rf'^\s*{re.escape(value)}\s*$')).first.click(); time.sleep(0.4)

    def set_period(self, key, start, end):
        it = self.item(key); it.scroll_into_view_if_needed()
        for k, v in ((0, start), (1, end)):
            if not v:
                continue
            it.locator('.atsx-date-picker-period-month-label').nth(k).click()
            d = self._dropdown('.atsx-date-picker-dropdown')
            if not d:
                raise RuntimeError('date panel did not open')
            if v == PRESENT:
                d.locator('[data-cy="-"]').first.click(); time.sleep(0.4)
                continue
            y, m = v.split('-')
            yr = d.locator(f'[data-cy="{y}"]').first
            if not yr.count():
                raise RuntimeError(f'year {y} not offered')
            yr.scroll_into_view_if_needed(); yr.click(); time.sleep(0.3)
            d.locator(f'[data-cy="{m}"]').first.click(); time.sleep(0.4)

    def delete_block(self, idx, first_key):
        """Remove one repeat block (education / internship / work) with its own remove button; True when it is gone."""
        blk = self.p.locator('.resumeEditForm-item').filter(has=self.p.locator(f'label[for="{idx}.{first_key}"]')).first
        if not blk.count():
            return False
        blk.scroll_into_view_if_needed(); blk.locator('.formOperate-removeBtn').first.click(); time.sleep(1)
        return not self.p.locator(f'label[for="{idx}.{first_key}"]').count()

    def add_block(self, section, prefix):
        """Click the section's Add button; returns the new block's key prefix (e.g. 'project[3]') or None."""
        before = set(self.keys(rf'{prefix}\[\d+\]\.'))
        sec = self.p.locator(f'text="{section}"').first.locator('xpath=ancestor::*[.//*[contains(@class,"addBtn")]][1]')
        btn = sec.locator('.createFormSection-addBtn, .formOperate-addBtn').last
        btn.scroll_into_view_if_needed(); btn.click(); time.sleep(1)
        new = sorted({k.split('.')[0] for k in set(self.keys(rf'{prefix}\[\d+\]\.')) - before})
        return new[0] if new else None

    def formily(self):
        out = []
        items = self.p.locator('.ud-formily-item[data-form-field-id]')
        for k in range(items.count()):
            it = items.nth(k)
            out.append({'key': it.get_attribute('data-form-field-id'), 'label': N(it.get_attribute('data-form-field-i18n-name')),
                        'multi': bool(it.locator('.ud__overflow').count()), 'required': bool(it.locator('.ud-formily-item-asterisk').count())})
        return out

    def formily_item(self, fid):
        return self.p.locator(f'.ud-formily-item[data-form-field-id="{fid}"]').first

    def formily_options(self, fid):
        it = self.formily_item(fid); it.scroll_into_view_if_needed()
        it.locator('.ud__select__selector').first.click()
        d = self._dropdown('.ud__select__dropdown')
        opts = [N(x.inner_text()) for x in d.locator('.ud__select__list__item').all()] if d else []
        self.p.keyboard.press('Escape'); time.sleep(0.4)
        return opts

    def set_formily(self, fid, values):
        it = self.formily_item(fid); it.scroll_into_view_if_needed()
        it.locator('.ud__select__selector').first.click()
        d = self._dropdown('.ud__select__dropdown')
        for v in values:
            opt = d.locator('.ud__select__list__item', has_text=re.compile(rf'^\s*{re.escape(v)}\s*$')).first
            if 'selected' not in (opt.get_attribute('class') or ''):
                opt.click(); time.sleep(0.4)
        if d.is_visible():
            self.p.keyboard.press('Escape'); time.sleep(0.4)

    def read_formily(self, fid):
        it = self.formily_item(fid)
        tags = [N(t.inner_text()) for t in it.locator('.ud__tag, [class*="selector__item"]').all() if N(t.inner_text())]
        if tags:
            return ' | '.join(tags)
        return N(it.locator('.ud__select__selector').first.inner_text())


def drop_unknown(tt, entries, plan, problems, first_key, res, log):
    """Parsed blocks that are not in config/ (a school kept off applications, an availability line read as an internship)
    are removed from the form and the removal is checked; their problems are dropped once the block is gone."""
    keep = {p['idx'] for p in plan}
    for e in entries:
        if e['idx'] in keep:
            continue
        gone = tt.delete_block(e['idx'], first_key)
        log(f"removed parsed block {e['idx']} ({e.get(first_key)!r}) — not in config" if gone else f"could not remove block {e['idx']}")
        res.append({'key': e['idx'], 'label': f"remove {e['idx']} ({e.get(first_key)!r}, not in config)", 'want': 'removed',
                    'page': 'removed' if gone else 'still there', 'ok': gone})
        if gone:
            problems = [p for p in problems if f"block {e['idx']}:" not in p]
    return problems


def signin(page, log, wait_captcha):
    """lifeattiktok / jobs.bytedance login page → e-mail + Keychain password + terms box → Sign in. CAPTCHA → wait for the
    candidate (never solved here). Returns (ok, why)."""
    sys.path.insert(0, HERE)
    from wd_signin import keychain_password, ACCOUNT
    pw = keychain_password()
    if not pw:
        return False, 'no Keychain item jobagent-workday'
    page.locator('input[placeholder="Email"]').first.fill(ACCOUNT)
    page.locator('input[type=password]').first.fill(pw)
    cb = page.locator('input.atsx-checkbox-input').first
    if cb.count() and not cb.is_checked():
        cb.check()
    page.locator('button.loginSubmit').first.click(); time.sleep(5)
    end = time.time() + wait_captcha * 60
    while '/login' in page.url:
        txt = page.inner_text('body')[:20000]
        if re.search(r'incorrect email or password', txt, re.I):
            return False, 'the site says: incorrect email or password (no account on this site yet?)'
        if not CAPTCHA_TEXT.search(txt) or time.time() > end:
            return False, 'CAPTCHA at sign-in' if CAPTCHA_TEXT.search(txt) else 'still on the login page'
        log('CAPTCHA at sign-in — waiting for the candidate to solve it in the job Chrome tab'); time.sleep(5)
    return True, ''


def run(page, url, resume, log, wait_captcha=0):
    res, problems, review = [], [], []
    page.goto(url, wait_until='domcontentloaded', timeout=60000)
    for _ in range(20):                                         # the redirect to /login happens in the page's script, seconds later
        if '/login' in page.url or page.locator('label[for="name"]').count():
            break
        time.sleep(1)
    if '/login' in page.url:
        ok, why = signin(page, log, wait_captcha)
        if not ok:
            return {'status': 'captcha' if 'CAPTCHA' in why else 'blocked', 'problems': [why], 'fields': [], 'slots': None, 'review': []}
        if '/apply' not in page.url:
            page.goto(url, wait_until='domcontentloaded', timeout=60000); time.sleep(5)
    slots = None
    for _ in range(25):                                         # the form and the slot banner render late
        slots = parse_slots(page.inner_text('body')[:30000])
        if page.locator('label[for="name"]').count() and slots:
            break
        time.sleep(1.5)
    tt = TT(page, log)
    log(f'slots: {slots}')
    if slots and slots['remaining'] <= 0:
        return {'status': 'no-slot', 'problems': [f"no application left in {slots['project']!r}"], 'fields': [], 'slots': slots, 'review': []}

    # 1. resume → let the parser fill the sections, then correct them from config/
    if resume:
        page.locator('input[type=file]').first.set_input_files(resume); time.sleep(3)
        for _ in range(10):
            yes = page.locator('text=/overwrite text in the fields/i')
            if yes.count() and yes.first.is_visible():
                page.locator('.atsx-message, [class*=parse], [class*=tip]').locator('text=/^\\s*Yes\\s*$/').first.click()
                break
            time.sleep(1)
        time.sleep(6)
    rb = page.locator('.uploadFile-preview').first
    rblock = N(rb.inner_text()) if rb.count() else ''
    rname = os.path.basename(resume) if resume else ''
    res.append({'key': 'resume', 'label': 'Resume', 'want': rname, 'page': rblock[:120],
                'ok': bool(rname) and rname[:25].lower() in rblock.lower()})

    sys.path.insert(0, os.path.join(ROOT, 'config'))
    import jsa_profile
    prof = jsa_profile.load()
    import jsa_profile
    wd = json.load(open(jsa_profile.data_file('wd_profile.json', 'JSA_WD_PROFILE'), encoding='utf-8'))   # the data home's config/ (ADR-0008)
    planned = [('name', prof['name']['full'], 'text'), ('mobile', re.sub(r'\D', '', prof['contact']['phone']), 'text'),
               ('email', prof['contact']['email'], 'text')]

    edu = [{'idx': k.split('.')[0], 'school': tt.read(k)} for k in tt.keys(r'education\[\d+\]\.school$')]
    ep, pr = edu_plan(edu, prof['education'], wd['education'])
    problems += drop_unknown(tt, edu, ep, pr, 'school', res, log)
    for e in ep:
        i = e['idx']
        planned += [(f'{i}.degree', e['degree'], 'select'), (f'{i}.fieldOfStudy', e['field'], 'text'), (f'{i}.period', f"{e['start']} {e['end']}", 'period')]
    langs = [{'idx': k.split('.')[0], 'language': tt.read(k)} for k in tt.keys(r'language\[\d+\]\.language$')]
    lp, pr = lang_plan(langs, wd.get('languages', [])); problems += pr
    planned += [(f"{l['idx']}.proficiency", l['proficiency'], 'select') for l in lp]
    jobs = [{'idx': k.split('.')[0], 'kind': k.split('[')[0], 'company': tt.read(k)} for k in tt.keys(r'(internship|work)\[\d+\]\.company$')]
    wp, pr = work_plan(jobs, wd.get('work', []))
    problems += drop_unknown(tt, jobs, wp, pr, 'company', res, log)
    for w in wp:
        planned += [(f"{w['idx']}.title", w['title'], 'text'), (f"{w['idx']}.period", f"{w['start']} {w['end']}", 'period')]
    projs = [{'idx': k.split('.')[0], 'name': tt.read(k)} for k in tt.keys(r'project\[\d+\]\.name$')]
    if 'projects' not in prof:                                  # no config source → shown for review, not changed
        review += [{'block': e['idx'], 'name': e['name'], 'title': tt.read(f"{e['idx']}.role"), 'period': tt.read(f"{e['idx']}.period")} for e in projs]
    else:                                                       # JSA-100: rewrite from config, drop the rest, add what is missing
        pp, pr = project_plan(projs, prof['projects'])
        problems += drop_unknown(tt, projs, pp, pr, 'name', res, log)
        for p in pp:
            if p['idx'] is None:
                p['idx'] = tt.add_block('Project Experience', 'project')
                log(f"added project block {p['idx']} for {p['name']!r}")
                if not p['idx']:
                    problems.append(f"could not add a project block for {p['name']!r}"); continue
            i = p['idx']
            planned += [(f'{i}.name', p['name'], 'text'), (f'{i}.role', p['role'], 'text'),
                        (f'{i}.period', f"{p['start']} {p['end']}", 'period'), (f'{i}.desc', p['desc'], 'text')]

    for key, want, typ in planned:
        err = None
        cur = tt.read(key)
        if cur is None:
            res.append({'key': key, 'label': key, 'want': want, 'page': '', 'ok': False, 'error': 'field not on the page'}); continue
        if not same(want, cur):
            try:
                if typ == 'text':
                    tt.set_text(key, want)
                elif typ == 'select':
                    tt.set_select(key, want)
                else:
                    tt.set_period(key, *want.split(' '))
            except Exception as e:
                err = f'{type(e).__name__}: {str(e)[:90]}'
        got = tt.read(key)
        res.append({'key': key, 'label': key, 'want': want, 'page': got, 'ok': same(want, got) and not err, 'error': err,
                    'changed': not same(want, cur)})

    # 2. the questions (work authorization, source) through the shared answer rules
    qs = tt.formily()
    for q in qs:
        q['options'] = tt.formily_options(q['key'])
    ans = answer([{'key': q['key'], 'label': q['label'], 'type': 'multi' if q['multi'] else 'select', 'options': q['options']} for q in qs])
    for q in qs:
        a = ans.get(q['key'], {})
        val = a.get('value') if a.get('status') == 'ok' else None
        want = [v for v in (val if isinstance(val, list) else [val]) if v] if val else []
        if not want or any(v not in q['options'] for v in want):
            res.append({'key': q['key'], 'label': q['label'], 'want': val, 'page': tt.read_formily(q['key']), 'ok': False,
                        'error': f"no rule answer among {q['options']}" if not want else 'answer not among the options'}); continue
        err = None
        try:
            tt.set_formily(q['key'], want)
        except Exception as e:
            err = f'{type(e).__name__}: {str(e)[:90]}'
        got = tt.read_formily(q['key'])
        res.append({'key': q['key'], 'label': q['label'], 'want': ' | '.join(want), 'page': got, 'rule': a.get('rule'),
                    'ok': same(' | '.join(want), got) and not err, 'error': err})

    # 3. privacy box next to Submit (required to submit; ticking it sends nothing)
    box = page.locator('label', has_text='Privacy Policy').locator('input[type=checkbox]').first
    if box.count():
        if not box.is_checked():
            box.check(force=True)
        res.append({'key': 'privacy', 'label': 'I have read and agreed to the Privacy Policy', 'want': 'Yes',
                    'page': 'Yes' if box.is_checked() else 'No', 'ok': box.is_checked()})
    for r in res:                                               # final pass: a later fill (parser, dropdown) must not have undone an earlier one
        if not r['ok'] or r['key'] in ('resume', 'privacy') or r.get('want') == 'removed':
            continue
        got = tt.read_formily(r['key']) if r['key'].isdigit() else tt.read(r['key'])
        if not same(r['want'], got):
            r.update(ok=False, page=got, error='changed after it was filled')
    visible_err = [N(x.inner_text()) for x in page.locator('.atsx-form-explain, .ud-formily-item-error-help, [class*="error-help"]').all() if x.is_visible() and N(x.inner_text())]
    if visible_err:
        problems.append('page shows errors: ' + '; '.join(visible_err[:5]))
    bad = [r for r in res if not r['ok']]
    if bad:
        problems.append('fields not confirmed: ' + '; '.join(f"{r['label'][:40]} ({r['page']!r})" for r in bad[:6]))
    try:                                                        # JSA-294: every education / internship block against its entry, by code
        import block_check as BC
        names = [{'key': f"{e['idx']}.school", 'label': f"{e['idx']}.school", 'page': e['school']} for e in edu] + \
                [{'key': f"{j['idx']}.company", 'label': f"{j['idx']}.company", 'page': j['company']} for j in jobs]
        rows = sorted([r for r in res + names if BC.TT_KEY.match(str(r.get('label') or ''))], key=lambda r: (str(r['label']).split('.')[0], str(r['label']).split('.')[1] not in ('school', 'company')))
        problems += ['block check: ' + p for p in BC.problems(rows)]
    except Exception as e:
        problems.append(f'block check failed: {type(e).__name__}: {str(e)[:80]}')
    return {'status': 'dry-run', 'problems': problems, 'fields': res, 'slots': slots, 'review': review}


def slot_guard(job, today=None):
    """Tracker slot check for this role (tiktok_slots.check over data/store/applications.jsonl)."""
    sys.path.insert(0, os.path.join(ROOT, 'scripts', 'store')); import store
    return tiktok_slots.check(job, store.load('applications'), today)


def banner_problem(banner, sl):
    """Pure (tested): the form's banner shows fewer applications left than the tracker → a submitted application is missing
    from the tracker; say so (the banner is the truth for this program)."""
    if not banner or not sl or not sl.get('counted'):
        return ''
    if banner['remaining'] < sl['remaining']:
        return (f"form banner: {banner['remaining']} left in {banner['project']!r}, tracker says {sl['remaining']} — "
                "an application is missing from data/store/applications.jsonl; add it before any submit")
    return ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--job'); ap.add_argument('--url'); ap.add_argument('--resume'); ap.add_argument('--track'); ap.add_argument('--out')
    ap.add_argument('--cdp', default='http://127.0.0.1:9222'); ap.add_argument('--wait-captcha', type=float, default=0)
    ap.add_argument('--keep-tab', action='store_true'); ap.add_argument('--today', help='submit day for the slot period (tests)')
    a = ap.parse_args()
    job = {}
    if a.job:
        for line in open(jpaths.data('store', 'jobs.jsonl'), encoding='utf-8'):
            r = json.loads(line)
            if r.get('id') == a.job:
                job = r; break
    posting = a.url or job.get('ats_url') or job.get('url')
    url = apply_url(posting)
    if not url:
        sys.exit(f'not a TikTok / ByteDance posting: {posting}')
    global COMPANY
    COMPANY = job.get('company') or ('ByteDance' if 'bytedance' in url else 'TikTok')   # referral questions (JSA-195)
    track = a.track or TRACKS.get(job.get('track'), 'Product_Manager')
    resume = a.resume or jpaths.resume('2026-10', jsa_profile.resume_file(f'{track}_A-Classic.pdf'))
    out = os.path.abspath(a.out or os.path.join(DATA, 'tiktok', a.job or url.split('/')[-2]))
    os.makedirs(out, exist_ok=True)
    t0 = time.time()
    logf = open(os.path.join(out, 'run_log.md'), 'a', encoding='utf-8')
    def log(m): logf.write(f'- {now()} {m}\n'); logf.flush(); print(m)
    sl = slot_guard(dict(job, url=job.get('url') or posting), a.today)
    log(f"slots ({sl['period']} {sl['program']}): {sl['used']}/{tiktok_slots.LIMIT} used in the tracker" + ('' if sl['counted'] else ' — role exempt / not limited'))
    if not sl['allowed']:
        log(f"REFUSED: {sl['reason']}")
        with open(os.path.join(DATA, 'results.jsonl'), 'a') as o:
            o.write(json.dumps({'at': now(), 'folder': os.path.basename(out), 'url': url, 'ats': 'tiktok', 'status': 'no-slot',
                                'problems': [sl['reason']], 'fields': 0, 'bad': 0, 'secs': round(time.time() - t0, 1)}) + '\n')
        sys.exit(2)
    log(f'start tiktok dry-run {url} (resume {os.path.basename(resume)})')
    from playwright.sync_api import sync_playwright
    import chrome_guard                                       # JSA-227: no autofill / password extension in the job Chrome
    if chrome_guard.stop(out, url, log, None, DATA, 'tiktok'): return
    with sync_playwright() as pw:
        ctx = cdp_connect.connect(pw, a.cdp).contexts[0]
        page = ctx.new_page()
        try:
            r = run(page, url, resume if os.path.exists(resume) else None, log, a.wait_captcha)
        except Exception as e:
            r = {'status': 'blocked', 'problems': [f'runner error {type(e).__name__}: {str(e)[:200]}'], 'fields': [], 'slots': None, 'review': []}
        try:
            page.mouse.click(2, 2); page.screenshot(path=os.path.join(out, 'filled_check.png'), full_page=True)
        except Exception:
            pass
        for f in r['fields']:
            log(f"  {'ok ' if f['ok'] else 'BAD'} {f['label'][:50]:50s} → {str(f['page'])[:50]}" + (f"  ({f['error']})" if f.get('error') else ''))
        for v in r['review']:
            log(f'  review project block: {v}')
        bp = banner_problem(r.get('slots'), sl)
        if bp:
            r['problems'].append(bp)
        n, ok = len(r['fields']), len([f for f in r['fields'] if f['ok']])
        json.dump({'at': now(), 'url': url, 'posting': posting, 'job': a.job, 'resume': os.path.basename(resume), **r,
                   'readback': f'{ok}/{n}'}, open(os.path.join(out, 'form_check.json'), 'w'), indent=1, ensure_ascii=False)
        log(('problems: ' + ' | '.join(r['problems'])) if r['problems'] else 'all checks pass — dry-run, NOT submitted (no submit path)')
        with open(os.path.join(DATA, 'results.jsonl'), 'a') as o:
            o.write(json.dumps({'at': now(), 'folder': os.path.basename(out), 'url': url, 'ats': 'tiktok', 'status': r['status'],
                                'problems': r['problems'][:8], 'fields': n, 'bad': n - ok, 'secs': round(time.time() - t0, 1)}) + '\n')
        if not a.keep_tab:
            page.close()
        log(f'STATUS {r["status"]} readback {ok}/{n} TIME {round(time.time() - t0, 1)}s')


if __name__ == '__main__':
    main()
