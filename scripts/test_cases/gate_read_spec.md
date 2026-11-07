# Gate: which link is read for a job row (JSA-046)

A job row has `url` (the link from the job list) and maybe `ats_url` (the company's own posting, resolved later).
A reader function load(link) returns a result with `status`: "ok", "closed" or "unreadable" (plus other data).
The gate's read(row, load) returns the result it uses:
1. It loads ats_url when the row has a non-empty ats_url, otherwise url.
2. If that result is "unreadable" AND the row has a non-empty ats_url AND a non-empty url AND url differs from ats_url,
   it also loads url; if this second result is not "unreadable" ("ok" or "closed"), the second result is returned.
3. In every other case the first result is returned (including when both are unreadable).
4. url is loaded at most once, ats_url at most once; when the first result is "ok" or "closed", nothing else is loaded.
