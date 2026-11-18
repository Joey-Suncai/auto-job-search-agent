#!/usr/bin/env python3
"""DeepSeek materials pipeline for the candidate's applications (facts: config/profile.json + config/resume_content.py).

  python3 ds_materials.py <app_folder> [--track Data_Analyst|Data_Engineer|Product_Manager|AI_Agentic_Engineer]
                                       [--save-payload]

Input : <app_folder>/jd.md   (full JD text)
        <app_folder>/questions.json  (optional: [{"id","label","limit"}], limit = characters; "unit":"words" allowed)
        <app_folder>/notes.md        (optional: extra facts Joey gave for THIS application, e.g. start window)
Output: content.json, resume docx/pdf, cover.txt + cover letter docx/pdf, keyword_map.md, fit_map.md,
        resume_report.md, open_answers.md, ds_usage.md.   See references/deepseek_materials.md.
Stdlib only for the API; python-docx / numpy / Pillow + soffice + pdftotext for the build (same as the resume scripts).
Exit 0 = verified and built, 1 = failed (ds_failed_response.json, resume_report.md), 3 = pending (time guard / DeepSeek timeout: rerun resumes from ds_step_a.json / ds_step_b.json). Always writes ds_status.json.
"""
import sys, os, re, json, copy, hashlib, shutil, subprocess, tempfile, argparse, datetime, time, zipfile
import urllib.request, urllib.error
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("JSA_ROOT") or os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RS = os.path.join(ROOT, "skills", "resume-updater", "scripts")
sys.path.insert(0, os.path.join(ROOT, "config"))
import jsa_profile  # noqa: E402  (JSA-077)
import paths as _jp  # noqa: E402  (the data home, ADR-0008; fact files JSA-339)
# the user's resume template is data: profile resume_template is relative to the data home, never to this code checkout
# (JSA-375: joined with ROOT it pointed into the read-only release ~/JobAgent/app after the two-repo cut-over)
TEMPLATE = jsa_profile.repo_path("resume_template") or _jp.resume("TEMPLATE.docx")
FILE_PREFIX = jsa_profile.get("name.file_prefix") or "Candidate"
SIGNATURE = jsa_profile.get("name.signature") or jsa_profile.get("name.full")
sys.path.insert(0, RS)
import content as C  # approved role wording (NAME, CONTACT, EDU, LEAD, ROLES)

TRACKS = ["Data_Engineer", "Data_Analyst", "Product_Manager", "AI_Agentic_Engineer"]
HEADLINES = {
    "Data_Engineer": "Data Engineering Internship 2027 · Python · SQL · Cloud-Native Data Pipelines",
    "Product_Manager": "AI Product / Product Analytics Internship 2027 · Evaluation Design · Data-Driven Decisions",
    "AI_Agentic_Engineer": "AI / Agentic Engineering Internship 2027 · LLM Agents · Evaluation · Human-in-the-Loop",
    "Data_Analyst": "Data Analyst / BI Internship 2027 · SQL · Python · R · Excel · Tableau",
}
BANNED_WORDS = ["leverage", "leveraged", "leveraging", "spearhead", "spearheaded", "orchestrate", "orchestrated",
                "synergy", "synergies", "dynamic", "passionate", "results-driven", "cutting-edge", "go-getter",
                "detail-oriented", "team player", "utilize", "utilized", "seamlessly", "robust"]
BANNED_PHRASES = ["i am writing to express", "great fit", "fast-paced", "passionate about", "i am confident that",
                  "i believe i would", "perfect fit"]
VISA_WORDS = [r"\bvisa\b", r"\bsponsor\w*", r"\bF-?1\b", r"\bCPT\b", r"\bOPT\b", r"work authori[sz]ation", r"green card", r"immigration"]
SOLO_WORDS = [r"\bindependently\b", r"\bsolo\b", r"\bby myself\b", r"\bon my own\b", r"\bsingle-handedly\b"]
DS_MODEL = "deepseek-flash"   # DeepSeek-V4.1-Flash; pinned (the old alias deepseek-chat also maps here)
PRICE = dict(hit=0.028, miss=0.28, out=0.42)   # USD per 1M tokens, deepseek-chat legacy list price; verify deepseek-flash pricing
BANK_SECTIONS, ORG_KEY = C.BANK_SECTIONS, C.ORG_KEY   # bullet-bank section codes (config/resume_content.py)

# ----------------------------------------------------------------------------- helpers
def rd(path):
    last = None
    for _ in range(4):
        try:
            return open(path, encoding="utf8").read()
        except OSError as e:
            last = e; time.sleep(2)
    raise last

def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
def unesc(s): return s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
def norm(s): return re.sub(r"\s+", " ", s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")).lower()   # GM posts "Intern,  Data" (2026-10-30)
def slug(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")

# ----------------------------------------------------------------------------- privacy scrub
SCRUB = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[email removed]"),
    (re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)"), "[phone removed]"),
    (re.compile(r"(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/\S*", re.I), "[url removed]"),
    (re.compile(r"\b\d{3,5}\s+[SNEW]\.?\s+\w+\s+(?:Ave|Avenue|St|Street|Rd|Road|Blvd)\b[^|\n]*", re.I), "[address removed]"),
    (re.compile(r"\bJ0\d{4}\b"), "[id]"),
]
DOB_LINE = re.compile(r"(date of birth|\bdob\b|\bborn\b|birthday)", re.I)
def _own_ids():
    """The candidate's own identifiers (profile) that must never reach DeepSeek: e-mail user, phone, street, site handle."""
    out = []
    em = (jsa_profile.get("contact.email") or "").split("@")[0]
    if em: out.append(re.escape(em[:-1] if len(em) > 6 else em))
    ph = re.sub(r"\D", "", jsa_profile.get("contact.phone") or "")
    if len(ph) >= 6: out.append(re.escape(ph[:3]) + r"\W?" + re.escape(ph[3:6]))
    st = ((jsa_profile.get("answers") or {}).get("address") or {}).get("text") or ""
    if st: out.append(re.escape(" ".join(st.split()[:2])))
    ws = (jsa_profile.get("contact.website") or "").rstrip("/").split("/")[-1]
    if ws: out.append(re.escape(ws))
    return out
FORBIDDEN_IN_PAYLOAD = _own_ids() + [r"linkedin\.com/in", r"github\.com/", r"[\w.+-]+@[\w-]+\.[a-z]{2,}", r"\bJ0\d{4}\b"]

def scrub(text):
    out = []
    for ln in text.splitlines():
        if DOB_LINE.search(ln): continue
        for rx, rep in SCRUB: ln = rx.sub(rep, ln)
        out.append(ln)
    return "\n".join(out)

def assert_payload_clean(payload):
    bad = [p for p in FORBIDDEN_IN_PAYLOAD if re.search(p, payload, re.I)]
    if bad: raise SystemExit("REFUSING TO SEND: private pattern in payload: " + ", ".join(bad))

# ----------------------------------------------------------------------------- bank / stories
def parse_bank():
    sec, cur, items, cnt = None, None, [], {}
    for ln in rd(_jp.fact("bullet-bank.md")).splitlines():
        if ln.startswith("## "):
            sec = BANK_SECTIONS.get(ln[3:].strip()); cur = None; continue
        if sec and ln.startswith("- "):
            cnt[sec] = cnt.get(sec, 0) + 1
            cur = dict(id=f"{sec}{cnt[sec]:02d}", sec=sec, text=ln[2:].strip(), used_in="", tags="")
            items.append(cur); continue
        m = re.match(r"\s*\*used in:\s*(.*?)\s*·\s*tags:\s*(.*?)\*\s*$", ln)
        if m and cur: cur["used_in"], cur["tags"] = m.group(1), m.group(2)
    return items

def parse_stories():
    t = rd(_jp.fact("story-bank.md"))
    t = t[:t.index("## Archive")]
    stories, cur = {}, None
    for ln in t.splitlines():
        m = re.match(r"^(#{2,3})\s+(S\d+[a-z]?)\s+—\s+(.*)$", ln)
        if m:
            cur = dict(id=m.group(2), lines=[m.group(3)], confirmed=False); stories[cur["id"]] = cur; continue
        if ln.startswith("## Job Searching Agent"):
            cur = dict(id="S8ctx", lines=["Job Searching Agent: shared facts for S8a-S8e"], confirmed=True); stories["S8ctx"] = cur; continue
        if ln.startswith("## Motivations"):
            cur = dict(id="_mot", lines=[], confirmed=True); stories["_mot"] = cur; continue
        if ln.startswith("## ") or ln.startswith("---"):
            if ln.startswith("## "): cur = None
            continue
        if cur is None or not ln.strip(): continue
        if "Status:**" in ln:
            if "Confirmed" in ln: cur["confirmed"] = True
            continue
        if "Detail on hold" in ln: continue
        cur["lines"].append(ln.strip())
    out = {}
    for sid, s in stories.items():
        if sid == "_mot":
            for ln in s["lines"]:
                m = re.match(r"^- (M\d):\s*(.*)$", ln)
                if m: out[m.group(1)] = "Motivation: " + m.group(2)
        elif s["confirmed"]:
            out[sid] = "\n".join(s["lines"])
    return out

def profile_facts():
    t = rd(_jp.fact("candidate-profile.md"))
    keep = re.compile(r"^(Available for employment|Willing to travel|Relocation / on-site|GPA|Target compensation|"
                      r"Internship housing needed|English proficiency|Education entry|Current location|How did you hear|"
                      r"Previous engineering internship)", re.I)
    rows = []
    for ln in t.splitlines():
        if ln.startswith("|"):
            cells = [c.strip().strip("*") for c in ln.strip().strip("|").split("|")]
            if len(cells) >= 2 and keep.match(cells[0]):
                rows.append(f"{cells[0]}: {re.sub(r'[(][^)]*[)]', '', cells[1]).strip()}")
    return scrub("\n".join(rows)).splitlines()

# ----------------------------------------------------------------------------- DeepSeek
USAGE = dict(calls=0, hit=0, miss=0, out=0, prompt=0)

class Pending(Exception): pass
class Failed(Exception):
    def __init__(self, errors, step="?"):
        super().__init__("; ".join(map(str, errors))); self.errors = list(errors); self.step = step

T0 = time.time()
# Measured: reasoning_effort "low" still burns ~6000 reasoning tokens (40-75 s, often truncated JSON); thinking disabled = ~5 s per step.
# Default: thinking off. DS_EFFORT=low|high turns reasoning back on (slow).
THINK = dict(reasoning_effort=os.environ["DS_EFFORT"]) if os.environ.get("DS_EFFORT") else dict(thinking={"type": "disabled"})
BUDGET = 160          # whole-run guard (s); device shell is capped at 180
CALL_TIMEOUT = 90     # per DeepSeek call (s)
def elapsed(): return time.time() - T0

def ds_call(messages, max_tokens=4500, timeout=CALL_TIMEOUT, step="?"):
    """One call + one retry (same effort, 20% smaller max_tokens) on timeout / HTTP / bad-JSON. Raises Pending or Failed."""
    if not os.environ.get("DEEPSEEK_API_KEY"):
        for p in (os.environ.get("DEEPSEEK_KEY_FILE", ""), "~/deepseek/api_key", "~/mnt/deepseek/api_key"):
            f = os.path.expanduser(p) if p else ""
            if f and os.path.exists(f):
                os.environ["DEEPSEEK_API_KEY"] = rd(f).strip()
                break
        else:
            raise Failed("DeepSeek API key not found (~/deepseek/api_key)")
    err = None
    for attempt in (0, 1):
        to = min(timeout, BUDGET - elapsed() - 4)
        if to < 25: raise Pending(f"step {step}: not enough time left in this run ({BUDGET - elapsed():.0f}s)")
        mt = max_tokens if attempt == 0 else int(max_tokens * 0.8)
        body = json.dumps(dict(model=DS_MODEL, messages=messages, response_format={"type": "json_object"},
                               temperature=0.3, max_tokens=mt, **THINK)).encode()
        req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + os.environ["DEEPSEEK_API_KEY"]})
        try:
            with urllib.request.urlopen(req, timeout=to) as r:
                d = json.loads(r.read().decode())
            u = d.get("usage", {})
            USAGE["calls"] += 1; USAGE["prompt"] += u.get("prompt_tokens", 0); USAGE["out"] += u.get("completion_tokens", 0)
            hit = u.get("prompt_cache_hit_tokens", 0); USAGE["hit"] += hit
            USAGE["miss"] += u.get("prompt_cache_miss_tokens", u.get("prompt_tokens", 0) - hit)
            txt = d["choices"][0]["message"]["content"]
            return json.loads(txt), txt
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}"
            if e.code in (400, 401, 402, 403, 422): raise Failed([f"DeepSeek {err} (not retryable)"], step)
        except (OSError, json.JSONDecodeError, KeyError, IndexError) as e:   # timeout, URLError, truncated JSON ...
            err = type(e).__name__ + (" (timeout)" if "timed out" in str(e) else "")
        time.sleep(2)
    raise Pending(f"step {step}: DeepSeek {err} twice")

