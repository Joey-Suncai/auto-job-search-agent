#!/usr/bin/env python3
"""Workday sign-in / create-account without Joey (his rule 2026-10-30: 「按钥匙串做」).

The password lives only in the macOS Keychain; this script reads it and types it into password fields. It is never
printed, logged, written to a file or sent to a model. The account e-mail is Joey's application address.
    security add-generic-password -s jobagent-workday -a <your e-mail> -w     # once, by the user

    from wd_signin import auto_signin
    ok, why = auto_signin(page, log, folder, is_auth=lambda: w.extract()['auth'])    # True = signed in; False = hand to Joey (why says what stopped it)

Order on a Workday auth page: sign in → if the tenant has no account (or says the credentials are wrong) open
"Create Account" → fill e-mail / password / verify password, tick the account-terms box → submit → if the tenant
asks to verify the e-mail, open the newest verification link from Gmail (read-only IMAP) in the same browser →
sign in again. A CAPTCHA, a second failure, or a missing Keychain item → False (the runner then waits for Joey).
Only the terms box of the account form is ticked; application consent / marketing boxes are not touched here.
"""
import os, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077: personal facts come from config/profile.json)
ACCOUNT = jsa_profile.get('accounts.workday_email') or jsa_profile.get('contact.email')
SERVICE = 'jobagent-workday'
# Workday renders a 'noCaptchaWrapper' div on every auth page: it means "no CAPTCHA here" (a Workday employer 2026-10-30)
CAPTCHA = ('iframe[src*="captcha"], iframe[title*="captcha" i], '
           '[data-automation-id*="captcha" i]:not([data-automation-id="noCaptchaWrapper"]), .g-recaptcha, #px-captcha')

A = lambda aid: f'[data-automation-id="{aid}"]'
SIGNIN_EMAIL = f'{A("email")} , input[type="email"]'
SUBMIT_SIGNIN = A('signInSubmitButton')
SUBMIT_CREATE = A('createAccountSubmitButton')
CREATE_LINK = f'{A("createAccountLink")}, button:has-text("Create Account"), a:has-text("Create Account")'
SIGNIN_LINK = f'{A("signInLink")}, button:has-text("Sign In"), a:has-text("Sign In")'
TERMS = A('createAccountCheckbox')
ERR = re.compile(r"wrong (email|password)|invalid (e-?mail|user ?name|password|credentials)|incorrect|no account|doesn't exist|does not exist|"
                 r"not recogni[sz]ed|could not sign you in|sign[- ]?in (failed|unsuccessful)|account (is |has been )?locked|too many", re.I)
VERIFY = re.compile(r'verify (your )?(account|e-?mail)|verification (e-?mail|link)|check your (e-?mail|inbox)|activate your account', re.I)
EXISTS = re.compile(r'already (exists|in use|registered|associated)|account with (this|that) e-?mail|e-?mail (address )?is already', re.I)
# JSA-207: what the tenant SAID decides what Joey is told (message_kind → failure_code), tested by DeepSeek cases
LOCKED = re.compile(r'\b(account|user)\b[^.|]{0,40}\b(locked|disabled|suspended)\b|\blocked out\b|account locked|'
                    r'too many (failed |unsuccessful |invalid )?(sign[- ]?in |login |log-in )?(attempts|tries)|temporarily (disabled|locked|suspended)', re.I)
WRONG = re.compile(r"\b(wrong|invalid|incorrect|not recogni[sz]ed|not valid)\b|could not sign you in|sign[- ]?in (failed|unsuccessful)|"
                   r"\bno account\b|account (does not|doesn't|doesn\u2019t) exist", re.I)
