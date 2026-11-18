# JSA-300: four small helpers of the eligibility gate's job-page readers

1. adp_wfn_api(link) → [key, api_url] or null.
   - Only links to an ADP Workforce Now career center: host workforcenow.adp.com or workforcenow.cloud.adp.com, path
     /mascsr/default/mdf/recruitment/recruitment.html, followed by a query string. Anything else → null.
   - The query parameters cid and jobId are read case-insensitively (cid / CID, jobId / jobid / JOBID; ccId / ccid too).
     When cid or jobId is missing or empty → null (such a link is a job list, not one posting).
   - key = "adp:" + cid lower-cased + ":" + jobId lower-cased.
   - api_url = "https://" + host lower-cased + "/mascsr/default/careercenter/public/events/staffing/v1/job-requisitions/"
     + jobId + "?cid=" + cid + "&lang=en_US", and, only when the link has a non-empty ccId, "&ccId=" + ccId appended.
     Values keep their original case and are URL-quoted (plain letters, digits, "-", "_" stay as they are).
   - Other parameters (lang, source, selectedMenuKey …) are ignored.

2. gh_boards_in_page(page_html) → list of Greenhouse board names the page names, lower-cased, in order of first
   appearance, each once. A board name is the word ([A-Za-z0-9_-]+) right after any of:
   "boards.greenhouse.io/embed/job_board?for=", "boards.greenhouse.io/embed/job_board/js?for=",
   "job-boards.greenhouse.io/", "job-boards.eu.greenhouse.io/", "job-boards.greenhouse.io/embed/job_board?for=",
   "boards.greenhouse.io/", "boards.eu.greenhouse.io/", "boards-api.greenhouse.io/v1/boards/", "boards-api.eu.greenhouse.io/v1/boards/".
   The words embed, v1, jobs, job_app, job_board are never boards. Empty / None page → [].

3. wd_search.job_url(host, tenant, site, path) → the public URL of one Workday posting. path is the posting path
   "/job/<location>/<slug>_<id>" (a missing leading "/" is added).
   - host ending in "myworkdaysite.com" (shared host, e.g. wd3.myworkdaysite.com): "https://" + host + "/recruiting/" +
     tenant + "/" + site + path  (no locale).
   - any other host (e.g. acme.wd5.myworkdayjobs.com): "https://" + host + "/en-US/" + site + path.
   wd_search.parse_tenant(url) → [host, tenant, site] or null; on wdN.myworkdaysite.com it accepts an optional locale
   segment such as "en-US" before "recruiting": https://wd5.myworkdaysite.com/en-US/recruiting/oatey/Oatey_External_/job/x
   → ["wd5.myworkdaysite.com", "oatey", "Oatey_External_"]. A myworkdaysite link without "recruiting/<tenant>/" →
   null. myworkdayjobs links: host lower-cased, tenant = first host label, site = first path segment after an optional
   locale; first segment "wday" or "job" → null.

4. page_verdict(url, final_url, title, text, http) — what a page rendered in a browser showed. Only these two new rules
   are tested here (plus that they do not break the old ones):
   a. Closed notice: the page text (first 2500 characters) contains "can't view this job because" / "cannot view this
      job because" (also position / posting / requisition), and the page has little job text (under 3000 characters,
      or fewer than 3 job words such as responsibilities, qualifications, requirements, experience, degree, skills)
      → status "closed". Example: Seagate: "Search Jobs\nYou can't view this job because it's not available at this time.\nAbout Seagate".
   b. Site error: a short page (under 1500 characters) whose first 2500 characters say the site itself failed —
      "problem with the service", "try again later", "try again after sometime" / "after some time", "trouble loading the
      job" (or page / posting), "something went wrong", "service unavailable" / "service temporarily unavailable" —
      → status "unreadable" (not "login"), even when a line "Sign in" is at the top of the page. This test comes after
      the security-check test (a CAPTCHA / "verify you are human" page → "stop"), after the closed tests (404/410 → "closed";
      a closed notice wins over a site error), and before the sign-in test.
   c. Unchanged: a short page whose first line is "Sign in" and that has no site-error words → "login"; a page with
      plenty of job text (over 600 characters and at least 2 job words) and no closed notice → "ok".

5. clearcompany_route(link) → [company, job_id] or null (both lower-cased). A ClearCompany posting link is one of:
   - https://<co>.clearcompany.com/careers/jobs/<guid>  (anything may follow, e.g. "/apply?source=x"); <co> must not be
     apply, app, www, careers-api or careers-content.
   - https://apply.clearcompany.com/<co>?jobId=<guid>  (the parameter name in any case: jobId / jobid / JOBID; it may
     come after other parameters).
   <guid> = 8-4-4-4-12 hex digits. Any other link (the job list /careers/jobs without an id, a non-guid id,
   another site) → null.
   clearcompany_site_id(page_html) → the guid in data-site-id="<guid>" (single or double quotes, spaces around "=" allowed),
   lower-cased; no such attribute or empty page → null.

6. gate_run.read_ids(text) → the set of row ids an --ids file names: the text is split into lines, "#" starts a comment
   to the end of its line, the rest is split on whitespace and commas, empty parts dropped. None / "" → empty set.
   gate_run.pick(jobs, due, ids) → the list of rows (dicts with "id") this run checks, in the original order:
   when ids is a set (even an empty one) exactly the rows whose id is in it, whatever due says (empty set → []);
   when ids is None, the rows for which due(row) is true. (In cases, due is given as the list of ids it returns true for.)
