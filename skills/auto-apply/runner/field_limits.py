"""The page's own limits on a text box, and whether a value meets them (JSA-312).

A dry run's read-back only compares the values filled in; an employer (Oracle, 2026-11-11) read back 51/51 and was still refused
at Submit in four places: a minor "None" under the 5-character minimum, a 1086-character career answer in a 200-character
box (questions.json had guessed 1500), and two links without http(s)://. The limits were on the page all along — in the
platform's question data (Oracle REST `recruitingCEQuestions`: MinimumLength / MaximumLength), in the box's attributes
(maxlength / minlength / type=url / pattern) or in its hint text ("4 out of 50 characters", "Enter Link 1 in the format:
http://example.com"). This module reads them (pure functions, tested) and judges a value before it is filled; the runners
also count any error the page itself marks after the fill as a failure.

limits = {'max': int|None, 'min': int|None, 'format': 'url'|None, 'pattern': str|None, 'source': str}
"""
import html
import re

N = lambda s: re.sub(r'\s+', ' ', str(s if s is not None else '')).strip()


def norm_prompt(s):
    """A question's text as a lookup key: tags and entities removed, lower case, punctuation and the required '*' dropped."""
    s = html.unescape(re.sub(r'<[^>]+>', ' ', str(s or '')))
    s = re.sub(r'[^0-9a-z]+', ' ', s.lower())
    return N(s)


def _int(v):
    try:
        v = int(float(v))
    except (TypeError, ValueError):
        return None
    return v if v > 0 else None


PROMPT_KEYS = ('Prompt', 'QuestionText', 'QuestionPrompt', 'Text', 'Label', 'Name')
MAX_KEYS = ('MaximumLength', 'MaxLength', 'MaximumCharacters', 'maxLength', 'Length')   # Oracle: questionnaire / profile blocks / name block (live 11-11)
MIN_KEYS = ('MinimumLength', 'MinLength', 'MinimumCharacters', 'minLength')


def limits_from_json(data):
    """Pure (tested). Any JSON the platform sent (Oracle REST: {'items': [{'Prompt', 'MinimumLength', 'MaximumLength', …}]},
    nested under questionnaires / sections) → {norm_prompt: limits}. A row with neither limit is left out."""
    out = {}

    def walk(x):
        if isinstance(x, dict):
            mx = next((_int(x[k]) for k in MAX_KEYS if k in x and _int(x[k])), None)
            mn = next((_int(x[k]) for k in MIN_KEYS if k in x and _int(x[k])), None)
            pr = next((x[k] for k in PROMPT_KEYS if isinstance(x.get(k), str) and x.get(k).strip()), None)
            if pr and (mx or mn):
                key = norm_prompt(pr)
                if key:                                    # the same prompt in two blocks: the tightest limits win
                    out[key] = merge(out.get(key), {'max': mx, 'min': mn, 'format': None, 'pattern': None, 'source': 'platform data'})
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(data)
    return out


COUNTER_RE = re.compile(r'\b(\d+)\s*(?:out of|of|/)\s*(\d+)\s*characters?\b', re.I)
MAX_RE = re.compile(r'\b(?:a )?(?:maximum|max\.?|up to|no more than|at most|limit(?:ed)? (?:of|to)?)\s*(?:of\s*)?(\d+)\s*characters?\b', re.I)
MIN_RE = re.compile(r'\b(?:at least|minimum(?: of)?|min\.?|no fewer than)\s*(\d+)\s*characters?\b', re.I)
URL_HINT_RE = re.compile(r'in the format:?\s*https?://|\bmust (?:be|start with) (?:a )?(?:valid )?(?:url|https?://)|\bvalid (?:url|web address|link)\b', re.I)


def limits_from_text(text):
    """Pure (tested). A box's hint / error text → limits: "4 out of 50 characters" (Oracle's counter) and "Enter a maximum
    of 200 characters." → max; "The value must have at least 5 characters." → min; "Enter Link 1 in the format:
    http://example.com." → format 'url'. Nothing found → all None."""
    t = N(text)
    maxes = [_int(m.group(2)) for m in COUNTER_RE.finditer(t)] + [_int(m.group(1)) for m in MAX_RE.finditer(t)]
    mins = [_int(m.group(1)) for m in MIN_RE.finditer(t)]
    mx = min([x for x in maxes if x], default=None)     # several sentences: the tightest wins
    mn = max([x for x in mins if x], default=None)
    fmt = 'url' if URL_HINT_RE.search(t) else None
    return {'max': mx, 'min': mn, 'format': fmt, 'pattern': None, 'source': 'page text' if (mx or mn or fmt) else None}


