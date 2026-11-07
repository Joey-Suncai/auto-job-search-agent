"""Append-only daily update for Joey's Job Hunt dashboard.
Clones the curated GitHub job lists, finds roles NOT already in the dashboard, scores them with the same
rules as the weekly pipeline, and appends them to the existing rows. Existing rows are never changed or removed.
usage: python3 append_new.py <workdir>   (workdir holds prev/dash_jobs_prev.json and raw/perm_ellis.txt)"""
import sys, os, re, json, csv, math, html, shutil, subprocess, collections, datetime as dt
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'config'))
import jsa_profile  # noqa: E402  (JSA-077)
JOB_NOTE = jsa_profile.get('work_auth.job_note')   # e.g. how a summer internship is authorized (CPT)

W = os.path.abspath(sys.argv[1]); SRC = f"{W}/src"; OUT = f"{W}/out"; os.makedirs(OUT, exist_ok=True)
TODAY = dt.date.today(); NOW_Y = TODAY.year
REPOS = ["SimplifyJobs/Summer2027-Internships", "SimplifyJobs/New-Grad-Positions", "vanshb03/Summer2027-Internships", "vanshb03/New-Grad-2027",
         "speedyapply/2027-AI-College-Jobs", "speedyapply/2027-SWE-College-Jobs", "zapplyjobs/Internships-2027",
         "jobright-ai/2026-Data-Analysis-New-Grad", "jobright-ai/2026-Data-Analysis-Internship",
         "jobright-ai/2026-Business-Analyst-New-Grad", "jobright-ai/2026-Business-Analyst-Internship",
         "flexapply/companies-that-sponsor-h1b", "sergyinfo/h1b-open-data"]

# ---------------- 1. clone (data only; nothing from the repos is executed)
failed = []
if "--no-clone" not in sys.argv:
    shutil.rmtree(SRC, ignore_errors=True); os.makedirs(SRC)
    for r in REPOS:
        p = subprocess.run(["git", "clone", "-q", "--depth", "1", f"https://github.com/{r}", f"{SRC}/{r.replace('/', '_')}"], capture_output=True, text=True)
        if p.returncode: failed.append(r)
print("clone failures:", failed or "none")
def exists(p): return os.path.exists(f"{SRC}/{p}")

# ---------------- helpers (same rules as build_jobs.py)
SUFFIX = r"\b(inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|limited|plc|lp|llp|holdings?|group|the|usa|us|america|na|n\.a|services|technologies|technology|labs?|global|international)\b"
def norm(c):
    c = (c or "").lower().replace("&", " and "); c = re.sub(r"\.com\b", "", c); c = re.sub(r"[^a-z0-9 ]+", " ", c); c = re.sub(SUFFIX, " ", c)
    return re.sub(r"\s+", " ", c).strip()
