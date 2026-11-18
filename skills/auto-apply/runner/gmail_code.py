#!/usr/bin/env python3
"""Read a fresh verification / security code from Joey's application inbox (read-only IMAP).

Password: a Gmail *app password* stored only in macOS Keychain:
    security add-generic-password -a <your gmail> -s job-agent-gmail -w
(the command prompts for it; nothing is written to files, logs or chat).

    python3 gmail_code.py --since-min 10 --sender greenhouse        # prints the code or exits 1
    from gmail_code import wait_for_code; wait_for_code(sender='greenhouse', since=ts, timeout=120)
The mailbox is opened read-only (EXAMINE): nothing is marked read, moved or deleted.
"""
import argparse, email, imaplib, os, re, subprocess, sys, time
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077: personal facts come from config/profile.json)
ACCOUNT = jsa_profile.get('accounts.gmail')
SERVICE = 'job-agent-gmail'
def extract_code(text, n=None):
    """The one-time code in a code mail, or None. A code is a whole 6-10 character letters/digits token.
    1. Code block first (JSA-304): a line that names the code and ends with ":" ("Copy and paste this code into the security
       code field on your application:") followed by a line holding only the token — Greenhouse's layout. This wins over
       anything earlier (the subject "Security code for your application to a Greenhouse employer" once gave "a Greenhouse employer").
    2. Else within 200 characters after the word 'code' (or 'passcode', 'pass code', 'one-time password', 'OTP' — Goldman
       Sachs 2026-11-05: "one-time passcode: 710027"): the token right after the word ("code: 204518", "code is 204518")
       wins whatever digits it has; further away the first token with a digit that is not an 8-digit YYYYMMDD date. A code
       starting with 19 / 20 is a code (JSA-297, an employer 2026-11-10).
    A token with no digit (Greenhouse's letter-only codes, Veeam / a Greenhouse employer 2026-11) counts only in those two code
    positions (block line, or right after the word), only with the expected length `n` (the number of code boxes; default
    8, Greenhouse), and only in mixed case that is not a word: an upper-case letter after the first character and a
    lower-case letter ("FTyAUMIB", "jbeRmAeA"). ALL-CAPS, all-lower and Capitalized words never count — an unusual code in
    one case is then not read (the run stops with "no code found") rather than a word being typed."""
    tok = r'(?<![A-Za-z0-9])([A-Za-z0-9]{6,10})(?![A-Za-z0-9])'
    trig = r'\b(?:pass ?code|code|one[- ]time password|otp)\b'
    def ok_pos(t):                                   # a token in a code position
        return bool(re.search(r'\d', t)) or _letter_code(t, n)
    for m in re.finditer(r'(?im)^[^\n]*' + trig + r'[^\n]*:[ \t\r]*\n(?:[ \t\r]*\n)*[ \t]*([A-Za-z0-9]{6,10})[ \t\r]*$', text):
        if ok_pos(m.group(1)):
            return m.group(1)
    for m in re.finditer(trig, text, re.I):
        rest = text[m.end():m.end() + 200]
        first = re.match(r'(?:\s*(?:[:\-–]|\bis\b))*\s*' + tok, rest, re.I)
        if first and ok_pos(first.group(1)):
            return first.group(1)
        for t in re.finditer(tok, rest):
            if re.search(r'\d', t.group(1)) and not _is_date(t.group(1)):
                return t.group(1)
    return None


def _letter_code(t, n=None):
    """A letters-only token that can be a code (JSA-304): length n (default 8), an upper-case letter after the first
    character and a lower-case letter — so never an ALL-CAPS, all-lower or Capitalized English word."""
    return (t.isalpha() and len(t) == (n or 8) and any(c.isupper() for c in t[1:]) and any(c.islower() for c in t))


def _is_date(s):
    """An 8-digit YYYYMMDD calendar date (1900-2099), e.g. 20261110 — never a code unless right after the word (JSA-297)."""
    m = re.fullmatch(r'(19|20)\d\d(\d\d)(\d\d)', s)
    return bool(m) and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(3)) <= 31