# JSA-334: Workday's generic alert "You may have entered the wrong email address or password or your account might be
# locked." is NOT a lock — a hedged / conditional / future mention counts as wrong_password (Joey 2026-11-12, fix B)
_LK = r'(locked|disabled|suspended)( out)?'
HEDGED = re.compile(r'\b(might|may|could)\s+(also\s+)?(be|have been|get|become)\s+(\w+\s+)?' + _LK + r'|'
                    r'\bif\b[^.|]{0,40}?\b(is|are|was|has been|gets|becomes)\s+(\w+\s+)?' + _LK + r'|'
                    r'\b(will|would|can|may|might|could)\s+(be\s+)?(\w+\s+)?(locked|disabled|suspended|lock|disable|suspend)\b[^.|]*', re.I)
WARN = re.compile(r'\b(after|if|once|when)\b[^.|]{0,30}\b(too many|\d+|several|multiple)\b[^.|]{0,30}\b(attempts|tries)\b[^.|]*', re.I)
AGENT_SINCE = '2026-10-28'   # the agent's first Workday account creations; a tenant mail from before = Joey's own old account


def message_kind(text):
    """Pure (tested). The tenant's alert text → locked | exists | wrong_password | verify | none (first rule wins).
    Only a definite lock is 'locked'; hedged / conditional / future lock words are removed first and mean wrong_password."""
    t = str(text or '')
    hedged = bool(HEDGED.search(t) or WARN.search(t))
    plain = WARN.sub(' ', HEDGED.sub(' ', t))
    if LOCKED.search(plain): return 'locked'
    if EXISTS.search(t): return 'exists'
    if WRONG.search(plain) or hedged: return 'wrong_password'
    if VERIFY.search(t): return 'verify'
    return 'none'


def old_account_mail(mails, since=AGENT_SINCE):
    """Pure. A tenant mail from before the agent's time and no agent verify mail = Joey's own old account."""
    mails = mails or []
    return (any(m.get('kind') == 'other' and str(m.get('date', '')) < since for m in mails)
            and not any(m.get('kind') == 'verify' and str(m.get('date', '')) >= since for m in mails))


def after_wrong(s):
    """Pure (tested, JSA-334). After a wrong_password answer: retry_long | give_up | old_account | create (first rule wins)."""
    if s.get('has_long') and not s.get('tried_long'): return 'retry_long'
    if s.get('created'): return 'give_up'
    if old_account_mail(s.get('mails'), s.get('agent_since') or AGENT_SINCE): return 'old_account'
    return 'create'


def failure_code(t):
    """Pure (tested). Why sign-in failed after the create-account step, from the run's trace + this tenant's Gmail mails:
    locked | old_account | agent_account_password | no_verify_mail | no_answer | other (first rule wins)."""
    since = t.get('agent_since') or AGENT_SINCE
    mails = t.get('mails') or []
    agent_verify = any(m.get('kind') == 'verify' and str(m.get('date', '')) >= since for m in mails)
    old_mail = old_account_mail(mails, since)
    err = t.get('error')
    if err == 'locked': return 'locked'
    if t.get('exists_msg') or old_mail: return 'old_account'
    if agent_verify and err == 'wrong_password': return 'agent_account_password'
    if t.get('created') and not agent_verify and (err in ('wrong_password', 'none') or t.get('verify_banner')): return 'no_verify_mail'
    if err == 'none': return 'no_answer'
    return 'other'


JOEY_TODO = {   # the queue line for each failure_code (the agent never changes or resets a password)
    'locked': 'the tenant locked the account (too many tries) — Joey: unlock it with "Forgot your password?" in the tab (or wait), then rerun',
    'old_account': 'Joey already had an account on this tenant from before ({old}) and the Keychain passwords do not open it — '
                   'Joey: sign in with your old password (or "Forgot your password?") in the tab, then rerun',
    'agent_account_password': 'the agent created and verified this account ({verify}) but both Keychain passwords are refused now — '
                              'Joey: "Forgot your password?" in the tab, then rerun',
    'no_verify_mail': 'new account, but no verification e-mail from this tenant reached Gmail — Joey: look for it (spam) or press '
                      '"Resend" in the tab, open the link, then rerun',
    'no_answer': 'the tenant gave no recognisable answer to the sign-in (its message is in signin.json) — Joey: look at the tab',
    'other': 'sign-in failed for a reason the runner does not know (signin.json) — Joey: look at the tab',
}