TRACKS = [
    ("AI Product Manager", r"(?=.*(?:\b(?:ai|artificial intelligence|machine learning|ml|llm|genai|gen ai|generative|agents?|agentic|conversational)\b|\ba\.i\.(?!\w)))(?=.*\b(?:product manag\w*|product owner|apm|associate product|product lead|product intern|product strategy)\b)"),   # Joey 2026-11-03: AI PM is its own track, checked before AI Agentic Eng
    ("AI Agentic Engineer", r"\b(ai|a\.i\.|artificial intelligence|machine learning|ml|llm|genai|gen ai|generative|agent|agentic|nlp|deep learning|applied scien|research engineer|ai/ml|computer vision|mlops)\b"),
    ("Data Engineer", r"\b(data engineer|data engineering|analytics engineer|data platform|data infrastructure|etl|data pipeline|big data|data warehouse|database|data ops|dataops|data architect)\b"),
    ("Data Analyst", r"\b(data analysts?|data analytics|business analysts?|business analytics|bi analyst|bi developer|power bi|business intelligence|analytics analyst|analytics intern|reporting analyst|insights analyst|marketing analyst|operations analyst|business operations|data visuali[sz]ation|data & analytics|data and analytics|analyst, data|analyst, business intelligence|analyst, reporting|analyst, client reporting|financial data analyst|master data analyst|data integrity|growth analyst|strategy analyst)\b"),
    ("Product Manager", r"\b(product manager|product management|apm|associate product|product analyst|product owner|product operations|product strategy|technical program|program manager|product designer|product intern|product)\b"),
    ("Data Science / Analytics", r"\b(data scien|data analy|analytics|business intelligence|bi analyst|business analyst|quantitative|quant|insights|statistic|decision scien|operations research|economist|research analyst|data intern|data)\b"),
]
def track_of(t):
    t = t.lower()
    for n, rx in TRACKS:
        if re.search(rx, t): return n
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|director|head of|vp|vice president|manager ii|manager iii|architect|phd|ph\.d|postdoc|mba)\b", re.I)
INTERN = re.compile(r"\b(intern|internship|co-?op|summer associate|summer analyst|summer 2027|2027 summer)\b", re.I)
NEWGRAD = re.compile(r"\b(new grad|new college grad|graduate|early career|entry|university|campus|junior|associate|analyst i\b|engineer i\b|level 1|2027 start|class of 2027|rotational|apm)\b", re.I)
def level_of(t, hint=""):
    s = f"{t} {hint}"
    return "Internship" if INTERN.search(s) else "New Grad / Entry" if NEWGRAD.search(s) else "Early Career (unlabeled)"
BAD = r"\b(canada|toronto|vancouver|montreal|london|uk|united kingdom|india|bangalore|bengaluru|hyderabad|singapore|germany|berlin|munich|paris|france|ireland|dublin|amsterdam|netherlands|spain|madrid|barcelona|poland|warsaw|israel|tel aviv|japan|tokyo|china|beijing|shanghai|hong kong|australia|sydney|melbourne|brazil|mexico|switzerland|zurich|sweden|stockholm|korea|seoul|taiwan|philippines|vietnam|romania|portugal|lisbon|italy|milan|czech|prague|emea|apac|latam|ontario|uae|dubai|south africa|argentina|colombia|chile|denmark|norway|finland|belgium|austria|hungary|ukraine|serbia|greece|turkey|egypt|nigeria|kenya|pakistan|indonesia|malaysia|thailand|new zealand)\b"
def is_us(loc):
    l = (loc or "").lower()
    return not (l and re.search(BAD, l) and not re.search(r"\b(united states|usa|us\b|remote - us|remote, us|new york|san francisco|chicago|seattle|boston|austin)\b", l))
def ts_to_date(ts):
    try: return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date().isoformat()
    except Exception: return ""
def age_to_date(s):
    m = re.search(r"(\d+)\s*(minute|hour|day|week|month|mo|d|h|w|m)\b", s or "")
    if not m: return ""
    d = {"minute": 0, "m": 0, "hour": 0, "h": 0, "day": 1, "d": 1, "week": 7, "w": 7, "month": 30, "mo": 30}[m.group(2)] * int(m.group(1))
    return (TODAY - dt.timedelta(days=d)).isoformat()
MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
def mon_day(s):
    m = re.match(r"([A-Z][a-z]{2})\s+(\d{1,2})", s or "")
    if not m or m.group(1) not in MON: return ""
    y = NOW_Y if MON[m.group(1)] <= TODAY.month else NOW_Y - 1
    return f"{y}-{MON[m.group(1)]:02d}-{int(m.group(2)):02d}"

# ---------------- company data: H-1B, PERM, contacts
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import h1b_match  # noqa: E402  (one matcher for every writer, JSA-098)
H1B = h1b_match.H1B(h1b_match.records_from(SRC))
def h1b_for(c):
    return H1B.lookup(c)
PERM = {}
if os.path.exists(f"{W}/raw/perm_ellis.txt"):
    for line in open(f"{W}/raw/perm_ellis.txt"):
        p = line.rstrip("\n").split("|")
        if len(p) >= 7 and p[1] == "1": PERM[norm(p[0])] = {"perm": int(p[3] or 0), "gc_sponsor": p[2], "perm_months": p[5].replace("m", " months")}
