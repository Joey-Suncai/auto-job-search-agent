"""Job Search Agent — normalize, dedupe and score postings from every source.
Inputs:  src/ (cloned GitHub job lists + H-1B data) and raw/ (Chrome-collected jsa_*.json)
Outputs: out/jobs.json, out/companies.json, out/sources.json, out/connections.json
"""
import json, re, os, glob, math, html, collections, datetime as dt
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077)
JOB_NOTE = jsa_profile.get('work_auth.job_note')   # e.g. how a summer internship is authorized (CPT)
from urllib.parse import urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
SRC, RAW, OUT = f"{HERE}/src", f"{HERE}/raw", f"{HERE}/out"
os.makedirs(OUT, exist_ok=True)
_today = dt.datetime.now(dt.timezone.utc)
NOW = dt.datetime(_today.year, _today.month, _today.day, tzinfo=dt.timezone.utc)   # scoring date = today
# date the Chrome-collected files (LinkedIn, Built In, Handshake, ATS, HN) were scraped; relative ages there count from this day
CHROME = dt.datetime.fromisoformat(os.environ.get("CHROME_SCRAPE_DATE", "2026-10-23")).replace(tzinfo=dt.timezone.utc)

# ------------------------------------------------------------------ helpers
SUFFIX = r"\b(inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|limited|plc|lp|llp|holdings?|group|the|usa|us|america|na|n\.a|services|technologies|technology|labs?|global|international)\b"
def norm(c):
    c = (c or "").lower().replace("&", " and ")
    c = re.sub(r"\.com\b", "", c)
    c = re.sub(r"[^a-z0-9 ]+", " ", c)
    c = re.sub(SUFFIX, " ", c)
    return re.sub(r"\s+", " ", c).strip()

def title_case_token(tok):
    return tok.replace("-", " ").replace("_", " ").title()

TRACKS = [
    ("AI Product Manager", r"(?=.*(?:\b(?:ai|artificial intelligence|machine learning|ml|llm|genai|gen ai|generative|agents?|agentic|conversational)\b|\ba\.i\.(?!\w)))(?=.*\b(?:product manag\w*|product owner|apm|associate product|product lead|product intern|product strategy)\b)"),   # Joey 2026-11-03: AI PM is its own track, checked before AI Agentic Eng
    ("AI Agentic Engineer", r"\b(ai|a\.i\.|artificial intelligence|machine learning|ml|llm|genai|gen ai|generative|agent|agentic|nlp|deep learning|applied scien|research engineer|ai/ml|computer vision|mlops)\b"),
    ("Data Engineer",       r"\b(data engineer|data engineering|analytics engineer|data platform|data infrastructure|etl|data pipeline|big data|data warehouse|database|data ops|dataops|data architect)\b"),
    ("Data Analyst",        r"\b(data analysts?|data analytics|business analysts?|business analytics|bi analyst|bi developer|power bi|business intelligence|analytics analyst|analytics intern|reporting analyst|insights analyst|marketing analyst|operations analyst|business operations|data visuali[sz]ation|data & analytics|data and analytics|analyst, data|analyst, business intelligence|analyst, reporting|analyst, client reporting|financial data analyst|master data analyst|data integrity|growth analyst|strategy analyst)\b"),
    ("Product Manager",     r"\b(product manager|product management|apm|associate product|product analyst|product owner|product operations|product strategy|technical program|program manager|product designer|product intern|product)\b"),
    ("Data Science / Analytics", r"\b(data scien|data analy|analytics|business intelligence|bi analyst|business analyst|quantitative|quant|insights|statistic|decision scien|operations research|economist|research analyst|data intern|data)\b"),
]
def track_of(t):
    t = t.lower()
    for name, rx in TRACKS:
        if re.search(rx, t): return name
    return None

SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|director|head of|vp|vice president|manager ii|manager iii|architect|phd|ph\.d|postdoc|mba)\b", re.I)
INTERN = re.compile(r"\b(intern|internship|co-?op|summer associate|summer analyst|summer 2027|2027 summer)\b", re.I)
NEWGRAD = re.compile(r"\b(new grad|new college grad|graduate|early career|entry|university|campus|junior|associate|analyst i\b|engineer i\b|level 1|2027 start|class of 2027|rotational|apm)\b", re.I)

def level_of(t, hint=""):
    s = f"{t} {hint}"
    if INTERN.search(s): return "Internship"
    if NEWGRAD.search(s): return "New Grad / Entry"
    return "Early Career (unlabeled)"

def is_us(loc):
    l = (loc or "").lower()
    if not l: return True
    bad = r"\b(canada|toronto|vancouver|montreal|london|uk|united kingdom|india|bangalore|bengaluru|hyderabad|singapore|germany|berlin|munich|paris|france|ireland|dublin|amsterdam|netherlands|spain|madrid|barcelona|poland|warsaw|israel|tel aviv|japan|tokyo|china|beijing|shanghai|hong kong|australia|sydney|melbourne|brazil|mexico|switzerland|zurich|sweden|stockholm|korea|seoul|taiwan|philippines|vietnam|romania|portugal|lisbon|italy|milan|czech|prague|emea|apac|latam|ontario|uae|dubai|south africa|argentina|colombia|chile|denmark|norway|finland|belgium|austria|hungary|ukraine|serbia|greece|turkey|egypt|nigeria|kenya|pakistan|indonesia|malaysia|thailand|new zealand)\b"
    if re.search(bad, l) and not re.search(r"\b(united states|usa|us\b|remote - us|remote, us|new york|san francisco|chicago|seattle|boston|austin)\b", l):
        return False
    return True

def ts_to_date(ts):
    try: return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date().isoformat()
    except Exception: return ""

def age_to_date(s, base=None):
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month|mo|d|h|w|m)\b", s or "")
    if not m: return ""
    n, u = int(m.group(1)), m.group(2)
    days = {"minute": 0, "m": 0, "hour": 0, "h": 0, "day": 1, "d": 1, "week": 7, "w": 7, "month": 30, "mo": 30}[u] * n
    return ((base or NOW) - dt.timedelta(days=days)).date().isoformat()

def iso(d):
    if not d: return ""
    return str(d)[:10]

# ------------------------------------------------------------------ H-1B data (one matcher for every writer: h1b_match.py, JSA-098)
sys.path.insert(0, HERE)
import h1b_match  # noqa: E402
H1B = h1b_match.H1B(h1b_match.records_from(SRC))
if not H1B.emp:
    sys.exit(f"no H-1B data under {SRC} (clone flexapply/companies-that-sponsor-h1b and sergyinfo/h1b-open-data)")
def h1b_for(company):
    return dict(H1B.lookup(company), cert=None)

# ------------------------------------------------------------------ Green card (PERM) data from Ellis, top sponsor companies
PERM = {}
if os.path.exists(f"{RAW}/perm_ellis.txt"):
    for line in open(f"{RAW}/perm_ellis.txt"):
        p = line.rstrip("\n").split("|")
        if len(p) < 7 or p[1] != "1": continue
        PERM[norm(p[0])] = {"perm": int(p[3] or 0), "perm_year": p[4], "gc_sponsor": p[2], "perm_months": p[5].replace("m", " months"), "gc_commit": p[6]}
def perm_for(company):
    k = norm(company)
    if k in PERM: return PERM[k]
    for pk, v in PERM.items():
        if pk and (k.startswith(pk + " ") or pk.startswith(k + " ")) and len(min(k, pk, key=len)) > 3: return v
    return None

# ------------------------------------------------------------------ LinkedIn connections (1st-degree, current employer from headline)
# LinkedIn connections (1st-degree, current employer from headline) + second-degree paths: personal data → config/connections.json (JSA-077)
_CJ = jsa_profile.data_file('connections.json')
_C = json.load(open(_CJ, encoding='utf-8')) if os.path.exists(_CJ) else {}
CONN = {k: [tuple(x) for x in v] for k, v in _C.get('connections', {}).items()}
ALUMNI_LINK = _C.get('alumni_link', {})
def conn_for(company):
    k = norm(company)
    for key, people in CONN.items():
        if k == key or k.startswith(key + " ") or (len(key) > 4 and key in k):
            return people
    if k in ("aws",): return CONN["amazon"]
    if k in ("ey",): return CONN["ernst and young"]
    return []
