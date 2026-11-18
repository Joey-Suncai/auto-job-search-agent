# LinkedIn job page → company apply link — spec (2026-11-05, JSA-178)

Four pure functions. A "LinkedIn job page" URL is linkedin.com/jobs/view/<6+ digit id> (optionally with a slug before
the id: /jobs/view/data-intern-at-acme-4476043330) or any linkedin.com URL with ?currentJobId=<id>.

## company_link(href) → str
The href of the page's apply control → the company URL. LinkedIn wraps it: https://www.linkedin.com/safety/go/?url=<
percent-encoded URL>&trk=… or /redir/redirect?url=…; unwrap it (decode the percent-encoding). Then drop tracking query
parameters (utm_* , source, src, ref, trk, gh_src, fbclid, gclid …) and keep every other parameter (gh_jid, jobId, …) as
written; drop an empty query. Return "" when the href is empty, not http(s), or (after unwrapping) still a linkedin.com
page. A direct non-LinkedIn https URL is returned cleaned the same way.

## resolve(info) → {"li_apply", "reason", "apply_url", "ats_url"}
info = {"controls": [{"text": str, "aria": str, "href": str, "visible": bool}], "closed": bool, "head": str (the start of
the page text)}.
0. No controls and head contains (any case) "Job id provided may not be valid", "job posting has been removed" or
   "This job is no longer available" or "Not currently accepting applications" → li_apply "closed".
1. closed true → li_apply "closed", apply_url "" and ats_url "".
2. Else look at the VISIBLE controls (in order): a control whose text — or, if the text says neither, whose aria-label
   — contains "Easy Apply" → li_apply "easy" (apply_url "", ats_url ""); a control that says "Apply" as a word (and not
   "applied" / "no longer accepting") → li_apply "external", apply_url = company_link(href), ats_url = apply_url when it
   is ONE posting on a known applicant-tracking system, else "". The first control that is easy or external decides.
   Known systems (host): greenhouse.io, myworkdayjobs.com, lever.co, ashbyhq.com, icims.com, oraclecloud.com,
   smartrecruiters.com, workable.com, successfactors.com, jibeapply.com (subdomains count). "One posting": Workday path
   contains /job/ or /details/; Greenhouse /jobs/<digits> or gh_jid=<digits>; otherwise a UUID or 5+ digits in a row in
   the path or a query value. A careers home page (https://acme.wd5.myworkdayjobs.com/External) is not one posting.
2b. (JSA-313, 2026-11-11) No visible easy / external control, and head contains (any case) "Not currently accepting
   applications" or "No longer accepting applications" → li_apply "closed" (apply_url "", ats_url ""), even when the
   page has other controls that are not apply controls (e.g. "Tailor my resume", "Show match details", "Save") or only
   hidden apply controls. A visible apply control decides before this rule.
2c. Else the same as rule 2 over the hidden controls (visible false).
3. No such control → li_apply "unknown".
Only li_apply, apply_url and ats_url are checked by the cases (reason is free text).

## apply_row(row, res, li_url, today) → row
Always sets linkedin_url = li_url, li_apply = res.li_apply, li_apply_reason = res.reason, li_apply_on = today.
external with an apply_url: row.apply_url = it when the row has no apply_url or its apply_url contains "linkedin.com"
(else the old value stays); when res.ats_url is set and the row has no ats_url: ats_url = res.ats_url, ats_resolved =
"linkedin apply link (JSA-178)", ats_resolved_on = today (an existing ats_url is never replaced).
closed: elig = "已关闭", elig_reason = res.reason, elig_checked = today. easy / unknown: nothing else changes.

## targets(rows, wellfound_pages, redo=False) → [[row id, LinkedIn job id]]
A row is a target when its url is a LinkedIn job page, or when a Wellfound page record {"id": <row id>, "opened":
[urls…]} names it and one of its opened URLs is a LinkedIn job page (the first such URL gives the job id). Skipped: rows
with an ats_url; rows with a li_apply value (unless redo); rows whose elig is 不可投, 已关闭 or 重复. Order: elig 可投
first, then tier A, B, C, D, anything else; then level starting with "Intern" (any case) before other levels; ties keep
the input order.
