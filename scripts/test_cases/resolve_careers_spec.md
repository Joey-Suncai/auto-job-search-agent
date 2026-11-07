# Spec: resolve_careers — company careers page → ATS → matching posting (JSA-055 / JSA-091)

Rows from job aggregators (jobright, Handshake) have only company + title + location. The resolver visits the company's
own website, detects which applicant-tracking system (ATS) it links to, and, on the searchable ones, picks the posting
with the same title. Never guess: when unsure, no match.

## detect_ats(text) → list of [system, ident]
Scans a page's HTML (plus its final URL) for links to known systems. Each (system, ident) appears once. Result order:
by system in this fixed order: workday, greenhouse, lever, ashby, icims, oraclecloud, successfactors, taleo,
smartrecruiters, workable, jobvite, bamboohr, adp, ultipro, paylocity, eightfold, phenom, avature, dayforce.
- workday: `https://<tenant>.wd<N>.myworkdayjobs.com/[<locale like en-US>/]<site>/...` → ident = [host, tenant, site]
  (host lower-case, e.g. "acme.wd5.myworkdayjobs.com", tenant = first host label, site = first path part that is not a
  locale). Also `https://wd<N>.myworkdaysite.com/recruiting/<tenant>/<site>/...` → [host, tenant, site]. A Workday URL with
  no site part (just the host, or the path starts with "wday" or "job") is ignored.
- greenhouse: `boards.greenhouse.io/<token>`, `job-boards.greenhouse.io/<token>`, `boards.greenhouse.io/embed/job_board?for=<token>`,
  `boards-api.greenhouse.io/v1/boards/<token>` → ident = token (case kept).
- lever: `jobs.lever.co/<token>` (or jobs.eu.lever.co) → token. ashby: `jobs.ashbyhq.com/<token>` → token (URL-decoded).
- Tokens "embed", "jobs", "v1", "boards", "api", "www", "static", "assets", "js", "css", "search" (any case) are not boards → ignored.
- icims: host `<x>.icims.com` → ident = that host, lower-case. oraclecloud: host `<x>.fa.<y>.oraclecloud.com` → host.
  taleo: `<x>.taleo.net` → host. bamboohr: `<x>.bamboohr.com` → host. eightfold: `<x>.eightfold.ai` → host.
  avature: `<x>.avature.net` → host. smartrecruiters: `jobs.smartrecruiters.com/<slug>` or `careers.smartrecruiters.com/<slug>` → slug lower-case.
  workable: `apply.workable.com/<slug>` → slug. jobvite: `jobs.jobvite.com/<slug>` → slug.
- Text with none of these → [].

## names_company(page_html, company, final_url) → bool   (wrong-company guard for a guessed domain)
Distinctive words of the company = the name lower-cased, text in parentheses removed, legal suffixes removed
(inc, llc, corp, corporation, co, company, ltd, group, technologies, technology, holdings, lab, labs), punctuation → space,
then generic words dropped: and, the, of, group, inc, llc, co, company, corporation, corp, services, solutions, systems,
international, global, national, american, america, partners, capital, management, health, bank, financial, university,
department, state, institute, team, securities, llp, lp, limited, partnership, us, usa, north, south, new, first,
general, united; and one-letter words dropped. No distinctive words left → false.
1. Host check (only when final_url is given): label = the registrable label of the host (for "www.boozallen.com" →
   "boozallen"; for "x.co.uk" → "x"). Passes if some distinctive word of ≥ 3 letters is inside the label, or the label is
   inside the company key squashed (lower-case, suffixes removed, all non-alphanumerics removed), or the label equals the
   initials of the company key's words. Otherwise → false (e.g. a guessed domain that redirected to linkedin.com or a
   domain-parking site).
2. Name check on the page's `<title>` plus `og:site_name` content (HTML entities decoded, lower-case): true if the
   distinctive words joined with no spaces appear inside that text with all non-alphanumerics removed; otherwise true
   only if EVERY one of the first two distinctive words appears as a whole word in the text.

## is_challenge(status, page_html) → bool   (security check → skip the company, never bypass)
True if the page `<title>` begins with "Just a moment", "Attention Required", "Access Denied" or "Security check" (any
case, any status). Also true if status is 403, 429 or 503 and the first 20,000 characters contain any of: "just a moment...",
"cf-chl", "challenge-platform", "attention required", "captcha", "are you a robot", "access denied", "perimeterx",
"px-captcha", "_incapsula_". A 200 page that merely mentions "captcha" in its body (no such title) → false. A 404 → false.

