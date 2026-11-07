"""resolve_builtin (JSA-004), offline: JSON-LD reading, title matching, board tokens. Prints `fails 0` when all pass."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import resolve_builtin as rb

fails = 0
def ok(c, label):
    global fails
    fails += 0 if c else 1
    print(("PASS " if c else "FAIL ") + label)

page = ('<html><script type="application/ld&#x2B;json">{"@context":"https://schema.org","@type":"JobPosting","title":"Data Ops Engineer Intern",'
        '"hiringOrganization":{"@type":"Organization","name":"KelLumkel"}}</script> Builtin.jobPostInit({"job":{"applyUrl":""}})</html>')
ok(rb.posting_of(page) == ('Data Ops Engineer Intern', 'KelLumkel'), 'JobPosting read from Built In\'s escaped ld+json')
ok(rb.best_match('Data Ops Engineer Intern', [('Data Ops Engineer Intern', 'u1'), ('Data Engineer', 'u2')])[2] == 'u1', 'exact title wins')
ok(rb.best_match('Data Engineer Intern, 2027 Summer U.S.', [('Software Engineer Intern', 'u1'), ('Data Analyst', 'u2')]) is None, 'no close title → None')
ok(rb.best_match('Data Analyst Intern', [('Data Analyst Intern', 'a'), ('Data Analyst Intern', 'b')]) is None, 'two equal postings (cities) → None, not a guess')
jobs = [{'company': 'KelLumkel Inc.', 'url': 'https://job-boards.greenhouse.io/kellumkel/jobs/1'},
        {'company': 'Ostbraros', 'url': 'https://jobs.ashbyhq.com/ostbraros/ae4a6f7d-a240-4fa2-8c8e-04cc906e4ef9/application'},
        {'company': 'Zoox', 'url': 'https://jobs.lever.co/zoox/7206fd97-14e4-43a0-b903-ba65dfeee53e/apply'}]
kb = rb.known_boards(jobs)
ok(kb.get('kellumkel') == [('greenhouse', 'kellumkel')] and kb.get('ostbraros') == [('ashby', 'ostbraros')] and kb.get('zoox') == [('lever', 'zoox')], 'board tokens from known URLs (suffixes dropped)')
ok(('lever', 'southernfarmbureau') in rb.guesses('Southern Farm Bureau'), 'slug guesses for unknown companies')
r = rb.resolve('x', {}, page='<html><script type="application/ld+json">{"@type":"JobPosting","title":"X"}</script> "applyUrl":"https://jobs.lever.co/acme/1"</html>')
ok(r.get('ats_url') == 'https://jobs.lever.co/acme/1' and r['how'] == 'applyUrl on the page', 'a public applyUrl is used as is')
r = rb.resolve('x', {}, page='"applyUrl":"/job/a/1?handler=ApplyRedirect"', follow=lambda u: 'https://www.atlassian.com/company/careers/details/26272?iisn=BuiltIn&iis=Job+Board+Paid')
ok(r.get('ats_url') == 'https://www.atlassian.com/company/careers/details/26272' and r['ats'] == 'redirect', 'logged-in ApplyRedirect followed, tracking params dropped')
r = rb.resolve('x', {}, page='"applyUrl":"/job/a/1?handler=ApplyRedirect"', follow=lambda u: 'https://builtin.com/job/a/1')
ok('error' in r, 'a redirect that stays on Built In is not an answer')
print(f"fails {fails}")
sys.exit(1 if fails else 0)