def app_password():
    # 'jobagent-gmail' is the item the daily email check uses (2026-10-30); 'job-agent-gmail' is the older name
    for service in ('jobagent-gmail', SERVICE):
        r = subprocess.run(['security', 'find-generic-password', '-a', ACCOUNT, '-s', service, '-w'], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    raise SystemExit('Gmail app password not in Keychain (service jobagent-gmail). See the docstring.')


def html_text(h):
    """Pure (tested). An HTML mail body → its visible text: <style> and <script> blocks removed with their contents (CSS
    such as ".containerWidth code {…}" held a fake "code", an employer 2026-11-03), every other tag replaced by a space."""
    h = re.sub(r'<(style|script)\b[^>]*>.*?</\1\s*>', ' ', str(h or ''), flags=re.S | re.I)
    return re.sub(r'<[^>]+>', ' ', h)


def _text(msg):
    parts = []
    for p in (msg.walk() if msg.is_multipart() else [msg]):
        if p.get_content_type() in ('text/plain', 'text/html'):
            try:
                t = p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8', 'replace')
            except Exception:
                continue
            parts.append(html_text(t) if p.get_content_type() == 'text/html' else t)
    return '\n'.join(parts)


def imap_since(since):
    """Pure (tested). IMAP SINCE takes a bare date and Gmail compares it in its own zone (not UTC): from 18:00 Chicago the
    UTC date is already tomorrow, so a code mail sent minutes ago fell before "SINCE <UTC date>" and was missed
    (an employer / Oracle 2026-11-03). Search from the day before `since` (any zone; naive = UTC); the exact `since` filter is
    applied to each mail's Date afterwards. → 'DD-Mon-YYYY'."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    return (since.astimezone(timezone.utc) - timedelta(days=1)).strftime('%d-%b-%Y')


def find_code(sender=None, since=None, hint=None, exclude=(), accept=None, n=None):
    since = since or (datetime.now(timezone.utc) - timedelta(minutes=10))
    mails = []
    M = imaplib.IMAP4_SSL('imap.gmail.com')
    try:
        M.login(ACCOUNT, app_password())
        M.select('INBOX', readonly=True)
        crit = ['SINCE', imap_since(since)]
        if sender:
            crit = ['FROM', sender] + crit
        typ, data = M.search(None, *crit)
        ids = (data[0] or b'').split()[-15:]
        for i in reversed(ids):
            typ, d = M.fetch(i, '(BODY.PEEK[])')
            msg = email.message_from_bytes(d[0][1])
            try:
                when = parsedate_to_datetime(msg['Date'])
            except Exception:
                continue
            if when < since:
                continue
            subj = str(make_header(decode_header(msg.get('Subject', ''))))
            body = subj + '\n' + _text(msg)
            if accept is not None and not accept(str(make_header(decode_header(msg.get('From', '')))), body):
                continue                                       # another sender's code (Oracle: another tenant, JSA-226)
            mails.append((when, body))
        return choose_code(mails, since, hint, exclude, n)
    finally:
        try: M.logout()
        except Exception: pass


def choose_code(mails, since, hint=None, exclude=(), n=None):
    """Pure (tested): mails = [(sent datetime, subject + body)] → the code to type. Newest mail first; only mails sent at
    or after `since`; a code in `exclude` (already typed into another form) is skipped; with a `hint` (the company name)
    only a mail that names it counts — two forms waiting at once must not swap codes (Walleye / a Greenhouse employer 2026-10-31)."""
    for when, body in sorted(mails, key=lambda m: m[0], reverse=True):
        if when < since:
            continue
        if hint and hint.lower() not in body.lower():
            continue
        c = extract_code(body, n)
        if c and c not in exclude:
            return c
    return None


NOT_RECEIPT = re.compile(r"security code|verification code|newsletter|job alert|interview|unfortunately|not moving forward|regret", re.I)
CONF_RX = re.compile(r"thank(s| you) for (your )?(applying|application|interest)|application (was |has been )?(received|submitted)|we.ve received your application|received your application", re.I)


def squash(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


ROLE_GENERIC = {'intern', 'internship', 'internships', 'summer', 'fall', 'spring', 'winter', '2025', '2026', '2027', 'the', 'and', 'of', 'a', 'an', 'for', 'at', 'co', 'op', 'program'}
SUBJ_RECEIPT = re.compile(r"thank(s| you) for (your )?(applying|application)|application (was |has been )?(received|submitted)|we.ve received your application|received your application", re.I)
SUBJ_INTEREST = re.compile(r"thank(s| you) for (your )?interest", re.I)
BODY_RECEIVED = re.compile(r"received your application|application (has been |was )?(successfully )?(received|submitted)|successfully (submitted|received)", re.I)


def role_names(title, text):
    """Pure (tested). True when `text` names the job `title`: at least one role word (generic words like intern / summer / 2026 do not
    count) and EVERY role word present as a whole word."""
    rw = [w for w in re.findall(r'[a-z0-9]+', (title or '').lower()) if w not in ROLE_GENERIC]
    words = set(re.findall(r'[a-z0-9]+', (text or '').lower()))
    return bool(rw) and all(w in words for w in rw)


def is_receipt(subj, body=None):
    """Pure (tested). A receipt subject; "thank you for your interest" alone only when the body says the application was received (JSA-390)."""
    if SUBJ_RECEIPT.search(subj or ''): return True
    return bool(SUBJ_INTEREST.search(subj or '') and body and BODY_RECEIVED.search(body))


def company_keys(company):
    """Pure. The strings a company is looked for by in a sender / subject: the full name, the name without The / Inc / LLC, its first word (≥ 3 characters)."""
    words = [squash(w) for w in re.findall(r"[A-Za-z0-9&'.]+", company or '') if squash(w) not in ('the', 'inc', 'llc', 'co', 'a', 'an')]
    return [k for k in [squash(company), ''.join(words)] + words[:1] if len(k) >= 3]


def role_words(title):
    return {w for w in re.findall(r'[a-z0-9]+', (title or '').lower()) if w not in ROLE_GENERIC}


def choose_mail(mails, since, company, role='', siblings=()):
    """Pure (tested): mails = [(sent datetime, from, subject[, body])] → the subject of the application-received mail of THIS application,
    or None. Only mails sent at or after `since`; a receipt subject (is_receipt); the company named in the sender or subject (letters and
    digits only, lower case: "a Lever employer" = "FieldAI"; the first word of a multi-word company is enough). Newest first. A time with no zone
    counts as UTC. JSA-390: a mail that names this `role` wins; one that names a sibling (another application at the company) is skipped;
    one that names neither counts only when there are no siblings (company + receipt is then unambiguous)."""
    keys = company_keys(company)
    if not keys:
        return None
    utc = __import__('datetime').timezone.utc               # a Date header with "-0000" parses naive (11-02 TypeError): read it as UTC
    aware = lambda d: d.replace(tzinfo=utc) if d.tzinfo is None else d
    since = aware(since)
    mails = [(aware(m[0]), m[1], m[2], m[3] if len(m) > 3 else None) for m in mails]
    siblings = list(siblings or [])
    for when, frm, subj, body in sorted(mails, key=lambda m: m[0], reverse=True):
        if when < since or not is_receipt(subj, body) or NOT_RECEIPT.search(subj or ''):
            continue
        hay = squash(frm) + ' ' + squash(subj)
        if not any(k in hay for k in keys):
            continue
        text = (subj or '') + ' ' + (body or '')
        if role_names(role, text) and not any(role_names(t, text) and role_words(t) > role_words(role) for t in siblings):   # "Analyst" is not "Senior Analyst"
            return subj
        if any(role_names(t, text) for t in siblings): continue
        if not siblings: return subj
    return None


def folder_meta(folder_path, key):
    import json
    for fn in ('wd_job.json', 'job.json', 'plan.json'):
        try:
            v = str(json.load(open(os.path.join(folder_path, fn), encoding='utf-8')).get(key) or '').strip()
            if v: return v
        except (OSError, ValueError):
            pass
    return ''


def self_folder():
    """The application folder this process works on: the argv entry that is a folder of the data home's applications (every runner takes it), else None."""
    try:
        import paths as jpaths
        apps = os.path.realpath(jpaths.apps())
        for a in sys.argv[1:]:
            p = os.path.realpath(os.path.expanduser(a))
            if os.path.isdir(p) and os.path.dirname(p) == apps: return os.path.basename(p)
    except Exception:
        pass
    return None


def sibling_titles(company, since, exclude_folder=None, runner=None, apps=None, hours=6):
    """Pure-ish (tested with temp dirs, JSA-390). The job titles of OTHER applications at `company` whose Submit was recorded (results.jsonl:
    submitted / unconfirmed, no dry run) within `hours` before `since` or later — their receipts can land in this application's mail
    window. A title may be '' (unknown); a non-empty list means "the company has another application: company + receipt is ambiguous"."""
    import json, paths as jpaths
    runner = runner or jpaths.data('runner'); apps = apps or jpaths.apps()
    rp = os.path.join(runner, 'results.jsonl')
    if not os.path.exists(rp): return []
    key = squash(company); out, seen = [], set()
    utc = timezone.utc
    since = since if since.tzinfo else since.replace(tzinfo=utc)
    for line in open(rp, encoding='utf-8'):
        try: r = json.loads(line)
        except ValueError: continue
        f = r.get('folder')
        if not f or f == exclude_folder or f in seen or r.get('mode') == 'dry-run' or r.get('status') not in ('submitted', 'unconfirmed'): continue
        try:
            at = datetime.fromisoformat(str(r.get('at')))
            at = at if at.tzinfo else at.astimezone()
        except ValueError: continue
        if at < since - timedelta(hours=hours): continue
        if key and squash(folder_meta(os.path.join(apps, f), 'company')) == key:
            seen.add(f); out.append(folder_meta(os.path.join(apps, f), 'title'))
    return out


def find_mail(since, company, role='', siblings=None, exclude_folder=None):
    """Read-only: the application-received mail of THIS application since `since` (subject) or None. JSA-390: bodies of the few mails that
    pass the company / receipt filters are read too (role words, "your interest" subjects); `siblings` defaults to sibling_titles()."""
    if exclude_folder is None:                               # the runner's own folder: argv holds it (every runner takes the app folder)
        exclude_folder = self_folder()
    if exclude_folder and not role:
        try:
            import paths as jpaths; role = folder_meta(os.path.join(jpaths.apps(), exclude_folder), 'title')
        except Exception: pass
    if siblings is None:
        try: siblings = sibling_titles(company, since, exclude_folder)
        except Exception: siblings = ['']                      # unknown → fail closed: only a mail that names the role counts
    M = imaplib.IMAP4_SSL('imap.gmail.com')
    try:
        M.login(ACCOUNT, app_password())
        M.select('INBOX', readonly=True)
        typ, data = M.search(None, 'SINCE', imap_since(since))
        mails = []
        ids = (data[0] or b'').split()[-200:]                  # headers only, one round trip; a busy day has 100+ mails (10-31)
        if not ids:
            return None
        typ, d = M.fetch(b','.join(ids), '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE)])')
        for part in d:
            if not isinstance(part, tuple):
                continue
            msg = email.message_from_bytes(part[1])
            try:
                when = parsedate_to_datetime(msg['Date'])
            except Exception:
                continue
            mid = re.match(rb'\s*(\d+)', part[0] or b'')
            mails.append([when, str(make_header(decode_header(msg.get('From', '')))), str(make_header(decode_header(msg.get('Subject', '')))), None, mid.group(1) if mid else None])
        keys = company_keys(company)
        aw = lambda d: d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        cand = [m for m in mails if m[4] and aw(m[0]) >= aw(since) and any(k in squash(m[1]) + ' ' + squash(m[2]) for k in keys) and not NOT_RECEIPT.search(m[2] or '')
                and (SUBJ_RECEIPT.search(m[2] or '') or SUBJ_INTEREST.search(m[2] or ''))]
        for m in sorted(cand, key=lambda m: m[0], reverse=True)[:8]:       # bodies of the few possible receipts only
            try:
                typ, bd = M.fetch(m[4], '(BODY.PEEK[])')
                m[3] = _text(email.message_from_bytes(bd[0][1]))[:6000]
            except Exception:
                pass
        return choose_mail([tuple(m[:4]) for m in mails], since, company, role=role, siblings=siblings)
    finally:
        try: M.logout()
        except Exception: pass


def wait_for_mail(since, company, timeout=180, role='', siblings=None, exclude_folder=None):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = find_mail(since, company, role=role, siblings=siblings, exclude_folder=exclude_folder)
        if s:
            return s
        time.sleep(15)
    return None


def find_link(sender=None, since=None, pattern=r'https://\S+'):
    """Newest link matching `pattern` in a mail from `sender` since `since` (read-only, like find_code)."""
    since = since or (datetime.now(timezone.utc) - timedelta(minutes=10))
    M = imaplib.IMAP4_SSL('imap.gmail.com')
    try:
        M.login(ACCOUNT, app_password())
        M.select('INBOX', readonly=True)
        crit = ['SINCE', imap_since(since)]
        if sender:
            crit = ['FROM', sender] + crit
        typ, data = M.search(None, *crit)
        for i in reversed((data[0] or b'').split()[-60:]):   # 15 was too few on a busy day (an employer verify mail 2026-11-01)
            typ, d = M.fetch(i, '(BODY.PEEK[])')
            msg = email.message_from_bytes(d[0][1])
            try:
                if parsedate_to_datetime(msg['Date']) < since:
                    continue
            except Exception:
                continue
            raw = msg.as_string()
            raw = re.sub(r'=\r?\n', '', raw).replace('=3D', '=').replace('&amp;', '&')   # quoted-printable soft breaks
            m = re.search(pattern, raw, re.I)
            if m:
                return m.group(0).rstrip('.,)>"\'')
        return None
    finally:
        try: M.logout()
        except Exception: pass


def _raw_parts(msg):
    """Decoded text/plain + text/html parts (HTML kept as is, so href links survive; base64 and quoted-printable decoded)."""
    out = []
    for p in (msg.walk() if msg.is_multipart() else [msg]):
        if p.get_content_type() in ('text/plain', 'text/html'):
            try:
                out.append(p.get_payload(decode=True).decode(p.get_content_charset() or 'utf-8', 'replace'))
            except Exception:
                continue
    return '\n'.join(out).replace('&amp;', '&')


def recent_mails(since, limit=40):
    """Read-only: every INBOX mail dated at or after `since`, any sender → [{date, from, subject, body}] (date = ISO with
    zone; body = decoded parts, links intact). Headers first in one round trip; bodies only for the mails in the window
    (JSA-274: a tenant's verify mail can come from its own HR domain, so the sender cannot be the IMAP filter)."""
    if since.tzinfo is None:
        since = since.replace(tzinfo=timezone.utc)
    M = imaplib.IMAP4_SSL('imap.gmail.com')
    try:
        M.login(ACCOUNT, app_password())
        M.select('INBOX', readonly=True)
        _, data = M.search(None, 'SINCE', imap_since(since))
        ids = (data[0] or b'').split()[-200:]
        if not ids:
            return []
        _, d = M.fetch(b','.join(ids), '(BODY.PEEK[HEADER.FIELDS (DATE)])')
        keep = []
        for part in d:
            if not isinstance(part, tuple):
                continue
            num = part[0].split()[0]
            try:
                when = parsedate_to_datetime(email.message_from_bytes(part[1])['Date'])
            except Exception:
                continue
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when >= since:
                keep.append(num)
        out = []
        for i in keep[-limit:]:
            _, x = M.fetch(i, '(BODY.PEEK[])')
            msg = email.message_from_bytes(x[0][1])
            try:
                when = parsedate_to_datetime(msg['Date'])
            except Exception:
                continue
            out.append({'date': when.isoformat(), 'from': str(make_header(decode_header(msg.get('From', '')))),
                        'subject': str(make_header(decode_header(msg.get('Subject', '')))), 'body': _raw_parts(msg)})
        return out
    finally:
        try: M.logout()
        except Exception: pass


def wait_for_link(sender=None, since=None, timeout=180, pattern=r'https://\S+'):
    t0 = time.time()
    while time.time() - t0 < timeout:
        link = find_link(sender, since, pattern)
        if link:
            return link
        time.sleep(8)
    return None


def wait_for_code(sender=None, since=None, timeout=120, hint=None, exclude=(), n=None):
    t0 = time.time()
    while time.time() - t0 < timeout:
        c = find_code(sender, since, hint, exclude, n=n)
        if c:
            return c
        time.sleep(8)
    return None


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--sender'); ap.add_argument('--since-min', type=int, default=10)
    a = ap.parse_args()
    c = find_code(a.sender, datetime.now(timezone.utc) - timedelta(minutes=a.since_min))
    print(c or 'no code'); sys.exit(0 if c else 1)
