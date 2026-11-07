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
def extract_code(text):
    """First whole 6-10 character token containing a digit, within 200 characters after the word 'code' (or 'passcode',
    'pass code', 'one-time password', 'OTP' — an employer 2026-11-05: "one-time passcode: 710027")."""
    for m in re.finditer(r'\b(?:pass ?code|code|one[- ]time password|otp)\b', text, re.I):
        for t in re.finditer(r'(?<![A-Za-z0-9])([A-Za-z0-9]{6,10})(?![A-Za-z0-9])', text[m.end():m.end() + 200]):
            if re.search(r'\d', t.group(1)) and not re.fullmatch(r'(19|20)\d\d\d*', t.group(1)):
                return t.group(1)
    return None


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


def find_code(sender=None, since=None, hint=None, exclude=(), accept=None):
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
        return choose_code(mails, since, hint, exclude)
    finally:
        try: M.logout()
        except Exception: pass


def choose_code(mails, since, hint=None, exclude=()):
    """Pure (tested): mails = [(sent datetime, subject + body)] → the code to type. Newest mail first; only mails sent at
    or after `since`; a code in `exclude` (already typed into another form) is skipped; with a `hint` (the company name)
    only a mail that names it counts — two forms waiting at once must not swap codes (Walleye / a Greenhouse employer 2026-10-31)."""
    for when, body in sorted(mails, key=lambda m: m[0], reverse=True):
        if when < since:
            continue
        if hint and hint.lower() not in body.lower():
            continue
        c = extract_code(body)
        if c and c not in exclude:
            return c
    return None


NOT_RECEIPT = re.compile(r"security code|verification code|newsletter|job alert|interview|unfortunately|not moving forward|regret", re.I)
CONF_RX = re.compile(r"thank(s| you) for (your )?(applying|application|interest)|application (was |has been )?(received|submitted)|we.ve received your application|received your application", re.I)


def squash(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())


def choose_mail(mails, since, company):
    """Pure (tested): mails = [(sent datetime, from, subject)] → the subject of the company's application-received mail,
    or None. Only mails sent at or after `since`; the subject must read as a receipt (CONF_RX); the company must be named
    in the sender or subject (letters and digits only, lower case: "a Lever employer" = "FieldAI"); first word of a multi-word
    company is enough ("a Lever employer" → "humble"). Newest first. A time with no zone counts as UTC."""
    words = [squash(w) for w in re.findall(r"[A-Za-z0-9&'.]+", company or '') if squash(w) not in ('the', 'inc', 'llc', 'co', 'a', 'an')]
    keys = [k for k in [squash(company), ''.join(words)] + words[:1] if len(k) >= 3]
    if not keys:
        return None
    utc = __import__('datetime').timezone.utc               # a Date header with "-0000" parses naive (11-02 TypeError): read it as UTC
    aware = lambda d: d.replace(tzinfo=utc) if d.tzinfo is None else d
    since = aware(since)
    mails = [(aware(w), f, s) for w, f, s in mails]
    for when, frm, subj in sorted(mails, key=lambda m: m[0], reverse=True):
        if when < since or not CONF_RX.search(subj or '') or NOT_RECEIPT.search(subj or ''):
            continue
        hay = squash(frm) + ' ' + squash(subj)
        if any(k in hay for k in keys):
            return subj
    return None


def find_mail(since, company):
    """Read-only: the company's application-received mail since `since` (subject) or None."""
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
            mails.append((when, str(make_header(decode_header(msg.get('From', '')))), str(make_header(decode_header(msg.get('Subject', ''))))))
        return choose_mail(mails, since, company)
    finally:
        try: M.logout()
        except Exception: pass


def wait_for_mail(since, company, timeout=180):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = find_mail(since, company)
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


def wait_for_link(sender=None, since=None, timeout=180, pattern=r'https://\S+'):
    t0 = time.time()
    while time.time() - t0 < timeout:
        link = find_link(sender, since, pattern)
        if link:
            return link
        time.sleep(8)
    return None


def wait_for_code(sender=None, since=None, timeout=120, hint=None, exclude=()):
    t0 = time.time()
    while time.time() - t0 < timeout:
        c = find_code(sender, since, hint, exclude)
        if c:
            return c
        time.sleep(8)
    return None


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--sender'); ap.add_argument('--since-min', type=int, default=10)
    a = ap.parse_args()
    c = find_code(a.sender, datetime.now(timezone.utc) - timedelta(minutes=a.since_min))
    print(c or 'no code'); sys.exit(0 if c else 1)