def perm_for(c):
    k = norm(c)
    if k in PERM: return PERM[k]
    for pk, v in PERM.items():
        if pk and (k.startswith(pk + " ") or pk.startswith(k + " ")) and len(min(k, pk, key=len)) > 3: return v
# referral info per company comes from the dashboard's own rows (contacts, warm paths, LinkedIn counts)
prev = json.load(open(f"{W}/prev/dash_jobs_prev.json"))
REF = {}
for j in prev:
    c = REF.setdefault(norm(j["company"]), {"contacts": "", "warm_path": "", "detail": ""})
    if j.get("contacts") and not c["contacts"]: c["contacts"] = j["contacts"]; c["detail"] = j["referral_detail"]
    if j.get("warm_path") and not c["warm_path"]: c["warm_path"] = j["warm_path"]

# ---------------- collect GitHub-list rows
rows = []; stats = collections.Counter()
def add(**r):
    r.setdefault("loc", ""); r.setdefault("posted", ""); r.setdefault("salary", ""); r.setdefault("spons_flag", ""); r.setdefault("terms", ""); r.setdefault("force_track", "")
    r["company"] = (r.get("company") or "").strip(); r["title"] = html.unescape((r.get("title") or "").strip())
    if r["company"] and r["title"]: rows.append(r); stats[r["source"]] += 1
for f, label in [("SimplifyJobs_Summer2027-Internships", "Simplify Summer 2027"), ("SimplifyJobs_New-Grad-Positions", "Simplify New Grad"),
                 ("vanshb03_Summer2027-Internships", "vanshb03 Summer 2027"), ("vanshb03_New-Grad-2027", "vanshb03 New Grad 2027")]:
    if not exists(f"{f}/.github/scripts/listings.json"): continue
    for x in json.load(open(f"{SRC}/{f}/.github/scripts/listings.json")):
        if not x.get("active") or not x.get("is_visible", True): continue
        flag = {"Offers Sponsorship": "offers", "Does Not Offer Sponsorship": "no", "U.S. Citizenship is Required": "citizen"}.get(x.get("sponsorship", ""), "")
        add(source=label, company=x.get("company_name"), title=x.get("title"), loc="; ".join(x.get("locations") or []), url=x.get("url"),
            posted=ts_to_date(x.get("date_posted")), spons_flag=flag, level_hint="intern" if "Summer" in label else "new grad",
            terms="; ".join(x.get("terms") or []) if isinstance(x.get("terms"), list) else "")
def md_rows(path):
    for line in open(path, encoding="utf-8"):
        if line.startswith("| ") and not line.startswith(("| Company", "|---", "| -")): yield [c.strip() for c in line.strip().strip("|").split("|")]
def strip_md(s):
    s = re.sub(r"<[^>]+>", "", s); s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s); return s.replace("**", "").strip()
def first_url(s):
    m = re.search(r'href="([^"]+)"', s) or re.search(r"\]\((https?://[^)\s]+)\)", s); return m.group(1) if m else ""
for f, label, hint in [("speedyapply_2027-AI-College-Jobs/README.md", "SpeedyApply AI Intern", "intern"), ("speedyapply_2027-AI-College-Jobs/NEW_GRAD_USA.md", "SpeedyApply AI New Grad", "new grad"),
                       ("speedyapply_2027-SWE-College-Jobs/README.md", "SpeedyApply SWE Intern", "intern"), ("speedyapply_2027-SWE-College-Jobs/NEW_GRAD_USA.md", "SpeedyApply SWE New Grad", "new grad")]:
    if not exists(f): continue
    last = ""
    for c in md_rows(f"{SRC}/{f}"):
        if len(c) < 6: continue
        co = strip_md(c[0]) or last; last = co if co and co != "↳" else last
        if co == "↳": co = last
        add(source=label, company=co, title=strip_md(c[1]), loc=strip_md(c[2]), salary=strip_md(c[3]), url=first_url(c[4]), posted=age_to_date(strip_md(c[5])), level_hint=hint)
