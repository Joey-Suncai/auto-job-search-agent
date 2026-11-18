#!/usr/bin/env python3
"""Fact gate for critical questions (JSA-281, Joey 2026-11-10: 「逐条修 + 关键题加闸门」).

Before every submit, canon.audit() runs this on what the page holds (label + value), whatever wrote the value — a rule,
a saved qa answer, the folder's answers.json, DeepSeek or the Workday profile. A value that contradicts the user's facts
in config/profile.json is a hard mismatch: the runner does not submit and the question goes to the user.

The 11-10 independent audit found the wrong answers this gate is for — rules or merged qa entries that matched the
wrong part of a question:
  conviction    "Have you ever been convicted of a felony …?" answered Yes (a Workday employer: background_drug matched the
                "criminal background check" notice before the question)                → answers.conviction
  any_employer  "authorized to work for any U.S Employer?" answered Yes (a Greenhouse employer)      → F-1: No until 2026-11-11;
                JSA-310 (Joey 11-11, work_auth.claim_authorized): Yes — a No / "not authorized" is the mismatch
  degree_level  "Level of education completed once you've graduated?" → Bachelor (Tinder); "currently pursuing a
                Bachelor's, Master's, or PhD in Data Science …?" → No (Ramp)           → education[] (level, current)
  major         "Undergrad Discipline(s)" / "Secondary Major" → Data Science (a Greenhouse employer, a Greenhouse employer) → education[] majors
  start_date    "availability to start" 06/01/2027 written into answers.json (Ankura)   → answers.start_date / ft_start
  pattern       a value that is a regex ('^agree$' typed into the salary box, Protective)  → never an answer
  qa            the user's own saved answer for this exact question, overridden (Tinder: Machine Learning vs his
                AI product management)                                                  → profile qa (exact question)
  defense       "Are there any reasons why you would not be able to fully contribute in support of the U.S. military
                …?" answered No by the government rule (a Lever employer 11-05, JSA-316; Joey: Yes — Chinese citizen, export
                control) → only the user's saved answer (qa, exact question or its own pattern); none → the user

A value the user confirmed for a tenant passes: `python3 canon.py --learn <tenant> fact:<key> "<value>"` (canon's learned
values, the same file). Pure functions; profile = the dict from config/profile.json (jsa_profile.load()).

  check(label, value, prof, typ='', learned=None) → None | {key, label, value, want, reason, evidence}
  audit(records, prof=None, learned=None)         → [mismatch, …]   records = [{"label", "value"[, "type", "options", "source"]}]
  plan_records(plan)                              → records from a plan.json (full labels, options, the answer's source)
"""
import re

NORM_WS = re.compile(r'\s+')


def norm(s):
    s = str(s if s is not None else '')
    s = re.sub('[​-‍⁠﻿­]', '', s).replace('’', "'").replace('‘', "'")
    return NORM_WS.sub(' ', s).strip()


def low(s):
    return norm(s).lower()


SECTION_RE = re.compile(r'^(.+?)\(([^()]*)\)\s*:\s*(.+)$')   # "Formal Education (University of Chicago): Degree" (= canon)


def question_part(label):
    """Pure (tested). The asking part of a label: the sentences that end in '?' (a notice before them only explains);
    none → the whole label. A "Section (entry): Field" label → the field."""
    lab = norm(label)
    m = SECTION_RE.match(lab)
    if m:
        return m.group(3)
    qs = [x for x in re.split(r'(?<=[.?!])(?<!\bu\.s\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\bvs\.)\s+', lab, flags=re.I) if re.search(r'\?\s*\)?\s*$', x.strip())]   # JSA-310: never split after "U.S." / "e.g." ("authorized to work in the U.S. without restriction?" lost its first half)
    return ' '.join(qs) if qs else lab