## norm_title(t)
Removes "(Full-Time)", "(Full Time)", "(Part-Time)", "(Remote)", "(Hybrid)", "(Onsite)", "(On-site)", "(Contract)" (any
case), the words "full time" / "full-time", "United States", "USA", "U.S."; a trailing " - Remote" / " - Hybrid" /
" - United States"; then a trailing city tail " - <City>, <ST>" or ", <City>, <ST>" (ST = two capital letters); collapses spaces.

## similarity(a, b)
Words = lower-case, every non [a-z0-9 ] character → space, split on spaces, minus stop words {the, a, an, and, of, for, in,
to, u, s, us, usa}. similarity = |A ∩ B| / max(1, |A ∪ B|) (Jaccard), computed on norm_title of both titles.

## city_of(location)
Lower-case; drop "+ N" and everything after it; drop the word "remote" (and a following "or"); take the text before the
first comma, trimmed; drop the word "city". "New York, NY + 2" → "new york"; "Remote or Freeport, IL + 8" → "freeport";
"New York City, NY" → "new york"; "Remote" → "".

## match_posting(title, location, postings) → [score, posting_title, url] or null
postings = [[title, url, location]]. Floor = 0.75.
- Best similarity < 0.75 (or no postings) → null.
- All postings with the best score share one URL → that posting, unless: the row has a city (city_of(location) non-empty),
  the posting location is non-empty, the posting location does not contain the city, the posting location does not say
  "<N> Locations", "remote", "multiple", "united states", "nationwide" or equal "us", and the row's title does not contain
  the city → null (same title in another city = a different opening).
- Several postings tie on the best score with different URLs → the single one whose location contains the row's city;
  none, or more than one with different URLs → null.

## decide(row, systems, postings_of) → {code, system, ats_url?, why?}
- row has a non-empty ats_url → code "already".
- empty title → code "no_title".
- systems empty → code "no_system", system "".
- Try each searchable system (workday, greenhouse, lever, ashby) in the given order; postings_of(system, ident, title)
  gives postings; the first match_posting hit → code "match", ats_url = the posting URL, system = that system.
- Searchable systems present but no hit → code "no_match", system = first searchable system.
- Only non-searchable systems → code "other_system", system = the first system in the list; no ats_url. (Since JSA-112, 2026-11-03, the systems ats_search.py reads — icims, taleo, oraclecloud, … — count as searchable when their ident is a real board: a search that finds nothing → "no_match"; see ats_search_spec.md.)

## Additions (2026-11-03)
- norm_title also expands abbreviations, whole words, any case, an optional trailing dot: Sr → senior, Jr → junior,
  Assoc → associate, Mgr → manager, Eng → engineer, Mgmt → management, Quant → quantitative, ML → machine learning,
  Intl → international. So "Quant Analytics Assoc." and "Quantitative Analytics Associate" are similarity 1.0.
- The city tail may also follow a dash with no space before it: "Data Scientist- Abbott Park, IL" → "Data Scientist".
- names_company: when no distinctive word is left after dropping generic words (e.g. "Bank of America"), the distinctive
  words are the company key's words other than the, and, of (one-letter words still dropped) → "bank", "america".
- domain_candidates(company) → list of domains, no duplicates, in this order: words = company key (lower-case, text in
  parentheses removed, legal suffixes removed, punctuation → space) minus "the" and "and"; the part of the name after
  " and " / " & " is dropped when that part ends in "securities" or "sons". Candidates: all words joined + ".com"; first
  two words joined + ".com"; first word + ".com" (left out when the first word has < 3 letters and there are more words);
  words joined by "-" + ".com"; when ≥ 3 words, their initials + ".com"; finally all words joined + ".org". A name with
  characters outside a-z0-9 after cleaning (e.g. Chinese) → [].
- board_guesses(company) → for slug in [all words of the company key joined, joined by "-"] (each ≥ 3 letters, no
  duplicates) and for ats in greenhouse, lever, ashby: [ats, slug]. The first word alone is never a guess for a multi-word name.

## Additions (2026-11-03, b) — finding the company's site
- same_name(a, b) → true when the two company keys (lower-case, legal suffixes removed, punctuation → space, spaces
  collapsed) are equal, or equal after removing every non-alphanumeric character ("JPMorgan Chase" = "an employer").
  An empty name (nothing left after cleaning) is never the same as anything.
