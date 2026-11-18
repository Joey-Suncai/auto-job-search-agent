"""Health of the Claude mail reader (JSA-280 ①, the root cause behind JSA-266).

On 11-05 / 06 the Anthropic credit ran out and every claude_reader call returned 400 for days; the only sign was one
line in the normal push. Every email / SMS run now records how its Claude reads went in
data/runner/daily/reader_health.json (shared by email_check.py and sms_check.py):

  {"ok": bool, "since": "<first failure of this outage, ISO time>", "fails": <failed reads since>,
   "cause": "credit|auth|error", "error": "<last message>", "last_ok": "<ISO time>", "alerted": "<since of the alerted outage>"}

Joey 2026-11-10 (JSA-280 ①): one notification, once the reads have failed for more than ALERT_HOURS in a row — it names
the cause (credit balance / API key / other). One good read ends the outage; a run with no read leaves the state as is.
"""
import datetime, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "config"))
import paths as jpaths  # noqa: E402

ALERT_HOURS = 2
CREDIT = re.compile(r"credit balance is too low|insufficient credit", re.I)
AUTH = re.compile(r"authentication|invalid x-api-key|api key|unauthori[sz]ed|forbidden|permission denied", re.I)
WHY = {"credit": "Anthropic 额度用完（credit balance is too low）— 去 console.anthropic.com → Billing 充值",
       "auth": "Anthropic API key 无效或缺失（Keychain jobagent-anthropic）",
       "error": "Claude API 一直出错"}


def path():
    return jpaths.data("runner", "daily", "reader_health.json")


def cause_of(err):
    """Pure (tested). 'credit' · 'auth' · 'error' for an exception (or its text)."""
    name = type(err).__name__ if isinstance(err, BaseException) else ""
    text = f"{name} {err}"
    if CREDIT.search(text):
        return "credit"
    if name in ("AuthenticationError", "PermissionDeniedError", "LookupError") or AUTH.search(text):
        return "auth"
    return "error"


def update(state, fails, oks, now):
    """Pure (tested). fails = this run's failed reads (exceptions or texts), oks = good reads, now = aware datetime.
    Returns (new state, alert) — alert = (title, body) to push now, or None."""
    s = dict(state or {})
    stamp = now.isoformat(timespec="seconds")
    if oks:                                  # one good read = the reader is up (a single refused message is no outage)
        s = {"ok": True, "fails": 0, "last_ok": stamp}
        return s, None
    if not fails:
        return s, None                       # nothing read this run: no news either way
    if s.get("ok", True) or not s.get("since"):
        s.update(since=stamp, fails=0)
        s.pop("alerted", None)
    last, n = fails[-1], s.get("fails") or 0
    n = len(n) if isinstance(n, list) else int(n)
    s.update(ok=False, cause=cause_of(last), error=str(last)[:300], fails=n + len(fails))
    since = datetime.datetime.fromisoformat(s["since"])
    if now - since <= datetime.timedelta(hours=ALERT_HOURS) or s.get("alerted") == s["since"]:
        return s, None
    s["alerted"] = s["since"]
    body = (f"{WHY[s['cause']]}。自 {s['since'][:16].replace('T', ' ')} 起 {s['fails']} 次读信失败：{str(last)[:120]}\n"
            "这期间新信只记为「待读」，不改申请阶段；恢复后自动重读。")
    return s, ("⚠️ 读信暂停超过 2 小时", body)


def load(p=None):
    try:
        return json.load(open(p or path()))
    except (OSError, ValueError):
        return {}


def save(state, p=None):
    p = p or path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w") as f:
        json.dump(state, f, indent=1, ensure_ascii=False, sort_keys=True)
    os.replace(p + ".tmp", p)


def record(fails, oks, now=None, p=None, push=True, notify=None):
    """Load → update → save; pushes the alert (if any). Returns the alert or None."""
    now = now or datetime.datetime.now().astimezone()
    s, alert = update(load(p), fails, oks, now)
    save(s, p)
    if alert and push:
        if notify is None:
            from notify import notify
        notify(*alert)
    return alert


class Tracked:
    """Wraps a reader: counts good reads and keeps the failures for record(). A reader that is not available at all
    (no key / no SDK) is passed as `down` — every read raises with that reason, so the mail waits as Pending."""

    def __init__(self, reader=None, down=None):
        self.reader, self.down, self.fails, self.oks = reader, down, [], 0
        self.usage = getattr(reader, "usage", {"calls": 0, "input": 0, "cache_read": 0, "output": 0})

    def read(self, m):
        try:
            if self.reader is None:
                raise self.down
            v = self.reader.read(m)
        except Exception as e:
            self.fails.append(e)
            raise
        self.oks += 1
        return v