def tenant_key(page_url):
    """Pure (tested). The Workday tenant name: gaig.wd1.myworkdayjobs.com → 'gaig'; wd3.myworkdaysite.com/recruiting/x/… → 'x'."""
    from urllib.parse import urlsplit
    u = urlsplit(page_url or '')
    host = (u.hostname or '').lower()
    if host.endswith('myworkdaysite.com'):
        m = re.match(r'/recruiting/([^/?#]+)', u.path or '', re.I)
        return m.group(1).lower() if m else ''
    return host.split('.')[0] if host.endswith('myworkdayjobs.com') else ''


def tenant_mails(page_url, days=500):
    """Read-only Gmail (All Mail): the tenant's Workday mails, any folder, last `days` days → [{date, kind}] (kind = verify
    when the subject or a link asks to verify / activate the account). Never prints or stores a body or a link."""
    import email, imaplib
    from email.header import decode_header, make_header
    from email.utils import parsedate_to_datetime
    import gmail_code
    key = tenant_key(page_url)
    if not key:
        return []
    out = []
    M = imaplib.IMAP4_SSL('imap.gmail.com')
    try:
        M.login(gmail_code.ACCOUNT, gmail_code.app_password())
        if M.select('"[Gmail]/All Mail"', readonly=True)[0] != 'OK':
            M.select('INBOX', readonly=True)
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime('%d-%b-%Y')
        _, data = M.search(None, 'FROM', key, 'SINCE', since)
        for i in (data[0] or b'').split()[-30:]:
            _, d = M.fetch(i, '(BODY.PEEK[HEADER.FIELDS (DATE FROM SUBJECT)])')
            h = email.message_from_bytes(d[0][1])
            frm = str(make_header(decode_header(h.get('From', '')))).lower()
            if 'workday' not in frm and key not in _sender_domain(frm):   # own HR domain counts too (vanguardhr.com, JSA-274)
                continue
            subj = str(make_header(decode_header(h.get('Subject', ''))))
            try:
                day = parsedate_to_datetime(h['Date']).date().isoformat()
            except Exception:
                continue
            out.append({'date': day, 'kind': 'verify' if VERIFY.search(subj) or re.search(r'verify|activat', subj, re.I) else 'other',
                        'subject': subj[:80]})
    finally:
        try: M.logout()
        except Exception: pass
    return out


def keychain_password(service=SERVICE, account=ACCOUNT):
    r = subprocess.run(['security', 'find-generic-password', '-s', service, '-a', account, '-w'], capture_output=True, text=True)
    return r.stdout.rstrip('\n') if r.returncode == 0 else ''


def _visible(page, sel):
    try:
        loc = page.locator(sel)
        return any(loc.nth(i).is_visible() for i in range(min(loc.count(), 4)))
    except Exception:
        return False


def _first_visible(page, sel):
    loc = page.locator(sel)
    for i in range(min(loc.count(), 6)):
        if loc.nth(i).is_visible():
            return loc.nth(i)
    return None


def _click(page, sel):
    """Workday puts a transparent 'click_filter' div over its submit buttons; click that when it is there."""
    el = _first_visible(page, sel)
    if el is None:
        return False
    flt = el.locator(A('click_filter'))
    target = flt.first if flt.count() else el
    for how in ('click', 'force', 'dispatch'):
        try:
            if how == 'click': target.click(timeout=3000)
            elif how == 'force': target.click(force=True, timeout=3000)
            else: target.dispatch_event('click')
            return True
        except Exception:
            continue
    return False


def _text(page):
    try:
        return re.sub(r'\s+', ' ', page.inner_text('body'))[:6000]
    except Exception:
        return ''


ALERTS = f'{A("errorMessage")}, {A("inputAlert")}, [role="alert"], {A("errorBanner")}, {A("alertMessage")}'


