#!/usr/bin/env python3
"""Critical vs non-critical form questions (Joey 2026-11-05: 「重要信息不能错，非重要信息能够达到95%以上正确率」, 「就按这个分」).

CRITICAL (0 wrong answers allowed on a submitted form):
  work_auth   ① work authorization / sponsorship / visa type / citizenship / immigration
  education   ② school, degree, major / field of study, GPA, degree start / graduation dates
  contact     ③ his name, e-mail, phone, address
  eeo         ④ gender, race / ethnicity, disability, veteran (and the other self-identification questions)
  experience  ⑤ anything written as his experience (work history, employer, job titles, years of experience, projects)
              or as other people's contact details (references)
NON-CRITICAL (answer accuracy ≥ 95 %): how-heard / source, communication preference, pay expectation, available start date,
  location / relocation / work arrangement, optional and everything else.

    from field_class import field_class
    field_class("Will you now or in the future require sponsorship?")   # → ('critical', 'work_auth')
    field_class("How did you hear about us?")                            # → ('non-critical', '')

Order: work authorization first (it outranks every other wording), then the explicit non-critical wordings (how heard,
pay, availability, location …), then the other critical groups (canon.py keys + wordings). Spec + DeepSeek cases:
scripts/test_cases/field_class_spec.md, scripts/test_field_class.py.
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
try:
    import canon  # noqa: E402  (classify(label) → the canonical high-stakes key)
except Exception:                                                  # never break a report because the facts file is missing
    canon = None

CANON_GROUP = {'work_auth_any_employer': 'work_auth', 'work_auth_today': 'work_auth', 'work_permit': 'work_auth',
               'sponsorship_countries': 'work_auth', 'sponsorship_now': 'work_auth', 'sponsorship_future': 'work_auth',
               'immigration_status': 'work_auth', 'degree_level': 'education', 'education_field': 'education',
               'school': 'education', 'gender': 'eeo', 'ethnicity': 'eeo', 'disability': 'eeo', 'veteran_status': 'eeo'}
WORK_AUTH = re.compile(r'sponsor|\bvisa\b|work authori[sz]ation|authori[sz]ed to (work|be employed)|legally (able|eligible|permitted) to work|'
                       r'right to work|work permit|immigration|citizen(ship)?\b|permanent resident|\bcpt\b|\bopt\b|h-?1b|export (control|compliance)|'
                       r'\bus person\b|\bu\.s\. person\b', re.I)
NON_CRITICAL = re.compile(r'how did you (hear|find|learn)|where did you (hear|find|see)|referral source|^source\b|'
                          r'communication (method|preference)|preferred (method of )?(contact|communication)|text message|\bsms\b|whatsapp|'
                          r'salary|\bpay\b|compensation|hourly rate|wage|'
                          r'(available|availability) to start|earliest (start|availability|date you can start)|when (can|could|would) you (start|begin)|'
                          r'desired start|internship start|^(?!.*\b(degree|program|school|university|college|enrol\w*|education|graduat\w*)\b).*start date|'
                          r'relocat|location preference|preferred (office )?location|which (office|location|city|site)s? (would|do|are)|'
                          r'work (arrangement|model|schedule)|\bremote\b|hybrid|on-?site|in[- ]office|travel', re.I)
EDUCATION = re.compile(r'\bgpa\b|grade point|\bdegree\b|\bmajor\b|\bminor\b|field of study|area of study|discipline|school|university|college|'
                       r'graduat|enrol|class standing|year in school|academic (year|standing|level)|transcript|coursework', re.I)
EEO = re.compile(r'\brace\b|ethnic|hispanic|latino|gender|\bsex\b|disabilit|veteran|military|pronoun|sexual orientation|transgender|lgbt', re.I)
DATES = re.compile(r'^(start|end|from|to)( date)?\s*(month|year|date)?$|^(start|end) date (month|year)$|^(from|to) (month|year)$|'
                   r'date (started|ended|of graduation)|graduation (date|year|month)', re.I)   # Workday education / work-history blocks
EXPERIENCE = re.compile(r'project(s)? (or two )?you(\'ve| have)? (worked|built|done|led|made)|description of (a|your|one) project|'
                        r'employer|employment history|work (history|experience)|job title|company name|current (company|title|position)|'
                        r'previous (role|position|job|employer)|responsibilit|years of (relevant |professional |work )?experience|'
                        r'reference|referee|describe (a|your) (project|experience|role|time)|tell us about (a|your) (project|experience|time|work)|'
                        r'portfolio|github|linkedin|skills? (you have|with)|proficien', re.I)
CONTACT = re.compile(r'(^|\b)(first|last|middle|full|legal|given|family|preferred)\s+name\b|^name\b|^your name|e-?mail|phone|mobile|'
                     r'address|street|\bzip\b|postal code|postcode|\bcity\b|\bstate\b|province|country of residence|date of birth', re.I)


def field_class(label):
    """Pure (tested). A question's label → (class, group): ('critical', '<group>') or ('non-critical', '')."""
    q = ' '.join(str(label or '').split())
    if not q:
        return 'non-critical', ''
    key = None
    if canon is not None:
        try:
            key = canon.classify(canon.question_of(q))
        except Exception:
            key = None
    if (key and CANON_GROUP.get(key) == 'work_auth') or WORK_AUTH.search(q):
        return 'critical', 'work_auth'
    if DATES.search(q):
        return 'critical', 'education'                             # his degree / work dates (Workday names the block, not the field)
    if key == 'source_channel' or NON_CRITICAL.search(q):
        return 'non-critical', ''
    if key in CANON_GROUP:
        return 'critical', CANON_GROUP[key]
    if EEO.search(q):
        return 'critical', 'eeo'
    if EDUCATION.search(q):
        return 'critical', 'education'
    if EXPERIENCE.search(q):
        return 'critical', 'experience'
    if CONTACT.search(q):
        return 'critical', 'contact'
    return 'non-critical', ''


if __name__ == '__main__':
    for a in sys.argv[1:]:
        print(field_class(a), '|', a)
