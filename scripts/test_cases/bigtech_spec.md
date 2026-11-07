# Big-tech career sites — search parsers + company mapping (JSA-133)

Every returned posting is a dict {"title", "location", "url"} with whitespace collapsed and trimmed in title and location.

## parse_amazon(d)
Pure (tested). amazon.jobs `search.json` → [{title, location, url}]: `jobs[].title`, `normalized_location` (else `location`), url = https://www.amazon.jobs + `job_path` (else /en/jobs/<id_icims>); rows without a title or a path / id are skipped.

## parse_apple(d)
Pure (tested). jobs.apple.com `/api/v1/search` → [{title, location, url}], one entry per (posting × location): `res.searchResults[]` (or `searchResults[]`) with `postingTitle`, `locations[].name`, url = https://jobs.apple.com/en-us/details/<positionId>/<transformedPostingTitle> (slug 'role' when missing); a posting without locations gives one entry with location ''; entries without a title or positionId are skipped.

## parse_google_list(page)
Pure (tested). A Google Careers results page → [{title, location, url}]: every link whose aria-label is "Learn more about <Title>" and whose href holds jobs/results/<digits>; url = https://www.google.com/about/careers/ applications/ + the href without a leading './' or '/about/careers/applications/' and without its query; location '' (the gate reads it from the posting). Duplicate urls are kept once, in page order.

## big_tech(company)
Pure (tested). A company that hires through its own career site that ats_search reads (an employer / AWS → amazon, an employer → apple, Google → google; JSA-133) → [(system, ident)], else []. Names are matched from the start, case- insensitive ("Amazon Web Services (AWS)" → amazon; "a Workday employer" / "Google DeepMind" → none).