def alum_link_for(company):
    k = norm(company)
    for key, why in ALUMNI_LINK.items():
        if k == key or k.startswith(key + " ") or (len(key) > 4 and key in k): return why
    return ""

# ------------------------------------------------------------------ collect
rows = []
src_stats = collections.Counter()
def add(**r):
    r.setdefault("loc", ""); r.setdefault("posted", ""); r.setdefault("salary", ""); r.setdefault("spons_flag", ""); r.setdefault("li_conn", 0); r.setdefault("li_alumni", 0); r.setdefault("level_hint", "")
    r["company"] = (r.get("company") or "").strip(); r["title"] = html.unescape((r.get("title") or "").strip())
    if not r["company"] or not r["title"]: return
    rows.append(r); src_stats[r["source"]] += 1

# 1. Simplify + vanshb03 structured lists
for f, label in [("SimplifyJobs_Summer2027-Internships", "Simplify Summer 2027"), ("SimplifyJobs_New-Grad-Positions", "Simplify New Grad"),
                 ("vanshb03_Summer2027-Internships", "vanshb03 Summer 2027"), ("vanshb03_New-Grad-2027", "vanshb03 New Grad 2027")]:
    for x in json.load(open(f"{SRC}/{f}/.github/scripts/listings.json")):
        if not x.get("active") or not x.get("is_visible", True): continue
        sp = x.get("sponsorship", "")
        flag = {"Offers Sponsorship": "offers", "Does Not Offer Sponsorship": "no", "U.S. Citizenship is Required": "citizen"}.get(sp, "")
        add(source=label, company=x.get("company_name"), title=x.get("title"), loc="; ".join(x.get("locations") or []), url=x.get("url"),
            posted=ts_to_date(x.get("date_posted")), spons_flag=flag, level_hint="intern" if "Summer" in label else "new grad",
            terms="; ".join(x.get("terms") or []) if isinstance(x.get("terms"), list) else "")

# 2. Markdown tables (speedyapply, zapply, jobright)
def md_rows(path):
    for line in open(path, encoding="utf-8"):
        if not line.startswith("| ") or line.startswith("| Company") or line.startswith("|---") or line.startswith("| -"): continue
        yield [c.strip() for c in line.strip().strip("|").split("|")]
def strip_md(s):
    s = re.sub(r"<[^>]+>", "", s); s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s); return s.replace("**", "").strip()
def first_url(s):
    m = re.search(r'href="([^"]+)"', s) or re.search(r"\]\((https?://[^)\s]+)\)", s); return m.group(1) if m else ""
for f, label, hint in [("speedyapply_2027-AI-College-Jobs/README.md", "SpeedyApply AI Intern", "intern"),
                       ("speedyapply_2027-AI-College-Jobs/NEW_GRAD_USA.md", "SpeedyApply AI New Grad", "new grad"),
                       ("speedyapply_2027-SWE-College-Jobs/README.md", "SpeedyApply SWE Intern", "intern"),
                       ("speedyapply_2027-SWE-College-Jobs/NEW_GRAD_USA.md", "SpeedyApply SWE New Grad", "new grad")]:
    last_co = ""
    for c in md_rows(f"{SRC}/{f}"):
        if len(c) < 6: continue
        co = strip_md(c[0]) or last_co; last_co = co if co and co != "↳" else last_co
        if co == "↳": co = last_co
        add(source=label, company=co, title=strip_md(c[1]), loc=strip_md(c[2]), salary=strip_md(c[3]), url=first_url(c[4]), posted=age_to_date(strip_md(c[5])), level_hint=hint)
