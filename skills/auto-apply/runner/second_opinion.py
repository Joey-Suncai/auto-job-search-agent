#!/usr/bin/env python3
"""Second opinion on uncertain rule answers (JSA-202, Joey 2026-11-05).

answer_rules.js marks an answer `uncertain` when a person would double-check it: the question was inverted ("able to
work WITHOUT sponsorship"), or several high-stakes rules with different answers fitted and one won by order (about 1.4 %
of all questions seen so far). rules_bridge.js sends only those answers here. DeepSeek (deepseek-flash) gets the
question, its options and the candidate's standard facts on that topic only (work authorization / sponsorship / visa /
education rows of candidate-profile.md — never EEO, contact or anything else), and answers the question itself without
seeing the rule's answer. Same answer → kept (`second_opinion: agree`); different answer, no answer, or an API error →
status unknown: the runner asks Joey. The rules stay the decider: the model can only stop an answer, never supply one.

    echo '[{"key", "label", "options", "type", "value", "rule", "uncertain"}]' | python3 second_opinion.py
        → {key: {"agree": bool, "model": str | null, "why": str}}
On only when the runner sets CX_SECOND_OPINION=1 (every run_*.py / prep script does); off when JSA_NO_PUSH or CX_DATA is set
(tests, replay); when off every answer is returned agreed with
why "off" so tests stay deterministic and offline.
"""
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'config'))
import paths as _jp  # noqa: E402
PROFILE_MD = _jp.fact('candidate-profile.md')   # the data home's fact file, else the repo's old place (JSA-339)
DS_URL = 'https://api.deepseek.com/chat/completions'
DS_MODEL = os.environ.get('CX_DS_MODEL', 'deepseek-flash')
KEY_PATHS = [os.environ.get('DEEPSEEK_KEY_FILE', ''), os.path.expanduser('~/deepseek/api_key'),
             os.path.expanduser('~/mnt/deepseek/api_key')]
TOPIC = re.compile(r'sponsor|authori[sz]|visa|\bF-?1\b|\bCPT\b|\bOPT\b|H-?1B|citizen|permanent|any employer|restriction|'
                   r'degree|graduat|enrol|school|year in|GPA|major|master|bachelor|student', re.I)
SENSITIVE = re.compile(r'gender|race|ethnic|hispanic|veteran|disab|orientation|transgender|pronoun|phone|e-?mail|address|'
                       r'birth|age\b|salary|compensation', re.I)


def enabled(env=None):
    """Pure (tested). The second opinion runs only in live runs."""
    env = os.environ if env is None else env
    return env.get('CX_SECOND_OPINION') == '1' and not (env.get('JSA_NO_PUSH') or env.get('CX_DATA'))


def facts(md_text):
    """Pure (tested). The standard-answer table rows and education lines on the uncertain topics only — never EEO or contact."""
    out, sect = [], ''
    for line in md_text.splitlines():
        if line.startswith('## '):
            sect = line
        if not (sect.startswith('## Standard application-form answers') or sect.startswith('## Education')):
            continue
        if line.startswith('|') and set(line.replace('|', '').strip()) <= set('-: '):
            continue
        if TOPIC.search(line) and not SENSITIVE.search(line):
            out.append(line.strip())
    return '\n'.join(out)


def norm(v):
    """Pure (tested). Compare answers loosely: case, punctuation, a trailing bracketed note ("F-1 (CPT)" = "F-1")."""
    s = re.sub(r'\s*\(.*\)\s*$', '', str(v or '').strip())
    return re.sub(r'[^a-z0-9]+', '', s.lower())


def same(rule_value, model_value, options=()):
    """Pure (tested). Do the rule and the model give the same answer?"""
    if model_value is None:
        return False
    a, b = norm(rule_value), norm(model_value)
    if not a or not b:
        return False
    if a == b:
        return True
    if options:                                          # both must name the same option
        oa = [o for o in options if norm(o) == a or norm(o).startswith(a) or a.startswith(norm(o))]
        ob = [o for o in options if norm(o) == b or norm(o).startswith(b) or b.startswith(norm(o))]
        return bool(oa) and oa == ob
    return continues(rule_value, model_value) or continues(model_value, rule_value)