YES = re.compile(r"^(yes|true|i am\b(?! not)|i have\b(?! not| never)|i do\b(?! not)|i will\b(?! not)|i can\b(?! ?not))", re.I)
NO = re.compile(r"^(no|false|n/a|none|never|i am not|i'm not|i have not|i haven't|i have never|i do not|i don't|i was not|i will not|i cannot|i can't)\b", re.I)
AUX = re.compile(r'^(are|is|am|do|does|did|will|would|can|could|have|has|had|were|was)\b', re.I)

# ---- conviction (answer_rules CONVICT_Q)
CONVICT = re.compile(r'\b(been|ever been|ever|was|were|are you) (convicted|found guilty|charged)\b|\bconvicted of\b|\bpl(ea|e)d(ed)? (guilty|no contest|nolo)'
                     r'|\bfelon(y|ies)?\b|\bcriminal (record|history|conviction|offen[cs]e|charges?)\b|\bconvictions?\b', re.I)
NEGATED_STMT = re.compile(r"\b(have not|haven't|has not|never) (ever )?been (convicted|charged|found guilty)\b|\bi certify\b", re.I)

# ---- authorization for any employer (answer_rules any_employer)
ANY_EMP = re.compile(r'\b(any|all) ((u\.?\s?s\.?|united states|american)\s*)?employers?\b|without (any )?restriction|unrestricted', re.I)
AUTH = re.compile(r'authori[sz]|eligib|permitted|legally|right to work|allowed to work', re.I)
PERMANENT = re.compile(r'\bpermanent(ly)?\b', re.I)   # JSA-310

# ---- degree level
FUTURE_ED = re.compile(r"once (you'?ve |you have |you are |you're |you )?graduat|will you (have|hold|receive|earn|complete|obtain)\b|upon graduation|after (you )?graduat|when you graduate|(will|expect to) (have|hold|receive|earn|complete|obtain)\b"
                       r"|expected (degree|level)|degree (that )?(you are|you're) (currently )?(pursuing|seeking|working|obtaining|earning)"
                       r"|(currently|now) (pursuing|enrolled|working towards?|studying)|\bpursuing\b|\bseeking\b|in progress", re.I)
DONE_ED = re.compile(r'highest (completed |attained )?(level of )?(education|degree|schooling)|(most recently )?completed (form|level) of (education|schooling)'
                     r'|degrees? (you have )?(earned|completed|attained|obtained)|education completed', re.I)
DEGREE_Q = re.compile(r'\b(degree|education|schooling|bachelor|master|undergrad|graduate|ph\.?\s?d|doctora)', re.I)
MASTER_V = re.compile(r"\bmasters?\b|master'?s|\bm\.?\s?s\.?(c\.?)?$|^m\.?\s?s\.?\b|\bmba\b|(?<!under)graduate (degree|program|student|school|studies)|\bpost-?grad", re.I)
HIGHER_V = re.compile(r'\bdoctor|ph\.?\s?d|\bmba\b|\bjd\b|\bmd\b', re.I)
BACH_V = re.compile(r"\bbachelor|undergrad|\bb\.?\s?[as]\.?\b|college degree|\bassociate|high school|\bged\b", re.I)
LISTS_MASTER = re.compile(r"\bmaster'?s?\b|\bgraduate (degree|program|studies)\b|\bm\.?\s?s\.?\b|ph\.?\s?d", re.I)
LISTS_BACH = re.compile(r"\bbachelor'?s?\b|\bundergrad(uate)?\b|\bb\.?\s?[as]\.?\b", re.I)
HIS_FIELDS = re.compile(r'data science|statistic|quantitative|analytic', re.I)   # his M.S. Applied Data Science
FIELDS_NAMED = re.compile(r'\bin ([a-z][a-z ,/&-]{3,})', re.I)