- pick_lookup(company, suggestions): suggestions = list of {"name", "domain"} from a name → domain service. Returns the
  domains (lower-case, no duplicates, original order) of the suggestions whose name is same_name as the company. Items
  that are not objects or have no domain are ignored. "Qorvo Power" is not "Qorvo, Inc."; "Qorvo" is.
- borrow_domains(company, jobs): jobs = list of rows {"company", "url", "ats_url"}. For rows whose company is same_name,
  take the host of url and of ats_url; skip hosts that contain any of: jobright, joinhandshake, linkedin, builtin, indeed,
  glassdoor, greenhouse.io, lever.co, ashbyhq, myworkday, icims, smartrecruiters, workable, github, simplify, zapply,
  vansh, ziprecruiter, wellfound, "google.", bit.ly. Reduce each host to its registrable domain: the last two labels
  ("careers.acme.com" → "acme.com"), or the last three when the second-to-last label is co / com / org / ac
  ("jobs.acme.co.uk" → "acme.co.uk"). Return them without duplicates in first-seen order.
- script_srcs(page, base, limit=4): URLs from <script ... src="..."> in the page, resolved against base, kept only when
  their host ends with the base host's last two labels (same site; a CDN on another domain is dropped), no duplicates, at most limit.
- sitemap_career_urls(xml, limit=4): the <loc> URLs of a sitemap that contain "career" or a path word "job"/"jobs"
  (case-insensitive), in order, at most limit.

## Addition (2026-11-03, c) — campus-only postings
- match_posting first drops every posting whose title names a school that the row's title does not name. Schools = the
  whole words harvard, mit, stanford, princeton, yale, columbia, berkeley, cmu, carnegie, uchicago, "chicago booth",
  wharton, penn, cornell, caltech, waterloo, university, college (any case). "Junior Quant Developer 2027 | Harvard" is
  dropped for the row "Junior Quantitative Developer, 2027"; kept for the row "Junior Quantitative Developer 2027 - Harvard".

## Addition (2026-11-03, e) — LinkedIn rows, more systems, shorter searches
- **kind(url)** → "jobright" for `jobright.ai/jobs/info/…`, "handshake" for any `joinhandshake.com` URL, "linkedin" for
  `linkedin.com/jobs/view/…` or `linkedin.com/comm/jobs/view/…` (any case, with or without www); anything else (a LinkedIn
  company page, a profile, a Greenhouse link) → null. A LinkedIn page is never fetched; only the row's company and title are used.
- **detect_ats** also records these systems by name, after all the systems listed above, in this order:
  brassring (`jobs.brassring.com`, `sjobs.brassring.com`, `ts.brassring.com` → that host), jazzhr (`<x>.applytojob.com`
  or `app.jazz.co` → that host), clearcompany (`apply.clearcompany.com` or `<x>.hrmdirect.com` → host), paycom
  (`paycomonline.net` → "paycomonline.net"), rippling (`ats.rippling.com/<slug>` → slug), breezy (`<x>.breezy.hr` → host),
  recruitee (`<x>.recruitee.com` → host), teamtailor (`<x>.teamtailor.com` → host), pinpoint (`<x>.pinpointhq.com` → host),
  dover (`app.dover.com/apply/<slug>` or `app.dover.io/apply/<slug>` → slug). Hosts are lower-case.
  (Revised 2026-11-03 by JSA-112, Joey 「补上」: adp, paycom, paylocity, dayforce, brassring and clearcompany now keep the
  part of the URL that names the tenant — see ats_search_spec.md, Addition d.)
- ultipro also matches `n<digits>.ultipro.com/<path>` (as well as recruiting.ultipro.com / recruiting2.ultipro.com) → ident =
  host + "/" + first path part, lower-case.
- smartrecruiters also matches `www.smartrecruiters.com/<Slug>` → slug lower-case, but NOT when the first path part is one of the
  vendor's own pages: company, customers, resources, blog, about, platform, pricing, product, solutions, demo, legal,
  privacy, jobs, careers, integrations (any case), and the slug must start with a letter.
- **norm_title** also removes "(Multiple openings)", "(Several positions)", "(3 roles)" — i.e. "(" + multiple / several / a
  number + opening(s) / position(s) / role(s) + ")" (any case) — and a trailing " in <City>, <ST>" with an optional final
  period ("Data Scientist in Cupertino, CA." → "Data Scientist").