last_co = ""
for c in md_rows(f"{SRC}/zapplyjobs_Internships-2027/README.md"):
    if len(c) < 6: continue
    co = strip_md(c[0]); co = last_co if co in ("↳", "") else co; last_co = co
    flag = "offers" if "Sponsor" in c[4] else ""
    add(source="Zapply Internships 2027", company=co, title=strip_md(c[1]), loc=strip_md(c[2]), posted=age_to_date(strip_md(c[3])), spons_flag=flag, url=first_url(c[5]), level_hint="intern")
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
def mon_day(s):
    m = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2})", s or "")
    if not m or m.group(1) not in MON: return ""
    y = NOW.year if MON[m.group(1)] <= NOW.month else NOW.year - 1
    return f"{y}-{MON[m.group(1)]:02d}-{int(m.group(2)):02d}"
for f, label, hint in [("jobright-ai_2026-Data-Analysis-New-Grad", "Jobright Data Analysis New Grad", "new grad"),
                       ("jobright-ai_2026-Data-Analysis-Internship", "Jobright Data Analysis Intern", "intern"),
                       ("jobright-ai_2026-Business-Analyst-New-Grad", "Jobright Business Analyst New Grad", "new grad"),
                       ("jobright-ai_2026-Business-Analyst-Internship", "Jobright Business Analyst Intern", "intern")]:
    if not os.path.exists(f"{SRC}/{f}/README.md"): continue
    last_co = ""
    for c in md_rows(f"{SRC}/{f}/README.md"):
        if len(c) < 5 or c[0].startswith("---") or c[0].startswith("-----"): continue
        co = strip_md(c[0])
        if co in ("↳", ""): co = last_co
        last_co = co
        add(source=label, company=co, title=strip_md(c[1]), loc=strip_md(c[2]) + ("; Remote" if "Remote" in c[3] else ""), url=first_url(c[1]),
            posted=mon_day(strip_md(c[4])), level_hint=hint, force_track="Data Analyst" if re.search(r"analy|intelligence|\bbi\b|insight|reporting", c[1], re.I) else "")

# 3. LinkedIn (Chrome)
lj = {}
for fn in ("jsa_linkedin_jobs.json", "jsa_linkedin_da.json"):
    if os.path.exists(f"{RAW}/{fn}"): lj.update(json.load(open(f"{RAW}/{fn}")))
for jid, r in lj.items():
    p = r.split(" ~ "); q = p[0]; rest = " ~ ".join(p[4:])
    con = re.search(r"(\d+) connections? works?", rest); alu = re.search(r"(\d+) school alumni", rest)
    sal = re.search(r"\$[\d,.Kk]+(?:/hr|/yr)?(?: - \$[\d,.Kk]+(?:/hr|/yr)?)?", rest)
    add(source="LinkedIn", company=p[2] if len(p) > 2 else "", title=p[1] if len(p) > 1 else "", loc=p[3] if len(p) > 3 else "",
        url=f"https://www.linkedin.com/jobs/view/{jid}/", posted=age_to_date(rest, CHROME), salary=sal.group(0) if sal else "",
        li_conn=int(con.group(1)) if con else 0, li_alumni=int(alu.group(1)) if alu else 0, level_hint="intern" if "intern" in q else "new grad",
        force_track="Data Analyst" if q.startswith("DA") and re.search(r"analy|intelligence|\bbi\b|insight|reporting", p[1] if len(p) > 1 else "", re.I) else "")

# 4. Company ATS boards (Chrome)
_combo = {"ats": [], "hn": []}
for fn in ("jsa_ats_and_hn_1023.json", "jsa_ats_and_hn.json"):  # newest board snapshot wins
    if os.path.exists(f"{RAW}/{fn}"): _combo = json.load(open(f"{RAW}/{fn}")); break