# ---- major / field of study (answer_rules discipline / majorWhich)
MAJOR_Q = re.compile(r'\bmajor\b|discipline|field of study|area of study|concentration|program of study|course of study|\bminor\b', re.I)
NOT_MAJOR = re.compile(r'\bnot major\b|major[- ]specific|\bgpa\b|grade point|\bmajor (event|change|project|incident|life)|\bmajors? in\b.{0,20}\?', re.I)
SECOND_MAJOR = re.compile(r'\b(second(ary)?|double|additional|2nd|other) (major|discipline|field( of study)?|concentration)\b|\bminor\b|\bmajor\s*(#?\s*2|two)\b', re.I)
UNDERGRAD = re.compile(r"\bunder\s?-?grad(uate)?\b|\bbachelor'?s?\b|\bb\.\s?[as]\.?(?=\s|$)|\bcollege major\b", re.I)
GRADUATE = re.compile(r"\b(master'?s?|graduate (school|program|degree|studies)|post\s?-?grad|m\.\s?s\.|ph\.?\s?d)\b", re.I)
EMPTYISH = re.compile(r'^(none|n/?a|not applicable|no|-+|no (second|secondary|minor)\b.*|i (do not|don\'t) have (one|a (second|secondary) major|a minor))\.?$', re.I)

# ---- start date
START_Q = re.compile(r'availab\w* (to|for) (start|begin)|(earliest|desired|preferred|expected|potential) (possible )?start|\bstart date\b|when (can|could|would) you (start|begin)|date (you are |you\'re )?available|availability date', re.I)
MONTHS = {m: i for i, m in enumerate(['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'], 1)}


def date_parts(s):
    """Pure (tested). 'M/D/YYYY', 'YYYY-MM-DD', 'MM/YYYY', 'June 14, 2027', 'June 2027' → (y, m, d|None); else None."""
    s = low(s)
    m = re.search(r'\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b', s)
    if m:
        return int(m.group(3)), int(m.group(1)), int(m.group(2))
    m = re.search(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', s)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    m = re.search(r'\b(\d{1,2})[/.-](\d{4})\b', s)
    if m:
        return int(m.group(2)), int(m.group(1)), None
    m = re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})?,?\s*(\d{4})\b', s)
    if m:
        return int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)) if m.group(2) else None
    return None


def js_rx(s):
    """'/re/flags' (answer_rules form) → compiled Python regex; None when it does not compile."""
    m = re.fullmatch(r'/(.+)/([a-z]*)', str(s or '').strip(), re.S)
    try:
        return re.compile(m.group(1), re.I if 'i' in m.group(2) else 0) if m else None
    except re.error:
        return None


def qa_norm(s):
    """= answer_rules qaNorm / qa_add.norm."""
    s = str(s or '').lower().replace('‘', "'").replace('’', "'")
    s = re.sub(r'\(?\brequired\b\)?|\*', ' ', s)
    return re.sub(r"[^a-z0-9']+", ' ', s).strip()


def edu(prof, level):
    return next((e for e in (prof.get('education') or []) if e.get('level') == level), None)


def miss(key, label, value, want, reason, evidence):
    return {'key': 'fact:' + key, 'label': norm(label)[:120], 'value': norm(value)[:120], 'want': want, 'reason': reason, 'evidence': evidence}


def check_conviction(q, value, prof, label):
    if not CONVICT.search(q) or NEGATED_STMT.search(q):
        return None
    if not (re.search(r'\?', q) or AUX.match(q)):
        return None                                           # a notice or a statement, not the question
    fact = (prof.get('answers') or {}).get('conviction') or {}
    if fact.get('yes') is None:
        return miss('conviction', label, value, 'the user', 'conviction question: no fact on file (answers.conviction)', 'answers.conviction')
    want_no = fact.get('yes') is False
    v = low(value)
    if want_no and NO.match(v):
        return None
    if not want_no and YES.match(v):
        return None
    return miss('conviction', label, value, 'No' if want_no else 'Yes', 'conviction question answered against the fact',
                'answers.conviction (%s)' % fact.get('source', 'profile'))


