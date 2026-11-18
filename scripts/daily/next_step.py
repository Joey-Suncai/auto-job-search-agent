"""A concrete next step for the tracker's "Action needed" (JSA-265, Joey 2026-11-09: 「我想让 dashboard 的 application 里面的
action needed 能够清晰的讲下一步做什么，而不是让我自己去读邮件」).

Pure functions (spec: scripts/test_cases/next_step_spec.md, cases by DeepSeek, harness scripts/daily/test_next_step.py):
  is_vague(text)                              — True for an empty or generic line ("Read the email and act — see the link")
  rules_action(kind, subject, body, date)     — the step the keyword path writes when no model read the mail:
                                                {"action", "deadline" (YYYY-MM-DD or ""), "reread"}
The Claude reader (claude_reader.py) writes the step itself; these are the fallback and the vagueness check.
"""
import datetime, math, re

FILLER = set("read open check see the a an email mail message link it and act on take action follow instructions in as "
             "needed please accordingly respond your to do what asks".split())
OLD_GENERIC = "Read the email and act — see the link"      # the line this replaced; the backfill looks for it


def is_vague(text):
    words = re.sub(r"[^\w ]|_", " ", (text or "").lower()).split()
    return not [w for w in words if w not in FILLER]


ACTIONABLE = ("Assessment", "Interview", "Offer", "Action")
NUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}
MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
MON = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
CUE = r"(?:no later than|deadline:?|expires(?: on)?|until|before|due|by)"
DATE_FORMS = [
    (rf"{MON}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?", "mdy_name"),
    (r"(\d{4})-(\d{2})-(\d{2})", "iso"),
    (r"(\d{1,2})/(\d{1,2})(?:/(\d{4}))?", "mdy_num"),
]


def _date(kind, g, msg):
    try:
        if kind == "iso":
            return datetime.date(int(g[0]), int(g[1]), int(g[2]))
        if kind == "mdy_name":
            mo, d, y = MONTHS[g[0][:3].lower()], int(g[1]), g[2]
        else:
            mo, d, y = int(g[0]), int(g[1]), g[2]
        if y:
            return datetime.date(int(y), mo, d)
        x = datetime.date(msg.year, mo, d)
        return x if x >= msg else datetime.date(msg.year + 1, mo, d)
    except (ValueError, KeyError):
        return None


def find_deadline(text, date):
    msg = datetime.date.fromisoformat(date)
    out = []
    n = r"(\d+|" + "|".join(NUM) + r")"
    for m in re.finditer(rf"\bwithin\s+(?:the\s+next\s+)?{n}\s+(business\s+|working\s+)?(days?|hours?|hrs?)\b", text, re.I):
        k = int(m.group(1)) if m.group(1).isdigit() else NUM[m.group(1).lower()]
        if m.group(3).lower().startswith("d"):
            if m.group(2):
                d, left = msg, k
                while left:
                    d += datetime.timedelta(days=1)
                    left -= d.weekday() < 5
                out.append(d)
            else:
                out.append(msg + datetime.timedelta(days=k))
        else:
            out.append(msg + datetime.timedelta(days=math.ceil(k / 24)))
    for rx, kind in DATE_FORMS:
        for m in re.finditer(rf"\b{CUE}\s+(?:\w+day,?\s+)?(?:the\s+)?{rx}", text, re.I):
            d = _date(kind, m.groups(), msg)
            if d:
                out.append(d)
    ok = sorted(d for d in out if d >= msg)
    return ok[0].isoformat() if ok else ""


PLATFORMS = ["HackerRank", "CodeSignal", "HireVue", "Codility", "CoderPad", "Coderbyte", "Karat", "Pymetrics", "SHL", "Plum",
             "Mettl", "TestGorilla", "Glider", "Arctic Shores", "Criteria", "Pathstream", "Vervoe"]


def find_platform(text):
    hits = [(m.start(), p) for p in PLATFORMS for m in [re.search(rf"\b{re.escape(p)}\b", text, re.I)] if m]
    return min(hits)[1] if hits else "online"


def find_duration(text):
    for m in re.finditer(r"(\bwithin\s+)?\b(\d+)(?:\s+|-)(minutes?|mins?|hours?)\b", text, re.I):
        if m.group(1):
            continue
        return f"{m.group(2)} {'h' if m.group(3).lower().startswith('h') else 'min'}"
    return ""


REQUEST = re.compile(r"\b(please|kindly|you need to|you must|required to)\b", re.I)
IMPERATIVE = re.compile(r"^(complete|submit|provide|upload|log in|sign|fill out|confirm|reply|respond|schedule|verify|access|review)\b", re.I)


def request_sentence(body):
    for s in re.split(r"(?<=[.!?])\s+", " ".join((body or "").split())):
        if REQUEST.search(s) or IMPERATIVE.match(s):
            s = re.sub(r"https?://\S*", "", s)
            s = re.sub(r"^(hi|hello|hey|dear)\b[^,]{0,40},\s*", "", s.strip(), flags=re.I)
            s = re.sub(r"^(please|kindly)\s+", "", s, flags=re.I)
            s = " ".join(s.split()).rstrip(" :,")
            if not s:
                continue
            s = s[0].upper() + s[1:]
            if len(s) > 160:
                s = s[:s.rfind(" ", 0, 160)] + "…"
            return s
    return ""


def rules_action(kind, subject, body, date):
    if kind not in ACTIONABLE:
        return {"action": "", "deadline": "", "reread": False}
    text = f"{subject or ''} {body or ''}"
    out = {"action": "", "deadline": find_deadline(text, date), "reread": False}
    if kind == "Assessment":
        d = find_duration(text)
        out["action"] = f"Complete the {find_platform(text)} assessment" + (f" ({d})" if d else "") + " via the link in the email"
    elif kind == "Interview":
        if re.search(r"calendly|goodtime|schedule|book a time|select a time|pick a time|time slot", text, re.I):
            out["action"] = "Book an interview time via the scheduling link in the email"
        elif re.search(r"availability|available times", text, re.I):
            out["action"] = "Reply with your availability for the interview"
        else:
            out["action"] = "Reply to confirm the interview"
    elif kind == "Offer":
        out["action"] = "Review the offer and reply to the recruiter"
    else:
        s = request_sentence(body)
        if s:
            out["action"] = s
        else:
            out.update(action=f'Open the email "{(subject or "")[:80]}" and do what it asks — not read automatically yet', reread=True)
    return out
