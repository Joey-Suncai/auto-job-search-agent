#!/usr/bin/env python3
"""JSA-419 (rule 13: real form questions of the 2026-11-17 first Ashby batch; DeepSeek variants: test_cases/jsa419_qa_shapes_cases.json
when present): a qa entry answers by the SHAPE of the field — tick box / one-option consent / list / text box.
    python3 scripts/test_jsa419_qa_shapes.py"""
import json, os, subprocess, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..'))
SC = os.path.join(ROOT, 'skills', 'auto-apply', 'scripts')
sys.path.insert(0, SC); sys.path.insert(0, os.path.join(ROOT, 'skills', 'auto-apply', 'runner'))
import qa_add as QA  # noqa: E402
BASE = json.load(open(os.path.join(ROOT, 'config', 'profile.example.json'), encoding='utf-8'))
TMP = tempfile.mkdtemp(prefix='jsa419_')
bad = 0


def prof(table):
    p = os.path.join(TMP, 'profile.json')
    json.dump(dict(BASE, qa=table), open(p, 'w', encoding='utf-8'))
    return p


def ans(table, label, options, typ):
    fields = [{'key': 'x', 'label': label, 'type': typ, 'options': options}]
    r = subprocess.run(['node', os.path.join(ROOT, 'skills/auto-apply/runner/rules_bridge.js'), os.path.join(SC, 'answer_rules.js')],
                       input=json.dumps({'fields': fields, 'jd': '', 'company': ''}), capture_output=True, text=True,
                       env=dict(os.environ, JSA_PROFILE=prof(table)), timeout=60)
    return (json.loads(r.stdout or '{}') or {}).get('x') or {}


def case(name, got, want):
    global bad
    if got != want:
        bad += 1; print(f'DISAGREE {name}: got {got!r}, want {want!r}')


def val(a):
    return a.get('value') if a.get('status') == 'ok' else None


# 1. Fundwell one-option consent boxes: --yes ticks the only option (qa_add's own check included)
CONSENT = [
    ('Background-Check Acknowledgment', ['I authorize Fundwell to obtain a consumer report and background check about me for employment purposes.']),
    ('Applicant Affirmation', ['I certify that the information provided in this application is true and complete.']),
    ('Employment Application Terms & Disclosures', ['I have read and agree to the Employment Application Terms & Disclosures.']),
]
for q, opts in CONSENT:
    t = [QA.entry(q, yes=True, source='t', today='2026-11-17')]
    for typ in ('checkbox', 'radio', 'select'):
        case(f'consent {q} as {typ}', val(ans(t, q, opts, typ)), opts[0])
    got = QA.check(q, opts, prof(t))                        # what qa_add --yes runs before saving
    case(f'qa_add check {q}', got.get('status'), 'ok')
    case(f'--no never ticks {q}', val(ans([QA.entry(q, yes=False, source='t', today='2026-11-17')], q, opts, 'checkbox')), None)
for o in ('I am not authorized to work in the United States', 'None of the above', 'N/A', 'Not applicable', 'I cannot attest to this',
          'I have not been convicted', 'Remote only', "I don't agree", 'I don\u2019t consent', "I won't accept"):
    for typ in ('select', 'radio'):                          # reviewer JSA-419: a one-option list that is no consent is never ticked by a Yes
        case(f'one option {o!r} as {typ} not ticked', val(ans([QA.entry('Q one', yes=True, source='t')], 'Q one', [o], typ)), None)
for o in ('None of the above', 'N/A', 'I am not authorized to work'):
    case(f'one-option checkbox {o!r} not ticked', val(ans([QA.entry('Q two', yes=True, source='t')], 'Q two', [o], 'checkbox')), None)
neg = ['I do not agree to the terms.']                       # a one-option box that says no is never ticked by a Yes
case('negated single option', val(ans([QA.entry('Terms', yes=True, source='t')], 'Terms', neg, 'checkbox')), None)
case('two options still need Yes/No', val(ans([QA.entry('Terms2', yes=True, source='t')], 'Terms2', ['I agree', 'I disagree'], 'radio')), None)

# 2. qa #117 (years of experience): list pick "None", free-text value "0"
Y_MATCH = '/^\\W*(?:how\\W+many\\W+years\\W+of\\W+work\\W+experience\\W+do\\W+you\\W+have|please\\W+mention\\W+the\\W+number\\W+of\\W+years\\W+of\\W+work\\W+experience)\\W*$/i'
e117 = QA.entry('Do you have at least 1 year professional work experience?', pick=['/^no\\b/i', '/^0\\s*-\\s*1\\b/'], match=Y_MATCH, source='t', today='2026-11-06')
t = [e117]
YO = ['None', 'Less than 3 years', '3 - 5 years', '5+ years']
case('117 before: no pick for None', val(ans(t, 'How many years of work experience do you have?', YO, 'select')), None)
t = [QA.extend(e117, pick=['/^none$/i'], box='0')]
case('117 list None', val(ans(t, 'How many years of work experience do you have?', YO, 'select')), 'None')
case('117 text box', val(ans(t, 'Please mention the number of years of work experience', [], 'text')), '0')
case('117 old pick still works', val(ans(t, 'How many years of work experience do you have?', ['Yes', 'No'], 'radio')), 'No')