def cost():
    return (USAGE["hit"] * PRICE["hit"] + USAGE["miss"] * PRICE["miss"] + USAGE["out"] * PRICE["out"]) / 1e6

# ----------------------------------------------------------------------------- prompt
RULES = """You draft job-application materials for ONE candidate. Reply with a single JSON object only.
HARD RULES (every one is checked by a program; violations are sent back to you):
1. TRUTH ONLY. Use only facts in the supplied bullets, stories, motivations, profile facts and notes. Never invent a fact, number, tool, employer, feeling, quote or motivation. Never claim experience that is not in the stories (a JD tool he has not used is a GAP, list it as a gap, never write it into the resume or letter).
2. RESUME = SELECTION ONLY. You pick and order bullet IDs from the bullet bank and skill-line IDs from the skill pool. You never write resume sentences. Light tweaks only: keep the base track's structure, change at most 1-2 bullets/skill lines beyond reordering. Each experience/project section keeps (base count - 1) to (base count + 1) bullets; the first bullet under each job/project is the one matching the JD's #1 must-have. Keep a 'Languages' skill line. Put 'projects' before 'exp' only if the projects match the JD better.
3. HEADLINE: headline_title = the posting's exact job title (you may drop a location suffix like '- USA'), then 2-4 keywords copied EXACTLY (same words) from the skill lines or bullets you selected, e.g. 'SQL', 'Python', 'machine learning', 'forecasting'; a JD keyword that is not literally in your selected text (e.g. 'A/B testing', 'statistical modeling') is a gap and must NOT go in the headline. Check each keyword against your selected text before answering. The whole headline (title + ' · ' + keywords) must be at most 100 characters.
4. NO visa / sponsorship / work-authorization / immigration words anywhere in resume or letter or answers. If an open question asks about visa, sponsorship, work authorization or demographics, or asks for something the facts do not support, answer exactly "ASK" and put the reason in note.
5. The ECON 491 stock-return project is a TEAM OF 3: write 'team of 3' whenever you use story S6 in the letter or an answer; never write 'independently', 'solo', 'on my own'. The Job Searching Agent: say designed / operate / specified / set, never 'coded'.
6. Never write internal job IDs (like J0xxxx) or requisition numbers that look like tracker IDs. Never write phone, email, address, links, URLs, domain names (anything like x.com / x.io) or the @ sign anywhere in the letter or answers.
7. Every number, percent or count you write in the letter or answers must appear in a story/bullet you list in that paragraph's 'uses' (or in PROFILE/NOTES, list those as 'PROFILE'/'NOTES'; skill-line IDs SKn may also be listed). Do not round or convert numbers.
8. Plain, warm, specific words. Banned: leverage, spearhead, orchestrate, synergy, dynamic, passionate, results-driven, cutting-edge, detail-oriented, team player, utilize, seamlessly, robust, 'I am writing to express', 'great fit', 'fast-paced', 'passionate about', 'I am confident that'. No trait adjectives without a concrete example in the same or next sentence.
COVER LETTER (3-5 paragraphs, body 300-380 words, greeting separate, NO sign-off): (a) opening: start with the concrete company fact or the work he wants to do there (never 'I'm applying for …' / 'I am excited to apply …'), name the role, why this company specifically (one concrete company fact from the JD, tied to a motivation M1-M3), preview of what he brings; (b) the main story = Confirmed story whose tags best match the JD's #1 must-have: situation -> what he did and how -> result with numbers; (c) fit and context: 1-2 more must-haves with brief proof from other stories, answer the question the reader will have (e.g. economics degree for a technical role) once, no apology; logistics only if NOTES give them; (d) close: one line of fit, interest in talking, thanks. Do not summarize the resume; each paragraph adds how/why. Specificity test: another applicant could not send it with only the name changed. Greeting: 'Dear <Company> team,' unless a hiring manager's name is in the JD.
KEYWORD MAP: the JD's skills/tools/methods/verbs, must-haves first in JD order. true_for_him = yes | partly | no. For yes, resume_term = the exact word/phrase (<=4 words) that appears in your selected resume text (skills line or bullet).
FIT MAP: one row per must-have, strongest first: strong | partial | none, with evidence IDs. List real gaps (what the JD wants that the stories do not cover) in gaps.
ANSWERS: one per question in questions, in the first person, within the limit (count characters, or words if unit says so; stay at or below target_max, which is 85% of the limit; the limit is a hard cutoff; when a question has min, the answer has at least that many), built from stories, listing story IDs in uses."""

SCHEMA = """Return JSON with exactly these keys:
{
 "job": {"company": "...", "job_title": "title exactly as posted in the JD", "greeting": "Dear X team,"},
 "base_reason_zh": "one sentence in Chinese: why this base track",
 "resume": {
   "headline_title": "...", "headline_keywords": ["..",".."],
   "skill_lines": ["SK1","SK4",...],               // ordered, IDs from skill_pool
   "section_order": ["exp","projects"],            // or ["projects","exp"]
   "exp": {"HP": ["HP01",...], "FS": ["FS01",...]},        // keys exactly as in base_resume.experience
   "projects": {"JSA": ["JSA01",...], "ML": ["ML01",...]}  // keys exactly as in base_resume.projects
 },
 "keyword_map": [{"term":"","must_have":true,"true_for_him":"yes|partly|no","resume_term":"","evidence":["ID"],"action":"kept|moved up|added|gap"}],
 "fit_map": {"company_fact":"from the JD","rows":[{"must_have":"","evidence":["S6"],"strength":"strong|partial|none"}],"motivation":"M2","gaps":[""]},
 "cover_letter": {"greeting":"Dear ... ,","paragraphs":[{"text":"","uses":["S6","M2"]}]},
 "answers": [{"id":"","text":"","uses":["S2"],"note":""}]
}"""

def base_structure(track):
    role = C.ROLES[track]
    pool, ids = {}, {}
    for t in TRACKS:
        r = C.ROLES[t]
        for lab, txt in list(r["skills"]) + list(r.get("skills_a", [])):
            key = (lab, txt)
            if key not in ids:
                ids[key] = f"SK{len(ids) + 1}"; pool[ids[key]] = dict(label=lab, text=txt, tracks=[])
            pool[ids[key]]["tracks"].append(t)
    base_skills = [ids[(l, t)] for l, t in list(role["skills"]) + list(role.get("skills_a", []))]
    return role, pool, ids, base_skills

_RL = RULES.split("\n")
assert len(_RL) == 14, len(_RL)
_R = lambda *ns: [_RL[1 + n] for n in ns]
RULES_A = "\n".join(_RL[:2] + _R(1, 2, 3, 4) + [_RL[11], _RL[12]]) + "\nYou are doing STEP A of 2: resume selection, keyword map and fit map only. Do not write the letter or answers yet. Be concise: keyword_map at most 14 terms (must-haves first), fit_map at most 7 rows, no commentary. story_summaries are short excerpts for choosing evidence IDs only."
RULES_B = "\n".join(_RL[:2] + _R(1, 4, 5, 6, 7, 8) + [_RL[10], _RL[13]]) + "\nYou are doing STEP B of 2: the cover letter and open answers only. STEP A (resume selection and fit map) is given and fixed; cite its bullet IDs / skill IDs / stories in 'uses' when you refer to them. LENGTH: the letter body must be about 330 words (hard limits 280-390); four paragraphs of roughly 80 words. Count before answering; shorter is safer than longer."
RULES_B += ("\nSENTENCE RULES (every sentence is checked; a failing one is rewritten, and one that still fails blocks the application): "
            "(1) open the letter with the concrete company fact or the work he wants to do there, never 'I'm applying for …', 'I am excited to apply …', 'I am writing to …', '… draws me to …'; "
            "(2) never say what he has not done or lacks ('I have not …', 'I haven't …', 'no experience in …', 'I used X rather than Y'): a gap stays in fit_map only; "
            "(3) the M.S. is current (see PROFILE dates): 'I am pursuing an M.S. …', never 'starts' / 'will start' / 'incoming'; "
            "(4) tie a skill to the M.S. only when PROFILE ties it to the M.S. coursework; "
            "(5) the team-of-3 project: he 'led the code' (not 'led the project / benchmark'); the 70% result: 'part of a workflow that cut … by 70%'.")
SCHEMA_A = """Return JSON with exactly these keys:
{
 "job": {"company": "...", "job_title": "title exactly as posted in the JD", "greeting": "Dear X team,"},
 "base_reason_zh": "one sentence in Chinese: why this base track",
 "resume": {
   "headline_title": "...", "headline_keywords": ["..",".."],
   "skill_lines": ["SK1","SK4",...],               // ordered, IDs from skill_pool
   "section_order": ["exp","projects"],            // or ["projects","exp"]
   "exp": {"HP": ["HP01",...], "FS": ["FS01",...]},        // keys exactly as in base_resume.experience
   "projects": {"JSA": ["JSA01",...], "ML": ["ML01",...]}  // keys exactly as in base_resume.projects
 },
 "keyword_map": [{"term":"","must_have":true,"true_for_him":"yes|partly|no","resume_term":"","evidence":["ID"],"action":"kept|moved up|added|gap"}],
 "fit_map": {"company_fact":"from the JD","rows":[{"must_have":"","evidence":["S6"],"strength":"strong|partial|none"}],"motivation":"M2","gaps":[""]}
}"""
SCHEMA_B = """Return JSON with exactly these keys:
{
 "cover_letter": {"greeting":"Dear ... ,","paragraphs":[{"text":"","uses":["S6","M2"]}]},
 "answers": [{"id":"","text":"","uses":["S2"],"note":""}]
}"""
STOP = set("with that this from have will your their about which they them were been into more than also such other work experience team teams role skills ability strong using used build building years year ours our you are and the for can able including related required preferred plus must".split())
def toks(s): return set(w for w in re.findall(r"[a-z][a-z+#]{3,}", s.lower()) if w not in STOP)

TRACK_ABBR = {"Data_Engineer": "DE", "Data_Analyst": "DA", "Product_Manager": "PM", "AI_Agentic_Engineer": "AI"}

def select_stories(stories, jd, notes, n=10):
    """Confirmed stories ranked by keyword overlap with the JD; top n (max 3 of S8a-e) + S8ctx if any S8 + motivations."""
    jt = toks(jd + " " + notes)
    sc = []
    for sid, t in stories.items():
        if sid.startswith("M") or sid == "S8ctx": continue
        st = toks(t)
        sc.append((len(st & jt) / (len(st) ** 0.5 + 1), sid))
    sc.sort(reverse=True)
    pick, s8 = [], 0
    for _, sid in sc:
        if sid.startswith("S8"):
            if s8 >= 3: continue
            s8 += 1
        pick.append(sid)
        if len(pick) >= n: break
    if s8 and "S8ctx" in stories: pick.append("S8ctx")
    pick += [k for k in stories if k.startswith("M")]
    return {k: stories[k] for k in pick}

def never_phrases():
    """the NAMES among config/facts.json never-phrases (every word capitalised: "XJTLU", "Xi'an Jiaotong-Liverpool") —
    a name can be cut from a story without changing what it says; wording rules ("independently", "I cut review
    time") are never cut, the overclaim check still catches them."""
    try:
        import paths as jsa_paths
        fb = json.load(open(jsa_paths.config("facts.json"), encoding="utf-8"))
    except Exception:
        return []
    out = []
    for sec in fb.values():
        for e in sec if isinstance(sec, list) else []:
            out += [w for w in (e.get("never") or []) if isinstance(w, str) and w.split()
                    and all(x[:1].isupper() for x in w.split())] if isinstance(e, dict) else []
    return sorted(set(out), key=len, reverse=True)

def strip_never(text, phrases=None):
    """JSA-264: a Confirmed story may name a never-phrase (story-bank "Voice in XJTLU", "U-stage Voice Club, XJTLU");
    the writer copied it and the overclaim check then failed the whole letter. Take it out of what the writer sees:
    ' in X' / ', X' / '(X)' / 'X' go, so "the "Voice in XJTLU" flagship" → "the "Voice" flagship"."""
    if not isinstance(text, str):
        return text
    for w in (never_phrases() if phrases is None else phrases):
        q = re.escape(w)
        text = re.sub(r"\s+(in|at|of)\s+(the\s+)?" + q + r"\b", "", text, flags=re.I)
        text = re.sub(r",\s*" + q + r"\b", "", text, flags=re.I)
        text = re.sub(r"\s*\(\s*" + q + r"\s*\)", "", text, flags=re.I)
        text = re.sub(r"\b" + q + r"\b\s*", "", text, flags=re.I)
    return text

