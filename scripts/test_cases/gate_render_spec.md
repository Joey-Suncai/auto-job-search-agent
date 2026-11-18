# Gate: reading job pages the plain download cannot read (JSA-284)

Seven pure functions. Dates are YYYY-MM-DD strings.

## A. icims_read_url(link) -> string or null
An iCIMS link has host `<name>.icims.com` and a path starting `/jobs/<digits>`, optionally followed by `/<slug>` and more.
Return `https://<host lowercased>/jobs/<digits><slug part>/job?in_iframe=1`, where the slug part is `/<slug>` when the
path segment after the digits exists and is not exactly `job`, `login` or `candidate` (case-insensitive) — otherwise
it is empty. Every query parameter of the input (mode=apply, mobile, …) and everything after the slug is dropped.
http and https inputs are both accepted. A link that is not an iCIMS posting (other host, no /jobs/<digits>) → null.

## B. wd_page_gone(html) -> bool
A Workday public job page. True only when the HTML has a `<meta ... property="og:title" ...>` tag AND that tag has no
non-empty `content="..."` attribute (missing or `content=""`). No og:title tag at all → false. A tag with a non-empty
content → false. Attribute order inside the tag does not matter; matching of the tag is case-insensitive.

## C. clean_url(link) -> string   (only the iCIMS part is under test)
On hosts ending in `.icims.com`, these query parameters are removed (name match case-insensitive): mode, in_iframe,
mobile, needsRedirect, width, height, bga, jan1offset, jun1offset, hub, hashed. Tracking parameters (utm_*, source,
src, ref, gh_src, …) are removed on every host. Every other parameter is kept, byte for byte, in its order; when no
parameter is left the `?` goes too. The path is never changed. On hosts that are NOT *.icims.com, mode / width / height /
mobile / in_iframe etc. are kept. A non-http(s) input → "".

## D. closed_on(text, today) -> date or null
Looks in the first 6000 characters for a label followed by a date. Labels (case-insensitive) at the start of a line
(after a newline, or after a `|` separator, or at the very start): `Closed`, `Closing date`, `Close date`,
`Application deadline`, `Apply by`, `已关闭`, `截止日期`; then an optional `:` or `：`, optional "on ", then a date in one
of: `November 5, 2026` / `Nov 5, 2026` / `Nov. 5 2026` (month name, day, year; comma optional), `2026-11-05`,
`11/05/2026` (US month/day/year). Only the FIRST label+date that parses is used: if that date is before `today`
return it as YYYY-MM-DD, otherwise null (a later past date does not count). No such label+date → null.

## E. page_verdict(url, final_url, title, text, http, today) -> {"status", "why", ...}
The rendered text of one page. Whitespace runs are squeezed first; "head" = the first 2500 characters.
Checked in this order, first match wins:
1. "stop": the title matches a security check / CAPTCHA phrase (verify you are human, are you a robot, captcha,
   security check, unusual activity/traffic, press and hold, checking your browser, "just a moment...", access denied,
   request blocked, attention required, bot detection, pardon our interruption), or the text is shorter than 2500
   characters and the head contains such a phrase.
2. "login": final_url looks like a sign-in page (a path segment login / signin / sign-in / sso / auth / oauth / oauth2 /
   saml, or accounts.google.com, login.microsoftonline.com, okta.com) while the original url did not.
3. "closed": http is 404 or 410.
4. "closed": the head has a closed-posting notice (e.g. "no longer available", "no longer accepting", "position has been
   filled", "job not found", "job has expired", "this job is closed", "page not found", "page does not exist",
   "not accepting applications", "this opportunity is currently unavailable", "position is not available") AND (the text
   is shorter than 3000 characters OR fewer than 3 job words — responsibilit, qualification, requirement, what you'll do,
   about the role/job/position, job description, duties, you will, skills, experience, degree — occur in the first 20000
   characters).
5. "login": the text is shorter than 1500 characters and the head has a line starting with "Sign in" / "Log in" / "Login",
   or says "please sign in to view/continue/apply" or "you must sign in". (A short closed page whose header has a
   "Sign in" link is therefore "closed", rule 4.)
6. "closed": closed_on(text, today) gives a date.
7. "unreadable": http is 400 or more.
8. "unreadable": the text is shorter than 600 characters, or fewer than 2 job-word occurrences.
9. otherwise "ok", with "text" = the squeezed text cut to 40000 characters and "title" = the title.

## F. render_pick(lines, rows, cap) -> [{"id", "url"}]
`lines` are gate results {"id", "status", "why"}; `rows` maps id → job {"ats_url", "score"}. A line is picked when:
status is "unreadable"; its job has an ats_url starting with "http"; that ats_url is not on linkedin.com,
joinhandshake.com, jobright.ai, zapply.jobs or vansh.nyc; and its "why" does not mention "needs a login",
"security check" or "captcha" (case-insensitive). url = the job's ats_url. Order: higher score first (missing score = 0),
ties by id ascending. At most `cap` items; cap 0 or negative → none.

## G. render_merge(x, v) -> result
x is one gate result, v what the job Chrome read (or null / empty). Missing v → x unchanged. v.status "ok" → x with
status "ok", text = v.text, title = v.title (or x.title, or ""), loc = x.loc (or ""), why "rendered in the job Chrome";
v.status "closed" → status "closed", why = "rendered: " + v.why; any other v.status → status "unreadable", why =
"rendered: " + v.why + " | " + x.why. Other fields of x (id, key, level) are kept.
