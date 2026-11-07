# platform_counts — spec (JSA-113, 2026-11-03)

`scripts/platform_counts.py` counts the job store (`data/store/jobs.jsonl`, read only) by application platform, to pick
the next long-tail ATS worth a runner. Three pure functions are tested offline.

## platform_of(url) → string or null
The platform is decided by the URL's host only (lower-cased; scheme, port, path, query and fragment ignored). A host
matches a suffix when it equals the suffix or ends with "." + suffix (so `notworkable.com` is NOT workable).
Empty, missing or unparseable URL → null. A host that matches nothing below → null.

| platform | host suffixes |
|---|---|
| workable | `workable.com` |
| jazzhr | `applytojob.com`, `jazzhr.com` |
| adp | `adp.com` |
| ukg | `ultipro.com`, `ukg.net` |
| rippling | `rippling.com`, `rippling-ats.com` |
| dayforce | `dayforcehcm.com` |
| paycom | `paycomonline.net`, `paycom.com` |
| taleo | `taleo.net` |
| paylocity | `paylocity.com` |
| eightfold | `eightfold.ai` |
| avature | `avature.net` |
| yello | `yello.co` |
| jobvite | `jobvite.com` |
| clearcompany | `clearcompany.com` |
| breezy | `breezy.hr` |
| jibe | `jibeapply.com` |
| bamboohr | `bamboohr.com` |
| smartrecruiters | `smartrecruiters.com` |
| icims | `icims.com` |
| oracle | `oraclecloud.com` |
| successfactors | `successfactors.com`, `successfactors.eu`, `sapsf.com` |
| greenhouse | `greenhouse.io` |
| workday | `myworkdayjobs.com`, `myworkdaysite.com` |
| ashby | `ashbyhq.com` |
| lever | `lever.co` |

Examples: `https://apply.workable.com/acme/j/ABC/` → workable; `https://acme.applytojob.com/apply/xyz` → jazzhr;
`https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=1` → adp;
`https://recruiting2.ultipro.com/ACM1000/JobBoard/…` → ukg; `https://ats.rippling.com/acme/jobs/1` → rippling;
`https://WWW.Acme.Taleo.NET/careersection/2/jobdetail.ftl?job=1` → taleo; `https://www.google.com/?q=workable.com` → null
(the platform name appears only in the query).

### SuccessFactors career sites on a company's own domain (JSA-170, 2026-11-05)
SAP SuccessFactors career sites (Recruiting Marketing) usually run on the company's own host
(`careers.hfsinclair.com`, `jobs.paccar.com`), so the suffix table misses them. When **no suffix matches**, the URL is
`successfactors` if either:
- the query has a parameter `ats` whose value starts with `successf` (case-insensitive), e.g. `?ats=successfactors`
  or a cut-off `?ats=successf`; or
- the path (case-insensitive) is exactly `/job/<slug>/<id>` with an optional trailing `/`, where `<slug>` is one
  non-empty path segment and `<id>` is 8 to 12 digits.

Exception: hosts `builtin.com` or ending in `.builtin.com` (Built In is a job board whose own job pages use the same
`/job/<slug>/<id>` path) are never `successfactors` by these two rules → null. A suffix match always wins over these
rules (`https://acme.wd1.myworkdayjobs.com/job/x/12345678` stays workday).

Examples: `https://careers.hfsinclair.com/job/Dallas-IT-Data-Analytics-Intern-TX-75219/1430072400/?ats=successf` →
successfactors; `https://jobs.bunge.com/job/Chesterfield-Data-Science-Intern-MO-63017/1451720133/` → successfactors;
`https://jobs.acme.com/job/x/1234567` → null (7 digits); `https://jobs.acme.com/job/a/b/12345678` → null (two
segments); `https://jobs.acme.com/jobs/x/12345678` → null (`/jobs/`, not `/job/`);
`https://builtin.com/job/data-analyst/12345678` → null; `https://jobs.acme.com/apply?ats=successfactors` →
successfactors.

## row_platform(row) → string or null
`platform_of(row["ats_url"])` when that is not null; otherwise `platform_of(row["url"])`. Missing keys count as empty.
So a row whose `ats_url` is empty and `url` is a Workable link → workable; a row whose `ats_url` is a Rippling link and
`url` is a LinkedIn link → rippling; a row whose `ats_url` is a LinkedIn link (matches nothing) and `url` is a Lever link
→ lever.

## summarize(rows) → dict platform → counts
Only rows whose row_platform is not null are counted. For each platform:
- `rows`: number of rows.
- `ok`: rows with `elig` == "可投".
- `ok_ab`: 可投 rows whose `tier` is "A" or "B".
- `ok_intern`: 可投 rows whose `level` is "Internship".
- `ok_newgrad`: 可投 rows whose `level` is anything else that is non-empty ("New grad", "Early career", …).
- `ab_any`: rows (any elig) whose `tier` is "A" or "B", or whose `tier` is "Blocked" and `tier_orig` is "A" or "B".
Missing fields count as empty strings. A platform with no rows does not appear.