def _messages(page):
    """The tenant's visible alert / error texts (JSA-207: what it said is what Joey is told). Text only — a password field's
    value is never part of it; the account e-mail is masked."""
    out = []
    try:
        loc = page.locator(ALERTS)
        for i in range(min(loc.count(), 8)):
            el = loc.nth(i)
            if not el.is_visible():
                continue
            t = re.sub(r'\s+', ' ', el.inner_text(timeout=1500) or '').strip()
            if t and t not in out and not re.search(r'^(success|saved|uploaded|loading)', t, re.I):
                out.append(t[:200])
    except Exception:
        pass
    s = ' | '.join(out)[:500]
    return s.replace(ACCOUNT, '<e-mail>') if ACCOUNT else s


def _kind_now(page):
    """message_kind of the alerts, else of the page text (some tenants print the error as plain text)."""
    k = message_kind(_messages(page))
    return k if k != 'none' else message_kind(_text(page))


def _fill_email(page):
    el = _first_visible(page, SIGNIN_EMAIL)
    if el is None:
        return False
    el.fill(ACCOUNT)
    return True


def _fill_passwords(page, pw, n):
    loc = page.locator('input[type="password"]')
    vis = [loc.nth(i) for i in range(loc.count()) if loc.nth(i).is_visible()]
    for el in vis[:n]:
        el.fill(pw)
    return len(vis)


_IS_AUTH = None   # set by auto_signin: the runner's own detector (wd_page.js __wdAuth via WD.extract)


def signed_in(page):
    """Signed in = no auth form, not on a /login URL, no "verify your account" banner — checked twice 1.5 s apart,
    because right after a submit Workday shows an empty frame that looks like "no password field" (a Workday employer 2026-10-30)."""
    def once():
        try:
            if '/login' in page.url or _visible(page, A('signInFormo')) or _visible(page, A('auth_container')):
                return False
            if VERIFY.search(_text(page)):
                return False
            if _IS_AUTH is not None:
                return not _IS_AUTH()
            return not page.evaluate("() => [...document.querySelectorAll('input[type=password]')].some(e => e.offsetParent !== null)")
        except Exception:
            return False
    if not once():
        return False
    time.sleep(1.5)
    return once()


def _wait(page, until, secs=12):
    end = time.time() + secs
    while time.time() < end:
        if until():
            return True
        time.sleep(0.5)
    return False


def _create_form(page):
    return _visible(page, A('verifyPassword')) or (_visible(page, TERMS) and
            sum(1 for i in range(page.locator('input[type="password"]').count()) if page.locator('input[type="password"]').nth(i).is_visible()) >= 2)


LONG_SERVICE = 'jobagent-workday-long'   # 20-char random password, generated into the Keychain 2026-11-01 (Joey: 「脚本随机生成」)


def choose_password(page_text, pw, long_pw):
    """Pure (tested). The tenant's create-account form lists "A minimum of N characters" (PIMCO 12, BP 14, 2026-11-01):
    use the regular password unless it is shorter than N and the long one is long enough. Never None when pw exists."""
    m = re.search(r'minimum of (\d{1,2}) characters|at least (\d{1,2}) characters|(\d{1,2}) characters minimum', page_text or '', re.I)
    need = int(next(g for g in m.groups() if g)) if m else 0
    if pw and len(pw) >= need:
        return pw
    if long_pw and len(long_pw) >= need:
        return long_pw
    return pw


def verify_pattern(page_url=None):
    """Pure (tested). Regex for THIS tenant's verify/activate link: with 4 runs creating accounts at once, the newest
    Workday mail can belong to another company (a Workday employer / Arch got another tenant's link, 2026-11-01).
    https://invesco.wd1.myworkdayjobs.com/... → the host must be invesco.wd1.myworkdayjobs.com;
    https://wd3.myworkdaysite.com/recruiting/brevanhoward/... → host + /recruiting/brevanhoward. No URL → any Workday link."""
    from urllib.parse import urlsplit
    tail = r'[^\s"<>]*(verify|activat|confirm)[^\s"<>]*'
    u = urlsplit(page_url or '')
    host = (u.hostname or '').lower()
    if not re.search(r'myworkday(jobs|site)\.com$', host):
        return r'https://[^\s"<>]*(myworkday|workday)' + tail
    if host.endswith('myworkdaysite.com'):
        m = re.match(r'/recruiting/([^/?#]+)', u.path or '', re.I)
        if m:
            return r'https://' + re.escape(host) + r'/recruiting/' + re.escape(m.group(1)) + r'/' + tail
    return r'https://' + re.escape(host) + r'/' + tail


