"""Company name -> H-1B employer facts: the one matcher build_jobs.py, append_new.py and the store fix share (JSA-098).

The DOL / USCIS files name the legal entity ("WAL-MART ASSOCIATES, INC.", "Verizon Data Services LLC",
"Fidelity Technology Group, LLC d/b/a Fidelity Investments"); postings name the brand ("Walmart Global Tech",
"Verizon Communications", "Fidelity"). One employer must resolve to one family of filings:
  1. norm(): lower case, & -> and, drop .com, punctuation and legal / generic suffixes (inc, llc, group, global, ...).
  2. every employer name is indexed under each d/b/a part, and under a joined first pair when the first token is
     short ("wal mart associates" -> also "walmart associates"; "jp morgan chase" -> also "jpmorgan chase").
  3. lookup: ENTITIES (h1b_names.json: posting name -> its exact employer keys), else ALIASES (brand -> root, e.g.
     "walmart global tech" -> "walmart", "verizon communications" -> "verizon"), then the root itself plus every employer
     key that starts with "<root> ". A single GENERIC word ("north", "american") never takes a prefix family; any other
     single word takes one only when it is in FAMILIES or every candidate shares one next word (JSA-103: "Revel" is
     not "Revel Systems" + "Revel Consulting").
  4. no hit -> drop trailing listing noise ("five rings careers" -> "five rings") and look again.
  group_key() (ALIASES + the same drop) is the key two company rows share when they are one employer.
Spec: scripts/test_cases/h1b_match_spec.md.
"""
import csv, json, os, re, collections

SUFFIX = r"\b(inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|limited|plc|lp|llp|holdings?|group|the|usa|us|america|na|n\.a|services|technologies|technology|labs?|global|international)\b"
# page / listing noise a source appends to the name ("a Greenhouse employer LLC - Careers"); dropped when the full name has no filings
DESCRIPTORS = {"careers", "jobs", "hq", "hiring", "recruiting"}
# single words that name no employer on their own: exact match only, never "<word> ..." prefix families
GENERIC = {"american", "america", "north", "south", "east", "west", "national", "united", "general", "first", "new",
           "global", "state", "university", "city", "county", "advanced", "applied", "integrated", "digital",
           "data", "smart", "premier", "capital", "central", "pacific", "atlantic", "western", "eastern", "southern",
           "northern", "midwest", "texas", "california", "virginia", "florida", "york", "allied", "advantage", "building",
           "ryan", "parallel", "realm", "leland", "bank", "insurance", "health", "energy", "financial", "consulting"}
# brand -> root of its filing family (a tuple = several roots; "=root" = that key only, no prefix family). Unit / product names map to the parent only when the filings are the
# parent's (checked against the DOL names on 2026-11-03, JSA-098); "Hewlett Packard" is HP Inc., not HPE.
VERIZON = ("verizon", "cellco partnership")   # Cellco Partnership d/b/a Verizon Wireless
ALIASES = {"meta": "meta platforms", "facebook": "meta platforms", "alphabet": "google", "aws": "amazon",
           "amazon web services": "amazon", "jp morgan": "jpmorgan", "jpmorganchase": "jpmorgan", "jpmorgan chase": "jpmorgan",
           "ibm": ("=ibm", "international business machines"), "pwc": "pricewaterhousecoopers",
           "ey": "ernst and young", "ernst young": "ernst and young", "deloitte consulting": "deloitte",
           "walmart global tech": "walmart", "walmart tech": "walmart", "sam s club": "walmart",
           "verizon": VERIZON, "verizon communications": VERIZON, "verizon wireless": VERIZON, "cellco partnership": VERIZON,
           "telus digital": "telus", "ul solutions": "ul", "zt systems": "zt", "veeam software": "veeam",
           "virginia tech": "virginia polytechnic institute", "hewlett packard": "hp", "citi": "citibank",
           "citigroup": "citibank", "bofa": ("=bank of", "bofa"),
           "applied": "applied intuition"}   # the store's "Applied" is the Ashby board jobs.ashbyhq.com/applied
# brands whose suffix-free form is a generic word ("Capital Group" -> "capital"): matched on the name before
# suffixes are dropped; a tuple = several legal entities of one employer
RAW_ALIASES = {"bank of america": ("=bank of", "bofa"), "us bank": ("u s bank",),   # norm() drops "america": "bank of" alone, never "bank of ..."
               "capital group": ("capital companies", "capital research and management"),
               "capital group companies": ("capital companies", "capital research and management")}
# FAMILIES / ENTITIES / NOT_FAMILY live in h1b_names.json (JSA-103): one-word brands with a checked filing family,
# posting names pinned to their exact employer keys, and employer keys that share a brand's first word but are another firm
_NAMES = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "h1b_names.json"), encoding="utf-8"))
FAMILIES = set(_NAMES["families"])
ENTITIES = {k: tuple("=" + e for e in v) for k, v in _NAMES["entities"].items()}
NOT_FAMILY = set(_NAMES["not_family"])
DBA = re.compile(r"\s+(?:d\s*/?\s*b\s*/?\s*a|doing business as|aka|a/k/a)\.?\s+", re.I)


def raw(c):
    """lower case, & -> and, punctuation -> space; suffixes kept"""
    c = (c or "").lower().replace("&", " and ")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", c)).strip()


def norm(c):
    c = (c or "").lower().replace("&", " and ")
    c = re.sub(r"\.com\b", "", c)
    c = re.sub(r"[^a-z0-9 ]+", " ", c)
    c = re.sub(r"\bn a\b", " ", c)   # "N.A." after punctuation is gone ("Citibank, N.A.", "BANK OF AMERICA N.A.")
    c = re.sub(SUFFIX, " ", c)
    return re.sub(r"\s+", " ", c).strip()