def check_any_employer(q, value, prof, label):
    if not ANY_EMP.search(q) or not AUTH.search(q) or re.search(r'sponsor', q, re.I):
        return None
    wa = prof.get('work_auth') or {}
    if not wa.get('restricted'):
        return None
    v = low(value)
    if wa.get('claim_authorized'):                     # JSA-310 (Joey 2026-11-11): authorization questions = Yes, any employer too
        if PERMANENT.search(q):                        # "permanently authorized?" keeps its own fact (answers.any_employer.permanent)
            return None
        if NO.match(v) or re.search(r'\bnot (currently |presently |legally )*(authori[sz]ed|eligible|permitted)\b', v):
            return miss('any_employer', label, value, 'Yes', 'authorized for ANY employer: Joey 2026-11-11 answers every authorization question Yes',
                        "work_auth.claim_authorized (candidate-profile: 'Authorized to work for ANY employer = Yes', JSA-310)")
        return None
    if YES.match(v) and not re.search(r'\bnot\b|restrict|cpt|sponsor', v):
        return miss('any_employer', label, value, 'No', 'authorized for ANY employer: F-1 / CPT is employer-specific',
                    "work_auth.restricted (candidate-profile: 'Authorized to work for ANY employer now = No')")
    return None


CIT_STATUS = re.compile(r'\b(u\.?\s?s\.? )?citizen(ship)?\b|\b(lawful(ly)? )?permanent residen|green card|\bu\.?s\.? national\b', re.I)   # JSA-310
EXAMPLES = re.compile(r'\b(e\.\s?g\.|such as|for (example|instance)|including)[^?;()]*|\((e\.\s?g\.|such as)[^)]*\)', re.I)


def check_citizen_auth(q, value, prof, label):
    """JSA-310 (KBR 11-01, audit 11-11): "authorized to work … as a (i) U.S. citizen or national; or (ii) permanent resident?"
    asks for citizen / PR status → answers.citizen_pr (No); a Yes there is the mismatch. Examples ("e.g., U.S. citizen,
    permanent resident, F-1 OPT") only illustrate."""
    if not AUTH.search(q) or not CIT_STATUS.search(EXAMPLES.sub(' ', q)) or re.search(r'sponsor', q, re.I):
        return None
    fact = ((prof.get('answers') or {}).get('citizen_pr') or {})
    if fact.get('yes') is not False:
        return None
    if YES.match(low(value)) and not re.search(r'\bnot\b|\bno\b', low(value)):
        return miss('citizen_pr', label, value, 'No', 'authorization AS a U.S. citizen / permanent resident: he is neither',
                    "answers.citizen_pr (candidate-profile: not a U.S. citizen / permanent resident)")
    return None


def check_degree(q, value, prof, label):
    q = re.sub(r'\([^()]*\)', ' ', q)                     # "(Please do not list any degree that is in progress)" only explains (Voya 11-02)
    if not DEGREE_Q.search(q) or MAJOR_Q.search(q) and not re.search(r'level|highest|degree (type|level)', q, re.I):
        return None
    cur = next((e for e in (prof.get('education') or []) if e.get('current')), None)
    v = low(value)
    if not v:
        return None
    ev = 'profile education[] (%s)' % ', '.join(f"{e.get('level')} {e.get('major')}{' (current)' if e.get('current') else ''}" for e in prof.get('education') or [])
    yn = bool(YES.match(v) or NO.match(v)) and len(v) < 25
    if yn and re.search(r'(currently|now) (pursuing|enrolled|studying|working towards?)', q, re.I) and cur:
        fields = FIELDS_NAMED.search(q)
        if LISTS_MASTER.search(q) and (not fields or HIS_FIELDS.search(fields.group(1))):
            return None if YES.match(v) else miss('degree_level', label, value, 'Yes', f"currently pursuing a {cur.get('level')}'s ({cur.get('major')})", ev)
        if LISTS_BACH.search(q) and not LISTS_MASTER.search(q):
            return None if NO.match(v) else miss('degree_level', label, value, 'No', "not pursuing a bachelor's (completed)", ev)
        return None
    if yn:
        return None
    if FUTURE_ED.search(q) and cur:
        if cur.get('level') == 'master' and (BACH_V.search(v) or HIGHER_V.search(v)) and not MASTER_V.search(v):
            return miss('degree_level', label, value, "Master's", 'the degree being pursued / held after graduation is the M.S.', ev)
        return None
    if DONE_ED.search(q):
        done = [e for e in prof.get('education') or [] if not e.get('current')]
        if done and all(e.get('level') == 'bachelor' for e in done) and (MASTER_V.search(v) or HIGHER_V.search(v)) and not BACH_V.search(v):
            return miss('degree_level', label, value, "Bachelor's", 'highest COMPLETED education is the B.A. (the M.S. is in progress)', ev)
    return None