def build_context(track, bank, stories, jd, notes, questions):
    role, pool, _, base_skills = base_structure(track)
    by_text = {b["text"]: b for b in bank}
    unmatched = []
    def idsof(bl):
        out = []
        for b in bl:
            if b in by_text: out.append(by_text[b]["id"])
            else: unmatched.append(b); out.append("?")
        return out
    exp = [dict(key=ORG_KEY[e["org"]], org=e["org"], title=e["title"], date=e["date"], base_bullets=idsof(e["bullets"])) for e in role["exp"]]
    prj = [dict(key=ORG_KEY[p["title"]], title=p["title"], tag=p["tag"], date=p["date"], base_bullets=idsof(p["bullets"])) for p in role["projects"]]
    order = ["projects", "exp"] if track == "AI_Agentic_Engineer" else ["exp", "projects"]
    base = dict(track=track, base_headline=HEADLINES[track], base_section_order=order, base_skill_lines=base_skills,
                education=[f'{e["school"]}: {e["degree"]}, {e["date"]}' for e in C.EDU], experience=exp, projects=prj,
                leadership="fixed, not editable")
    # smaller prompt: bullets of the base resume + bullets used in this track; skill lines of this track + 3 best JD-matching others
    base_ids = {i for e in exp + prj for i in e["base_bullets"]}
    ab = TRACK_ABBR[track]
    bsel = [b for b in bank if b["sec"] != "VC" and (b["id"] in base_ids or ab in [x.strip() for x in b["used_in"].split(",")])]
    bank_payload = [dict(id=b["id"], text=b["text"], tags=b["tags"]) for b in bsel]
    jt = toks(jd)
    others = sorted([(len(toks(v["text"]) & jt), k) for k, v in pool.items() if k not in base_skills and track not in v["tracks"]], reverse=True)
    keep_sk = list(base_skills) + [k for s, k in others[:3] if s > 0]
    pool_payload = {k: dict(label=pool[k]["label"], text=pool[k]["text"]) for k in keep_sk}
    sel_stories = {k: strip_never(v) for k, v in select_stories(stories, jd, notes).items()}
    qs = [dict(id=q["id"], label=scrub(q["label"]), limit=q.get("limit"), target_max=(int(int(q["limit"]) * 0.85) if q.get("limit") else None), unit=q.get("unit", "characters"),
               **({"min": int(q["min"])} if q.get("min") else {}),       # JSA-312: the page's minimum, read from the live form
               **({"description": scrub(q["description"])} if q.get("description") else {})) for q in questions]
    ctx = dict(task="Tailor for this job", jd=scrub(jd), notes=scrub(notes), base_resume=base, skill_pool=pool_payload,
               bullet_bank=bank_payload, confirmed_stories=sel_stories, profile_facts=profile_facts(), questions=qs)
    return ctx, unmatched

