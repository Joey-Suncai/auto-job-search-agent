# ApplicantPro (JSA-149, 2026-11-04)
- detect: a host `<name>.applicantpro.com` anywhere in a page / URL is the system "applicantpro" with ident = that host
  (lower case as found). Not preceded by a letter, digit, dot or hyphen (so "x.casellejobs.applicantpro.com" yields the
  full host only once, and "notapplicantpro.com" is not a match).
- applicantpro_site_id(page_html): the digits of the first `"domain_id":"<digits>"` (quotes around the number optional,
  spaces allowed around the colon), else "".
- parse_applicantpro(page_html, data, host): data = {"data": {"jobs": [...]}}; every job with an `id` and a `title` becomes
  {"title", "location", "url"}: url = "https://<host>/jobs/<id>"; location = city and state abbreviation joined by ", "
  (missing parts skipped); when `workplaceType` contains "remote" (any case) "; Remote" is appended (or just "Remote"
  when there is no city / state). Jobs without id or title, non-dict entries, and a missing / null data → skipped / [].