if _combo["ats"]:
    for x in _combo["ats"]:
        add(source={"greenhouse": "Greenhouse boards", "lever": "Lever boards", "ashby": "Ashby boards"}[x["s"]],
            company=x.get("cn") or title_case_token(x["c"]), title=x["t"], loc=x.get("l", ""), url=x.get("u", ""), posted=iso(x.get("d")),
            salary=x.get("p", ""), level_hint=x.get("e", ""))

# 5. Built In (Chrome)
if os.path.exists(f"{RAW}/jsa_builtin.json"):
    for x in json.load(open(f"{RAW}/jsa_builtin.json")):
        parts = x["x"].split(" ~ ")
        loc = next((p for p in parts if re.search(r", [A-Z]{2}, USA|USA$|United States|Remote", p)), "")
        sal = next((p for p in parts if re.search(r"\d+K?-\d+K? (Hourly|Annually)", p)), "")
        posted = next((p for p in parts if re.search(r"(Ago|Hours|Days|Week|Month)", p, re.I)), "")
        add(source="Built In", company=x["c"], title=x["t"], loc=loc, url=x["u"], salary=sal, posted=age_to_date(posted.lower(), CHROME), level_hint=x["q"])

if os.path.exists(f"{RAW}/builtin_da_1023.txt"):
    for line in open(f"{RAW}/builtin_da_1023.txt"):
        p = line.rstrip("\n").split("|")
        if len(p) < 7: continue
        slug = re.sub(r"[^a-z0-9]+", "-", p[1].lower()).strip("-")
        posted = (CHROME - dt.timedelta(days=1)).date().isoformat() if p[5] == "Yesterday" else CHROME.date().isoformat() if re.search(r"(Minute|Hour)", p[5]) else age_to_date(p[5].lower().replace("one ", "1 "), CHROME)
        add(source="Built In", company=p[2], title=p[1], loc=p[3] or "United States", url=f"https://builtin.com/job/{slug}/{p[0]}", salary=p[4], posted=posted,
            level_hint=p[6].lower(), force_track="Data Analyst")

# 6. Handshake, sponsorship-open filter (Chrome)
if os.path.exists(f"{RAW}/jsa_handshake_visa.json"):
    for jid, r in json.load(open(f"{RAW}/jsa_handshake_visa.json")).items():
        p = r.split(" ~ ")
        if len(p) < 3: continue
        meta = p[3] if len(p) > 3 else ""
        loc = next((x for x in p[4:] if re.search(r"(, [A-Z]{2}\b|Remote|United States)", x)), "")
        add(source="Handshake (visa-open filter)", company=p[1], title=p[2], loc=loc, url=f"https://app.joinhandshake.com/jobs/{jid}",
            salary=(meta.split("·")[0].strip() if "$" in meta else ""), spons_flag="offers", level_hint=meta, posted=age_to_date(p[-1], CHROME))

# 7. Hacker News Who's Hiring (Chrome)
if _combo["hn"]:
    for x in _combo["hn"]:
        first = x["first"]; parts = [s.strip() for s in first.split("|")]
        co = parts[0][:60] if parts else ""
        title = next((s for s in parts[1:] if track_of(s) or INTERN.search(s)), parts[1] if len(parts) > 1 else "See post")
        loc = next((s for s in parts[1:] if re.search(r"(remote|onsite|on-site|hybrid|, [A-Z]{2}\b|NYC|SF|San Francisco|New York|Chicago)", s, re.I)), "")
        txt = x["txt"]
        flag = "no" if re.search(r"(no visa|not sponsor|cannot sponsor|unable to sponsor|no sponsorship|without sponsorship|us citizens? only|must be a us citizen)", txt, re.I) else ("offers" if re.search(r"(visa sponsor|sponsor visas?|h-?1b|will sponsor|sponsorship available|sponsorship: yes|visa: yes)", txt, re.I) else "")
        add(source="Hacker News Who's Hiring", company=co, title=title[:120], loc=loc[:80], url=x["u"], posted=iso(x.get("d")), spons_flag=flag,
            level_hint=("intern " if re.search(r"\bintern", txt, re.I) else "") + ("new grad" if re.search(r"(new grad|junior|entry)", txt, re.I) else ""))

