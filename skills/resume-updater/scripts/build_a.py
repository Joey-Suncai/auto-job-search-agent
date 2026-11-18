"""Style A: classic layout, cloned from the original resume's own paragraph XML."""
import re, sys, os, shutil, subprocess
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import paths  # noqa: E402  (scratch + output in the data home, JSA-377)
from content import NAME, CONTACT, EDU, LEAD, ROLES, FILE_PREFIX, LEAD_ON

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = paths.work('resume')   # un/ build_*/ out/ live here, not in the (read-only) code
if not os.path.exists(os.path.join(WORK, 'un/word/document.xml')):   # from-scratch rebuild (JSA-012): unpack + merge runs
    subprocess.run([sys.executable, os.path.join(HERE, 'prepare_template.py')], check=True)
X = open(os.path.join(WORK, 'un/word/document.xml')).read()
P = re.findall(r'<w:p[ >].*?</w:p>', X, flags=re.S)
HEAD, TAIL = X[:X.index('<w:body>') + len('<w:body>')], X[X.index('<w:sectPr'):]
# margins >= 0.5 in on all sides (MIT CAPD; resume-updater §1.6) — the template has 0.43 in top/bottom
TAIL = TAIL.replace('w:top="620"', 'w:top="720"').replace('w:bottom="620"', 'w:bottom="720"')

def esc(s): return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def fill(tpl, texts):
    it = iter(texts)
    def rep(m):
        return '<w:t xml:space="preserve">' + esc(next(it)) + '</w:t>'
    out = re.sub(r'<w:t(?: [^>]*)?>[^<]*</w:t>', rep, tpl)
    return re.sub(r' w14:paraId="[^"]+"', '', out)

T = dict(name=P[0], contact=P[1], section=P[2], schoolLoc=P[3], degree=P[7], courses=P[8],
         skill=P[13], org=P[16], titleDate=P[17], bullet=P[18], project=P[25])
# headline line: italic version of contact
T['headline'] = P[1].replace('<w:rFonts w:eastAsia="Times New Roman"/></w:rPr>', '<w:rFonts w:eastAsia="Times New Roman"/><w:i/><w:iCs/></w:rPr>')

HEADLINES = {
    "Data_Engineer": "Data Engineering Internship 2027 · Python · SQL · Cloud-Native Data Pipelines",
    "Product_Manager": "AI Product / Product Analytics Internship 2027 · Evaluation Design · Data-Driven Decisions",
    "AI_Agentic_Engineer": "AI / Agentic Engineering Internship 2027 · LLM Agents · Evaluation · Human-in-the-Loop",
    "Data_Analyst": "Data Analyst / BI Internship 2027 · SQL · Python · R · Excel · Tableau",
}

def build(key, r):
    # optional per-role typography knobs (resume-updater §1.6): a_bullet_after, a_section_before
    T = dict(globals()['T'])
    if r.get('a_bullet_after'):
        T['bullet'] = T['bullet'].replace('</w:numPr>', '</w:numPr><w:spacing w:after="%d"/>' % r['a_bullet_after'], 1)
        # the "Courses:" lines are bullets too and take the same spacing (the four 2026-10 bases, rebuilt by JSA-012)
        T['courses'] = T['courses'].replace('</w:numPr>', '</w:numPr><w:spacing w:after="%d"/>' % r['a_bullet_after'], 1)
    if r.get('a_section_before'):
        T['section'] = T['section'].replace('w:before="80"', 'w:before="%d"' % r['a_section_before'])
    out = [fill(T['name'], [NAME]), fill(T['contact'], [CONTACT]), fill(T['headline'], [HEADLINES[key]])]
    out.append(fill(T['section'], ['Education']))
    for e in EDU:
        out.append(fill(T['schoolLoc'], [e['school'], e['loc']]))
        out.append(fill(T['degree'], [e['degree'], e['detail'], e['date']]))
        out.append(fill(T['courses'], ['Courses: ', e['courses']]))
    out.append(fill(T['section'], ['Skills']))
    for k, v in r['skills'] + r.get('skills_a', []):
        out.append(fill(T['skill'], [k + ': ', v]))
    def exp():
        out.append(fill(T['section'], ['Internship Experience']))
        for j in r['exp']:
            out.append(fill(T['org'], [j['org']]))
            out.append(fill(T['titleDate'], [j['title'], j['date']]))
            out.extend([fill(T['bullet'], [b]) for b in j["bullets"]])
    def proj():
        out.append(fill(T['section'], ['Projects']))
        for p in r['projects']:
            out.append(fill(T['project'], [p['title'], ' (' + p['tag'] + ')', p['date']]))
            out.extend([fill(T['bullet'], [b]) for b in p["bullets"]])
    if key == 'AI_Agentic_Engineer':
        proj(); exp()
    else:
        exp(); proj()
    if LEAD_ON:                                       # off when the activity's fact says on_resume false (JSA-255)
        out.append(fill(T['section'], ['Leadership Experience']))
        out.append(fill(T['org'], [LEAD['org']]))
        out.append(fill(T['titleDate'], [LEAD['title'], LEAD['date']]))
        bl = LEAD['bullets_short'] if r['lead_short'] else LEAD['bullets_full']
        out += [fill(T['bullet'], [b]) for b in bl]
    return HEAD + ''.join(out) + TAIL

os.makedirs(os.path.join(WORK, 'out'), exist_ok=True)
for key, r in ROLES.items():
    d = os.path.join(WORK, 'build_' + key)
    shutil.rmtree(d, ignore_errors=True); shutil.copytree(os.path.join(WORK, 'un'), d)
    open(os.path.join(d, 'word/document.xml'), 'w').write(build(key, r))
    if r.get('a_sz'):  # base font size in half-points (21 = 10.5pt, 22 = 11pt)
        sp = os.path.join(d, 'word/styles.xml'); st = open(sp).read()
        st = st.replace('<w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>',
                        '<w:sz w:val="%d"/><w:szCs w:val="%d"/><w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>' % (r['a_sz'], r['a_sz']), 1)
        open(sp, 'w').write(st)
    fn = os.path.join(WORK, 'out', f'{FILE_PREFIX}_Resume_{key}_A-Classic.docx')
    if os.path.exists(fn): os.remove(fn)
    subprocess.run(['zip', '-Xqr', fn, '.'], cwd=d, check=True)
    print(fn)