if exists("zapplyjobs_Internships-2027/README.md"):
    last = ""
    for c in md_rows(f"{SRC}/zapplyjobs_Internships-2027/README.md"):
        if len(c) < 6: continue
        co = strip_md(c[0]); co = last if co in ("↳", "") else co; last = co
        add(source="Zapply Internships 2027", company=co, title=strip_md(c[1]), loc=strip_md(c[2]), posted=age_to_date(strip_md(c[3])),
            spons_flag="offers" if "Sponsor" in c[4] else "", url=first_url(c[5]), level_hint="intern")
for f, label, hint in [("jobright-ai_2026-Data-Analysis-New-Grad", "Jobright Data Analysis New Grad", "new grad"), ("jobright-ai_2026-Data-Analysis-Internship", "Jobright Data Analysis Intern", "intern"),
                       ("jobright-ai_2026-Business-Analyst-New-Grad", "Jobright Business Analyst New Grad", "new grad"), ("jobright-ai_2026-Business-Analyst-Internship", "Jobright Business Analyst Intern", "intern")]:
    if not exists(f"{f}/README.md"): continue
    last = ""
    for c in md_rows(f"{SRC}/{f}/README.md"):
        if len(c) < 5 or c[0].startswith("---"): continue
        co = strip_md(c[0]); co = last if co in ("↳", "") else co; last = co
        add(source=label, company=co, title=strip_md(c[1]), loc=strip_md(c[2]) + ("; Remote" if "Remote" in c[3] else ""), url=first_url(c[1]),
            posted=mon_day(strip_md(c[4])), level_hint=hint, force_track="Data Analyst" if re.search(r"analy|intelligence|\bbi\b|insight|reporting", c[1], re.I) else "")
print("raw rows:", dict(stats))

# ---------------- filter + dedupe
jobs = {}
for r in rows:
    tr = track_of(r["title"])
    if (r["force_track"] and tr in (None, "Data Science / Analytics", "Product Manager") and re.search(r"analy|intelligence|\bbi\b|insight|reporting|visuali", r["title"], re.I)
            and not re.search(r"scien|quant|engineer|researcher|product manager", r["title"], re.I)): tr = r["force_track"]
    if not tr or (SENIOR.search(r["title"]) and not INTERN.search(r["title"])) or re.search(r"\b(phd|ph\.d|doctoral)\b", r["title"], re.I) or not is_us(r["loc"]): continue
    t26 = r["title"] + " " + r["terms"]
    if re.search(r"\b2026\b", t26) and not re.search(r"2027|2028", t26): continue
    if re.search(r"\b(ii|iii|iv|2|3|4)\s*$|\b(engineer|scientist|analyst|manager) (ii|iii|iv)\b|\b(experienced|mid-level|midlevel)\b", r["title"], re.I) and not INTERN.search(r["title"]): continue
    k = (norm(r["company"]), re.sub(r"[^a-z0-9]+", " ", r["title"].lower()).strip())
    j = jobs.get(k)
    if not j:
        j = jobs[k] = dict(r); j["sources"] = [r["source"]]; j["urls"] = {r["source"]: r.get("url", "")}; j["track"] = tr
    else:
        if r["source"] not in j["sources"]: j["sources"].append(r["source"]); j["urls"][r["source"]] = r.get("url", "")
        for f in ("loc", "posted", "salary"):
            if not j.get(f) and r.get(f): j[f] = r[f]
        if r["spons_flag"] in ("no", "citizen"): j["spons_flag"] = r["spons_flag"]
        elif r["spons_flag"] == "offers" and j["spons_flag"] not in ("no", "citizen"): j["spons_flag"] = "offers"
        if r["posted"] and (not j["posted"] or r["posted"] > j["posted"]): j["posted"] = r["posted"]
        j["level_hint"] = (j.get("level_hint", "") + " " + r.get("level_hint", "")).strip()