URL_LABEL_RE = re.compile(r'^\s*(link\s*\d*|url|website|web ?site|personal (web)?site|portfolio( (url|link|website))?|'
                          r'linked ?in( profile)?( url| link)?|github( profile)?( url| link)?)\s*\??\s*$', re.I)


def url_box(label, input_type=None):
    """Pure (tested). A box that wants a full web address: type=url, or a bare link label (Link 1, Website, Portfolio,
    LinkedIn Profile URL, GitHub). A question that only mentions a link in a sentence is not one."""
    return str(input_type or '').lower() == 'url' or bool(URL_LABEL_RE.match(N(label)))


BARE_ADDR_RE = re.compile(r'^(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}(/\S*)?$', re.I)


def fix_url(value, limits=None, label='', input_type=None):
    """Pure (tested). A url box (format 'url', type=url or a bare link label) given a bare address — the profile keeps
    "linkedin.com/in/…" for the resume — gets "https://" in front: the same address in the form the page accepts (an employer
    11-11: "Enter Link 1 in the format: http://example.com"). Anything else is returned as it is."""
    if not isinstance(value, str):
        return value
    v = value.strip()
    wants = (limits or {}).get('format') == 'url' or url_box(label, input_type)
    if wants and v and not re.match(r'^https?://', v, re.I) and BARE_ADDR_RE.match(v):
        return 'https://' + v
    return value


def merge(*ls):
    """Pure (tested). The tightest of several limits (attribute, page text, platform data): smallest max, largest min,
    any url format. Sources are joined."""
    out = {'max': None, 'min': None, 'format': None, 'pattern': None, 'source': None}
    src = []
    for l in ls:
        if not l:
            continue
        if l.get('max'):
            out['max'] = l['max'] if not out['max'] else min(out['max'], l['max'])
        if l.get('min'):
            out['min'] = l['min'] if not out['min'] else max(out['min'], l['min'])
        if l.get('format'):
            out['format'] = l['format']
        if l.get('pattern') and not out['pattern']:
            out['pattern'] = l['pattern']
        if l.get('source') and (l.get('max') or l.get('min') or l.get('format') or l.get('pattern')):
            src.append(l['source'])
    out['source'] = ' + '.join(dict.fromkeys(src)) or None
    return out


def lookup(label, table):
    """Pure (tested). The platform-data limits for a label: exact normalised match, else the one prompt that starts with /
    is contained in the label (labels carry a '*' or 'if applicable.' the prompt may not)."""
    if not table:
        return None
    k = norm_prompt(label)
    if not k:
        return None
    if k in table:
        return table[k]
    hits = [v for p, v in table.items() if len(p) >= 12 and (k.startswith(p) or p.startswith(k))]
    return hits[0] if len(hits) == 1 else None


def check(value, limits, label=''):
    """Pure (tested). Does `value` meet the limits? → None, or a reason code:
    'too_long' (over max), 'too_short' (under min; an empty value is not judged here — required-empty is the runner's check),
    'not_url' (a url box whose value is not http(s)://…), 'pattern' (fails the page's pattern)."""
    if value is None:
        return None
    v = N(value) if not isinstance(value, str) else value.strip()
    if not v:
        return None
    l = limits or {}
    if l.get('max') and len(v) > int(l['max']):
        return 'too_long'
    if l.get('min') and len(v) < int(l['min']):
        return 'too_short'
    if l.get('format') == 'url' or url_box(label):
        if not re.match(r'^https?://[^\s/]+\.[^\s]+$', v, re.I):
            return 'not_url'
    if l.get('pattern'):
        try:
            if not re.fullmatch(l['pattern'], v):
                return 'pattern'
        except re.error:
            pass
    return None


def why(reason, value, limits):
    """A one-line explanation for the run log / Joey."""
    n = len(str(value or '').strip())
    l = limits or {}
    src = f" ({l.get('source')})" if l.get('source') else ''
    return {'too_long': f'{n} characters, the box allows {l.get("max")}{src}',
            'too_short': f'{n} characters, the box needs at least {l.get("min")}{src}',
            'not_url': 'the box wants a full web address starting with http:// or https://',
            'pattern': f'does not match the page\'s format {l.get("pattern")!r}'}.get(reason, reason or '')


PAGE_ERROR_RE = re.compile(r'must have at least \d+|maximum of \d+ characters|in the format:|is required|is not valid|invalid|'
                           r'too (long|short)|exceeds|must be|enter a valid', re.I)


def page_error_text(row_text, label='', value=''):
    """Pure (tested). The error sentence(s) a page printed in a field's row (label and value removed), or ''."""
    t = N(row_text)
    for s in (N(label), N(value)):
        if s and len(s) > 3:
            t = t.replace(s, ' ')
    t = N(t)
    return t if PAGE_ERROR_RE.search(t) else ''