def check_major(q, value, prof, label):
    if not MAJOR_Q.search(q) or NOT_MAJOR.search(q):
        return None
    v = low(value)
    if not v or v in ('false', 'true'):
        return None
    ba, cur = edu(prof, 'bachelor'), next((e for e in (prof.get('education') or []) if e.get('current')), None)
    sm = low(((prof.get('answers') or {}).get('secondary_major') or {}).get('text'))
    if SECOND_MAJOR.search(q) and not re.search(r'\bmajor(s|\(s\))?\b[^?]{0,30}\b(and|&|/)\s*(any )?minor|\bin addition to\b', q, re.I):   # "major and minor/concentration?" asks the major too (= answer_rules majorWhich)
        if EMPTYISH.match(v) or (sm and v == sm):
            return None
        return miss('major', label, value, sm or 'empty / none', 'second major / minor: none on file', 'profile education[] majors; answers.secondary_major')
    if UNDERGRAD.search(q) and not GRADUATE.search(re.sub(r'\bunder\s?-?graduate\b', ' ', q, flags=re.I)) and ba and ba.get('major'):
        if low(ba['major']) in v or any(low(ba['major']) == p.strip() for p in re.split(r'[/,&|]| and ', v)):
            return None
        return miss('major', label, value, ba['major'], "the undergrad major is the bachelor's (%s)" % ba.get('degree'), 'profile education[] bachelor')
    if GRADUATE.search(q) and cur and ba and ba.get('major') and low(ba['major']) in v and not HIS_FIELDS.search(v):
        return miss('major', label, value, cur.get('major'), "the graduate major is the master's (%s)" % cur.get('degree'), 'profile education[] master')
    return None


def check_start(q, value, prof, label):
    if not START_Q.search(q) or SECTION_RE.match(norm(label)):   # "Previous Employment (Frost & Sullivan): Start Date" is that entry's date
        return None
    got = date_parts(value)
    if not got:
        return None
    a = prof.get('answers') or {}
    want = date_parts((a.get('start_date') or {}).get('text') or '')
    ft = (a.get('ft_start') or {}).get('after')                 # "2028-01": a full-time start
    if ft and (got[0], got[1]) >= tuple(int(x) for x in ft.split('-')[:2]):
        return None
    if not want:
        return None
    if (got[0], got[1]) == (want[0], want[1]) and (got[2] is None or want[2] is None or got[2] == want[2]):
        return None
    return miss('start_date', label, value, a['start_date']['text'], 'internship start date differs from the fact',
                'answers.start_date (full-time: ft_start %s)' % (ft or '-'))