# ----------------------------------------------------------------------------- verification
def numtokens(s):
    return set(re.sub(r"[,$]", "", m).rstrip("%") for m in re.findall(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?", s))

def verify_a(d, V):
    """V: dict with bank, stories, skill_pool, base, jd, notes, profile, questions, track. returns (errors, warnings)"""
    E, W = [], []
    bank = {b["id"]: b for b in V["bank"]}
    known = set(bank) | set(V["stories"]) | set(V["skill_pool"]) | {"PROFILE", "NOTES"}
    rs = d.get("resume") or {}
    base = V["ctx"]["base_resume"]
    # --- resume selection
    for sec, items in (("exp", base["experience"]), ("projects", base["projects"])):
        got = rs.get(sec) or {}
        if set(got) != {i["key"] for i in items}: E.append(f"resume.{sec} keys must be exactly {[i['key'] for i in items]}, got {list(got)}")
        for i in items:
            ids = got.get(i["key"], [])
            n0 = len(i["base_bullets"])
            if len(ids) != len(set(ids)): E.append(f"{i['key']}: duplicate bullet IDs")
            if not (max(1, n0 - 1) <= len(ids) <= n0 + 1): E.append(f"{i['key']}: {len(ids)} bullets, allowed {max(1, n0 - 1)}-{n0 + 1}")
            for b in ids:
                if b not in bank: E.append(f"{i['key']}: unknown bullet ID {b}")
                elif bank[b]["sec"] != i["key"]: E.append(f"{b} belongs to {bank[b]['sec']}, not {i['key']}")
    tot0 = sum(len(i["base_bullets"]) for i in base["experience"] + base["projects"])
    tot = sum(len(v) for sec in ("exp", "projects") for v in (rs.get(sec) or {}).values())
    if tot > tot0 + 1: E.append(f"total bullets {tot} > base {tot0}+1 (light tweaks only)")
    sk = rs.get("skill_lines") or []
    pool = V["skill_pool"]
    for s in sk:
        if s not in pool: E.append(f"unknown skill line ID {s}")
    if len(sk) != len(set(sk)): E.append("duplicate skill line IDs")
    n0 = len(base["base_skill_lines"])
    if not (n0 - 1 <= len(sk) <= n0 + 1): E.append(f"skill lines {len(sk)}, allowed {n0 - 1}-{n0 + 1}")
    if not any(pool.get(s, {}).get("label") == "Languages" for s in sk):
        # local repair (2026-10-28): the Languages line is fixed on every resume → put the base track's line back
        lang = [s for s in base["base_skill_lines"] if pool.get(s, {}).get("label") == "Languages"] or [s for s, v in pool.items() if v.get("label") == "Languages"]
        if lang:
            sk = rs["skill_lines"] = [x for x in sk if x != lang[0]] + [lang[0]]
            if len(sk) > n0 + 1: sk = rs["skill_lines"] = sk[:n0] + [lang[0]]
            W.append(f"skills: Languages line {lang[0]} was missing — added back")
        else: E.append("Languages skill line missing")
    if rs.get("section_order") not in (["exp", "projects"], ["projects", "exp"]): E.append("section_order must be ['exp','projects'] or ['projects','exp']")
    text = resume_text(d, V)
    body_text = resume_text(d, V, False)
    # --- headline
    job = d.get("job") or {}
    jt, ht = job.get("job_title", ""), rs.get("headline_title", "")
    if ht and " · " in ht and norm(ht) not in norm(jt):
        # local repair (2026-10-28): DeepSeek put "Title · kw · kw" into headline_title → split it
        parts = [x.strip() for x in ht.split(" · ") if x.strip()]
        rs["headline_title"] = ht = parts[0]
        if len(rs.get("headline_keywords") or []) < 2: rs["headline_keywords"] = parts[1:5]
        W.append("headline: title and keywords were merged in headline_title — split")
    if not jt or norm(jt) not in norm(V["jd"]): E.append(f"job.job_title '{jt}' not found verbatim in the JD")
    if not ht or norm(ht) not in norm(jt): E.append(f"headline_title '{ht}' must be the posted title (substring of job_title)")
    kws = rs.get("headline_keywords") or []
    if not (2 <= len(kws) <= 4): E.append("headline_keywords must be 2-4")
    # local repairs (2026-10-27): drop unsupported / overflow keywords instead of failing the whole step
    bad = [k for k in kws if norm(k) not in body_text]
    if bad and len(kws) - len(bad) >= 2:
        rs["headline_keywords"] = kws = [k for k in kws if k not in bad]; W.append(f"headline: dropped keywords not on the resume {bad}")
    for k in kws:
        if norm(k) not in body_text: E.append(f"headline keyword '{k}' does not appear in the selected resume text")
    while len(headline(d)) > 100 and len(kws) > 2:
        drop = kws[-1]; rs["headline_keywords"] = kws = kws[:-1]; W.append(f"headline: dropped '{drop}' to fit 100 chars")
    SEP = r"(?:\s[-–—|]|\s?,)\s"                     # " - part" and ", part" (Bedrock 2026-10-31: "Safety Engineer, Agentic …")
    while len(headline(d)) > 100 and re.search(SEP, rs.get("headline_title", "")):   # long posted titles (a Workday employer 2026-10-30): cut trailing parts; a prefix stays a substring of the title
        rs["headline_title"] = re.split(SEP + r"(?!.*" + SEP + r")", rs["headline_title"])[0].strip(); W.append(f"headline: shortened title to '{rs['headline_title']}'")
    if len(headline(d)) > 100: E.append(f"headline too long ({len(headline(d))} chars, max 100)")
    # --- keyword map / fit map
    for r in d.get("keyword_map") or []:
        if r.get("true_for_him") == "yes" and r.get("must_have") and norm(r.get("resume_term", "")) not in text:
            alt = [x for x in re.split(r"[,(;/]| or | and ", r.get("resume_term", "") + "," + r.get("term", "")) if len(x.strip()) > 1]
            hit = next((x.strip() for x in alt if norm(x.strip()) in text), None)
            if hit: r["resume_term"] = hit; W.append(f"keyword_map: '{r.get('term')}' resume_term adjusted to '{hit}'")
            else:  # local repair (2026-10-27): downgrade instead of failing — the map must never overclaim
                r["true_for_him"], r["action"] = "partly", "gap"
                W.append(f"keyword_map: '{r.get('term')}' downgraded yes→partly (nothing like '{r.get('resume_term')}' on the resume)")
        for e in r.get("evidence") or []:
            if e not in known and e not in pool: E.append(f"keyword_map: unknown evidence ID {e}")
    fm = d.get("fit_map") or {}
    if not fm.get("rows"): E.append("fit_map.rows empty")
    for r in fm.get("rows") or []:
        if r.get("strength") not in ("strong", "partial", "none"): E.append(f"fit_map: bad strength '{r.get('strength')}'")
        for e in r.get("evidence") or []:
            if e not in known and e not in pool: E.append(f"fit_map: unknown ID {e}")
    if fm.get("motivation") not in V["stories"]: E.append("fit_map.motivation must be M1/M2/M3")
    return E, W

_FACTS = []


def overclaims(label, text, V):
    """JSA-242 / JSA-251: never-phrases and fact pairs from config/facts.json (truth_check.check_text) — e.g. "led the
    code" for the team-of-3 project (he led MOST of the code), "70%" without "workflow" (part of a workflow that cut
    review time). Numbers are checked by check_text above; only these two kinds are added here."""
    try:
        import truth_check as TC
    except Exception:
        return []
    if _facts_book() is None:
        return []
    out = []
    for e in TC.check_text(text, _FACTS[0], V.get("jd") or ""):
        if e.startswith("never-phrase") or e.startswith("pair:"):
            out.append(f"{label}: overclaim — {e} (write it as the fact says)")
    return out


# ----------------------------------------------------------------------------- sentence checks (JSA-242 / JSA-190)
# Four kinds of sentence that passed every check and needed a hand edit (gh10 2026-11-06, decisions-log 2026-11-05):
# (a) the M.S. in the wrong tense ("starts in 2026" while he is enrolled), (b) a skill tied to the M.S. that the facts do
# not tie to it ("my M.S. is where the Tableau comes from"), (c) "I haven't done X / no experience in X", (d) a boilerplate
# opener ("I'm applying for …", "I am excited to apply …"); plus two ownership slips the facts' `ownership` field rules
# out ("That workflow cut review time by 70%" — he contributed to the workflow; "a benchmark I led" — he led the code).
# A flagged sentence is rewritten by DeepSeek (≤ 2 tries); still failing → the folder is blocked for Joey.
_ABBR = ("m.s.", "b.a.", "b.s.", "m.a.", "u.s.", "e.g.", "i.e.", "dr.", "mr.", "ms.", "mrs.", "st.", "no.", "vs.", "inc.", "jr.")
_OPEN_START = [r"(?:i am|i'm)\s+(?:so\s+|very\s+|truly\s+|really\s+)?(?:excited|thrilled|delighted|eager|pleased|happy|honou?red)\s+to\b",
               r"(?:i am|i'm)\s+(?:writing\s+to\s+)?apply(?:ing)?\b", r"i\s+am\s+writing\s+(?:to|in|because)\b",
               r"i\s+(?:would|'d)\s+like\s+to\s+(?:apply|express|submit)\b", r"please\s+accept\b",
               r"(?:i\s+)?was\s+(?:so\s+)?(?:excited|thrilled|delighted)\s+to\s+(?:see|find|learn|come across)\b",
               r"(?:it\s+is\s+)?with\s+great\s+(?:interest|enthusiasm|excitement)\b", r"as\s+an?\s+(?:aspiring|enthusiastic|motivated)\b"]
_OPEN_ANY = [r"\bexcited\s+to\s+apply\b", r"\bthrilled\s+to\s+apply\b", r"\bwriting\s+to\s+apply\b", r"\bplease\s+accept\s+my\s+application\b",
             r"\bdraws?\s+me\s+to\b", r"\bcaught\s+my\s+(?:eye|attention)\b"]
_NEG = [r"\bi(?:\s+have|'ve)\s+(?:not|never)\b(?!\s+only\b)", r"\bi\s+haven'?t\b", r"\bi(?:\s+have|'ve)\s+yet\s+to\b",
        r"\bi\s+(?:do\s+not|don'?t)\s+(?:yet\s+)?have\s+(?:any\s+|much\s+|direct\s+|hands-on\s+|professional\s+|formal\s+|prior\s+)*(?:experience|exposure|background)\b",
        r"\b(?:no|little|limited|minimal)\s+(?:prior\s+|direct\s+|hands-on\s+|professional\s+|formal\s+|industry\s+)*(?:experience|exposure|background)\s+(?:in|with)\b",
        r"\bmy\s+(?:experience|exposure)\s+(?:with|in)\s+[^.;]{1,40}\bis\s+(?:limited|minimal)\b", r"\bnot\s+yet\s+(?:used|worked|built|had)\b",
        r"\bi\s+lack\b", r"\bi(?:\s+am|'m)\s+(?:still\s+)?new\s+to\b", r"\bi(?:\s+have|'ve)\s+(?:only\s+)?used\s+[\w .+-]{1,30}?\s+rather\s+than\b",
        r"\bi\s+(?:did\s+not|didn'?t)\s+(?:get\s+to\s+)?(?:use|work|build)\b", r"\bwhile\s+i\s+have\s+not\b"]
_MS = r"\bM\.\s?S\.?(?![a-z])|\bMS\b|\bmaster'?s\b|\bapplied\s+data\s+science\b|\buniversity\s+of\s+chicago\b|\buchicago\b|\bgraduate\s+(?:program|studies|degree)\b"
_FUTURE = (r"\b(?:starts?|starting|begins?|beginning|commencing|incoming|upcoming|admitted|accepted\s+(?:to|into)|"
           r"will\s+(?:soon\s+)?(?:start|begin|join|enter|enroll|pursue|attend|be\s+(?:starting|beginning|joining|entering|pursuing|attending|enrolled|starting))|"
           r"(?:am|'m)\s+(?:about|set|going)\s+to\s+(?:start|begin|join|enter|pursue)|plan(?:ning)?\s+to\s+(?:start|begin|attend|pursue|join|enroll))\b")
_CAUSE = (r"\b(?:is|was)\s+where\b|\bcomes?\s+from\b|\bcame\s+from\b|(?<![\w-])(?:learn(?:ed|t)?|picked\s+up|gained|honed|sharpened|acquired|"
          r"mastered)\b|\b(?:taught|gave|trained|grounded|equipped)\s+me\b|\bthanks\s+to\s+my\b|\bthrough\s+my\b")
_TOOLS_EXTRA = ["Power BI", "Looker", "Spark", "PySpark", "Hadoop", "AWS", "Azure", "GCP", "dbt", "Airflow", "Kafka", "PyTorch",
                "TensorFlow", "Java", "Scala", "C++", "JavaScript", "TypeScript", "MATLAB", "SAS", "Stata", "SPSS", "Alteryx",
                "Qlik", "BigQuery", "Redshift", "Docker", "Kubernetes", "LangChain", "RAG", "A/B testing", "deep learning", "NLP"]


def sentences(text):
    """Pure (tested). Split prose into sentences at . ! ? + space + a capital / digit / quote, never after an
    abbreviation such as "M.S." or "U.S." ("my M.S. in Applied Data Science" stays one sentence)."""
    t = str(text or "").strip()
    out, start = [], 0
    for m in re.finditer(r"[.!?][\"'”’)]?\s+(?=[A-Z0-9\"“(])", t):
        word = t[:m.start() + 1].split()[-1].lower() if t[:m.start() + 1].split() else ""
        if word.lstrip("(\"“") in _ABBR: continue
        out.append(t[start:m.end()].strip()); start = m.end()
    if t[start:].strip(): out.append(t[start:].strip())
    return out


def _facts_book():
    if not _FACTS:
        try:
            import paths as jsa_paths
            _FACTS.append(json.load(open(jsa_paths.config("facts.json"), encoding="utf-8")))
        except Exception:
            return None
    return _FACTS[0]


_MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def sentence_rules(fb, today=None):
    """Pure (tested). The data the sentence checks need, from config/facts.json: whether the M.S. has started (its
    entry's first 'Mon YYYY' ≤ today), the skills the facts tie to the M.S., the skill vocabulary, and the ownership
    rules ("he led the code" → a 'led' near the entry's anchors must say 'led the code'; "contributed to the workflow" →
    the pair head (70%) must come with 'part of' / 'contributed')."""
    today = today or datetime.date.today()
    fb = fb or {}
    ms = next((e for e in fb.get("entries") or [] if e.get("kind") == "education" and re.search(r"\bM\.\s?S\.|master", e.get("role") or "", re.I)), None)
    started = False
    if ms:
        m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", ms.get("dates") or "")
        if m and m.group(1).lower() in _MON: started = today >= datetime.date(int(m.group(2)), _MON[m.group(1).lower()], 1)
    ms_skills = set()
    for f in fb.get("facts") or []:
        if ms and f.get("entry") == ms.get("id"): ms_skills |= {s.lower() for s in (f.get("skills") or []) + (f.get("anchors") or [])}
    vocab = set(_TOOLS_EXTRA)
    sk = fb.get("skills") or {}
    for v in (sk.get("true") or {}).values(): vocab |= set(v)
    vocab |= set(sk.get("not_true") or [])
    for f in fb.get("facts") or []: vocab |= set(f.get("skills") or [])
    vocab = {re.sub(r"\s*\(.*\)$", "", v).strip() for v in vocab if isinstance(v, str) and v.strip()}
    vocab -= {"economics"}   # his B.A. subject: "my M.S. follows an economics background" ties nothing to the M.S.
    led, part = [], []
    for f in fb.get("facts") or []:
        own = f.get("ownership") or ""
        m = re.search(r"\bhe led (the [a-z]+)", own)
        if m:
            anchors = list(f.get("anchors") or [])
            t3 = re.search(r"\bteam of \d+", own)
            if t3: anchors.append(t3.group(0))
            led.append(dict(id=f["id"], need=m.group(1), anchors=anchors))
        m = re.search(r"\bcontributed to the ([a-z]+)", own)
        if m:
            for a, b in f.get("pairs") or []:
                if b.lower() == m.group(1): part.append(dict(id=f["id"], head=a, noun=b))
    edu = {e.get("id") for e in fb.get("entries") or [] if e.get("kind") == "education"}
    other = {}
    for f in fb.get("facts") or []:
        if f.get("entry") in edu: continue
        for a in (f.get("anchors") or []) + ([re.search(r"\bteam of \d+", f.get("ownership") or "").group(0)] if re.search(r"\bteam of \d+", f.get("ownership") or "") else []):
            if len(a) >= 4: other.setdefault(a, f.get("entry") or f["id"])
    return dict(other_anchors=sorted(other.items(), key=lambda x: -len(x[0])), ms_started=started, ms_name=(ms or {}).get("role") or "the M.S.", ms_dates=(ms or {}).get("dates") or "",
                ms_skills=ms_skills, vocab=sorted(vocab, key=len, reverse=True), led=led, part=part)


def _clauses(s):
    return [c for c in re.split(r";|:|\s+[—–]\s+|\s+-\s+|,\s+(?=(?:and|but|which|while|so|whereas)\b)", s) if c.strip()]


def _named(s, vocab):
    out = []
    for v in vocab:
        rx = rf"(?<![\w+#]){re.escape(v)}(?![\w+#])"
        if re.search(rx, s) if len(v) <= 3 else re.search(rx, s, re.I):
            if not any(v.lower() in o.lower() for o in out): out.append(v)
    return out


def sentence_flags(s, R, first=False, negation=True):
    """Pure (tested). The problems of ONE sentence → list of short reasons ([] = clean). first = the letter's opening
    sentence (opener rules); negation=False for an answer to a yes/no question ("Have you worked at X?")."""
    out, low = [], s.lower().replace("’", "'")
    if first:
        lead = re.sub(r"^[\"“(\s]+", "", low)
        for rx in _OPEN_START:
            if re.match(rx, lead): out.append("opener: boilerplate opening — open with the concrete company fact or the work he wants to do"); break
    for rx in _OPEN_ANY:
        if re.search(rx, low): out.append(f"opener: boilerplate phrase '{re.search(rx, low).group(0)}'"); break
    if negation:
        for rx in _NEG:
            m = re.search(rx, low)
            if m: out.append(f"negation: '{m.group(0)}' — never say what he has not done (a gap stays in fit_map)"); break
    if re.search(_MS, s, re.I):
        if R.get("ms_started"):
            m = re.search(_FUTURE, low)
            if m: out.append(f"ms_tense: '{m.group(0)}' — he is enrolled now ({R.get('ms_name')}, {R.get('ms_dates')}); write 'I am pursuing' / 'I'm in'")
        for cl in _clauses(s):   # the M.S., the causal tie and the skill in ONE clause ("…, which is where" ties to what precedes)
            if re.search(_MS, cl, re.I) and re.search(_CAUSE, cl.lower()):
                bad = [v for v in _named(cl, R.get("vocab") or []) if v.lower() not in R.get("ms_skills", set())]
                if bad: out.append(f"ms_cause: {', '.join(bad[:4])} tied to the M.S., but the facts do not tie it to the M.S."); break
        for cl in _clauses(s):   # a project / job from another entry placed inside the M.S. ("In my M.S. coursework I led the code for a team of 3")
            if re.search(_MS, cl, re.I):
                hit = next((a for a, e in R.get("other_anchors") or [] if re.search(rf"(?<![\w-]){re.escape(a)}(?![\w-])", cl, re.I)), None)
                if hit: out.append(f"ms_cause: '{hit}' is from {dict(R['other_anchors'])[hit]}, not from the M.S."); break
    for r in R.get("led") or []:
        if re.search(r"\bled\b", low) and any(a.lower() in low for a in r["anchors"]):
            if re.search(rf"\bled\b(?!\s+{re.escape(r['need'])}\b)", low):
                out.append(f"ownership: say 'led {r['need']}' (fact {r['id']}), not led the whole project"); break
    for r in R.get("part") or []:
        if r["head"].lower() in low and not re.search(r"\bpart of\b|\bcontribut", low):
            out.append(f"ownership: '{r['head']}' was the result of a {r['noun']} he contributed to — write 'part of a {r['noun']} that …' (fact {r['id']})")
    return out


def _yes_no_question(label):
    return bool(re.match(r"\s*(?:have|has|did|do|are|were|is)\s+you\b", str(label or ""), re.I))


def text_flags(text, R, letter_first=False, negation=True):
    """[(sentence index, sentence, [reasons])] for every flagged sentence of a paragraph / answer."""
    ss = sentences(text)
    return [(i, s, f) for i, s in enumerate(ss) for f in [sentence_flags(s, R, first=letter_first and i == 0, negation=negation)] if f]


def sentence_errors(d, V, R=None):
    """Error strings for verify_b: every flagged sentence still in the letter / answers."""
    R = R if R is not None else V.get("_srules") or sentence_rules(_facts_book())
    E = []
    for n, p in enumerate((d.get("cover_letter") or {}).get("paragraphs") or [], 1):
        for i, s, fl in text_flags(p.get("text", ""), R, letter_first=(n == 1)):
            E += [f"letter p{n}: {x} — '{s[:80]}'" for x in fl]
    qs = {q["id"]: q for q in V.get("questions") or []}
    for a in d.get("answers") or []:
        if (a.get("text") or "").strip() == "ASK": continue
        neg = not _yes_no_question((qs.get(a.get("id")) or {}).get("label"))
        for i, s, fl in text_flags(a.get("text", ""), R, negation=neg):
            E += [f"answer '{a.get('id')}': {x} — '{s[:80]}'" for x in fl]
    return E


REWRITE_SYS = """You fix ONE sentence of a job-application cover letter or answer. Reply with JSON {"sentence": "..."} only.
Keep the sentence's place in the paragraph and its true content; remove only the problem named. Use only facts in SOURCE
(never a new fact, number, tool, feeling or motivation). Rules: the M.S. is current (he is enrolled now: "I am pursuing",
"I'm in"), never "starts" / "will start"; tie a skill to the M.S. only when SOURCE ties it to the M.S. coursework; never
say what he has not done or lacks ("I haven't", "no experience in", "rather than X") — write what he has done, or return
"" to drop the sentence; never open with "I'm applying for", "I am excited to apply", "I am writing to" — open with the
concrete company fact or the work he wants to do; the team-of-3 project: he "led the code"; the 70% result: "part of a
workflow that cut … by 70%". No visa or work-authorization words, no banned words (leverage, passionate, dynamic, robust,
utilize, seamlessly, spearhead, orchestrate)."""


def rewrite_text(text, R, ctx, label, uses, V, known, letter_first=False, negation=True, tries=2, step="B-fix"):
    """JSA-242 / 190: every flagged sentence of `text` → DeepSeek rewrite (≤ `tries` each), accepted only when the new
    sentence has no flag, no check_text error and no overclaim. Returns (new text, notes). Raises Failed('blocked: …')
    when a sentence still fails after `tries` rewrites — the folder waits for Joey."""
    notes = []
    for _ in range(12):   # one fix per pass; the indices move when a sentence is dropped
        ss = sentences(text)
        fl = text_flags(text, R, letter_first, negation)
        if not fl: return text, notes
        i, s, reasons = fl[0]
        last, base = reasons, set(check_text("x", text, uses, V, known))   # only NEW errors count against a rewrite
        for t in range(tries):
            msg = dict(sentence=s, problems=reasons if t == 0 else last, paragraph=text, position=("opening sentence of the letter" if letter_first and i == 0 else f"sentence {i + 1}"),
                       source=ctx, where=label)
            d, _raw = ds_call([{"role": "system", "content": REWRITE_SYS}, {"role": "user", "content": json.dumps(msg, ensure_ascii=False)}], 400, step=step)
            new = str((d or {}).get("sentence") or "").strip()
            if not new:
                if len(ss) > 1 and not (letter_first and i == 0):
                    last = []; break
                last = ["the sentence cannot be dropped here; rewrite it"]; continue
            cand = " ".join(ss[:i] + [new] + ss[i + 1:])   # paragraph-level checks (team of 3, numbers vs. uses) on the whole paragraph
            last = sentence_flags(new, R, first=letter_first and i == 0, negation=negation) \
                + [e for e in check_text("x", cand, uses, V, known) if e not in base] + overclaims("x", new, V)
            if not last: break
        if last:
            raise Failed([f"blocked: {label}: sentence still fails after {tries} rewrites ({'; '.join(last)[:160]}) — '{s[:90]}' — needs Joey"], step)
        ss = ss[:i] + ([new] if new else []) + ss[i + 1:]
        notes.append(f"{label}: rewrote ({'; '.join(r.split(':')[0] for r in reasons)}): '{s[:70]}' → '{(new or '(dropped)')[:70]}'")
        text = " ".join(ss)
    raise Failed([f"blocked: {label}: too many flagged sentences — needs Joey"], step)


def fix_sentences(d, V):
    """Rewrite the flagged sentences of step B (letter paragraphs, open answers) in place. → notes (warnings)."""
    R = V.get("_srules")
    if R is None:
        R = V["_srules"] = sentence_rules(_facts_book())
    known = set(V["bank_by_id"]) | set(V["stories"]) | set(V["skill_pool"]) | {"PROFILE", "NOTES"}
    notes = []

    def ctx_of(uses):
        src = []
        for u in uses or []:
            if u in V["stories"]: src.append(V["stories"][u])
            elif u in V["bank_by_id"]: src.append(V["bank_by_id"][u]["text"])
            elif u in V["skill_pool"]: src.append(V["skill_pool"][u]["text"])
        return "\n".join(src + list(V.get("profile") or []))[:6000]

    for n, p in enumerate((d.get("cover_letter") or {}).get("paragraphs") or [], 1):
        if text_flags(p.get("text", ""), R, letter_first=(n == 1)):
            p["text"], nt = rewrite_text(p.get("text", ""), R, ctx_of(p.get("uses")), f"letter p{n}", p.get("uses") or [], V, known, letter_first=(n == 1))
            notes += nt
    qs = {q["id"]: q for q in V.get("questions") or []}
    for a in d.get("answers") or []:
        if (a.get("text") or "").strip() == "ASK": continue
        neg = not _yes_no_question((qs.get(a.get("id")) or {}).get("label"))
        if text_flags(a.get("text", ""), R, negation=neg):
            a["text"], nt = rewrite_text(a.get("text", ""), R, ctx_of(a.get("uses")), f"answer '{a.get('id')}'", a.get("uses") or [], V, known, negation=neg)
            notes += nt
    return notes


def verify_b(d, V):
    """letter + answers + global checks (d = step A merged with step B)"""
    E, W = [], []
    known = set(V["bank_by_id"]) | set(V["stories"]) | set(V["skill_pool"]) | {"PROFILE", "NOTES"}
    cl = d.get("cover_letter") or {}
    paras = cl.get("paragraphs") or []
    if not (3 <= len(paras) <= 5): E.append(f"letter has {len(paras)} paragraphs, need 3-5")
    body = "\n\n".join(p.get("text", "") for p in paras)
    wc = len(re.findall(r"[\w'’-]+", body))
    if wc > 400: E.append(f"letter is {wc} words, max 400: cut at least {wc - 340} words (target about 340)")
    if wc < 250: E.append(f"letter is {wc} words, min 250")
    if not cl.get("greeting"): E.append("letter greeting missing")
    used_all = set()
    for n, p in enumerate(paras, 1):   # local repair (2026-10-30, a Workday employer "86,000", a Workday employer "$200"): a sentence whose only fault is a company figure quoted from the JD is dropped
        sents = re.split(r"(?<=[.!?])\s+", p.get("text", ""))
        keep = []
        for sn in sents:
            es = check_text("x", sn, p.get("uses") or [], V, known)
            nums = [re.search(r"number '([^']+)'", e) for e in es]
            if es and all(m and m.group(1) in V["jd"] for m in nums): W.append(f"letter p{n}: dropped a sentence quoting a JD figure: '{sn[:60]}...'"); continue
            keep.append(sn)
        if len(keep) < len(sents) and keep: p["text"] = " ".join(keep)
        E += check_text(f"letter p{n}", p.get("text", ""), p.get("uses") or [], V, known)
        used_all |= set(p.get("uses") or [])
    if len([u for u in used_all if u in V["stories"] and not u.startswith("M")]) < 2: E.append("letter must cite at least 2 stories")
    if not (used_all & {"M1", "M2", "M3"}): E.append("letter must use a motivation (M1-M3) in the why-this-company part")
    warn_terms(body, V, W, "letter")
    E += overclaims("letter", body, V)
    E += sentence_errors(d, V)   # JSA-242 / 190: tense, M.S. cause, negation, opener, ownership (fix_sentences ran first)
    # --- answers
    qs = {q["id"]: q for q in V["questions"]}
    ans = {a.get("id"): a for a in d.get("answers") or []}
    for qid, q in qs.items():
        a = ans.get(qid)
        if not a: E.append(f"answer missing for question '{qid}'"); continue
        t = a.get("text", "")
        if t.strip() == "ASK": continue
        lim = q.get("limit")
        if lim:
            n = len(re.findall(r"\S+", t)) if q.get("unit") == "words" else len(t)
            if n > int(lim): E.append(f"answer '{qid}' is {n} {q.get('unit', 'characters')}, limit {lim}")
        if q.get("min"):                                   # JSA-312: the page refuses a shorter answer (an employer 11-11: minimum 5)
            n = len(re.findall(r"\S+", t)) if q.get("unit") == "words" else len(t.strip())
            if n < int(q["min"]): E.append(f"answer '{qid}' is {n} {q.get('unit', 'characters')}, minimum {q['min']}")
        E += check_text(f"answer '{qid}'", t, a.get("uses") or [], V, known)
        E += overclaims(f"answer '{qid}'", t, V)
        warn_terms(t, V, W, f"answer {qid}")
    for qid in ans:
        if qid not in qs: W.append(f"extra answer id '{qid}' ignored")
    # --- global
    allgen = json.dumps(d, ensure_ascii=False)
    if re.search(r"\bJ0\d{4}\b", allgen): E.append("internal job ID (J0xxxx) present")
    return E, W

def verify_b_fixed(A, d, V):
    """Step B's verify: first the sentence rewrites (fix_sentences mutates d, so the checkpoint keeps the fixed text),
    then verify_b. A 'blocked:' Failed from a rewrite propagates (the folder waits for Joey, no whole-letter re-ask)."""
    notes = fix_sentences(d, V)
    E, W = verify_b({**A, **d}, V)
    return E, notes + W

def leaked_ids(t, known):
    """Pure (tested). The story-bank IDs (S6, M2, JSA05, PROFILE, S8ctx …) that appear in prose as a whole token — case
    sensitive, not part of a longer word or a hyphenated / digit-continued token. Sorted."""
    return sorted(k for k in known if re.search(rf"(?<![\w-]){re.escape(k)}(?![\w-])", str(t or "")))


def wrong_program(t):
    """Pure (tested). True when the prose names his degree program as plain "Data Science" (a master's / M.S. / degree /
    program … in Data Science, or "my master's is in Data Science") instead of "Applied Data Science" (Joey: a Lever employer
    2026-11-04)."""
    t = str(t or "")
    return bool(re.search(r"(?:\b(?:master'?s|masters|ms|degree|program|graduate studies)\b|\bm\.s\.)(?:(?<=\.)|[^.;]){0,30}?\bin\s+(?!applied\b)data science\b", t, re.I))


def check_text(label, t, uses, V, known):
    E = []
    low = t.lower()
    for u in uses:
        if u not in known: E.append(f"{label}: unknown ID in uses: {u}")
    if not uses: E.append(f"{label}: 'uses' is empty")
    bl = low
    for nm in {str(V.get("company") or "").lower().strip(), str(V.get("company_low") or "").strip()} - {""}:
        bl = bl.replace(nm, " ")   # the company's own name is no banned word ("a Lever employer" → 'dynamic', JSA-264)
    for w in BANNED_WORDS:
        if re.search(rf"\b{re.escape(w)}\b", bl): E.append(f"{label}: banned word '{w}'")
    for ph in BANNED_PHRASES:
        if ph in low: E.append(f"{label}: banned phrase '{ph}'")
    for rx in VISA_WORDS:
        if re.search(rx, t, re.I): E.append(f"{label}: visa/work-authorization wording '{re.search(rx, t, re.I).group(0)}' not allowed")
    for rx in SOLO_WORDS:
        if re.search(rx, t, re.I): E.append(f"{label}: '{re.search(rx, t, re.I).group(0)}' not allowed (ECON 491 was a team of 3)")
    if re.search(r"\bJ0\d{4}\b", t): E.append(f"{label}: internal job ID")
    if wrong_program(t): E.append(f"{label}: the program is 'Applied Data Science' (M.S. Applied Data Science, UChicago), never plain 'Data Science'")
    leaked = leaked_ids(t, known)   # a story-bank ID in the prose ("… a distance (M2).", Firework / an employer 2026-11-04)
    if leaked: E.append(f"{label}: story-bank ID(s) in the text {leaked[:4]} — write the story, never its ID")
    m_c = re.search(r"@|https?://|linkedin\.com|github\.com|\d{3}[-. ]\d{3}[-. ]\d{4}", t, re.I)
    if m_c: E.append(f"{label}: contact detail/link matched '{m_c.group(0)}' in: '...{t[max(0,m_c.start()-40):m_c.end()+25]}...' (remove it)")
    if "S6" in uses and "team of 3" not in low: E.append(f"{label}: uses S6 but never says 'team of 3'")
    if re.search(r"\becon 491\b", low) and "team of 3" not in low: E.append(f"{label}: mentions ECON 491 without 'team of 3'")
    if any(u.startswith("S8") for u in uses) and re.search(r"\bcoded\b", low): E.append(f"{label}: never say 'coded' for the Job Searching Agent")
    # numbers
    src = ""
    for u in uses:
        if u in V["stories"]: src += "\n" + V["stories"][u]
        elif u in V["bank_by_id"]: src += "\n" + V["bank_by_id"][u]["text"]
        elif u in V["skill_pool"]: src += "\n" + V["skill_pool"][u]["text"]
        elif u == "PROFILE": src += "\n" + "\n".join(V["profile"])
        elif u == "NOTES": src += "\n" + V["notes"]
    allowed = numtokens(src)
    loose = numtokens(V["jd"]) | numtokens(V["notes"]) | {"2026", "2027", "2028", "2029", "2030"}
    for m in re.finditer(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?%?", t):
        tok = m.group(0); base = re.sub(r"[,$]", "", tok).rstrip("%")
        if base in allowed: continue
        plain_int = re.fullmatch(r"\d{1,4}", base) and "%" not in tok and "$" not in tok
        if plain_int and base in loose: continue
        E.append(f"{label}: number '{tok}' not found in the cited stories/bullets {uses}")
    return E

def warn_terms(t, V, W, label):
    """capitalised terms in the JD that appear nowhere in the candidate's facts (possible claimed-but-unverified tool)."""
    jd_caps = set(re.findall(r"\b[A-Z][A-Za-z0-9+#.]{2,}\b", V["jd"]))
    for w in re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][A-Za-z0-9+#.]{2,}\b", t):
        if w in jd_caps and w.lower() not in V["corpus"] and w.lower() not in V["company_low"]:
            W.append(f"{label}: '{w}' is in the JD but nowhere in his facts; check it is not a claimed skill")

# ----------------------------------------------------------------------------- resume assembly
def headline(d):
    r = d["resume"]
    return " · ".join([r["headline_title"]] + list(r["headline_keywords"]))

def chosen_role(d, V, spacing):
    base = copy.deepcopy(C.ROLES[V["track"]])
    rs = d["resume"]; bank = V["bank_by_id"]; pool = V["skill_pool"]
    r = copy.deepcopy(base)
    r.pop("summary", None)   # the bank-pick (legacy) resume never had a summary; build_docx prints one since JSA-250 → two pages (JSA-264)
    r["label"] = rs["headline_title"]
    r["skills"] = [(pool[s]["label"], pool[s]["text"]) for s in rs["skill_lines"]]
    r["skills_a"] = []
    for e in r["exp"]: e["bullets"] = [bank[b]["text"] for b in rs["exp"][ORG_KEY[e["org"]]]]
    for p in r["projects"]: p["bullets"] = [bank[b]["text"] for b in rs["projects"][ORG_KEY[p["title"]]]]
    r["a_bullet_after"], r["a_section_before"] = spacing
    return r

def merge_runs(p):
    runs = list(re.finditer(r"<w:r(?: [^>]*)?>(.*?)</w:r>", p, flags=re.S))
    info = []
    for m in runs:
        mm = re.fullmatch(r"(<w:rPr>.*?</w:rPr>)?<w:t(?: [^>]*)?>([^<]*)</w:t>", m.group(1), flags=re.S)
        info.append((m, mm.group(1) or "", mm.group(2)) if mm else (m, None, None))
    out, last, i = [], 0, 0
    while i < len(info):
        m, rpr, txt = info[i]
        j = i
        if rpr is not None:
            while j + 1 < len(info) and info[j + 1][1] == rpr and info[j + 1][0].start() == info[j][0].end():
                j += 1
        if j > i:
            out.append(p[last:m.start()])
            out.append('<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, "".join(info[k][2] for k in range(i, j + 1))))
            last = info[j][0].end()
        i = j + 1
    out.append(p[last:])
    return "".join(out)

class Tpl:
    def __init__(self):
        z = zipfile.ZipFile(TEMPLATE)
        self.zip = {n: z.read(n) for n in z.namelist()}
        self.names = z.namelist()
        x = self.zip["word/document.xml"].decode("utf8")
        x = re.sub(r"<w:proofErr[^>]*/>", "", x)
        bi = x.index("<w:body>") + len("<w:body>")
        self.head, self.tail = x[:bi], x[x.index("<w:sectPr"):]
        self.tail = self.tail.replace('w:top="620"', 'w:top="720"').replace('w:bottom="620"', 'w:bottom="720"')
        P = [merge_runs(p) for p in re.findall(r"<w:p[ >].*?</w:p>", x[bi:x.index("<w:sectPr")], flags=re.S)]
        want = {0: 1, 1: 1, 2: 1, 3: 2, 7: 3, 8: 2, 13: 2, 16: 1, 17: 2, 18: 1, 25: 3}
        for i, n in want.items():
            got = len(re.findall(r"<w:t(?: [^>]*)?>[^<]*</w:t>", P[i]))
            if got != n: raise SystemExit(f"template paragraph {i}: expected {n} text runs after merge, got {got}")
        self.T = dict(name=P[0], contact=P[1], section=P[2], schoolLoc=P[3], degree=P[7], courses=P[8], skill=P[13],
                      org=P[16], titleDate=P[17], bullet=P[18], project=P[25])
        h = P[1].replace('<w:rFonts w:eastAsia="Times New Roman"/></w:rPr>', '<w:rFonts w:eastAsia="Times New Roman"/><w:i/><w:iCs/></w:rPr>')
        if "<w:i/>" not in h: h = h.replace("</w:rPr>", "<w:i/><w:iCs/></w:rPr>", 1)
        self.T["headline"] = h

def fill(tpl, texts):
    it = iter(texts)
    out = re.sub(r"<w:t(?: [^>]*)?>[^<]*</w:t>", lambda m: '<w:t xml:space="preserve">' + esc(next(it)) + "</w:t>", tpl)
    return re.sub(r' w14:paraId="[^"]+"', "", out)

def bullet_xml(T, b):
    """One bullet paragraph. b = text, or {"text", "bold": [terms]} — each term (written exactly in the text, first
    occurrence) becomes a bold run (direction masters, JSA-250); plain text keeps the template run."""
    if isinstance(b, str) or not b.get("bold"):
        return fill(T["bullet"], [b if isinstance(b, str) else b["text"]])
    text, spans = b["text"], []
    for t in b["bold"]:
        i = text.find(t)
        if i >= 0 and not any(i < e and i + len(t) > s0 for s0, e in spans):
            spans.append((i, i + len(t)))
    spans.sort()
    runs, pos = [], 0
    for s0, e in spans:
        if s0 > pos:
            runs.append('<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % esc(text[pos:s0]))
        runs.append('<w:r><w:rPr><w:b/><w:bCs/></w:rPr><w:t xml:space="preserve">%s</w:t></w:r>' % esc(text[s0:e]))
        pos = e
    if pos < len(text):
        runs.append('<w:r><w:t xml:space="preserve">%s</w:t></w:r>' % esc(text[pos:]))
    para = fill(T["bullet"], ["\x00"])
    first = re.search(r"<w:r>.*?</w:r>", para, flags=re.S).group(0)
    return para.replace(first, "".join(runs), 1)


def build_docx(tp, r, head_text, order, path):
    T = dict(tp.T)
    if r.get("a_bullet_after"): T["bullet"] = T["bullet"].replace("</w:numPr>", '</w:numPr><w:spacing w:after="%d"/>' % r["a_bullet_after"], 1)
    if r.get("a_section_before"): T["section"] = T["section"].replace('w:before="80"', 'w:before="%d"' % r["a_section_before"])
    out = [fill(T["name"], [C.NAME]), fill(T["contact"], [C.CONTACT]), fill(T["headline"], [head_text])]
    if r.get("summary"):   # optional 2-line summary (direction masters, JSA-250; asked per candidate and direction)
        out += [fill(T["section"], ["Summary"]), fill(T["skill"], ["", r["summary"]])]
    out.append(fill(T["section"], ["Education"]))
    for e in C.EDU:
        out += [fill(T["schoolLoc"], [e["school"], e["loc"]]), fill(T["degree"], [e["degree"], e["detail"], e["date"]]),
                fill(T["courses"], ["Courses: ", e["courses"]])]
    out.append(fill(T["section"], ["Skills"]))
    for k, v in r["skills"] + r.get("skills_a", []): out.append(fill(T["skill"], [k + ": ", v]))
    def exp():
        out.append(fill(T["section"], ["Internship Experience"]))
        for j in r["exp"]:
            out.extend([fill(T["org"], [j["org"]]), fill(T["titleDate"], [j["title"], j["date"]])])
            out.extend([bullet_xml(T, b) for b in j["bullets"]])
    links = []   # (rId, url) for project titles that link out (direction masters, JSA-250)
    def proj():
        out.append(fill(T["section"], ["Projects"]))
        for p in r["projects"]:
            para = fill(T["project"], [p["title"], " (" + p["tag"] + ")", p["date"]])
            if p.get("url"):
                rid = "rIdLink%d" % (len(links) + 1)
                links.append((rid, p["url"]))
                first = re.search(r"<w:r>.*?</w:r>", para, flags=re.S).group(0)   # the bold title run
                run = first.replace("<w:b/><w:bCs/></w:rPr>", '<w:b/><w:bCs/><w:u w:val="single"/></w:rPr>', 1)
                para = para.replace(first, '<w:hyperlink r:id="%s" w:history="1">%s</w:hyperlink>' % (rid, run), 1)
            out.append(para)
            out.extend([bullet_xml(T, b) for b in p["bullets"]])
    for f in ((proj, exp) if order == ["projects", "exp"] else (exp, proj)): f()
    lead = (C.LEAD if C.LEAD_ON else False) if r.get("lead") is None else r["lead"]   # a direction master brings its own (False = no section, JSA-250); LEAD_ON false = off every resume (JSA-255)
    if lead:
        out += [fill(T["section"], ["Leadership Experience"]), fill(T["org"], [lead["org"]]), fill(T["titleDate"], [lead["title"], lead["date"]])]
        out += [fill(T["bullet"], [b]) for b in (lead.get("bullets") or (C.LEAD["bullets_short"] if r["lead_short"] else C.LEAD["bullets_full"]))]
    doc = tp.head + "".join(out) + tp.tail
    z = dict(tp.zip); z["word/document.xml"] = doc.encode("utf8")
    if links:
        rels = z["word/_rels/document.xml.rels"].decode("utf8")
        add = "".join('<Relationship Id="%s" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" '
                      'Target="%s" TargetMode="External"/>' % (rid, esc(u)) for rid, u in links)
        z["word/_rels/document.xml.rels"] = rels.replace("</Relationships>", add + "</Relationships>").encode("utf8")
    if r.get("a_sz"):
        st = z["word/styles.xml"].decode("utf8")
        st = st.replace('<w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>',
                        '<w:sz w:val="%d"/><w:szCs w:val="%d"/><w:lang w:val="en-US" w:eastAsia="zh-CN" w:bidi="ar-SA"/></w:rPr></w:rPrDefault>' % (r["a_sz"], r["a_sz"]), 1)
        z["word/styles.xml"] = st.encode("utf8")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for n in tp.names: zf.writestr(n, z[n])

def to_pdf(docx, outdir):
    prof = os.path.join(tempfile.gettempdir(), f"lo_ds_profile_{os.getpid()}")   # one profile per process: 4 parallel runs shared one and soffice failed (2026-10-31)
    if elapsed() > BUDGET: raise Pending("build: run time budget reached before PDF conversion")
    try: cp = run(["soffice", "--headless", "-env:UserInstallation=file://" + prof, "--convert-to", "pdf", "--outdir", outdir, docx], timeout=max(15, min(60, 176 - elapsed())))
    except subprocess.TimeoutExpired: raise Pending("build: soffice timed out")
    pdf = os.path.join(outdir, os.path.basename(docx)[:-5] + ".pdf")
    if not os.path.exists(pdf): raise SystemExit("soffice failed: " + (cp.stderr or cp.stdout)[:300])
    return pdf

def pages_of(pdf):
    return int(re.search(r"Pages:\s+(\d+)", run(["pdfinfo", pdf]).stdout).group(1))

def fill_bottom(pdf):
    import numpy as np
    from PIL import Image
    d = tempfile.mkdtemp()
    run(["pdftoppm", "-r", "72", "-gray", "-f", "1", "-l", "1", "-png", pdf, os.path.join(d, "f")])
    f = sorted(os.listdir(d))[0]
    im = np.asarray(Image.open(os.path.join(d, f)))
    rows = np.where((im < 160).sum(1) > 0)[0]
    shutil.rmtree(d, ignore_errors=True)
    return int(rows.min()), int(rows.max())

def resume_text(d, V, with_headline=True):
    rs = d["resume"]; bank = V["bank_by_id"]; pool = V["skill_pool"]
    parts = [headline(d)] if with_headline else []
    parts += [pool[s]["label"] + ": " + pool[s]["text"] for s in rs.get("skill_lines", []) if s in pool]
    for sec in ("exp", "projects"):
        for ids in (rs.get(sec) or {}).values():
            parts += [bank[b]["text"] for b in ids if b in bank]
    parts += list(C.LEAD["bullets_full"]) + [e["school"] + " " + e["degree"] + " " + e["courses"] for e in C.EDU]
    return norm("\n".join(parts))

def docx_bullets(docx):
    x = zipfile.ZipFile(docx).read("word/document.xml").decode("utf8")
    out = []
    for p in re.findall(r"<w:p[ >].*?</w:p>", x, flags=re.S):
        if "<w:numPr>" in p:
            t = unesc("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", p)))
            if not t.startswith("Courses:"): out.append(t)
    return out

# ----------------------------------------------------------------------------- cover letter docx
def build_letter(path, company, job_title, greeting, paras, date_str):
    import docx
    from docx.shared import Pt, Inches, RGBColor
    D = docx.Document()
    s = D.sections[0]
    s.left_margin = s.right_margin = s.top_margin = s.bottom_margin = Inches(0.75)
    s.page_width, s.page_height = Inches(8.5), Inches(11)
    st = D.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11)
    st.element.rPr.rFonts.set(docx.oxml.ns.qn("w:eastAsia"), "Calibri")
    def para(text, size=11, bold=False, color=None, after=9, line=None):
        p = D.add_paragraph(); pf = p.paragraph_format
        pf.space_after = Pt(after); pf.space_before = Pt(0)
        if line: pf.line_spacing = line
        r = p.add_run(text); r.font.name = "Calibri"; r.font.size = Pt(size); r.bold = bold or None
        if color: r.font.color.rgb = RGBColor.from_string(color)
        return p
    para(C.NAME, 18, True, "800000", 0)
    para(C.CONTACT.replace(" | ", "  |  "), 9.5, False, "555555", 12)
    para(date_str, 11, False, None, 10)
    para(f"{company} — {job_title}", 11, True, None, 10)
    para(greeting, 11, False, None, 9, 1.15)
    for t in paras: para(t, 11, False, None, 9, 1.15)
    para("Sincerely,", 11, False, None, 0)
    para(SIGNATURE, 11, False, None, 0)
    D.save(path)

# ----------------------------------------------------------------------------- reports
def where(term, d, V):
    t = norm(term); rs = d["resume"]; bank = V["bank_by_id"]; pool = V["skill_pool"]; loc = []
    if t in norm(headline(d)): loc.append("Headline")
    for s in rs["skill_lines"]:
        if t in norm(pool[s]["label"] + " " + pool[s]["text"]): loc.append("Skills › " + pool[s]["label"])
    for sec in ("exp", "projects"):
        for k, ids in rs[sec].items():
            for b in ids:
                if t in norm(bank[b]["text"]): loc.append(b)
    return "; ".join(loc[:4]) or "—"

def write_keyword_map(path, d, V, company, title):
    L = [f'# Keyword map — {company}, "{title}"', f"Base: {V['track']} · A-Classic · {V['today']}. Gaps are never added. (Generated by ds_materials.py; 'where' is computed locally.)",
         "| JD term (JD order) | true? | where on resume | action |", "| --- | --- | --- | --- |"]
    for r in d["keyword_map"]:
        w = where(r["resume_term"], d, V) if r.get("resume_term") else "—"
        L.append(f"| {r.get('term','')}{'' if r.get('must_have') else ' (nice-to-have)'} | {r.get('true_for_him','')} | {w} | {r.get('action','')} |")
    open(path, "w", encoding="utf8").write("\n".join(L) + "\n")

def write_fit_map(path, d, V, company, title):
    fm = d["fit_map"]
    L = [f"# Fit map — {company}, {title}", f"Resume sent: {V['track']}-based tailored A-Classic. Company fact (from JD): {fm.get('company_fact','')}",
         "| # | Must-have | Story / fact | Strength |", "|---|---|---|---|"]
    for i, r in enumerate(fm["rows"], 1):
        L.append(f"| {i} | {r.get('must_have','')} | {', '.join(r.get('evidence') or [])} | {r.get('strength','')} |")
    used = sorted({u for p in d["cover_letter"]["paragraphs"] for u in p.get("uses", [])})
    L += [f"Motivation: {fm.get('motivation')}.", "Story bank gaps (not invented): " + ("; ".join(fm.get("gaps") or []) or "none"),
          "Used in letter: " + ", ".join(used)]
    open(path, "w", encoding="utf8").write("\n".join(L) + "\n")

def write_resume_report(path, d, V, res, company, title, key, fails=None, warns=None):
    bank = V["bank_by_id"]; base = V["ctx"]["base_resume"]; rs = d.get("resume", {}) if d else {}
    L = [f"# 简历修改报告 — {company}「{title}」", f"基础版本：**{V['track']}**（A-Classic）· {V['today']}",
         f"文件：`{FILE_PREFIX}_Resume_{key}_A-Classic.docx` / `.pdf`" if res else "文件：未生成（验证失败）"]
    if fails:
        L += ["", "## 验证失败 (FAILED)"] + [f"- {x}" for x in fails]
        open(path, "w", encoding="utf8").write("\n".join(L) + "\n"); return
    L.append(f"**为什么选 {V['track']}：** {d.get('base_reason_zh','')}")
    ch = []
    hb, hn = HEADLINES[V["track"]], headline(d)
    ch.append(f"**标题行**：{hn}（原：{hb}）")
    pool = V["skill_pool"]; sb = base["base_skill_lines"]; sn = rs["skill_lines"]
    if sb != sn:
        add = [pool[s]["label"] for s in sn if s not in sb]; rem = [pool[s]["label"] for s in sb if s not in sn]
        ch.append("**Skills**：顺序 " + " → ".join(pool[s]["label"] for s in sn) + (f"；新增 {', '.join(add)}" if add else "") + (f"；删除 {', '.join(rem)}" if rem else ""))
    for sec, items in (("exp", base["experience"]), ("projects", base["projects"])):
        for i in items:
            b0, b1 = i["base_bullets"], rs[sec][i["key"]]
            if b0 == b1: continue
            parts = []
            if set(b1) - set(b0): parts.append("新增 " + "; ".join(f"{x}「{bank[x]['text'][:60]}…」" for x in b1 if x not in b0))
            if set(b0) - set(b1): parts.append("删除 " + "; ".join(f"{x}「{bank[x]['text'][:60]}…」" for x in b0 if x not in b1))
            if set(b0) == set(b1) or not parts: parts.append("顺序：" + " → ".join(b1))
            elif [x for x in b1 if x in b0] != [x for x in b0 if x in b1]: parts.append("顺序：" + " → ".join(b1))
            ch.append(f"**{i['key']} bullets**：" + "；".join(parts))
    if rs["section_order"] != base["base_section_order"]: ch.append("**版块顺序**：" + " → ".join(rs["section_order"]))
    for kind, k, x in (d.get("fill_added") or []):   # JSA-063 page top-up
        ch.append(f"**补满一页**：加回基础版的 {k} bullet {x}「{bank[x]['text'][:60]}…」" if kind == "bullet" else f"**补满一页**：加回基础版的技能行 {pool[x]['label']}")
    L += ["", f"## 改动（共 {len(ch)} 处）"] + [f"{n}. {c}" for n, c in enumerate(ch, 1)]
    L.append("未改：教育、Leadership、字号；其余 bullet 与基础版相同。")
    nonum = [l.strip()[2:].replace("no number: ", "") for l in res["check"].splitlines() if l.strip().startswith("·")]
    L += ["", "## 检查结果",
          f"- 版面：1 页，top={res['top']}，bottom={res['bottom']}（目标 730–756）✓；间距 bullet_after={res['cfg'][0]} section_before={res['cfg'][1]}；check_resume.py：ok",
          "- 所有 bullet 逐字来自 bullet-bank.md（ID 校验 + 对 docx 文本逐条比对）；没写签证身份"]
    if nonum: L.append("- 无数字的 bullet（仅提示）：" + " | ".join(nonum))
    kw = d["keyword_map"]
    L += ["", "## 关键词", "- 已覆盖：" + " · ".join(r["term"] for r in kw if r.get("true_for_him") == "yes"),
          "- 缺口（未添加）：" + (" · ".join(r["term"] for r in kw if r.get("true_for_him") == "no") or "无"),
          "- fit map 缺口：" + ("; ".join(d["fit_map"].get("gaps") or []) or "无")]
    if warns: L += ["", "## 需人工留意"] + [f"- {w}" for w in warns]
    open(path, "w", encoding="utf8").write("\n".join(L) + "\n")

# ----------------------------------------------------------------------------- main
def hsh(*parts): return hashlib.sha1("\x00".join(parts).encode("utf8")).hexdigest()[:12]

def jload(p):
    try: return json.load(open(p, encoding="utf8"))
    except Exception: return None

def run_step(app, name, system, payload, verifyfn, ckpt, meta, fresh, maxtok, st):
    """Reuse a verified checkpoint, else call DeepSeek (+ one re-ask on verification failure). Returns (data, warnings)."""
    cp = os.path.join(app, ckpt)
    if not fresh:
        c = jload(cp)
        if c and c.get("meta") == meta:
            try:
                errs, warns = verifyfn(c["data"])
                if not errs:
                    st["steps_s"][name] = "cached"; return c["data"], warns
            except (Failed, Pending):
                raise
            except Exception:
                pass
    messages = [{"role": "system", "content": system}, {"role": "user", "content": "INPUT (json):\n" + payload}]
    st["prompt_chars"][name] = len(system) + len(payload)
    t = time.time()
    for attempt in (0, 1):
        d, raw = ds_call(messages, maxtok, step=name)
        try: errs, warns = verifyfn(d)
        except (Failed, Pending): raise   # a sentence that still fails after its rewrites blocks the folder (JSA-242)
        except Exception as e: errs, warns = [f"malformed JSON structure: {type(e).__name__} {e}"], []
        if not errs:
            json.dump(dict(meta=meta, data=d), open(cp, "w", encoding="utf8"), ensure_ascii=False, indent=1)
            st["steps_s"][name] = round(time.time() - t, 1); return d, warns
        if attempt == 0:
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": "Your JSON failed local verification. Fix ONLY these problems and return the complete corrected JSON (same schema):\n- " + "\n- ".join(errs[:25])}]
            st["retries"] += 1
    st["steps_s"][name] = round(time.time() - t, 1)
    json.dump(dict(step=name, errors=errs, response=raw), open(os.path.join(app, "ds_failed_response.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    open(os.path.join(app, "ds_last_response.json"), "w", encoding="utf8").write(raw or "")
    raise Failed(errs, name)

def finish(app, st, code, status, step, errors=()):
    st.update(status=status, step=step, elapsed_s=round(elapsed(), 1), deepseek_tokens=USAGE["prompt"] + USAGE["out"],
              cost_est=round(cost(), 4), errors=list(errors)[:25], prompt_tokens=USAGE["prompt"], completion_tokens=USAGE["out"], calls=USAGE["calls"])
    json.dump(st, open(os.path.join(app, "ds_status.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    if USAGE["calls"]:
        with open(os.path.join(app, "ds_usage.md"), "a", encoding="utf8") as f:
            f.write(f"{datetime.date.today()} | {os.path.basename(app)} | {DS_MODEL} | {status}/{step} | calls={USAGE['calls']} | prompt={USAGE['prompt']} (cache-hit {USAGE['hit']}) | completion={USAGE['out']} | est. cost=${cost():.4f} | {st['elapsed_s']}s\n")
    try:   # JSA-412: the build commits the folder it wrote (materials, ds_status, score …) on the spot; best effort
        sys.path.insert(0, os.path.join(ROOT, "scripts", "store"))
        import data_git
        data_git.commit_application(app, f"data: materials {status}/{step} — {os.path.basename(app)}")
    except Exception:
        pass
    sys.exit(code)


def _sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(app, track, res, lpdf, wc, used, company, title):
    """materials_manifest.json — what was produced, with hashes, so a runner can prove the upload matches (2026-10-29)."""
    man = dict(generated_at=datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'), source='ds_materials.py',
               track=track, company=company, title=title)
    rf = os.path.basename(res['pdf'])
    man['resume'] = dict(file=rf, sha256=_sha(os.path.join(app, rf)), docx=os.path.basename(res['docx']),
                         pages=1, bottom=res.get('bottom'), layout=res.get('cfg'), check='pass')
    lf = os.path.basename(lpdf)
    man['letter'] = dict(decision='generated', file=lf, sha256=_sha(os.path.join(app, lf)),
                         words=wc, stories=list(used), fact_check='pass')
    pf = os.path.join(app, 'platform.json')
    if os.path.exists(pf):
        try:
            man['platform'] = json.load(open(pf, encoding='utf-8'))
        except Exception:
            pass
    json.dump(man, open(os.path.join(app, 'materials_manifest.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return man

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app"); ap.add_argument("--track", choices=TRACKS); ap.add_argument("--save-payload", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="ignore ds_step_a.json / ds_step_b.json checkpoints")
    ap.add_argument("--tailor", choices=["auto", "master", "legacy"], default="auto",
                    help="resume source (JSA-251, JSA-388): always the track's approved direction master — auto / master = tailored by tailor.py "
                         "(a failed check → the master unchanged); legacy = the master unchanged, no tailoring. No master → the job fails, never a bank pick")
    a = ap.parse_args()
    app = os.path.abspath(a.app)
    st = dict(status="failed", step="init", steps_s={}, prompt_chars={}, retries=0)
    try:
        run_all(app, a, st)
    except Pending as e:
        print("PENDING: rerun to continue"); print("  reason:", e, "| elapsed %.0fs, checkpoints kept" % elapsed())
        finish(app, st, 3, "pending", st.get("step", "?"), [str(e)])
    except Failed as e:
        print(f"FAILED at step {e.step}. Failures ({len(e.errors)}):"); [print(" -", x[:230]) for x in e.errors[:12]]
        print("  see ds_failed_response.json; DeepSeek tokens", USAGE["prompt"] + USAGE["out"])
        finish(app, st, 1, "failed", e.step, e.errors)
    except SystemExit as e:
        if e.code in (0, None): raise
        print("FAILED:", e.code); finish(app, st, 1, "failed", st.get("step", "?"), [str(e.code)])
    except Exception as e:
        msg = f"{type(e).__name__}: {e}"; print("FAILED:", msg); finish(app, st, 1, "failed", st.get("step", "?"), [msg])

def master_resume(jd, track, company, title, docx_name, tailoring=True):
    """JSA-251: the approved direction master for this track, tailored to the JD by tailor.py and checked by
    truth_check.py (+ layout, check_resume). → None (no approved master for the track) or dict(res=None | the
    ds_materials-shaped result, note, keyword_map, tailored, swaps, terms, changes, direction, approved). When the
    tailored version fails a check, the approved master itself is laid out (never a weaker resume silently)."""
    sys.path.insert(0, os.path.join(ROOT, "skills", "resume-updater", "scripts"))
    import tailor as TL, direction_master as DM
    direction = TL.TRACK_DIRECTION.get(track)
    if not direction:
        return None
    master, mpath = TL.approved_master(direction)
    if not master:
        return None
    import paths as jsa_paths
    fb = json.load(open(jsa_paths.config("facts.json"), encoding="utf-8"))
    role = json.load(open(jsa_paths.role_file(f"{direction}.json"), encoding="utf-8"))   # the data home's rebuilt library first (JSA-278: the repo copy is a stale seed)
    out_docx = os.path.join(tempfile.mkdtemp(prefix="tailor_"), os.path.basename(docx_name))
    r = TL.run(jd, direction, fb, role, master, mpath, title, company, out_docx)
    r.update(direction=direction, approved=mpath)
    if not tailoring:   # JSA-388: the old --tailor legacy (bank pick of the four old role versions) = the approved master as it is
        r.update(ok=False, errs=["tailoring switched off (--tailor legacy)"], changes=[], swaps=[], terms=[],
                 keyword_map=f"# Keyword map — {company}, {title}\n\nNo tailoring (--tailor legacy): the approved {direction} master is used unchanged.\n")
    lr, why = r["res"], ""
    if not r["ok"]:
        why = "; ".join(r["errs"][:3])
        lr, lerr = DM.layout(master, fb, out_docx, TL.order_of(role), {c["id"]: c["weight"] for c in role["competencies"]})
        if lerr:
            r.update(res=None, note=f"resume: tailored {direction} master failed ({why}) and the master itself did not lay out "
                                    f"({lerr}) — no resume built")
            return r
        r["tailored"], r["swaps"] = lr["master"], []
    rd_ = DM.role_dict(lr["master"], fb, C, ["exp", "projects"], lr["cfg"], lr.get("extra") or [])
    r["res"] = dict(docx=lr["docx"], pdf=lr["pdf"], cfg=lr["cfg"], top=lr.get("top", 0), bottom=lr["bottom"], role=rd_,
                    check=lr.get("check") or "")   # write_resume_report reads check / top (JSA-264: KeyError on the first master run)
    tb, ta = TL.coverage(r["terms"], "before"), TL.coverage(r["terms"], "after")
    r["note"] = (f"resume: approved {direction} master tailored by tailor.py (top JD terms on the page {tb[1]}→{ta[1]}/{ta[2]}, "
                 f"{len(r['changes'])} change(s), truth_check pass)" if r["ok"] else
                 f"resume: tailored {direction} master failed ({why}) — the approved master used unchanged; queue for review" if tailoring else
                 f"resume: approved {direction} master used unchanged (--tailor legacy: no tailoring)")
    return r


def run_all(app, a, st):
    jd = rd(os.path.join(app, "jd.md"))
    qpath, npath = os.path.join(app, "questions.json"), os.path.join(app, "notes.md")
    questions = json.loads(rd(qpath)) if os.path.exists(qpath) else []
    notes = rd(npath) if os.path.exists(npath) else ""
    folder = os.path.basename(app.rstrip("/"))
    key = slug(re.sub(r"^\d{4}-\d{2}-\d{2}_", "", folder))
    today = datetime.date.today()
    bank, stories = parse_bank(), parse_stories()
    bank_by_id = {b["id"]: b for b in bank}
    inputs = hsh(jd, notes, json.dumps(questions, sort_keys=True))

    st["step"] = "track"
    track = a.track
    ca = None if a.fresh else jload(os.path.join(app, "ds_step_a.json"))
    if not track and ca and ca.get("meta", {}).get("inputs") == inputs: track = ca["meta"].get("track")
    if not track:   # JSA-194: tested rules decide when the title / JD is clear; DeepSeek only breaks a tie
        import pick_track as PT
        jt = (jload(os.path.join(app, "job.json")) or {}).get("title") or ""
        if not jt:   # no job.json title: the JD's first heading line
            jt = next((l.lstrip("# ").strip() for l in jd.splitlines() if l.strip()), "")[:120]
        pk = PT.pick_track(jt, jd)
        st["track_by"] = ("rules: " if pk["confident"] else "deepseek (rules unsure): ") + pk["reason"]
        if pk["confident"]: track = pk["track"]
    if not track:
        d0, _ = ds_call([{"role": "system", "content": "Pick the best base resume track for a job. Reply JSON {\"track\": one of Data_Engineer|Data_Analyst|Product_Manager|AI_Agentic_Engineer}. Data_Engineer=pipelines/ETL/cloud data; Data_Analyst=analytics/BI/data science/reporting/stats; Product_Manager=product/PM/product analytics/strategy; AI_Agentic_Engineer=LLM/agents/AI engineering."},
                         {"role": "user", "content": scrub(jd)[:4000]}], 200, timeout=40, step="track")
        track = d0.get("track")
        if track not in TRACKS: raise Failed(["could not pick a track; pass --track"], "track")
    ctx, unmatched = build_context(track, bank, stories, jd, notes, questions)
    role, pool, _, _ = base_structure(track)
    corpus = norm("\n".join([b["text"] for b in bank] + list(stories.values()) + [x["text"] for x in pool.values()] + profile_facts() + [notes]))
    V = dict(bank=bank, bank_by_id=bank_by_id, stories=stories, skill_pool=pool, ctx=ctx, jd=ctx["jd"], notes=ctx["notes"],
             profile=ctx["profile_facts"], questions=questions, track=track, base_role=role, today=str(today), corpus=corpus, company_low="")
    pa = json.dumps({k: ctx[k] for k in ("task", "jd", "notes", "base_resume", "skill_pool", "bullet_bank")}, ensure_ascii=False)
    pa = pa[:-1] + ', "story_summaries": ' + json.dumps({k: v[:330] for k, v in ctx["confirmed_stories"].items()}, ensure_ascii=False) + "}"
    assert_payload_clean(pa + RULES + SCHEMA_A + SCHEMA_B)
    if a.save_payload: open(os.path.join(app, "ds_sent_payload.json"), "w", encoding="utf8").write(pa)

    # ---- step A
    st["step"] = "A"
    metaA = dict(inputs=inputs, track=track)
    A, warnsA = run_step(app, "A", RULES_A + "\n\n" + SCHEMA_A, pa, lambda d: verify_a(d, V), "ds_step_a.json", metaA, a.fresh, 4500, st)
    V["company_low"] = norm((A.get("job") or {}).get("company", ""))
    V["company"] = (A.get("job") or {}).get("company", "")

    # ---- step B
    st["step"] = "B"
    sel_b = sorted({b for sec in ("exp", "projects") for v in A["resume"][sec].values() for b in v})
    pb = json.dumps(dict(task="Write the cover letter and answers", jd=ctx["jd"], notes=ctx["notes"], step_a=dict(
        job=A["job"], headline=headline(A), fit_map=A["fit_map"], keyword_gaps=[r.get("term") for r in A["keyword_map"] if r.get("true_for_him") == "no"],
        selected_bullets={b: bank_by_id[b]["text"] for b in sel_b}, selected_skill_lines={s: pool[s]["text"] for s in A["resume"]["skill_lines"]}),
        confirmed_stories=ctx["confirmed_stories"], profile_facts=ctx["profile_facts"], questions=ctx["questions"]), ensure_ascii=False)
    assert_payload_clean(pb)
    metaB = dict(inputs=inputs, a=hsh(json.dumps(A, sort_keys=True)))
    B, warnsB = run_step(app, "B", RULES_B + "\n\n" + SCHEMA_B, pb, lambda d: verify_b_fixed(A, d, V), "ds_step_b.json", metaB, a.fresh, 4000, st)
    d = {**A, **B}
    warns = warnsA + warnsB
    company, title = d["job"].get("company", "?"), d["job"].get("job_title", "?")

    # ---- build
    st["step"] = "build"
    tp = Tpl()
    tmp = tempfile.mkdtemp(prefix="dsmat_")
    t = time.time()
    errs = []
    # JSA-388 (Joey 2026-11-17): the four old role versions are retired — the resume is always the approved direction master
    # (tailored by tailor.py, or unchanged); no bank-pick layout, no added sentences, no font change. See master step below.
    res = None
    lp = os.path.join(tmp, f"{FILE_PREFIX}_Cover_Letter_{slug(company)}.docx")
    build_letter(lp, company, title, d["cover_letter"]["greeting"], [p["text"] for p in d["cover_letter"]["paragraphs"]], today.strftime("%B %-d, %Y"))
    lpdf = to_pdf(lp, tmp)
    if pages_of(lpdf) != 1: errs.append(f"cover letter is {pages_of(lpdf)} pages, must be 1: shorten it")
    st["steps_s"]["build"] = round(time.time() - t, 1)
    if errs:
        write_resume_report(os.path.join(app, "resume_report.md"), d, V, None, company, title, key, fails=errs)
        json.dump(dict(step="build", errors=errs, response=d), open(os.path.join(app, "ds_failed_response.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
        raise Failed(errs, "build")
    # ---- resume from the approved direction master (JSA-251): tailor.py replaces the bank pick when it passes
    master_run = master_resume(jd, track, company, title, os.path.join(tmp, f"{FILE_PREFIX}_Resume_{key}_A-Classic.docx"),
                               tailoring=getattr(a, "tailor", "auto") != "legacy")
    if master_run and master_run.get("res"):
        res = master_run["res"]
        warns.append(master_run["note"])
    else:   # no approved master for the track, or it does not lay out: never a bank pick — the job is queued with the reason
        why = (master_run or {}).get("note") or f"no approved direction master for track {track}"
        errs = [why]
        write_resume_report(os.path.join(app, "resume_report.md"), d, V, None, company, title, key, fails=errs)
        json.dump(dict(step="tailor", errors=errs, response=d), open(os.path.join(app, "ds_failed_response.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
        raise Failed(errs, "tailor")
    # ---- write outputs
    out = lambda n: os.path.join(app, n)
    shutil.copyfile(res["docx"], out(os.path.basename(res["docx"]))); shutil.copyfile(res["pdf"], out(os.path.basename(res["pdf"])))
    shutil.copyfile(lp, out(os.path.basename(lp))); shutil.copyfile(lpdf, out(os.path.basename(lpdf)))
    r = res["role"]; r["lead_short_b"] = True; r["drop_b"] = []
    if master_run and master_run.get("res"):
        open(out("keyword_map.md"), "w", encoding="utf8").write(master_run["keyword_map"])
        json.dump(dict(tailored=dict(master_run["tailored"], swaps=master_run["swaps"]), changes=master_run["changes"],
                       terms=master_run["terms"], direction=master_run["direction"], approved=master_run["approved"]),
                  open(out("tailored.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    json.dump(dict(NAME=C.NAME, CONTACT=C.CONTACT, EDU=C.EDU, LEAD=C.LEAD, LEAD_ON=C.LEAD_ON, ROLES={key: r}), open(out("content.json"), "w", encoding="utf8"), ensure_ascii=False, indent=1)
    cover = d["cover_letter"]["greeting"] + "\n\n" + "\n\n".join(p["text"] for p in d["cover_letter"]["paragraphs"]) + "\n\nSincerely,\n" + SIGNATURE + "\n" + C.CONTACT + "\n"
    open(out("cover.txt"), "w", encoding="utf8").write(cover)
    write_keyword_map(out("keyword_map_legacy.md" if master_run and master_run.get("res") else "keyword_map.md"), d, V, company, title)
    write_fit_map(out("fit_map.md"), d, V, company, title)
    write_resume_report(out("resume_report.md"), d, V, res, company, title, key, warns=warns + ([f"{len(unmatched)} base bullet(s) not found in bullet-bank (kept as '?'): " + "; ".join(u[:50] for u in unmatched)] if unmatched else []))
    if master_run and master_run.get("res"):   # the PDF is the tailored master: say so above the bank-pick report
        rp = out("resume_report.md")
        head = ["# Resume source (JSA-251)", "", master_run["note"], "",
                "The PDF is the approved direction master with mechanical changes only (see keyword_map.md); the DeepSeek bank "
                "selection below is not on the PDF (kept for comparison, keyword_map_legacy.md).", "", "## Tailoring changes", ""]
        head += [f"- {c}" for c in master_run["changes"]] or ["- none"]
        open(rp, "w", encoding="utf8").write("\n".join(head) + "\n\n" + open(rp, encoding="utf8").read())
    qa = ["# Open answers (DeepSeek draft; verified against the story bank)"]
    for q in questions:
        an = next(x for x in d["answers"] if x["id"] == q["id"])
        qa += ["", f"## {q['id']} — {q['label']}", f"limit: {q.get('limit')} {q.get('unit', 'characters')} · length: {len(an['text'])} · uses: {', '.join(an.get('uses') or [])}"
               + (f" · note: {an['note']}" if an.get("note") else ""), "", an["text"]]
    if not questions: qa.append("\n(no questions.json)")
    open(out("open_answers.md"), "w", encoding="utf8").write("\n".join(qa) + "\n")
    wc = len(re.findall(r"[\w'’-]+", "\n\n".join(p["text"] for p in d["cover_letter"]["paragraphs"])))
    used = sorted({u for p in d["cover_letter"]["paragraphs"] for u in p.get("uses", [])} | {u for x in d["answers"] for u in x.get("uses", [])})
    ch = [l for l in open(out("resume_report.md"), encoding="utf8").read().splitlines() if re.match(r"^\d+\. ", l)]
    write_manifest(app, track, res, lpdf, wc, used, company, title)
    try:   # JSA-194: one materials_score.json per folder (coverage, base, bullet IDs, letter checks); never blocks the build
        sys.path.insert(0, os.path.join(ROOT, "scripts", "store"))
        import materials_score as MS; MS.write_folder(app)
    except Exception as e:
        print("materials_score skipped:", e)
    print(f"OK {company} — {title}")
    print(f"base: {track}; headline: {headline(d)}")
    print(f"resume changes ({len(ch)}):"); [print("  " + c[:150]) for c in ch[:4]]
    print(f"layout: 1 page, bottom={res['bottom']} (730-756), spacing {res['cfg']}, check_resume ok")
    print(f"letter: {wc} words, 1 page; stories: {', '.join(used)}")
    print(f"verification: PASS (IDs, exact bank text, numbers, banned words, no J-IDs/visa/contact, limits); re-asks={st['retries']}")
    if warns: print(f"warnings ({len(warns)}): " + " | ".join(w[:80] for w in warns[:2]))
    print(f"prompt chars {st['prompt_chars']}; steps_s {st['steps_s']}")
    finish(app, st, 0, "ok", "done")

if __name__ == "__main__":
    main()