def continues(short, long_):
    """Pure (tested, JSA-393). Is `long_` the answer `short` plus an explanation — what follows the short answer's words starts with a
    separator (comma, semicolon, colon, dash, bracket: "Yes" → "Yes, I am authorized") — or is `short` a bare yes / no / n/a?
    A trailing generic word (degree / program / level) adds nothing ("Master's" = "Master's Degree"). A longer NAME ("Hyde Park" → "Hyde Park Investment Services", "Master of Science" → "… in Data Science") is a different answer."""
    s0 = re.sub(r'\s*\(.*\)\s*$', '', str(short or '').strip())
    ns, nl = norm(s0), norm(long_)
    if not ns or len(nl) <= len(ns) or not nl.startswith(ns):
        return False
    raw, i, k = str(long_ or '').strip(), 0, 0              # walk the long text until the short answer's characters are used up
    while i < len(raw) and k < len(ns):
        if re.sub(r'[^a-z0-9]', '', raw[i].lower()):
            k += 1
        i += 1
    rest = raw[i:]
    if re.search(r"\b(not|no|never|but|however|unless|require[sd]?|need(s|ed)?|sponsor\w*|except|only)\b|n't", rest, re.I):
        return False                                        # a qualifier can turn the answer around: stop and ask
    if re.fullmatch(r'\s*(s|es|degree|degrees|program|programme|level|of america|student visa|visa)\s*', rest, re.I):
        return True                                         # "Master's" = "Master's Degree", "Bachelor" = "Bachelors", "United States" = "United States of America"
    if re.fullmatch(r'yes|no|na', ns):
        return not rest.strip() or not re.match(r'[a-z0-9]', rest[:1], re.I)   # a whole word, never "Yesterday" / "Not sure"
    return bool(re.match(r'\s*([,;:(\u2013\u2014]|-\s+[a-z])', rest))


def prompt(item, fact_text):
    opts = item.get('options') or []
    return ('You fill one job-application form question for a candidate, using ONLY the candidate facts below.\n'
            'Read the question exactly: note whether it asks about now, the internship, or the future, and whether it asks '
            '"do you NEED sponsorship" or "can you work WITHOUT sponsorship".\n\n'
            'Candidate facts:\n' + fact_text + '\n\n'
            'Question: ' + item['label'] + '\n' +
            ('Options (answer with one of them exactly): ' + ' | '.join(map(str, opts)) + '\n' if opts else 'Answer with a short value.\n') +
            'If the facts do not decide it, answer UNSURE.\n'
            'Reply as JSON: {"answer": "<option or short value or UNSURE>", "reason": "<one sentence>"}')


def ask_model(item, fact_text, post=None, prompt_text=None, model=None):
    """One DeepSeek call → (answer or None, reason). `post` is injectable for tests; prompt_text = another prompt
    (whole_read.py, JSA-288); model = another DeepSeek model (whole_read's confirming read)."""
    if post is None:
        key = next((open(p).read().strip() for p in KEY_PATHS if p and os.path.exists(p)), None)
        if not key:
            return None, 'no DeepSeek key'

        def post(body):
            req = urllib.request.Request(DS_URL, data=json.dumps(body).encode(), headers={
                'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key})
            return json.load(urllib.request.urlopen(req, timeout=40 if (body.get('model') or DS_MODEL) == DS_MODEL else 120))   # the stronger model thinks longer (JSA-288)
    body = {'model': model or DS_MODEL, 'temperature': 0, 'response_format': {'type': 'json_object'},
            'messages': [{'role': 'user', 'content': prompt_text or prompt(item, fact_text)}]}
    d = None
    for attempt in range(2):                             # one retry on a timeout / network error (JSA-288 replay: 6 pro timeouts)
        try:
            r = post(body)
            d = json.loads(r['choices'][0]['message']['content'])
            break
        except Exception as e:  # network, quota, bad JSON → no answer (the runner asks Joey)
            err = 'second opinion failed: ' + type(e).__name__
    if d is None:
        return None, err
    ans = str(d.get('answer') or '').strip()
    return (None if not ans or ans.upper() == 'UNSURE' else ans), str(d.get('reason') or '')[:200]


def review(items, md_text=None, post=None, env=None):
    """{key: {agree, model, why}} for the uncertain items."""
    if not enabled(env):
        return {it['key']: {'agree': True, 'model': None, 'why': 'off'} for it in items}
    fact_text = facts(md_text if md_text is not None else open(PROFILE_MD, encoding='utf-8').read())
    out = {}
    for it in items:
        m, why = ask_model(it, fact_text, post)
        out[it['key']] = {'agree': same(it.get('value'), m, it.get('options') or []), 'model': m, 'why': why}
    return out


if __name__ == '__main__':
    print(json.dumps(review(json.load(sys.stdin))))
