# posting — which URL a batch job uses, and which platform a URL is on

A batch job is a dict with at least `url` (string; may be an aggregator link like zapply.jobs, wellfound.com,
simplify.jobs, or a LinkedIn link) and optionally `ats_url` (string; the real applicant-tracking-system page).

## posting_url(job) -> str
Returns `ats_url` with surrounding whitespace removed when it is present and not blank; otherwise `url` with
surrounding whitespace removed; otherwise "" (missing keys, None values, None job).

## platform(url) -> str
Case-insensitive. Checked in this order; the first substring found wins:
greenhouse.io → greenhouse; gh_jid= → greenhouse; ashbyhq.com → ashby; lever.co → lever; myworkdayjobs.com → workday;
myworkdaysite.com → workday; oraclecloud.com → oracle; smartrecruiters.com → smartrecruiters; successfactors →
successfactors; sapsf.com → successfactors; icims.com → icims; jibeapply.com → icims; icims=1 → icims; workable.com → workable.
If none matches: a SuccessFactors RMK career page on a company's own domain → successfactors. Its shape is
scheme://host/job/<slug>/<id>/ where <id> is 8 to 12 digits, the trailing slash is optional, and the URL may end there or
continue with ?query or #fragment (but not with more path). Between the host and "job" there may be at most ONE extra path
segment (a locale or region, e.g. /NorthAmerica/job/... or /en_US/job/...); two or more extra segments do not count.
Hosts builtin.com and linkedin.com never count as SuccessFactors this way. Anything else → "" (empty string). None or "" → "".

## lever_parse(url) -> [site, uuid] or None
A Lever posting URL is jobs.lever.co/<site>/<uuid> or jobs.eu.lever.co/<site>/<uuid>, optionally followed by /apply or
anything else. <site> is letters, digits, underscore, dot, hyphen. <uuid> is the standard 8-4-4-4-12 hex form; it is
returned in lower case. The URL is percent-decoded first, and spaces right before or after <site> are ignored
(jobs.lever.co/Xpansiv%20/<uuid> → site "Xpansiv"). The site keeps its original case. Not a Lever posting (other host,
no uuid, malformed uuid) → None.
