import json, collections, re, os, datetime as _dt
TODAY = _dt.date.today().isoformat()
CHROME_DATE = os.environ.get('CHROME_SCRAPE_DATE', '2026-10-23')
J = json.load(open('out/jobs.json')); S = json.load(open('out/sources.json'))
keep = [j for j in J if j['level'] != 'Early Career (unlabeled)' or j['tier'] in ('A', 'B', 'C')]
TRACK = {"AI Product Manager": "AI Product Manager", "AI Agentic Engineer": "AI Agentic Eng", "Data Engineer": "Data Engineer", "Data Analyst": "Data Analyst", "Product Manager": "Product Manager", "Data Science / Analytics": "Data Sci / Analytics"}
def ref_kind(r):
    if r.startswith('1st-degree'): return '1st-degree contact'
    if 'LinkedIn connection' in r: return 'LinkedIn connection'
    if r == 'Warm intro path': return 'Warm intro'
    if 'alumni' in r: return 'School alumni'
    return 'Cold'
jobs = []
for j in keep:
    jobs.append({
        'id': j['id'], 'rank': j['rank'], 'score': j['score'], 'tier': j['tier'], 'company': j['company'], 'title': j['title'],
        'track': TRACK[j['track']], 'level': {'Internship': 'Internship', 'New Grad / Entry': 'New grad', 'Early Career (unlabeled)': 'Early career'}[j['level']],
        'location': j['location'] or '—', 'remote': 'Yes' if j['remote'] else 'No', 'posted': j['posted'] or '', 'salary': j['salary'] or '',
        'sources': '; '.join(j['sources']), 'n_sources': j['n_sources'], 'url': j['url'],
        'sponsorship': j['sponsorship'], 'h1b_fy25': j['h1b_fy25'] or 0, 'h1b_total': j['h1b_total'] or 0, 'h1b_since': j['h1b_since'] or '',
        'gc_sponsor': j.get('gc_sponsor') or '', 'gc_perm': j.get('gc_perm') if j.get('gc_perm') is not None else '', 'gc_months': j.get('gc_months') or '',
        'referral': ref_kind(j['referral']), 'referral_detail': j['referral'], 'contacts': '; '.join(j['contacts']), 'warm_path': j['warm_path'],
        'li_connections': j['li_connections'], 'li_alumni': j['li_alumni'],
        's_role': j['s_role'], 's_timing': j['s_timing'], 's_sponsor': j['s_sponsor'], 's_greencard': j['s_greencard'], 's_referral': j['s_referral'], 's_fresh': j['s_fresh'],
        'notes': ' | '.join(j.get('notes', [])),
    })
json.dump(jobs, open('out/dash_jobs.json', 'w'), ensure_ascii=False, separators=(',', ':'))

# companies
C = collections.defaultdict(list)
for j in jobs: C[j['company']].append(j)
comps = []
for c, L in C.items():
    b = max(L, key=lambda x: x['score'])
    comps.append({'company': c, 'open_roles': len(L), 'best_score': b['score'], 'best_tier': b['tier'], 'best_role': b['title'],
                  'a_roles': sum(1 for x in L if x['tier'] == 'A'), 'internships': sum(1 for x in L if x['level'] == 'Internship'),
                  'new_grad': sum(1 for x in L if x['level'] == 'New grad'), 'sponsorship': b['sponsorship'], 'h1b_fy25': b['h1b_fy25'],
                  'h1b_total': b['h1b_total'], 'h1b_since': b['h1b_since'], 'gc_sponsor': b['gc_sponsor'], 'gc_perm': b['gc_perm'], 'gc_months': b['gc_months'],
                  'referral': b['referral'], 'contacts': b['contacts'], 'warm_path': b['warm_path'],
                  'tracks': '; '.join(sorted({x['track'] for x in L}))})
comps.sort(key=lambda x: (-x['best_score'], -x['open_roles']))
json.dump(comps, open('out/dash_companies.json', 'w'), ensure_ascii=False, separators=(',', ':'))

