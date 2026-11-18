#!/usr/bin/env python3
"""JSA-299: the confirmation check after Submit. Runs the DeepSeek-written cases (test_cases/confirm_page_cases.json,
spec confirm_page_spec.md) against confirm_page.judge and every runner's wrapper (Workable / SmartRecruiters page_done,
Lever / Ashby form_done, Workday wd_done, SuccessFactors sf_done, Greenhouse = judge with run.CONFIRM_RE), plus fixed
mocks: the Bosch incident (form text with the greeting, no change → not confirmed), a real thank-you page (confirmed),
iCIMS after_submit and Oracle oracle_moved. Verdicts for case disagreements: confirm_page_verdicts.json.
    ~/.job-agent-venv/bin/python scripts/test_confirm_page.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'skills', 'auto-apply', 'runner'))
import confirm_page as CP  # noqa: E402
import run_workable as W  # noqa: E402
import run_form as RF  # noqa: E402
import run_wd as WD  # noqa: E402
import run_successfactors as S  # noqa: E402
import run_icims as IC  # noqa: E402
import run_oracle as O  # noqa: E402
import run as GH  # noqa: E402

# Each wrapper uses its own platform's sentence list; a verdict for a case disagreement may name the wrappers it covers
# ("only": [...]); without "only" it covers all.
CHECKS = {
    'judge': lambda b, a: CP.judge(b, a)[0],
    'greenhouse': lambda b, a: CP.judge(b, a, done_re=GH.CONFIRM_RE)[0],
    'workable/sr': lambda b, a: W.page_done(b, a)[0],
    'lever/ashby': lambda b, a: RF.form_done(b, a)[0],
    'workday': lambda b, a: WD.wd_done(b, a)[0],
    'successfactors': lambda b, a: S.sf_done(b, a)[0],
}

BOSCH_FORM = ("Motorsport Software and Data Analytics Graduate Intern. Screening questions. Reflect on a time when you faced "
              "challenges… Again, thank you for your interest in our internship opportunity. Submit")
URL = 'https://jobs.smartrecruiters.com/oneclick-ui/company/LumFencor/publication/7a66539e'
MOCKS = [  # (name, before, after, expect) — must hold for every wrapper
    ('Bosch 11-11: same form, spinner, button still there', {'url': URL, 'text': BOSCH_FORM, 'form': True},
     {'url': URL, 'text': BOSCH_FORM + ' Submitting…', 'form': True}, False),
    ('Bosch 11-11: same URL, button replaced by a spinner', {'url': URL, 'text': BOSCH_FORM, 'form': True},
     {'url': URL, 'text': BOSCH_FORM, 'form': False}, False),
    ('greeting only, even on a new URL', {'url': URL, 'text': BOSCH_FORM, 'form': True},
     {'url': URL + '/done', 'text': 'Thank you for your interest in Bosch.', 'form': False}, False),
    ('refused: errors, button still there', {'url': URL, 'text': BOSCH_FORM, 'form': True},
     {'url': URL, 'text': BOSCH_FORM + ' This field is required. Please fix the errors.', 'form': True}, False),
    ('real thank-you page on a success URL', {'url': 'https://apply.workable.com/acme/j/ABC123/apply/', 'text': 'Apply. Submit application', 'form': True},
     {'url': 'https://apply.workable.com/acme/j/ABC123/apply/success', 'text': 'Thank you for applying! We have received your application.', 'form': False}, True),
    ('real thank-you in place (same URL), new sentence, form gone', {'url': URL, 'text': BOSCH_FORM, 'form': True},
     {'url': URL, 'text': 'Your application has been submitted. We will be in touch.', 'form': False}, True),
]


def main():
    cases = json.load(open(os.path.join(HERE, 'test_cases', 'confirm_page_cases.json')))
    cases = cases['cases'] if isinstance(cases, dict) else cases
    vp = os.path.join(HERE, 'test_cases', 'confirm_page_verdicts.json')
    verdicts = json.load(open(vp)) if os.path.exists(vp) else {}
    bad, n = 0, 0
    for c in cases:
        v = verdicts.get(c['name']) or {}
        for k, fn in CHECKS.items():
            n += 1
            got = fn(c['before'], c['after'])
            if got == bool(c['expect']):
                continue
            if v.get('verdict') == 'case' and (not v.get('only') or k in v['only']):
                print(f'CASE  [{k}] {c["name"]} — {v["why"]}'); continue
            bad += 1; print(f'FAIL  [{k}] {c["name"]}: got {got} want {c["expect"]}')
    for name, b, a, want in MOCKS:
        for k, fn in CHECKS.items():
            n += 1
            got = fn(b, a)
            if got != want:
                bad += 1; print(f'FAIL  [{k}] mock {name}: got {got} want {want}')
    # Oracle: the final click's page must change, or the success sentence must be new
    of = {'url': 'https://x.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX/job/1/apply/section/4', 'text': 'Thank you for applying to Acme. Submit', 'form': True}
    for name, a, want in [('Oracle: same section, intro thanks', dict(of), False),
                          ('Oracle: new URL', dict(of, url=of['url'].replace('apply/section/4', 'my-profile'), form=False), True),
                          ('Oracle: same URL, new sentence', dict(of, text=of['text'] + ' Your application has been successfully submitted.'), True)]:
        n += 1
        if O.oracle_moved(of, a) != want:
            bad += 1; print(f'FAIL  mock {name}')
    # iCIMS: no step bar, the form's own "thank you for applying" → not done; a new sentence / a moved bar → done
    form = 'Thank you for applying to Acme. Please answer the questions below.'
    for name, args, want in [('iCIMS: same page, intro thanks', (form, None, form), 'pending'),
                             ('iCIMS: new sentence', (form + ' Your application has been submitted.', None, form), 'done'),
                             ('iCIMS: bar gone after step 3', ('Thank you for applying. Your application has been received.', 3, 'Step 3 of 3 (Current Step) Review ' + form), 'done'),
                             ('iCIMS: unknown before text (old call)', (form, None, None), 'done')]:
        n += 1
        got = IC.after_submit('https://x.icims.com/jobs/1/candidate', args[0], args[1], args[2])
        if got != want:
            bad += 1; print(f'FAIL  mock {name}: got {got} want {want}')
    # Replays of stored evidence (JSA-299 audit 2026-11-11: the page text read off submitted_confirmation.png)
    ash = 'https://jobs.ashbyhq.com/{}/x/application'
    replays = [
        ('Morpellkel 11-10 (screenshot = the form still)', RF.form_done,
         {'url': ash.format('morpellkel'), 'text': 'Applicant Form\nThank you for your interest in MorPellkel (USA, Santa Clara). Please complete the application details below\nSubmit Application', 'form': True},
         {'url': ash.format('morpellkel'), 'text': 'Applicant Form\nThank you for your interest in MorPellkel (USA, Santa Clara). Please complete the application details below\nSubmit Application', 'form': True}, False),
        ('Corsevpell 10-31 (Ashby banner "Success / Thanks for your interest")', lambda b, a: RF.form_done(b, a, 'ashby'),
         {'url': ash.format('corsevpell'), 'text': 'Computer Vision Research Engineer - Intern\nOverview\nApplication\nSubmit Application', 'form': True},
         {'url': ash.format('corsevpell'), 'text': 'Computer Vision Research Engineer - Intern\nOverview\nApplication\nSuccess\nThanks for your interest in Corsevpell!', 'form': False}, True),
        ('Corsevpell banner, Lever wrapper (no Ashby rule) → e-mail check', RF.form_done,
         {'url': ash.format('corsevpell'), 'text': 'Application\nSubmit Application', 'form': True},
         {'url': ash.format('corsevpell'), 'text': 'Application\nSuccess\nThanks for your interest in Corsevpell!', 'form': False}, False),
        ('Talkelver 11-10 (Ashby banner with "application has been received")', lambda b, a: RF.form_done(b, a, 'ashby'),
         {'url': ash.format('ramp'), 'text': 'Applied Scientist Intern\nApplication\nSubmit Application', 'form': True},
         {'url': ash.format('ramp'), 'text': 'Success\nThank you for your interest in Ramp! Your application has been received and will be reviewed by our team.', 'form': False}, True),
        ('Newell 11-05 (SF success page)', S.sf_done,
         {'url': 'https://jobs.sevfengal.com/talentcommunity/apply/123/', 'text': 'Upload a Resume Expand all sections Apply', 'form': True},
         {'url': 'https://jobs.sevfengal.com/talentcommunity/apply/123/', 'text': 'Your application has been successfully submitted! We appreciate your interest in joining Sevfengal. Back to Job Listings View Profile', 'form': False}, True),
    ]
    for name, fn, b, a, want in replays:
        n += 1
        got = fn(b, a)[0]
        if got != want:
            bad += 1; print(f'FAIL  replay {name}: got {got} want {want}')
    print(f'{n - bad}/{n} ok')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
