"""Pure (tested: test/t_posting.py). The one place that decides, for a batch job, which URL is the posting and which
platform that URL is on (JSA-331 / JSA-332, Joey 2026-11-12: one shared module instead of copies).

  posting_url(job)  → the job's `ats_url` (the real ATS page the gate resolved), else its `url` (may be an aggregator
                      or LinkedIn link). Every prep script and batch_apply look jobs up by this, never by `url` alone.
  platform(url)     → 'greenhouse' / 'ashby' / 'lever' / 'workday' / 'oracle' / 'smartrecruiters' / 'successfactors' /
                      'icims' / 'workable' / ''.
  lever_parse(url)  → (site, uuid) of a Lever posting, or None. Tolerates a percent-encoded / stray space around the
                      site slug (`jobs.lever.co/Xpansiv%20/<uuid>`).
"""
import re
from urllib.parse import unquote

HOSTS = (('greenhouse.io', 'greenhouse'), ('gh_jid=', 'greenhouse'), ('ashbyhq.com', 'ashby'),
         ('lever.co', 'lever'), ('myworkdayjobs.com', 'workday'), ('myworkdaysite.com', 'workday'),
         ('oraclecloud.com', 'oracle'), ('smartrecruiters.com', 'smartrecruiters'),
         ('successfactors', 'successfactors'), ('sapsf.com', 'successfactors'), ('icims.com', 'icims'),
         ('jibeapply.com', 'icims'), ('icims=1', 'icims'), ('workable.com', 'workable'))

# SuccessFactors RMK career site on the company's own domain (JSA-170): /job/<slug>/<8-12 digit id>/, optionally after
# one locale / region segment (careers.arthrex.com/NorthAmerica/job/…/1374001457/, JSA-332).
SF_RMK = re.compile(r'^https?://[^/]+/(?:[^/?#]+/)?job/[^/?#]+/\d{8,12}/?(?:[?#]|$)', re.I)
NOT_SF = ('builtin.com', 'linkedin.com')

LEVER = re.compile(r'jobs\.(?:eu\.)?lever\.co/\s*([\w.-]+)\s*/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', re.I)


def posting_url(job):
    """The URL to look the posting up by: `ats_url` when set (non-blank), else `url`."""
    job = job or {}
    return (str(job.get('ats_url') or '').strip() or str(job.get('url') or '').strip())


def platform(url):
    u = (url or '').strip().lower()
    for key, name in HOSTS:
        if key in u:
            return name
    if SF_RMK.search(u) and not any(h in u for h in NOT_SF):
        return 'successfactors'
    return ''


def lever_parse(url):
    m = LEVER.search(unquote(str(url or '')))
    return (m.group(1), m.group(2).lower()) if m else None