def check_qa(label, value, prof, options=None, source=''):
    """The user's saved answer for this EXACT question (qa, normalised question text; regex-only matches are not used —
    a merged pattern may be wrong). A saved Yes / No contradicted by the value is a mismatch whatever wrote it. A saved
    option / text is checked when the folder's answers.json wrote the value (a Lever employer 11-10), or when the form offered the
    saved option and another was taken — option lists differ per form, so elsewhere a rule's pick stands. Numbers
    (GPA bands, pay) and rankings are left to their own rules."""
    nl = qa_norm(question_part(label)) or qa_norm(label)
    full = qa_norm(label)
    if APPLIED_Q.search(label):
        return None                                           # "previously applied to …?" = the tracker (answer_rules applied_before), not a saved answer
    hits = [e for e in prof.get('qa') or [] if e.get('q') and not e.get('retired') and qa_norm(e['q']) in (nl, full)]
    v = low(value)
    if not hits or not v:
        return None
    if re.search(r'\brank\b|\border of\b', label, re.I):
        return None
    hits = [e for e in hits if not re.search(r'\d', str(e.get('text') or '') + ' '.join(e.get('pick') or []))]
    if not hits:
        return None
    from_answers = str(source or '').startswith('answers.json')
    for e in hits:
        picks = [js_rx(p) for p in e.get('pick') or []]
        if 'yes' not in e and not from_answers and not (options and any(p and any(p.search(norm(o)) for o in options) for p in picks)):
            return None                                       # option / text entry, value not from answers.json, saved option not offered
        if 'yes' in e and e['yes'] is not None:
            if (YES.match(v) if e['yes'] else NO.match(v)):
                return None
            continue
        if any(p and p.search(norm(value)) for p in picks):
            return None
        if e.get('text') and not any(p and p.pattern == e['text'] for p in picks) and low(e['text']) == v:
            return None
        if not picks and not e.get('text'):
            return None
    e = hits[-1]
    want = 'Yes' if e.get('yes') is True else 'No' if e.get('yes') is False else (e.get('text') or ' / '.join(e.get('pick') or []))
    return miss('qa', label, value, str(want)[:80], "differs from the user's saved answer for this question",
                'profile qa: %r (%s)' % (e.get('q', '')[:60], e.get('source', '')))


APPLIED_Q = re.compile(r'\b(previously|ever|already|before|in the past|prior(ly)?|last \d+ (months?|years?|days?)|past \d+ (months?|years?|days?))\b[^?]{0,60}\b(applied|submitted (an )?application)'
                       r'|\b(applied|submitted (an )?application)\b[^?]{0,80}\b(before|previously|in the past|prior|last \d+ (months?|years?|days?)|past \d+ (months?|years?|days?)|past year|last year)\b', re.I)   # = answer_rules APPLIED_Q


# ---- supporting military / defense missions (JSA-316) = answer_rules DEFENSE_SUPPORT
DEFENSE_SUPPORT = re.compile(r'^(?![\s\S]*\b(service members?|military spouses?|veterans?|(military|veteran) status|self[- ]identif\w*)\b)[\s\S]*'
                             r'(\b(support(s|ed|ing)?|contribut\w*|assist(s|ing)?|help(s|ing)?)\b[^?!]{0,60}\b(military|defen[cs]e|armed forces|allied forces|national security|warfighters?|department of (defense|war)|dod)\b'
                             r'|\b(military|defen[cs]e)[- ](missions?|applications?|projects?|programs?|customers?|clients?|industry|products?|technolog\w*|contracts?|systems?|sector|work)\b'
                             r'|\b(reasons?|objections?|concerns?|reservations?|hesitat\w*)\b[^?]{0,80}\b(military|defen[cs]e|armed forces)\b'
                             r'|\b(willing(ness)?|comfortable|able|okay|ok|object)\b[^?]{0,60}\b(military|defen[cs]e|armed forces)\b)', re.I)