- **wd_queries(title)** → the Workday search texts tried in order: first norm_title(title); then, only when that has more than
  three words (words = runs of letters / digits / & / +, punctuation dropped), its first three words joined by spaces. No
  empty or duplicate entries. A Workday search moves to the next text only when the previous one found no postings.

## Addition (2026-11-03, f) — finding the site and the system (JSA-069)
- **names_company** changes:
  - Generic words also include: incorporated, companies, enterprises, plc ("Ingredion Incorporated" → distinctive words [ingredion]).
  - The name check reads more of the page (page_names): the `<title>`, the content of meta og:site_name, og:title,
    application-name, apple-mobile-web-app-title, a JSON-LD "name" that follows `"@type": "Organization"` (or Corporation /
    WebSite), up to three copyright fragments (the text after "©", "&copy;", "(c)" or "Copyright" and optional years, up to 60
    characters, stopping at `<`, `"`, `{` or `}`), and the alt text of an `<img>` whose class contains "logo". Entities are
    decoded, text is lower-cased, and domain-like tokens (a word followed by .com / .org / .net / .io / .ai / .co / .us / .edu /
    .gov / .biz / .info, e.g. "nissan.com") are removed first — a page that names only its own address does not name a company.
  - Host check additions (only when final_url is given): a host whose last label is a country code or any TLD other than
    com, org, net, edu, gov, mil, io, ai, co, us, app, dev, tech, health, bank, inc, group, jobs, careers, coop, biz, info,
    energy, earth, me, tv, chat, so, xyz, cloud → false ("www.amway.my", "lenovo.com.cn", "regeneron.ie"). A host that starts
    with "ww" + digits + "." (a parking redirect such as "ww38.vulcan-materials.com") → false. A page that says the domain is
    for sale / parked (e.g. "This domain may be for sale", "buy this domain", "sedoparking", "parkingcrew", "hugedomains") →
    false, with or without final_url.
  - The initials check also accepts the initials of the raw name words before legal suffixes are removed
    ("Susquehanna International Group" → "sig" for host sig.com).
  - Strong host: when the host label equals the distinctive words joined with no spaces, or the company key squashed
    ("dematic" for Dematic, "erieinsurance" for Erie Insurance Group), it is enough that the first distinctive word appears
    as a whole word in the page names, OR that the distinctive words appear as a phrase (separated by at most three
    non-word characters) at least three times anywhere in the page HTML (case-insensitive). A label equal only to the first
    word ("nissan" for Nissan Motor Corporation) is not strong.
- **is_challenge** also true (any status) when the first 5,000 characters contain "_Incapsula_Resource" or "Request
  unsuccessful. Incapsula", and when the `<title>` begins with "captcha", "pardon our interruption", "are you a robot" or
  "human verification" (any case).
- **detect_ats**: successfactors also matches hosts ending in "jobs2web.com" (ident = the host, lower-case, e.g.
  "ey.jobs2web.com"); a new system njoyn (`<x>.njoyn.com` → host), listed after dover.
- **career_links(page, base)**: same link selection as before, plus links whose text says "search jobs", "open positions",
  "view jobs", "job search", "see all openings", "find a job", "apply now", "explore roles" (and close variants). Order: first
  links whose URL is a known ATS posting page (detect_ats finds something), then links whose text or URL says search / open
  / view jobs etc. or whose host is a different host starting with "careers." / "career." / "jobs.", then the rest in page
  order. At most 6, no duplicates.
- **wikidata_pick(company, results)**: results = list of {"id", "label", "description", "match": {"text"}, "aliases"}. Keep
  an id when (a) its description says it is an organisation (contains one of: compan, corporation, business, firm,
  manufactur, bank, insur, retail, conglomerate, organization/organisation, universit, college, school, hospital, health,
  agency, developer, startup, provider, enterprise, brand, subsidiary, airline, group, fund, trading, consult, software,
  publisher, laborator, government, department, authority, nonprofit, foundation, charity, chain, operator, carrier, maker,
  producer, studio, exchange, service — any case) AND (b) its label, match text or one of its aliases is the same company:
  same_name, or the same distinctive words squashed ("Ingredion" = "Ingredion Incorporated"; "Federal Express Corporation"
  as a match text = the company "Federal Express Corporation"). At most 2 ids, in order. Non-objects and items without an id are ignored.
- **alias_domains(company, table)**: table = {name: [domains] or a single domain string}; keys starting with "_" are
  comments. Returns the lower-cased domains of the first key that is same_name as the company; [] when none.