# contacts (1st-degree people mapped to companies with open roles)
P = collections.defaultdict(lambda: {'roles': 0, 'best': None})
for j in jobs:
    for person in filter(None, j['contacts'].split('; ')):
        name, _, head = person.partition(' — ')
        k = (name, j['company'])
        e = P[k]; e['roles'] += 1; e['head'] = head
        if not e['best'] or j['score'] > e['best']['score']: e['best'] = j
contacts = []
for (name, comp), e in P.items():
    contacts.append({'key': f"{name} @ {comp}", 'person': name, 'company': comp, 'headline': e['head'], 'open_roles': e['roles'],
                     'best_role': e['best']['title'], 'best_score': e['best']['score'], 'best_level': e['best']['level'],
                     'ask': f"Message {name.split()[0]}: ask for a referral or a 15-minute chat about {e['best']['title'][:60]}"})
warm = {}
for j in jobs:
    if j['warm_path'] and j['company'] not in warm: warm[j['company']] = j
for comp, j in warm.items():
    contacts.append({'key': f"Warm path @ {comp}", 'person': '(intro needed)', 'company': comp, 'headline': j['warm_path'], 'open_roles': sum(1 for x in jobs if x['company'] == comp),
                     'best_role': j['title'], 'best_score': j['score'], 'best_level': j['level'], 'ask': j['warm_path']})
contacts.sort(key=lambda x: -x['best_score'])
json.dump(contacts, open('out/dash_contacts.json', 'w'), ensure_ascii=False, separators=(',', ':'))

# sources progress
META = {
 'Simplify Summer 2027': ('Curated GitHub list', 'git clone SimplifyJobs/Summer2027-Internships', 'Posting-level sponsorship flag'),
 'Simplify New Grad': ('Curated GitHub list', 'git clone SimplifyJobs/New-Grad-Positions', 'Posting-level sponsorship flag'),
 'vanshb03 Summer 2027': ('Curated GitHub list', 'git clone vanshb03/Summer2027-Internships', 'Posting-level sponsorship flag'),
 'vanshb03 New Grad 2027': ('Curated GitHub list', 'git clone vanshb03/New-Grad-2027', 'Posting-level sponsorship flag'),
 'SpeedyApply AI Intern': ('Curated GitHub list', 'git clone speedyapply/2027-AI-College-Jobs', 'None'),
 'SpeedyApply AI New Grad': ('Curated GitHub list', 'git clone speedyapply/2027-AI-College-Jobs', 'None'),
 'SpeedyApply SWE Intern': ('Curated GitHub list', 'git clone speedyapply/2027-SWE-College-Jobs', 'None'),
 'SpeedyApply SWE New Grad': ('Curated GitHub list', 'git clone speedyapply/2027-SWE-College-Jobs', 'None'),
 'Zapply Internships 2027': ('Curated GitHub list', 'git clone zapplyjobs/Internships-2027', 'Visa column (Sponsor)'),
 'Jobright Data Analysis New Grad': ('Curated GitHub list', 'git clone jobright-ai/2026-Data-Analysis-New-Grad', 'None'),
 'Jobright Data Analysis Intern': ('Curated GitHub list', 'git clone jobright-ai/2026-Data-Analysis-Internship', 'None'),
 'Jobright Business Analyst New Grad': ('Curated GitHub list', 'git clone jobright-ai/2026-Business-Analyst-New-Grad', 'None'),
 'Jobright Business Analyst Intern': ('Curated GitHub list', 'git clone jobright-ai/2026-Business-Analyst-Internship', 'None'),
 'LinkedIn': ('Job site (network signals)', 'Chrome: 14 searches (10-22) + 8 Data Analyst searches (10-23), past month, US', 'None; adds connections/alumni counts'),
 'Greenhouse boards': ('Company job boards (API)', 'Chrome fetch: 848 Greenhouse boards', 'None'),
 'Lever boards': ('Company job boards (API)', 'Chrome fetch: 346 Lever boards', 'None'),
 'Ashby boards': ('Company job boards (API)', 'Chrome fetch: 692 Ashby boards', 'None'),
 'Built In': ('Job site', 'Chrome: 14 searches x up to 6 pages (10-22) + 10 Data/BI/Business Analyst searches (10-23), all US', 'None'),
 'Handshake (visa-open filter)': ('University job board', 'Chrome: UIUC Handshake, "Open to US visa sponsorship" filter', 'Employer is open to sponsorship'),
 "Hacker News Who's Hiring": ('Community thread', 'HN Algolia API: Oct + Sep 2026 threads', 'Parsed from post text'),
}
kept_c = collections.Counter(s for j in jobs for s in j['sources'].split('; '))
a_c = collections.Counter(s for j in jobs if j['tier'] in ('A', 'B') for s in j['sources'].split('; '))
srcs = []
for name, raw in S['raw'].items():
    t, how, visa = META.get(name, ('Other', '', ''))
    srcs.append({'source': name, 'type': t, 'method': how, 'visa_signal': visa, 'collected': raw, 'relevant_us': S['after_filter'].get(name, 0),
                 'in_dashboard': kept_c.get(name, 0), 'tier_ab': a_c.get(name, 0), 'last_run': TODAY if t == 'Curated GitHub list' else CHROME_DATE, 'cadence': 'Daily (automatic)' if t == 'Curated GitHub list' else 'Weekly (Chrome, with Joey)'})