# ---------------- keep only roles not already in the dashboard
dkey = lambda title, company: re.sub(r"[^a-z0-9]+", " ", title.lower()).strip() + "|" + re.sub(r"[^a-z0-9]+", "", company.lower())[:6]
have = {dkey(j["title"], j["company"]) for j in prev}
fresh = [j for j in jobs.values() if dkey(j["title"], j["company"]) not in have]

# ---------------- score (same weights as build_jobs.py)
TRACK_W = {"AI Product Manager": 25, "AI Agentic Engineer": 25, "Data Engineer": 25, "Data Analyst": 25, "Product Manager": 25, "Data Science / Analytics": 19}
TRACK_LBL = {"AI Product Manager": "AI Product Manager", "AI Agentic Engineer": "AI Agentic Eng", "Data Engineer": "Data Engineer", "Data Analyst": "Data Analyst", "Product Manager": "Product Manager", "Data Science / Analytics": "Data Sci / Analytics"}
LVL_LBL = {"Internship": "Internship", "New Grad / Entry": "New grad", "Early Career (unlabeled)": "Early career"}
nid = max([int(j["id"][1:]) for j in prev if re.match(r"J\d+$", j["id"])] or [0]) + 1   # empty store on a first run (JSA-079)
added = []
for j in fresh:
    t = j["title"]; lvl = level_of(t, j.get("level_hint", "")); h = h1b_for(j["company"]); pm = perm_for(j["company"]); ref = REF.get(norm(j["company"]), {})
    s_role = TRACK_W[j["track"]]
    if re.search(r"\b(software engineer|swe|backend|frontend|full.?stack)\b", t, re.I) and j["track"] != "AI Agentic Engineer": s_role -= 6
    if re.search(r"\b(hardware|firmware|embedded|mechanical|electrical|chip|silicon|rf)\b", t, re.I): s_role -= 12
    if re.search(r"\b(software (development )?engineer|sde|swe)\b", t, re.I) and not re.search(r"\b(data|ai|ml|machine learning|llm|agent|analytics)\b", t, re.I): s_role -= 8
    if re.search(r"\bmba\b", t, re.I): s_role -= 10
    if re.search(r"\bresearch (intern|scientist)\b", t, re.I): s_role -= 6
    s_role = max(0, s_role)
    if lvl == "Internship":
        s_time = 15 if re.search(r"(2027|summer)", t + " " + j["terms"] + " " + j.get("level_hint", ""), re.I) or "Summer 2027" in " ".join(j["sources"]) else 11
        if re.search(r"(fall 2026|winter 2026|spring 2027|fall 2027|co-?op)", t + " " + j["terms"], re.I): s_time = 6
    elif lvl == "New Grad / Entry":
        s_time = 15 if re.search(r"(2028|winter 2027|december 2027|january 2028)", t, re.I) else 8 if re.search(r"(2027|new grad|new college)", t, re.I) else 9
    else: s_time = 5
    flag = j["spons_flag"]
    if flag in ("no", "citizen"): s_sp = 0
    else:
        vol = h["fy25"] or (h["total"] / 15 if h["total"] else 0)
        s_sp = min(22, round(22 * math.log10(1 + vol) / math.log10(1 + 2000), 1)) if vol else 0
        if flag == "offers": s_sp = max(s_sp, 14) + 8
        s_sp = min(30, s_sp)
    s_gc = 0
    if flag not in ("no", "citizen"):
        if pm and pm["gc_sponsor"] == "Yes": s_gc = min(10, round(4 + 6 * min(1, math.log10(1 + pm["perm"]) / 2.5), 1))
        elif pm and pm["gc_sponsor"] == "No": s_gc = 1
        elif h["total"]: s_gc = min(7, round(3 * min(1, (2026 - (h["first"] or 2026)) / 12) + 4 * min(1, math.log10(1 + h["total"]) / 3.5), 1))
    if ref.get("contacts"): s_ref, rdet, rk = 15, "1st-degree connection works here", "1st-degree contact"
    elif ref.get("warm_path"): s_ref, rdet, rk = 8, "Warm intro path", "Warm intro"
    else: s_ref, rdet, rk = 0, "Cold", "Cold"
    s_fresh = 0
    try:
        age = (TODAY - dt.date.fromisoformat(j["posted"][:10])).days
        s_fresh = 5 if age <= 7 else 4 if age <= 14 else 3 if age <= 30 else 1 if age <= 90 else 0
    except Exception: pass
    total = round(s_role + s_time + s_sp + s_gc + s_ref + s_fresh, 1)
    tier = "Blocked" if flag in ("no", "citizen") else "A" if total >= 70 else "B" if total >= 55 else "C" if total >= 40 else "D"
    if lvl == "Early Career (unlabeled)" and tier not in ("A", "B", "C"): continue
    spons = ("Blocked: no sponsorship" if flag == "no" else "Blocked: citizenship required" if flag == "citizen" else "Posting offers sponsorship" if flag == "offers" else
             h1b_match.sponsor_label(h))
    notes = []
    if re.search(r"\bmba\b", t, re.I): notes.append("MBA-only role: check eligibility (you are M.S.)")
    if lvl == "Internship" and JOB_NOTE: notes.append(JOB_NOTE)
    if lvl == "New Grad / Entry": notes.append("Full-time: you graduate Dec 2027; confirm start date fits Jan 2028 (OPT/STEM OPT -> H-1B)")
    if flag in ("no", "citizen"): notes.append("Posting says no sponsorship / citizenship required")
    loc = j.get("loc", "")[:120]
    added.append({"id": f"J{nid:05d}", "rank": 0, "score": total, "tier": tier, "company": j["company"], "title": t, "track": TRACK_LBL[j["track"]], "level": LVL_LBL[lvl],
        "location": loc or "—", "remote": "Yes" if re.search(r"remote", loc, re.I) else "No", "posted": j["posted"] or "", "salary": j["salary"] or "",
        "sources": "; ".join(j["sources"]), "n_sources": len(j["sources"]), "url": next((u for u in j["urls"].values() if u), ""),
        "sponsorship": spons, "h1b_fy25": h["fy25"] or 0, "h1b_total": h["total"] or 0, "h1b_since": h["first"] or "",
        "gc_sponsor": (pm or {}).get("gc_sponsor", ""), "gc_perm": (pm or {}).get("perm", ""), "gc_months": (pm or {}).get("perm_months", ""),
        "referral": rk, "referral_detail": rdet, "contacts": ref.get("contacts", "") if rk == "1st-degree contact" else "", "warm_path": ref.get("warm_path", ""),
        "li_connections": 0, "li_alumni": 0, "s_role": s_role, "s_timing": s_time, "s_sponsor": s_sp, "s_greencard": s_gc, "s_referral": s_ref, "s_fresh": s_fresh,
        "notes": " | ".join(notes), "added": TODAY.isoformat()})
    nid += 1

# ---------------- merge: old rows untouched (only rank recomputed), new rows appended
allj = prev + added
for i, j in enumerate(sorted(allj, key=lambda x: -x["score"])): j["rank"] = i + 1
json.dump(allj, open(f"{OUT}/dash_jobs.json", "w"), ensure_ascii=False, separators=(",", ":"))
new_ab = sorted([j for j in added if j["tier"] in ("A", "B") and j["level"] == "Internship"], key=lambda j: -j["score"])
summary = {"date": TODAY.isoformat(), "jobs": len(allj), "prev_jobs": len(prev), "new_roles": len(added), "new_ab_internships": len(new_ab), "clone_failures": failed,
           "top_new": [{k: j[k] for k in ("score", "tier", "company", "title", "track", "sponsorship", "referral", "url")} for j in new_ab[:15]]}
json.dump(summary, open(f"{OUT}/refresh_summary.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: summary[k] for k in ("jobs", "prev_jobs", "new_roles", "new_ab_internships", "clone_failures")}))
for j in summary["top_new"]: print(j["score"], j["tier"], j["company"], "|", j["title"][:70], "|", j["sponsorship"], "|", j["referral"])
