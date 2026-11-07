# Spec: three SuccessFactors form details (2026-11-05)

1. **Privacy link** — `privacy_link(text) -> bool`. True when a link's text asks to open / read / review / view / accept a
   data-privacy document: "<verb> … (data) privacy [consent|protection] statement|agreement|policy|notice" (verb within
   ~30 characters before), or the bare text "Data Privacy Statement" / "Data Privacy Agreement" / "Data Privacy Consent
   Statement". False for cookie or privacy *settings* links, "Privacy" alone, "Accept cookies", "Terms of use".
2. **Source list naming sites** — `site_board(options) -> bool`: True when any option looks like "Job Board - <site>"
   (also "Job Board: X", "Job Board / X"); a plain "Job Board" or "Online job board" option is False.
   `board_pick(options, source, url, defaults)`: picks the option naming the job row's own board (from its source
   value or URL host: LinkedIn, Indeed, Glassdoor, Handshake, ZipRecruiter …); if the list does not have it, the option naming
   the first default that is listed (defaults = ["LinkedIn", "Indeed"]); None when no option names a known board or
   none of those are listed. Aggregators (Simplify, jobright, a GitHub list) are not boards → defaults apply.
3. **Zero-width characters** — `norm(text)`: lower-case, quotes / dashes normalised, whitespace collapsed, trailing "."
   dropped, and zero-width space / joiner / non-joiner / word joiner / BOM / soft hyphen removed, so
   "I am not a protected veteran​" equals "i am not a protected veteran".
