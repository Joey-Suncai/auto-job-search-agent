# Runner status of a job row for the dashboard — spec (2026-11-05, JSA-177)

`runner_status(platform)` maps a platform name (lower-case string) or null to one of four values:
- "ready" — platforms with a certified runner: greenhouse, workday, ashby, lever;
- "testing" — platforms with a runner that is not certified yet: oracle, smartrecruiters, workable, successfactors
  (submit path) and icims, jibe, tiktok (dry run only);
- "none" — any other known platform name (e.g. rippling, ukg, adp, dayforce, jazzhr, paylocity, taleo, bamboohr);
- "unknown" — platform is null or the empty string.

`runner_fields(row)` takes a job row (a dict that may have "ats_url" and "url") and returns
{"platform": <name or "">, "runner": <runner_status of that name>}. The platform is found from "ats_url" first, then
"url", by the host name: greenhouse.io → greenhouse, myworkdayjobs.com / myworkdaysite.com → workday, ashbyhq.com →
ashby, lever.co → lever, oraclecloud.com → oracle, smartrecruiters.com → smartrecruiters, workable.com → workable,
successfactors.com / successfactors.eu / sapsf.com → successfactors, icims.com → icims, jibeapply.com → jibe,
rippling.com → rippling, lifeattiktok.com / careers.tiktok.com → tiktok, joinbytedance.com / jobs.bytedance.com → bytedance
(a known platform without a runner), ultipro.com / ukg.net → ukg, adp.com → adp, dayforcehcm.com → dayforce (subdomains count, e.g.
boards.greenhouse.io, acme.wd5.myworkdayjobs.com). A row whose URLs match none of these (linkedin.com, wellfound.com, a
company's own careers page, empty or missing URLs) gives {"platform": "", "runner": "unknown"}.