- **looks_like_title(company)**: true when the company name contains a whole word intern / interns / internship /
  internships / co-op / coop, or "summer 20NN" / "20NN summer"; or contains engineer / analyst / scientist / developer /
  manager / associate together with intern / summer / a 20NN year. Otherwise false ("InternXL" → false, "Associate Bank" → false).
- **paren_acronym(company)**: the 2–8 letter, all upper-case text inside parentheses, lower-cased ("… Authority (WMATA)" →
  "wmata"); "" when none or when it is not all upper-case ("(formerly Acme)" → "").
- **foreign_host(host)**: true when the last label is not in the list above (com, org, net, …); "acme.co.uk" → true,
  "acme.io" → false.
- **match_posting** changes (2026-11-03, g): (1) clones — when the best-scoring postings all have the same title and the
  same location text (compared case-insensitively) but different URLs, they are one opening posted as several requisitions:
  the first of them (in input order) is returned. Best-scoring postings that differ in title or location still need the
  row's city to pick exactly one (as before). (2) The row's city counts as named in a posting location when any word of
  city_of(location) that has ≥ 4 letters and is not greater / area / metro / metropolitan / region / county / downtown
  appears (as a substring, lower-case) in the posting location; when the city has no such word, the whole city string must
  appear. "Greater Tampa Bay Area" is named by "US - Tampa, FL (Lithia area)". This applies both to the single-posting
  city check and to breaking ties.

## Addition (2026-11-03, h) — company inventory hints (ats_inventory.py)
- **keys(name)** → match keys, in this order, no duplicates: (1) the distinctive words of the name (as defined for
  names_company, including the generic words of addition f) joined with no spaces; (2) the company key (lower-case, legal
  suffixes inc / llc / corp / corporation / co / company / ltd / group / technologies / technology / holdings / lab / labs
  removed) with every non-alphanumeric character removed. A key shorter than 3 characters, or equal to one of apply,
  careers, career, jobs, job, join, work, home, recruiting, talent, hiring, is dropped. "Two Sigma" → ["twosigma"];
  "Ingredion Incorporated" → ["ingredion", "ingredionincorporated"]; "Apply" → [].
- **hint_of(fname, name, url)** → [system, ident] or null. If detect_ats(url) finds something, its first result. Otherwise,
  only when fname is "phenom" or "successfactors": [fname, the url's host lower-case] — unless the name (trimmed,
  lower-case) is one of the words above (apply, careers, …). Any other file with an unrecognised url → null.
  ("successfactors", "Roche", "https://careers.roche.com") → ["successfactors", "careers.roche.com"];
  ("successfactors", "Apply", "https://apply.iav.com") → null; ("greenhouse", "Acme", "https://job-boards.greenhouse.io/acme")
  → ["greenhouse", "acme"]; ("gem", "X", "https://jobs.gem.com/x") → null.
- **lookup(company, directory)** reads every *.csv in directory. Files have a header; rows are name,slug,url — except a
  row whose first field starts with "http", which is url,name,… (the phenom file). Each row → hint_of(file name without
  .csv, name, url); a hint is filed under every key of the row's name. lookup returns the hints filed under the
  company's keys (keys in order, hints in file-then-row order), no duplicates; [] when none.
- **career_links** (2026-11-03, i): a link whose host contains any of the borrow_domains skip words (jobright,
  joinhandshake, linkedin, builtin, indeed, glassdoor, greenhouse.io, lever.co, ashbyhq, myworkday, icims, smartrecruiters,
  workable, github, simplify, zapply, vansh, ziprecruiter, wellfound, "google.", bit.ly) is dropped — unless detect_ats
  recognises the URL (a Greenhouse / Lever / Ashby / Workday / iCIMS … board link stays). "https://www.linkedin.com/company/acme/jobs/"
  is dropped; "https://boards.greenhouse.io/acme" is kept.
- **Skip words, 2026-11-04 (j, JSA-137)**: the borrow_domains / career_links skip list also holds the social hosts
  instagram.com, facebook.com, twitter.com, youtube.com and x.com (x.com only as the whole host or its last two labels —
  "box.com" and "netflix.com" are not x.com). A social link is dropped from career_links like a LinkedIn link
  (Instagram's own page config names vendor hosts such as facebook.csod.com, which were read as the company's Cornerstone
  board), and a row whose url is on a social host lends no domain in borrow_domains.