def name_keys(name):
    """Every key one employer name is indexed under."""
    out = []
    for part in DBA.split(name or ""):
        k = norm(part)
        if not k:
            continue
        out.append(k)
        t = k.split()
        if len(t) >= 2 and len(t[0]) <= 4:
            out.append(" ".join([t[0] + t[1]] + t[2:]))
    return list(dict.fromkeys(out))


def strip_descriptors(k):
    t = k.split()
    while len(t) > 1 and t[-1] in DESCRIPTORS:
        t.pop()
    return " ".join(t)


def group_key(company):
    """The key two company rows share when they are one employer (alias rows merge on it)."""
    def root(v):
        return (v if isinstance(v, str) else v[0]).lstrip("=")
    if raw(company) in RAW_ALIASES:
        return root(RAW_ALIASES[raw(company)])
    k = root(ALIASES.get(norm(company), norm(company)))
    s = strip_descriptors(k)
    return root(ALIASES.get(s, s))


# rows whose names normalise alike but are different employers (never merged)
NOT_SAME = {frozenset({"Brunswick", "Brunswick Group"}), frozenset({"Sentinel Group", "Sentinel Technologies"}),
            frozenset({"Astera", "Astera Labs"})}


class H1B:
    def __init__(self, records):
        """records: iterable of {"name", "fy25", "total", "first"} (one per source row; same names add up)."""
        self.emp = {}                                  # canonical employer key -> facts
        self.index = collections.defaultdict(set)      # lookup key -> employer keys
        self.by_first = collections.defaultdict(set)   # first token -> lookup keys
        for r in records:
            keys = name_keys(r["name"])
            if not keys:
                continue
            e = self.emp.setdefault(keys[0], {"name": r["name"], "fy25": 0, "total": 0, "first": None})
            e["fy25"] += r.get("fy25") or 0
            e["total"] += r.get("total") or 0
            if r.get("first") and r["first"] < 9999:
                e["first"] = min(e["first"] or 9999, r["first"])
            for k in keys:
                self.index[k].add(keys[0])
                self.by_first[k.split()[0]].add(k)
        self._cache = {}

    def _hits(self, k):
        if not k:
            return set()
        only = k.startswith("=")
        k = k.lstrip("=")
        keys = {k} if k in self.index else set()
        n = len(k.split())
        if len(k) > 3 and k not in GENERIC and not only:
            # "<brand> IT ..." is an IT staffing firm that shares the word, not the brand ("Lumen IT Services")
            fam = {h for h in self.by_first.get(k.split()[0], ()) if h.startswith(k + " ") and h.split()[n] != "it" and h not in NOT_FAMILY}
            # one word that is not a checked family: the "<word> X ..." filers must all be one "X", else it is ambiguous
            if n == 1 and k not in FAMILIES and len({h.split()[1] for h in fam}) > 1:
                fam = set()
            keys |= fam
        return set().union(*[self.index[h] for h in keys]) if keys else set()

    def lookup(self, company):
        k0, ck = norm(company), raw(company)   # cache on the raw name: ENTITIES / RAW_ALIASES tell "Frontier Technology" from "Frontier"
        if ck in self._cache:
            return self._cache[ck]
        roots = ENTITIES[ck] if ck in ENTITIES else ENTITIES.get(k0)
        if roots is not None and not roots:
            res = {"fy25": 0, "total": 0, "first": None, "match": "none", "names": [], "key": k0}
            self._cache[ck] = res
            return res
        roots = roots or RAW_ALIASES.get(raw(company)) or ALIASES.get(k0, k0)
        if isinstance(roots, str):
            roots = (roots,)
        hits = set().union(*[self._hits(r) for r in roots])
        k = roots[0].lstrip("=")
        while not hits:
            s = strip_descriptors(k)
            s = ALIASES.get(s, s)
            s = (s if isinstance(s, str) else s[0]).lstrip("=")
            if s == k:
                break
            k = s
            hits = self._hits(k)
        res = {"fy25": 0, "total": 0, "first": None, "match": "none", "names": [], "key": k}
        for h in sorted(hits, key=lambda h: -(self.emp[h]["fy25"] + self.emp[h]["total"])):
            e = self.emp[h]
            res["fy25"] += e["fy25"]; res["total"] += e["total"]
            if e["first"]:
                res["first"] = min(res["first"] or 9999, e["first"])
            res["names"].append(e["name"])
        if hits:
            res["match"] = "exact" if k0 in self.index and k == k0 else "alias" if k != k0 else "prefix"
        res["names"] = res["names"][:4]
        self._cache[ck] = res
        return res


def sponsor_label(h):
    return ("Strong H-1B sponsor" if (h["fy25"] or 0) >= 100 or (h["total"] or 0) >= 1000 else
            "Some H-1B history" if (h["fy25"] or h["total"]) else "Unknown — verify")


H1B_LABELS = ("Strong H-1B sponsor", "Some H-1B history", "Unknown — verify")


def records_from(src):
    """The two cloned data repos under src/ -> records for H1B(). Missing files give no records."""
    out = []
    p = f"{src}/flexapply_companies-that-sponsor-h1b/data/h1b-sponsors-fy2025.json"
    if os.path.exists(p):
        for r in json.load(open(p)):
            out.append({"name": r["name"], "fy25": r.get("lcas", 0) or 0, "total": 0, "first": None})
    p = f"{src}/sergyinfo_h1b-open-data/employers_summary.csv"
    if os.path.exists(p):
        for r in csv.DictReader(open(p)):
            out.append({"name": r["employer_name"], "fy25": 0, "total": int(float(r["total_filings"] or 0)),
                        "first": int(r["first_fy"] or 9999)})
    return out
