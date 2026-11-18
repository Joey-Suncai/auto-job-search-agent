"""Was the application really handed in? One check for every runner (JSA-299).

The old checks read the page text after Submit and called any "thank you for your interest" a confirmation. Many forms
print that sentence on the form itself (Bosch SmartRecruiters 11-11: "Again, thank you for your interest in our
internship opportunity"), so a page that was still spinning — or one that had refused the submit — was recorded as
submitted. The rule now:

1. The page must have changed after the click: the form's submit button is gone, or the URL changed (the fragment alone
   does not count). No change → never confirmed by the page (the caller waits for the receipt e-mail instead).
2. An error banner on the page ("please fix", "is required", …) → not confirmed.
3. Success = a success URL (…/confirmation, /thanks, /apply/success …) that the page moved to, or a success sentence
   that was not on the page before the click, or a success sentence on a NEW page (URL changed) without the form. A
   button that only went away (a spinner in its place, same URL) needs a sentence the form did not already show.
4. "Thank you for your interest" alone is never a success sentence (it is how forms greet the candidate).

Pure: callers pass two snapshots, {'url': str, 'text': str, 'form': bool | None}; `form` = the submit button is visible
(None = unknown, then only the URL can show the change). `settle(page)` waits for the page to come to rest before the
confirmation screenshot."""
import re
import time

STRONG_RE = re.compile(
    r"thank(s| you)( so much)? for (applying|your application|submitting( your application)?)"
    r"|(your )?application (was |has been |is )?(successfully )?(submitted|received|sent|complete)"
    r"|submission (has been received|(is )?complete)"
    r"|we('ve| have) received your application|your application is (in|on its way)"
    r"|you have (successfully )?applied|successfully submitted",
    re.I)
WEAK_RE = re.compile(r"thank(s| you)( so much)? for your interest", re.I)   # a greeting, never a confirmation
ERROR_RE = re.compile(r"please (fix|correct|complete)|is required|required field|there (was|were) (an |some )?errors?"
                      r"|fields? require a valid input|error verifying|something went wrong|could not be submitted", re.I)
SUCCESS_URL_RE = re.compile(r"/confirmation\b|/thanks?\b|/thank-you|/apply/(success|thank)|application-submitted|/success\b", re.I)


def _n(s):
    return re.sub(r'\s+', ' ', str(s or '')).strip()


def url_key(u):
    """The URL without its fragment and trailing slash: a '#section' jump is not a new page."""
    return str(u or '').split('#', 1)[0].rstrip('/')


def changed(before, after):
    """Why the page counts as changed after the click ('url' / 'form gone'), or None."""
    if url_key(after.get('url')) and url_key(after.get('url')) != url_key(before.get('url')):
        return 'url'
    if before.get('form') and after.get('form') is False:
        return 'form gone'
    return None


def phrases(text, rx=STRONG_RE):
    return {m.group(0).lower() for m in rx.finditer(_n(text))}


def judge(before, after, done_re=STRONG_RE, extra=None):
    """→ (confirmed: bool, why: str). `done_re` = the runner's success sentences (never the weak greeting); `extra` =
    an extra success test on the after snapshot (e.g. Workday '/userHome', Oracle My Profile 'Applied on …'), which also
    needs the page change."""
    t = _n(after.get('text'))
    why = changed(before, after)
    if not why:
        return False, 'no page change after the click (form still there, same URL)'
    new = phrases(t, done_re) - phrases(before.get('text'), done_re)
    if ERROR_RE.search(t) and not (new and after.get('form') is False):
        return False, 'error text on the page'
    url_ok = bool(SUCCESS_URL_RE.search(url_key(after.get('url')))) and why == 'url'
    if url_ok:
        return True, f'success URL ({why})'
    if new:
        return True, f'new success sentence "{sorted(new)[0]}" ({why})'
    if why == 'url' and after.get('form') is False and phrases(t, done_re):
        return True, 'success sentence on a new page without the form (url)'
    if extra and extra(after):
        return True, f'success page ({why})'
    return False, 'page changed but no success sentence' + (' (only "thank you for your interest")' if WEAK_RE.search(t) else '')


def settle(page, secs=8):
    """Wait (≤ secs) for the page to stop loading before the confirmation screenshot."""
    try:
        page.wait_for_load_state('networkidle', timeout=secs * 1000)
    except Exception:
        pass
    time.sleep(1)


def shot_blank(png):
    """Pure (tested, JSA-223). True when a screenshot shows (almost) nothing: fewer than 0.1 % of its pixels differ from the
    most common colour by more than 16 in any channel (a Greenhouse employer 11-05: a white page with one 130 × 2 px link underline — the
    text had not been painted yet). Unreadable / empty bytes → True. Without Pillow the size alone cannot tell, → False."""
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        import io
        img = Image.open(io.BytesIO(png)).convert('RGB')
    except Exception:
        return True
    w, h = img.size
    if not w or not h:
        return True
    if w * h > 400000:                                  # a count of colours on a big shot is slow / heavy: look at a reduced copy
        f = max(2, int((w * h / 400000) ** 0.5) + 1)
        img = img.reduce(f); w, h = img.size
    colors = img.getcolors(maxcolors=w * h) or []
    if not colors:
        return True
    bg = max(colors)[1]
    ink = sum(n for n, c in colors if max(abs(c[i] - bg[i]) for i in range(3)) > 16)
    return ink < 0.001 * w * h


SUCCESS_JS = r"""() => /thank(s| you)|application (was |has been |is )?(successfully )?(submitted|received|sent)|received your application|successfully submitted/i.test(document.body ? document.body.innerText : '')"""


def confirmation_shot(page, path, log=None, tries=3):
    """The confirmation screenshot (JSA-223): settle, wait (≤ 8 s) until a success sentence is in the page text, take the
    full-page shot; a blank one (text not painted yet) is retaken after a pause, the last tries as a viewport shot. Keeps the
    last shot either way and says so in the log when it is still blank. Never raises. Returns True when the file is not blank."""
    say = log or (lambda m: None)
    try:
        if page.is_closed():
            return False
    except Exception:
        pass
    settle(page)
    try:
        page.wait_for_function(SUCCESS_JS, timeout=8000)
    except Exception:
        pass
    data = b''
    for i in range(max(1, tries)):
        try:
            page.evaluate('() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))')   # let a paint happen
        except Exception:
            pass
        try:
            data = page.screenshot(path=path, full_page=(i < tries - 1 or tries == 1))
        except Exception as e:
            say(f'confirmation screenshot failed: {str(e)[:80]}')
            return False
        try:
            blank = shot_blank(data)
        except Exception:
            blank = False
        if not blank:
            return True
        say(f'confirmation screenshot {i + 1} is blank — waiting and retaking')
        time.sleep(2 * (i + 1))
    say('confirmation screenshot is still blank after the retakes')
    return False