def check_defense(q, value, prof, label):
    """JSA-316: a question about supporting military / defense missions is answered only by the user's own saved
    answer — the exact question (normalised) or the entry's own pattern; no saved answer, or a value against it → the user.
    (Unlike check_qa, an entry's pattern counts here: no rule may answer these questions, so the saved answer is the fact.)"""
    if not DEFENSE_SUPPORT.search(q):
        return None
    nl, full = qa_norm(q), qa_norm(label)
    hits = []
    for e in prof.get('qa') or []:
        if not e or e.get('retired') or not (e.get('q') or e.get('match')):
            continue
        rx = js_rx(e.get('match'))
        if (e.get('q') and qa_norm(e['q']) in (nl, full)) or (rx and (rx.search(norm(label)) or rx.search(q))):
            hits.append(e)
    v = low(value)
    for e in reversed(hits):
        if e.get('yes') is not None:
            if YES.match(v) if e['yes'] else NO.match(v):
                return None
            continue
        if any(p and p.search(norm(value)) for p in (js_rx(x) for x in e.get('pick') or [])):
            return None
        if e.get('text') and low(e['text']) == v:
            return None
    if not hits:
        return miss('defense', label, value, 'the user', 'supporting military / defense missions: no saved answer — the user answers (no rule may)',
                    'profile qa (none for this question)')
    e = hits[-1]
    want = 'Yes' if e.get('yes') is True else 'No' if e.get('yes') is False else (e.get('text') or ' / '.join(e.get('pick') or []))
    return miss('defense', label, value, str(want)[:80], "supporting military / defense missions: differs from the user's saved answer",
                'profile qa: %r (%s)' % (e.get('q', '')[:60], e.get('source', '')))


PATTERN_V = re.compile(r'^\^.*|.*\$$|.*\\[ .()/\-bdsw].*|^/.+/[a-z]*$', re.S)


def check_pattern(q, value, prof, label):
    """A value that is a regex (a saved pick pattern typed as text: Protective 11-09 '^agree$') is never an answer."""
    v = norm(value)
    if PATTERN_V.match(v) and not re.match(r'^\$\s?\d', v):
        return miss('pattern', label, value, 'a real answer', 'the value is a match pattern, not an answer', 'qa entry text written from a pick pattern (JSA-281)')
    return None


CHECKS = (check_pattern, check_defense, check_conviction, check_citizen_auth, check_any_employer, check_degree, check_major, check_start)
SKIP_TYPES = {'file', 'hidden', 'password', 'account'}


def check(label, value, prof, typ='', learned=None, options=None, source=''):
    """Pure (tested). One field → None (consistent with the facts, or not a critical question) or the mismatch."""
    if str(typ or '').lower() in SKIP_TYPES:
        return None
    if isinstance(value, bool):
        value = 'Yes' if value else 'No'
    if isinstance(value, list):
        value = ' | '.join(str(x) for x in value)
    value = '' if value is None else str(value)
    if not norm(value) or low(value) in ('false', 'unchecked'):
        return None
    if str(typ or '').lower() == 'checkbox' and low(value) in ('true', 'checked'):
        return None                                         # a ticked box claims its label (canon judges category boxes)
    q = question_part(label)
    for fn in CHECKS:
        m = fn(q, value, prof, label)
        if m:
            break
    else:
        m = check_qa(label, value, prof, options, source)
    if m and learned and norm(value).lower() in [norm(x).lower() for x in learned.get(m['key'], [])]:
        return None                                         # the user confirmed this value for this tenant
    return m


def audit(records, prof=None, learned=None):
    """Every record that contradicts a fact (the runner blocks the submit on any)."""
    if prof is None:
        import jsa_profile
        prof = jsa_profile.load()
    out = []
    for r in records or []:
        m = check(r.get('label') or '', r.get('value'), prof, r.get('type') or '', learned, r.get('options'), r.get('source') or '')
        if m:
            out.append(m)
    return out


def plan_records(plan):
    """Pure (tested). plan.json → gate records for every answered field (full label, options, source) — the page probe
    cuts labels at 140 characters, so a question after a long notice is checked from the plan (run.py / run_form.py)."""
    return [{'label': f.get('label') or '', 'value': f.get('answer'), 'type': f.get('type') or '', 'options': f.get('options') or [],
             'source': f.get('source') or ''} for f in (plan or {}).get('fields') or [] if f.get('status') == 'ok' and isinstance(f.get('answer'), str)]