print("raw rows by source:", dict(src_stats))

# ------------------------------------------------------------------ filter, dedupe, score
def key_of(r):
    return (norm(r["company"]), re.sub(r"[^a-z0-9]+", " ", r["title"].lower()).strip())

jobs = {}
for r in rows:
    tr = track_of(r["title"])
    # rows from Data-Analyst searches/lists: analyst-type titles join the DA track (never data scientists, quants or engineers)
    if (r.get("force_track") and tr in (None, "Data Science / Analytics", "Product Manager")
            and re.search(r"analy|intelligence|\bbi\b|insight|reporting|visuali", r["title"], re.I)
            and not re.search(r"scien|quant|engineer|researcher|product manager", r["title"], re.I)): tr = r["force_track"]
    if not tr and r["source"] == "Hacker News Who's Hiring":
        tr = track_of(r.get("level_hint", "") + " " + r["title"]) or None
    if not tr: continue
    if SENIOR.search(r["title"]) and not INTERN.search(r["title"]): continue
    if re.search(r"\b(phd|ph\.d|doctoral)\b", r["title"], re.I): continue
    if not is_us(r["loc"]): continue
    # Only Summer 2027 internships (and full-time from 2027/2028): drop anything tied to 2026 (user, 2026-10-25)
    _t26 = r["title"] + " " + r.get("terms", "")
    if re.search(r"\b2026\b", _t26) and not re.search(r"2027|2028", _t26): continue
    if re.search(r"\b(ii|iii|iv|2|3|4)\s*$|\b(engineer|scientist|analyst|manager) (ii|iii|iv)\b|\b(experienced|mid-level|midlevel)\b", r["title"], re.I) and not INTERN.search(r["title"]): continue
    k = key_of(r)
    j = jobs.get(k)
    if not j:
        j = jobs[k] = dict(r); j["sources"] = [r["source"]]; j["urls"] = {r["source"]: r.get("url", "")}; j["track"] = tr
    else:
        if r["source"] not in j["sources"]: j["sources"].append(r["source"]); j["urls"][r["source"]] = r.get("url", "")
        for f in ("loc", "posted", "salary"):
            if not j.get(f) and r.get(f): j[f] = r[f]
        if r.get("spons_flag") in ("no", "citizen"): j["spons_flag"] = r["spons_flag"]
        elif r.get("spons_flag") == "offers" and j.get("spons_flag") not in ("no", "citizen"): j["spons_flag"] = "offers"
        j["li_conn"] = max(j.get("li_conn", 0), r.get("li_conn", 0)); j["li_alumni"] = max(j.get("li_alumni", 0), r.get("li_alumni", 0))
        if r["posted"] and (not j["posted"] or r["posted"] > j["posted"]): j["posted"] = r["posted"]
        j["level_hint"] = (j.get("level_hint", "") + " " + r.get("level_hint", "")).strip()

TRACK_W = {"AI Product Manager": 25, "AI Agentic Engineer": 25, "Data Engineer": 25, "Data Analyst": 25, "Product Manager": 25, "Data Science / Analytics": 19}
SKILL_HIT = re.compile(r"\b(python|sql|analytics|data|ai|llm|agent|product|machine learning|economics|finance|fintech|evaluation|insights)\b", re.I)