VERIFY_SUBJ = re.compile(r'\b(verify|verification|activate|activation|confirm)\b[^|]{0,40}\b(account|e-?mail|address)\b|'
                         r'\b(account|e-?mail)\b[^|]{0,30}\b(verification|activation|confirmation)\b', re.I)
VLINK = re.compile(r'https://[^\s"\'<>()]*(verify|activat|confirm)[^\s"\'<>()]*', re.I)
WD_HOST = re.compile(r'^https://[^/]*\b(myworkdayjobs|myworkdaysite|myworkday)\.com(/|$)', re.I)
CLOCK_MARGIN = timedelta(minutes=2)


def _when(s):
    d = datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _sender_domain(frm):
    m = re.search(r'@([A-Za-z0-9.-]+)', frm or '')
    return re.sub(r'[^a-z0-9]', '', m.group(1).lower()) if m else ''


def _is_tenant_link(link, page_url):
    """Pure (tested). A verification link on THIS tenant: verify_pattern (tenant host), or any *.myworkday.com host
    with /<tenant>/ in the path."""
    if re.match(verify_pattern(page_url), link, re.I):
        return bool(tenant_key(page_url)) or not page_url
    key = tenant_key(page_url)
    return bool(key) and bool(re.match(r'https://[^/]*\.myworkday\.com/' + re.escape(key) + r'/', link, re.I))


def choose_verify_link(mails, since, page_url, company=None):
    """Pure (tested, JSA-274). mails = [{date, from, subject, body}] → the link that verifies THIS tenant's account, or
    None. Senders vary (Vanguard: CrewCentral_noreply@vanguardhr.com), so the sender is one signal, not a filter.
    Spec: scripts/test_cases/verify_mail_spec.md. Only mails at or after since − 2 min; a tenant link counts on its own;
    a mail without one gives a link only with a verify subject AND a sender domain naming the tenant / company.
    Preference: tenant link > verify subject > newest."""
    since = _when(since) - CLOCK_MARGIN
    key = tenant_key(page_url)
    names = [n for n in {key, re.sub(r'[^a-z0-9]', '', (company or '').lower()),
                         re.sub(r'[^a-z0-9]', '', (re.findall(r'[A-Za-z0-9]+', company or '') or [''])[0].lower())} if len(n) >= 3]
    best = None
    for m in mails or []:
        try:
            when = _when(m.get('date'))
        except Exception:
            continue
        if when < since:
            continue
        links = [x.group(0).rstrip('.,;:)>"\'') for x in VLINK.finditer(m.get('body') or '')]
        subj_ok = bool(VERIFY_SUBJ.search(m.get('subject') or ''))
        dom = _sender_domain(m.get('from'))
        sender_ok = any(n in dom for n in names)
        tl = [x for x in links if _is_tenant_link(x, page_url)]
        if tl:
            link, rank = tl[0], 2
        elif subj_ok and sender_ok:
            am = re.search(r'@([A-Za-z0-9.-]+)', m.get('from') or '')
            raw_dom = am.group(1).lower().rstrip('.') if am else ''
            host = lambda x: re.match(r'https://([^/:?#]+)', x).group(1).lower()
            own = [x for x in links if WD_HOST.match(x) or (raw_dom and (host(x) == raw_dom or host(x).endswith('.' + raw_dom)))]
            if not own:
                continue
            link, rank = own[0], 1
        else:
            continue
        score = (rank, subj_ok, when)
        if best is None or score > best[0]:
            best = (score, link)
    return best[1] if best else None