srcs.sort(key=lambda x: -x['in_dashboard'])
json.dump(srcs, open('out/dash_sources.json', 'w'), ensure_ascii=False, separators=(',', ':'))

# applications (agent shortlist to start)
import os
PREV = 'out/dash_applications_prev.json'   # copy of the live tracker, made before every export
prev = json.load(open(PREV)) if os.path.exists(PREV) else []
ADD_TRACK = os.environ.get('ADD_TRACK', '')   # set to a track name to append its top roles (used when adding a role)
by_ct = {(j['company'], j['title']): j for j in jobs}
def nxt_of(j):
    return (f"Ask {j['contacts'].split(' — ')[0]} for a referral, then apply" if j['contacts'] else
            f"Ask for an intro: {j['warm_path']}" if j['warm_path'] else "Apply on the company site")
def app_of(j, upd):
    return {'job_id': j['id'], 'company': j['company'], 'title': j['title'], 'track': j['track'], 'level': j['level'], 'score': j['score'],
            'status': 'Shortlisted', 'applied_on': '', 'referral_status': 'To ask' if (j['contacts'] or j['warm_path']) else 'None',
            'next_step': nxt_of(j), 'url': j['url'], 'updated': upd}
apps = []; seen = set()
for a in prev:                                   # keep his shortlist and any status he set
    j = by_ct.get((a['company'], a['title'])) or next((x for x in jobs if a.get('url') and x['url'] == a['url']), None)
    if j: a = {**a, 'job_id': j['id'], 'score': j['score'], 'track': j['track'], 'url': j['url']}
    apps.append(a); seen.add((a['company'], a['title']))
per = collections.Counter(a['company'] for a in apps); added = 0
for j in sorted(jobs, key=lambda x: -x['score']):   # + top Data Analyst roles (tier A/B, max 2 per company)
    if not ADD_TRACK or j['track'] != TRACK.get(ADD_TRACK, ADD_TRACK) or j['tier'] not in ('A', 'B') or (j['company'], j['title']) in seen or per[j['company']] >= 2: continue
    per[j['company']] += 1; apps.append(app_of(j, TODAY)); added += 1
    if added >= 15: break
json.dump(apps, open('out/dash_applications.json', 'w'), ensure_ascii=False, separators=(',', ':'))
import os
for f in ['dash_jobs', 'dash_companies', 'dash_contacts', 'dash_sources', 'dash_applications']:
    print(f, round(os.path.getsize(f'out/{f}.json') / 1e6, 2), 'MB', len(json.load(open(f'out/{f}.json'))), 'rows')