out = []
for j in jobs.values():
    lvl = level_of(j["title"], j.get("level_hint", ""))
    h = h1b_for(j["company"])
    people = conn_for(j["company"]); alum = alum_link_for(j["company"])
    # --- Role fit (0-25)
    s_role = TRACK_W[j["track"]]
    if re.search(r"\b(software engineer|swe|backend|frontend|full.?stack)\b", j["title"], re.I) and j["track"] != "AI Agentic Engineer": s_role -= 6
    if re.search(r"\b(hardware|firmware|embedded|mechanical|electrical|chip|silicon|rf)\b", j["title"], re.I): s_role -= 12
    if re.search(r"\b(software (development )?engineer|sde|swe)\b", j["title"], re.I) and not re.search(r"\b(data|ai|ml|machine learning|llm|agent|analytics)\b", j["title"], re.I): s_role -= 8
    if re.search(r"\bmba\b", j["title"], re.I): s_role -= 10
    if re.search(r"\bresearch (intern|scientist)\b", j["title"], re.I): s_role -= 6
    s_role = max(0, s_role)
    # --- Timing fit (0-15): CPT summer 2027 internship or Dec-2027 full-time
    if lvl == "Internship":
        s_time = 15 if re.search(r"(2027|summer)", j["title"] + " " + j.get("terms", "") + " " + j.get("level_hint", ""), re.I) or "Summer 2027" in " ".join(j["sources"]) else 11
        if re.search(r"(fall 2026|winter 2026|spring 2027|fall 2027|co-?op)", j["title"] + " " + j.get("terms", ""), re.I): s_time = 6
    elif lvl == "New Grad / Entry":
        # He graduates Dec 2027 -> full-time start ~Jan 2028 (OPT/STEM OPT, then H-1B)
        s_time = 15 if re.search(r"(2028|winter 2027|december 2027|january 2028)", j["title"], re.I) else 8 if re.search(r"(2027|new grad|new college)", j["title"], re.I) else 9
    else:
        s_time = 5
    # --- Sponsorship (0-30): posting signal + H-1B track record
    flag = j.get("spons_flag", "")
    if flag in ("no", "citizen"):
        s_sp = 0
    else:
        vol = h["fy25"] or (h["total"] / 15 if h["total"] else 0)
        s_sp = min(22, round(22 * math.log10(1 + vol) / math.log10(1 + 2000), 1)) if vol else 0
        if flag == "offers": s_sp = max(s_sp, 14) + 8
        s_sp = min(30, s_sp)
    # --- Green-card proxy (0-10): long, steady H-1B history (PERM data added later for top companies)
    s_gc = 0; pm = perm_for(j["company"])
    if flag not in ("no", "citizen"):
        if pm and pm["gc_sponsor"] == "Yes":
            s_gc = min(10, round(4 + 6 * min(1, math.log10(1 + pm["perm"]) / 2.5), 1))
        elif pm and pm["gc_sponsor"] == "No":
            s_gc = 1  # Ellis shows no PERM for the matched legal entity: verify before relying on it
        elif h["total"]:
            yrs = 2026 - (h["first"] or 2026)
            s_gc = min(7, round(3 * min(1, yrs / 12) + 4 * min(1, math.log10(1 + h["total"]) / 3.5), 1))
    # --- Referral (0-15)
    if people: s_ref = 15; ref_type = "1st-degree connection works here"
    elif j.get("li_conn"): s_ref = 12; ref_type = f"{j['li_conn']} LinkedIn connection(s) work here"
    elif alum: s_ref = 8; ref_type = "Warm intro path"
    elif j.get("li_alumni"): s_ref = min(7, 2 + round(math.log2(1 + j["li_alumni"]))); ref_type = f"{j['li_alumni']} school alumni work here"
    else: s_ref = 0; ref_type = "Cold"
    # --- Freshness (0-5)
    s_fresh = 0
    if j.get("posted"):
        try:
            age = (NOW.date() - dt.date.fromisoformat(j["posted"][:10])).days
            s_fresh = 5 if age <= 7 else 4 if age <= 14 else 3 if age <= 30 else 1 if age <= 90 else 0
        except Exception: pass
    total = round(s_role + s_time + s_sp + s_gc + s_ref + s_fresh, 1)
    sponsor_label = ("Blocked: no sponsorship" if flag == "no" else "Blocked: citizenship required" if flag == "citizen" else
                     "Posting offers sponsorship" if flag == "offers" else
                     h1b_match.sponsor_label(h))
    notes = []
    if re.search(r"\bmba\b", j["title"], re.I): notes.append("MBA-only role: check eligibility (you are M.S.)")
    if lvl == "Internship" and JOB_NOTE: notes.append(JOB_NOTE)
    if lvl == "New Grad / Entry": notes.append("Full-time: you graduate Dec 2027; confirm start date fits Jan 2028 (OPT/STEM OPT -> H-1B)")
    if flag in ("no", "citizen"): notes.append("Posting says no sponsorship / citizenship required")
    tier = "Blocked" if flag in ("no", "citizen") else ("A" if total >= 70 else "B" if total >= 55 else "C" if total >= 40 else "D")
    primary_url = next((u for s, u in j["urls"].items() if u and s not in ("LinkedIn",)), "") or next(iter(j["urls"].values()), "")
    out.append({
        "id": f"J{len(out)+1:05d}", "company": j["company"], "title": j["title"], "track": j["track"], "level": lvl,
        "location": j.get("loc", "")[:120], "remote": bool(re.search(r"remote", j.get("loc", ""), re.I)),
        "posted": j.get("posted", ""), "salary": j.get("salary", ""), "sources": j["sources"], "n_sources": len(j["sources"]),
        "url": primary_url, "urls": j["urls"],
        "sponsorship": sponsor_label, "h1b_fy25": h["fy25"], "h1b_total": h["total"], "h1b_since": h["first"], "h1b_match": h["match"], "h1b_names": h["names"],
        "gc_perm": (pm or {}).get("perm"), "gc_sponsor": (pm or {}).get("gc_sponsor", ""), "gc_months": (pm or {}).get("perm_months", ""), "gc_commit": (pm or {}).get("gc_commit", ""), "gc_source": "Ellis PERM" if pm else ("H-1B history proxy" if h["total"] else ""),
        "referral": ref_type, "contacts": [f"{n} — {r}" for n, r in people], "warm_path": alum, "li_connections": j.get("li_conn", 0), "li_alumni": j.get("li_alumni", 0),
        "score": total, "tier": tier, "notes": notes,
        "s_role": s_role, "s_timing": s_time, "s_sponsor": s_sp, "s_greencard": s_gc, "s_referral": s_ref, "s_fresh": s_fresh,
    })