# 3. qa #106 (work location): text value beside the picks; the pick pattern text is no longer typed
L_MATCH = '/^\\W*(?:from\\W+where\\W+do\\W+you\\W+intend\\W+to\\W+work|preferred\\W+office\\W+s\\W+location)\\W*$/i'
e106 = QA.entry('Which location do you prefer to work out of?', pick=['/chicago/i', '/^u\\.?s\\.?$/i'], match=L_MATCH, source='t', today='2026-11-10')
case('106 before: text box unknown', val(ans([e106], 'From where do you intend to work?', [], 'text')), None)
t = [QA.extend(e106, box='Chicago, Illinois, United States')]
case('106 text box', val(ans(t, 'From where do you intend to work?', [], 'text')), 'Chicago, Illinois, United States')
case('106 list still picks', val(ans(t, 'Preferred Office(s) Location', ['U.S.', 'Shanghai', 'Beijing'], 'select')), 'U.S.')
case('106 Chicago option', val(ans(t, 'From where do you intend to work?', ['NYC office', 'Chicago office', 'Other'], 'select')), 'Chicago office')

# 4. qa #152 (team / area): closest option per form; the Persona wording is its own entry
OCT = ['Octopus Energy \U0001F419', 'Octopus Energy Services', 'Octopus Energy Engineering', 'Octopus Energy Trading \U0001F4C8', "I don't know - I just love what you're doing and want to know more!"]
PER = ['Humanoid Locomotion: Develop algorithms for walking', 'Perception Systems: Work on computer vision', 'Machine Learning: Implement learning algorithms, training pipelines, and model optimization for robotic applications', 'Autonomy: Develop navigation, planning']
e152 = QA.entry("Please select the area of Octopus you're interested in (you can select multiple!)", pick=['/^data & analytics$/i', '/^machine learning:/i'], source='t', today='2026-11-10')
OQ = "Please select the area of Octopus you're interested in (you can select multiple!)"
case('152 before: Octopus has no pick', val(ans([e152], OQ, OCT, 'multi')), None)
e152b = QA.extend(e152, pick=['/\\btrading\\b/i'])
PQ = 'Which team best fits your background and career goals?'
ePers = QA.entry(PQ, pick=['/^machine learning:/i'], source='Joey 2026-11-16', today='2026-11-17')
t = [e152b, ePers]
case('152 Octopus → Trading', val(ans(t, OQ, OCT, 'multi')), OCT[3])
case('152 Persona → Machine Learning', val(ans(t, PQ, PER, 'select')), PER[2])
case('152 no fitting option → unknown (ask)', val(ans(t, PQ, ['Sales', 'Legal', 'Finance'], 'select')), None)

# 5. extend() leaves the entry's other fields and refuses nothing-to-add
try:
    QA.extend(e106); case('extend with nothing', 'no error', 'ValueError')
except ValueError:
    pass
case('extend keeps match', QA.extend(e106, box='x')['match'], L_MATCH)
case('extend keeps source', QA.extend(e106, box='x')['source'], 't')

# 6. Fab2: the follow-up "If no, is your home country listed below?" carries its parent question and the country list
import plan_build as PB, form_prefetch as FP  # noqa: E402
posting = {'applicationForm': {'sections': [{'title': 'U.S. Export Control Questions', 'fieldEntries': [
    {'id': 'a', 'isRequired': True, 'field': {'path': 'p1', 'title': 'I am one of the following: (a) a citizen of the United States; (b) a lawful permanent resident of the United States; or (c) a person admitted into the United States as an asylee or refugee:', 'type': 'Boolean'}},
    {'id': 'b', 'isRequired': True, 'descriptionHtml': '<p>Armenia, Azerbaijan, Belarus, Burma, Cambodia, China, Cuba, </p><p>Kazakhstan, North Korea</p>',
     'field': {'path': 'p2', 'title': 'If no, is your home country listed below?', 'type': 'Boolean'}}]}]}, 'surveyForms': []}
fl = PB.ashby_fields(posting)
case('ashby help text', 'China' in (fl[1].get('help') or '') and '<' not in (fl[1].get('help') or ''), True)
case('no help when none', 'help' in fl[0], False)
plan = {'fields': [dict(f, status='needs_user') for f in fl], 'needs_user': [{'key': 'p2', 'label': fl[1]['label'], 'why': 'no rule', 'options': ['Yes', 'No'], 'required': True}]}
it = FP.items_of_plan(plan, {}, set())
ctx = (it[0].get('context') or '') if it else ''
case('follow-up context has parent', 'citizen of the United States' in ctx, True)
case('follow-up context has the list', 'North Korea' in ctx, True)
case('label stays the form\'s own', it[0]['label'] if it else None, 'If no, is your home country listed below?')

# 7. DeepSeek-written variants (spec: test_cases/jsa419_qa_shapes_spec.md); Claude's verdicts on disagreements: ..._verdicts.json
CD = os.path.join(HERE, 'test_cases')
cases = json.load(open(os.path.join(CD, 'jsa419_qa_shapes_cases.json'), encoding='utf-8'))
vp = os.path.join(CD, 'jsa419_qa_shapes_verdicts.json')
verdicts = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
for c in cases:
    en = c['entry']
    try:
        e = QA.entry(en['q'], yes=en.get('yes'), pick=en.get('pick'), box=en.get('box'), source='t', today='2026-11-17')
    except ValueError as ex:
        if c['name'] not in verdicts:
            bad += 1; print(f"DISAGREE (case unbuildable: {ex}) {c['name']}")
        continue
    got = val(ans([e], c['label'], c.get('options') or [], c['type']))
    if got != c['expect'] and c['name'] not in verdicts:
        bad += 1; print(f"DISAGREE {c['name']}: got {got!r}, want {c['expect']!r}  [{c.get('spec_quote', '')[:80]}]")
print(f'{len(cases)} DeepSeek cases, {len(verdicts)} judged')
print('JSA-419 qa shapes:', 'ALL PASS' if not bad else f'{bad} disagreements')
sys.exit(1 if bad else 0)