def wait_verify_link(since, page_url, company=None, timeout=180, read=None):
    """Live: poll Gmail (read-only, every sender) until choose_verify_link finds this tenant's link, or `timeout` s."""
    if read is None:
        from gmail_code import recent_mails as read
    t0 = time.time()
    while True:
        link = choose_verify_link(read(since - CLOCK_MARGIN), since, page_url, company)
        if link or time.time() - t0 >= timeout:
            return link
        time.sleep(8)


def verification_link(since, find_link=None, timeout=180, log=None, page_url=None, company=None):
    """Newest verify/activate link for this tenant in Gmail since `since` (read-only). find_link = a test double
    (old keyword interface); live runs use wait_verify_link (any sender, JSA-274)."""
    if find_link is None:
        return wait_verify_link(since, page_url, company, timeout)
    return find_link(sender='workday', since=since, timeout=timeout, pattern=verify_pattern(page_url))


def _open_link(page, link):
    tab = page.context.new_page()
    try:
        tab.goto(link, wait_until='domcontentloaded'); time.sleep(3)
    finally:
        tab.close()
    page.reload(wait_until='domcontentloaded'); time.sleep(2)


def auto_signin(page, log=None, folder=None, password=None, find_link=None, verify_timeout=180, is_auth=None,
                mail_history=None, settle=12, long_password=None):
    """mail_history(page_url) → [{date, kind}] of this tenant's Workday mails (default: read-only Gmail in a live run, i.e.
    when the password comes from the Keychain; tests inject it). settle = seconds to wait for the tenant's answer."""
    global _IS_AUTH
    _IS_AUTH = is_auth
    log = log or (lambda m: None)
    live = password is None
    pw = password if password is not None else keychain_password()
    if not pw:
        return False, 'no Workday password in the Keychain (service jobagent-workday)'
    long_pw = long_password if long_password is not None else (keychain_password(LONG_SERVICE) if live else '')
    if mail_history is None and live:
        mail_history = tenant_mails
    late_find = find_link if (find_link is not None or live) else False   # tests without find_link never reach Gmail
    tried_long = False
    fm = re.match(r'\d{4}-\d{2}-\d{2}_([^_]+)', os.path.basename(str(folder or '').rstrip('/')))
    company = fm.group(1) if fm else None                     # folder 2026-11-10_Vanguard_… → 'Vanguard' (sender-domain signal, JSA-274)
    created = verified = waited_blank = late_tried = False
    T = {'created': False, 'exists_msg': False, 'verify_banner': False, 'verified': False, 'error': 'none',
         'tried_long': False, 'create_msg': '', 'signin_msg': ''}   # the trace failure_code() reads (JSA-207)

    mail_cache = []

    def _mails():                                           # this tenant's Gmail mails, read once per run (read-only)
        if not mail_cache:
            got = []
            if mail_history:
                try:
                    got = mail_history(page.url) or []
                except Exception as e:
                    log(f'auto sign-in: Gmail look-up failed ({type(e).__name__})')
            mail_cache.append(got)
        return mail_cache[0]

    def _fail(base):
        mails = _mails()
        T.update(created=created, verified=verified, tried_long=tried_long)
        code = failure_code(dict(T, mails=mails, agent_since=AGENT_SINCE))
        old = sorted(m['date'] for m in mails if m.get('kind') == 'other' and m.get('date', '') < AGENT_SINCE)
        ver = sorted(m['date'] for m in mails if m.get('kind') == 'verify' and m.get('date', '') >= AGENT_SINCE)
        todo = JOEY_TODO[code].format(old='mail of ' + old[0] if old else 'the tenant said so',
                                      verify='verify mail of ' + ver[-1] if ver else 'earlier')
        if folder:
            try:
                import json
                rec = dict(T, code=code, reason=base, tenant=tenant_key(page.url), at=datetime.now().isoformat(timespec='seconds'),
                           mails=[{k: m.get(k) for k in ('date', 'kind', 'subject')} for m in mails][-10:])
                json.dump(rec, open(os.path.join(folder, 'signin.json'), 'w'), indent=1, ensure_ascii=False)
            except Exception:
                pass
        log(f'auto sign-in: failure type {code}' + (f' — tenant said: {T["signin_msg"][:120]}' if T['signin_msg'] else ''))
        return False, f'{base} [{code}] — {todo}'

    for attempt in range(9):   # create → verify → chooser → sign in needs more than 6 steps (a Workday employer 2026-10-30)
        if signed_in(page):
            log('auto sign-in: signed in'); return True, 'signed in'
        if _visible(page, CAPTCHA):
            return False, 'CAPTCHA on the sign-in page'
        if _create_form(page) and not (created and _visible(page, SUBMIT_SIGNIN)):   # after creating, a sign-in box wins (a Workday employer)
            if created:
                return False, 'create-account form came back after one try'
            _fill_email(page)
            use = choose_password(_text(page), pw, long_pw)
            if use is not pw: log('auto sign-in: this tenant needs a longer password — using the long Keychain item')
            n = _fill_passwords(page, use, 2)
            if n < 2:
                return False, 'create-account form without two password fields'
            for box in page.locator(TERMS).all():   # box.check() can fail silently (AMAT 2026-10-30) → force, then the label, then verify
                for how in ('check', 'force', 'label', 'js'):
                    try:
                        if not box.is_visible() or box.is_checked():
                            break
                        if how == 'check': box.check(timeout=3000)
                        elif how == 'force': box.check(force=True, timeout=3000)
                        elif how == 'label': page.locator(f'label[for="{box.get_attribute("id")}"]').first.click(timeout=3000)
                        else: box.evaluate('e => e.click()')
                    except Exception:
                        pass
            if any(b.is_visible() and not b.is_checked() for b in page.locator(TERMS).all()):
                return False, 'account-terms checkbox would not tick'

            t0 = datetime.now(timezone.utc) - timedelta(seconds=30)
            _click(page, SUBMIT_CREATE) or _click(page, 'button:has-text("Create Account")')
            time.sleep(1.5)
            if _create_form(page) and _visible(page, A('click_filter')):   # some tenants take the click only on the overlay div (a Workday employer / AMAT 2026-10-30)
                _click(page, A('click_filter'))
            created = True
            log('auto sign-in: account form submitted')
            _wait(page, lambda: signed_in(page) or VERIFY.search(_text(page)) or EXISTS.search(_text(page)) or _visible(page, CAPTCHA), settle)
            body = _text(page)
            T['create_msg'] = _messages(page)
            if EXISTS.search(body) or message_kind(T['create_msg']) == 'exists':
                T['exists_msg'] = True
                log('auto sign-in: the tenant says the account already exists — back to sign in')
                _click(page, SIGNIN_LINK)
                continue
            if VERIFY.search(body) and not signed_in(page):
                T['verify_banner'] = True
                if verified:
                    return _fail('tenant asks for e-mail verification again')
                log('auto sign-in: waiting for the verification e-mail')
                link = verification_link(t0, find_link, verify_timeout, log, page_url=page.url, company=company)
                if not link:
                    return _fail('no verification e-mail arrived')
                _open_link(page, link)
                verified = True
                log('auto sign-in: e-mail verified')
                if not signed_in(page) and not _visible(page, 'input[type="password"]'):
                    _click(page, SIGNIN_LINK)
            continue
        if _visible(page, 'input[type="password"]'):          # sign-in form
            _fill_email(page)
            _fill_passwords(page, pw, 1)
            _click(page, SUBMIT_SIGNIN) or _click(page, 'button:has-text("Sign In")')
            log('auto sign-in: credentials submitted')
            answered = lambda: signed_in(page) or ERR.search(_text(page)) or VERIFY.search(_text(page)) or _visible(page, CAPTCHA)
            if not _wait(page, answered, settle):
                _wait(page, answered, settle)                     # a slow tenant: wait once more before judging (JSA-207)
            if signed_in(page):
                continue
            kind = _kind_now(page)
            if kind == 'verify' and not verified:
                T['verify_banner'] = True
                t0 = datetime.now(timezone.utc) - timedelta(hours=24)   # tenant-matched link (verify_pattern), so an earlier attempt's mail is safe (an employer 2026-11-01)
                link = verification_link(t0, find_link, verify_timeout, log, page_url=page.url, company=company)
                if link:
                    _open_link(page, link)
                    verified = True; log('auto sign-in: e-mail verified')
                    continue
                return _fail('tenant asks for e-mail verification and no link arrived')
            if kind == 'wrong_password' and after_wrong({'has_long': bool(long_pw), 'tried_long': tried_long}) == 'retry_long' \
                    and _visible(page, 'input[type="password"]'):
                tried_long = True                                   # the account may have been created with the long password
                _fill_email(page); _fill_passwords(page, long_pw, 1)
                _click(page, SUBMIT_SIGNIN) or _click(page, 'button:has-text("Sign In")')
                log('auto sign-in: retried with the long Keychain password')
                if not _wait(page, answered, settle):
                    _wait(page, answered, settle)
                if signed_in(page):
                    continue
                kind = _kind_now(page)
            T['signin_msg'] = _messages(page)
            T['error'] = kind if kind in ('wrong_password', 'locked', 'none') else 'other'
            if kind == 'locked':
                return _fail('the tenant locked the account')
            if kind == 'wrong_password' and not created:      # JSA-334: Gmail first — Joey's own old account is never re-created
                step = after_wrong({'has_long': bool(long_pw), 'tried_long': True, 'created': created,
                                    'mails': _mails(), 'agent_since': AGENT_SINCE})
                if step == 'old_account':
                    log("auto sign-in: Gmail shows Joey's own older account on this tenant — not creating one")
                    return _fail('sign-in failed (an older account of Joey\'s exists)')
                if step == 'create' and _click(page, CREATE_LINK):
                    log('auto sign-in: no account here (or a different password) — trying Create Account')
                    _wait(page, lambda: _create_form(page), 8)
                    continue
            if created and not verified and not late_tried and late_find is not False and kind in ('wrong_password', 'none'):
                late_tried = True                                   # JSA-207: an account made on an earlier run may still be unverified —
                link = verification_link(datetime.now(timezone.utc) - timedelta(days=14), late_find, 1, log, page_url=page.url, company=company)
                if link:                                            # its link is in Gmail (this tenant's host only, verify_pattern)
                    _open_link(page, link)
                    verified = True; log("auto sign-in: opened this tenant's earlier verification link — signing in again")
                    if not signed_in(page) and not _visible(page, 'input[type="password"]'):
                        _click(page, SIGNIN_LINK)
                    continue
            return _fail('sign-in failed' + (' after creating the account' if created else ''))
        if _visible(page, A('SignInWithEmailButton')):            # social sign-in chooser first (a Workday employer 2026-10-30)
            btns = [b for b in page.locator(A('SignInWithEmailButton')).all() if b.is_visible()]
            for b in reversed(btns):                               # an employer / a Workday employer 2026-11-01: two copies, only the lower one opens the form
                try: b.click(timeout=4000)
                except Exception: continue
                log('auto sign-in: chose "Sign in with email"')
                if _wait(page, lambda: _visible(page, 'input[type="password"]') or _visible(page, CREATE_LINK), 6):
                    break
            continue
        if _click(page, CREATE_LINK) or _click(page, SIGNIN_LINK):  # an auth step with no form yet
            _wait(page, lambda: _visible(page, 'input[type="password"]'), 8)
            continue
        if not waited_blank:                                      # the login page renders late after a verify link (an employer, Mets 2026-11-01)
            waited_blank = True
            _wait(page, lambda: signed_in(page) or any(_visible(page, s) for s in ('input[type="password"]', A('SignInWithEmailButton'), CREATE_LINK, SIGNIN_LINK)), 15)
            continue
        return False, 'auth page without a sign-in or create-account form'
    return (True, 'signed in') if signed_in(page) else (False, 'sign-in did not finish in 9 steps')