out.sort(key=lambda x: -x["score"])
for i, o in enumerate(out): o["rank"] = i + 1
json.dump(out, open(f"{OUT}/jobs.json", "w"), ensure_ascii=False)

# companies rollup
comp = collections.defaultdict(lambda: {"jobs": 0, "best": 0, "tracks": collections.Counter(), "levels": collections.Counter()})
for o in out:
    c = comp[o["company"]]; c["jobs"] += 1; c["best"] = max(c["best"], o["score"]); c["tracks"][o["track"]] += 1; c["levels"][o["level"]] += 1
    c.update({k: o[k] for k in ("sponsorship", "h1b_fy25", "h1b_total", "h1b_since", "referral", "contacts", "warm_path")} if c["jobs"] == 1 else {})
companies = [{"company": k, **{kk: (dict(vv) if isinstance(vv, collections.Counter) else vv) for kk, vv in v.items()}} for k, v in comp.items()]
companies.sort(key=lambda x: -x["best"])
json.dump(companies, open(f"{OUT}/companies.json", "w"), ensure_ascii=False)
json.dump({"raw": dict(src_stats), "after_filter": dict(collections.Counter(s for o in out for s in o["sources"]))}, open(f"{OUT}/sources.json", "w"))
print("jobs:", len(out), "companies:", len(companies))
print("tiers:", collections.Counter(o["tier"] for o in out))
print("levels:", collections.Counter(o["level"] for o in out))
print("tracks:", collections.Counter(o["track"] for o in out))
print("sponsorship:", collections.Counter(o["sponsorship"] for o in out))
print("referral:", collections.Counter(o["referral"].split(" ")[0] if o["referral"][0].isdigit() else o["referral"] for o in out).most_common(8))
for o in out[:15]: print(o["score"], o["tier"], o["company"], "|", o["title"], "|", o["level"], "|", o["sponsorship"], "|", o["referral"], "|", ",".join(o["sources"]))
