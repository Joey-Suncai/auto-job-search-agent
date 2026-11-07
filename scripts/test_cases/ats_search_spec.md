# ats_search — spec (JSA-112, 2026-11-03)

`skills/job-hunt-pipeline/scripts/ats_search.py` searches public posting lists on careers systems other than
Workday / Greenhouse / Lever / Ashby. resolve_careers.py finds which system a company uses and an `ident` (a host or a
slug captured from a URL); ats_search turns (system, ident, query) into postings `{title, location, url}`.
Only the pure steps below are tested offline.

## root_domain(host) → string
- Lower-cases and strips dots at the ends, then keeps the last two labels: `www.acme.com` → `acme.com`,
  `careers.jobs.acme.com` → `acme.com`.
- When the second-to-last label is one of co / com / org / ac / gov / net AND the last label has exactly 2 letters
  (a country code), keeps the last three labels: `www.acme.co.uk` → `acme.co.uk`, `shop.acme.com.au` → `acme.com.au`.
- `acme.com` stays `acme.com`. Empty → empty string.

## career_hosts(site) → list
- Company site → `['careers.<root>', 'jobs.<root>']` in that order, root = root_domain(site).
- Empty site → `[]`.

## clean_ident(system, ident) → string or null
First: anything after an `@` is dropped (the `@site` suffix), whitespace and slashes at the ends are stripped, the result
is lower-cased, and a leading `2f` glued directly to a host label (a URL-encoded "/" left over, as in `2fhdr.taleo.net`)
is removed. Empty → null. Then per system:
- **icims**: must be exactly `<label>.icims.com`. Null when the label is vendor infrastructure — `www`, `i`, `login`,
  `cdn` or `cdn` + digits, `images`, `assets`, `static`, `cookie-policy-scripts`, `api`, `app`, `careers`, `jobs` — or
  contains `employee` or `internal` (employees-only site). `careers-acme.icims.com` → kept;
  `uscareers-medpace.icims.com` → kept.
- **oraclecloud**: must be `<label>.fa.<region>.oraclecloud.com`; null when the first label ends with `-dev`, `-test` or
  `-stage` (optionally followed by digits). `eofe.fa.us2.oraclecloud.com` → kept; `eofe-dev3.fa.us2.oraclecloud.com` → null.
- **taleo**: must be `<label>.taleo.net`, label not vendor infrastructure (same list as icims).
- **ultipro**: must be `<host>/<tenant>/JobBoard/<36-character board id>` where host is `recruiting.ultipro.com`,
  `recruiting2.ultipro.com` or `n<digits>.ultipro.com` (matching is case-insensitive). Returned as
  `<host>/<TENANT upper-case>/JobBoard/<board id lower-case>`. Without the board id (e.g. `recruiting2.ultipro.com/abc123`)
  → null.
- **bamboohr / breezy / recruitee / pinpoint / avature / jazzhr / eightfold / teamtailor**: must be `<label>.<vendor domain>`
  with vendor domains bamboohr.com, breezy.hr, recruitee.com, pinpointhq.com, avature.net, applytojob.com, eightfold.ai,
  teamtailor.com respectively; null when the label is vendor infrastructure (the icims list plus `staticfe`, `assets-cdn`,
  `vs-errors`) or contains `employee` / `internal`. `www.teamtailor.com` → null; `app.eightfold.ai` → null.
- **smartrecruiters / workable / jobvite / rippling**: ident is a slug: letters, digits, `_`, `-` only (starting with a
  letter or digit); null when it is vendor infrastructure (`api`, `embed`, `cdn-cgi`, `job-api`, `de-de`, `en-us`, `www`, …).
- **successfactors / phenom**: any non-empty ident is kept (it is a CDN host; the company site does the work).
- Any other system → null.

## with_site(systems, site) → list
- systems = list of [system, ident]. For successfactors, phenom, eightfold and teamtailor whose ident is a string without
  `@`, the ident becomes `<ident>@<site>`. Every other pair is unchanged, order kept.
- Empty site → the list unchanged.

## Parsers (page text → list of {title, location, url}); whitespace in title / location collapsed, HTML entities decoded
- **parse_icims(page, host)**: each `<a href="https://<host>/jobs/<digits>/<slug>/job…">` whose content is an optional
  `<span>…</span>` then `<h3>Title</h3>` is a posting; url = the href up to `/job` (query string dropped). location = the
  last `Location` field label (`<span class="sr-only field-label">Location</span><span>US-VA-Arlington</span>`) within
  the 1,500 characters before the link, else "". Links to another host are ignored.
- **parse_rmk(page, base)**: SuccessFactors career-site results: `<a … href="/job/<slug>/<digits>/" … class="jobTitle-link…">Title</a>`
  (attribute order either way). url = base joined with the href. The same href twice → one posting. location = the
  first `class="jobLocation…"` element's text within 2,500 characters after the link, else "".
- **parse_phenom(page)**: reads the JSON object after `"eagerLoadRefineSearch":`; postings = data.jobs. url = the job's
  applyUrl with a trailing `/apply` removed when applyUrl is on myworkdayjobs.com / myworkdaysite.com / greenhouse.io /
  lever.co / ashbyhq.com; otherwise `<baseUrl>job/<jobId>` where baseUrl is the page's `"baseUrl":"…"` value; a job with
  neither is skipped. location = cityStateCountry, else location, else "". No eagerLoadRefineSearch or broken JSON → [].
- **parse_oracle(d, host, site)**: d = the recruitingCEJobRequisitions JSON; postings = items[0].requisitionList; url =
  `https://<host>/hcmUI/CandidateExperience/en/sites/<site>/job/<Id>`, location = PrimaryLocation. Entries without Id
  skipped; no items → [].
- **parse_taleo(d, host, cs)**: d = Taleo searchjobs JSON; each requisitionList entry with a column list and contestNo →
  title = column[0]; location = column[1] — when it is a JSON list string (`["A","B"]`) its items joined with "; ";
  url = `https://<host>/careersection/<cs>/jobdetail.ftl?job=<contestNo>&lang=en`.
- **parse_jazz(page, host)**: `<a href="https://<host>/apply/<id>/<slug>">Title</a>`; location = the text after the next
  `fa-map-marker'></i>` within 600 characters, else "".
- **parse_jobvite(page, slug)**: `<a … href="/<slug>/job/<id>">Title</a>`; url = `https://jobs.jobvite.com/<slug>/job/<id>`;
  location = text of the next `jv-job-list-location">…</td` within 1,500 characters (tags removed), else "".
- **parse_rss(xml)**: each `<item>` with `<title>` and `<link>`; CDATA wrappers removed; location "".

## postings(system, ident, query)
- A system outside the list (icims, oraclecloud, successfactors, taleo, smartrecruiters, workable, jobvite, bamboohr,
  ultipro, eightfold, phenom, avature, jazzhr, rippling, breezy, recruitee, teamtailor, pinpoint) → [] without any request.
- An ident clean_ident rejects → [] without any request. Never raises.

## resolve_careers.decide with these systems
- A row whose systems include one of the systems above with an ident clean_ident accepts is searched like Workday /
  Greenhouse: a posting matching the title → code "match" with its url; none → code "no_match", system = that system.
- Systems whose ident clean_ident rejects, or systems not in the list (adp, paycom, …), are not searched; when nothing
  searchable is left → code "other_system", system = the first system in the list.
- Workday / Greenhouse / Lever / Ashby are searched first when present.

## Addition (2026-11-03, b): match_posting city check with country-suffixed locations
resolve_careers.match_posting(title, location, postings) → the matched posting url or null. postings = [[title, url, location]].
- When exactly one posting has the best title score: it is rejected (null) when the row's city (the part of the row's
  location before the first comma, "remote" words removed) is set, the posting's location is set, the city does not
  appear in the posting's location (nor in BOTH the row's title and the posting's title — revised after case
  review: a city named only in the row's title no longer excuses a posting in another city), AND the posting's location is not "wide".
- "Wide" = the posting location mentions "<n> locations", "remote", "multiple" or "nationwide", or is ONLY the country
  ("United States", "United States of America", "US", "USA", any case). A location such as "Phoenix, AZ, United States"
  or "Pensacola, FL, United States" is NOT wide — it names a city, so a row in Sunrise, FL does not match it.
- Title score: normalised titles, Jaccard ≥ 0.75; a trailing "- City, ST" in a title is dropped before scoring.

## Addition (2026-11-03, c): ideas taken from ats-scrapers
### backoff(attempt, retry_after=None, base=1.5, cap=30) → seconds
- When retry_after is a string of digits only (surrounding spaces allowed) whose value is ≤ cap → that value as a float.
- Otherwise base · 2^(attempt − 1), but never more than cap. attempt 1 → 1.5, 2 → 3.0, 3 → 6.0, 6 → 30.0 (capped).
- A Retry-After that is a date, empty, negative-looking ("-5") or above cap ("120") is ignored → the exponential value.
### is_blocked(status, body) → bool
- 429 → true, whatever the body.
- 403, 406, 202 or 503 → true when the body is empty / whitespace only, or its first 20,000 characters contain a challenge
  marker (case-insensitive: "just a moment...", "cf-chl", "challenge-platform", "attention required", "captcha",
  "are you a robot", "access denied", "request unsuccessful", "incapsula", "perimeterx", "px-captcha", "distil_").
  A 403 whose body is ordinary JSON such as {"message": "Not authorized for PCSX"} → false (a real answer, not a wall).
- Any status → true when a <title> in the first 5,000 characters starts with "just a moment", "attention required",
  "access denied" or "security check" (case-insensitive). 200 with a normal page → false. 500 with an empty body → false.
### parse_icims — location label (revised)
- The location field label may read "Location", "Locations", "Job Location" or "Job Locations"
  (`<span class="sr-only field-label">Job Locations</span><span> US-CA-Monrovia</span>` → "US-CA-Monrovia").
- The same job id twice on one page → one posting.
### parse_sitemal(xml) → postings
- Each RSS <item> with <title> and <link>; CDATA removed, entities decoded. When the title ends with a parenthesis that
  contains a comma — "Data Analyst (Houston, TX, US, 77042)" — the part before it is the title and the inside is the
  location ("Houston, TX, US, 77042"). A trailing parenthesis without a comma ("Engineer (Remote)") stays in the title
  and location is "". url = the link.
### parse_oracle (revised)
- The posting id is Id, else RequisitionNumber; an entry with neither is skipped.
### parse_jazz (revised): two markups on one page are both read
- List markup as before. Table markup: `<a class="job_title_link" href="/apply/jobs/details/<id>?&">Title</a>` → url =
  `https://<host>/apply/jobs/details/<id>` (query dropped), location = the text of the next `<td>` after the cell that
  holds the link (within 800 characters), else "". The same id in both markups → one posting.
### jobvite_range(page) → [start, end, total] or null
- From `class="jv-pagination-text">1-50 of 63` (spaces around "-" allowed, case-insensitive "of") → [1, 50, 63]. None → null.
### parse_rss (revised)
- Each <item> needs <title> and <link>; location = the <tt:city> and <tt:name> values inside that item, in order, duplicates
  removed, joined with ", " (Teamtailor feeds); none → "". CDATA wrappers removed from the title.
### parse_avature(page) → postings
- Links `<a … href="https://<host>/…/JobDetail/<slug>/<digits>">Title</a>`; title must contain a letter; the same id once.
- Location from the slug: the words before "United-States" with "-" → " ", then ", United States"
  ("Darlington-South-Carolina-United-States-Data-Analyst" → "Darlington South Carolina, United States"); a slug that starts
  with "United-States" → "United States"; no "United-States" → "".
### ukg_load_url(page, host, tenant) → board URL or null
- Reads `loadUrl: "/<TENANT>/JobBoard/<36-char id>/JobBoardView/LoadSearchResults"` (relative or absolute). Returns
  `https://<host>/<tenant as in the URL>/JobBoard/<id>` only when the URL is on the same host, the tenant matches
  (case-insensitive), the second segment is JobBoard (any case), the id has 36 characters of hex digits and dashes, and the path
  ends exactly in JobBoardView/LoadSearchResults; otherwise null. No loadUrl → null.
### clean_ident (revised)
- jobvite: `acme` or `careers/acme` are both kept (lower-cased); the tenant part must not be vendor infrastructure, "search" or
  "viewall".
- ultipro: host may also be `recruiting<digits>.ultipro.com` (e.g. recruiting3) or end in `.ultipro.ca`.

## Addition (2026-11-03, d): six more systems (Joey 「补上」)
### resolve_careers.detect_ats — the URL shapes these systems now keep (ident lower-case)
- adp: `workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?<query>` (also `workforcenow.cloud.adp.com`)
  → that whole host + path + query, lower-cased; a bare `workforcenow.adp.com` → "workforcenow.adp.com";
  `myjobs.adp.com/<slug>` → "myjobs.adp.com/<slug>".
- paycom: `paycomonline.net/v4/ats/web.php/portal/<32 hex>` (or `/jobs/<32 hex>`) → "paycomonline.net/v4/ats/web.php/portal/<token>"
  (the part after the token is dropped); any other paycomonline.net URL → "paycomonline.net".
- paylocity: `recruiting.paylocity.com/Recruiting/Jobs/All/<GUID>` (or `/List/`) → lower-cased host + path; else "recruiting.paylocity.com".
- dayforce: `jobs.dayforcehcm.com/[<locale like en-US>/]<tenant>[/<board>]` → host + those path parts, lower-cased.
- brassring: a `jobs.` / `sjobs.` / `ts.brassring.com` URL whose query has `partnerid=` → host + path + query (lower-cased);
  else the host.
- clearcompany: `apply.clearcompany.com/<slug>` → "apply.clearcompany.com/<slug>"; `<x>.hrmdirect.com` → that host; a bare
  `apply.clearcompany.com` → "apply.clearcompany.com".
### ats_search.clean_ident for the six
- adp: HTML entities in the ident are decoded twice ("&amp;", "&#038;"), anything after "#" dropped, query keys compared
  case-insensitively. Host must be `workforcenow.adp.com` or `workforcenow.cloud.adp.com`; `cid` must be 36 characters of
  hex digits and dashes; `ccId` must be 8 digits, "_", 6 digits. → "<host>/<cid>/<ccid>". Otherwise null (a bare host, a
  `myjobs.adp.com/<slug>` ident, a missing ccId).
- brassring: host `jobs.` / `sjobs.` / `ts.brassring.com`; `partnerid` and `siteid` in the query, both digits only (entities
  decoded, "#…" dropped) → "<host>/<partnerid>/<siteid>"; else null.
- paycom: the ident must end in `/portal/<32 hex>` or `/jobs/<32 hex>` → the 32-hex token; else null.
- paylocity: must end in `/recruiting/jobs/all/<GUID>` or `/list/<GUID>` (GUID = 8-4-4-4-12 hex) → the GUID; else null.
- dayforce: path after the host, split on "/"; a leading locale ("en-us", "fr") is dropped only when three parts remain;
  exactly two parts left and the second is not "jobs" → "<tenant>/<board>"; else null ("jobs.dayforcehcm.com/en-us" → null).
- clearcompany: `apply.clearcompany.com/<slug>` (slug not vendor infrastructure and not "v1") or `<x>.hrmdirect.com` → kept as
  is; a bare `apply.clearcompany.com` → null.
### Parsers
- **parse_adp(d, host, cid, ccid)**: d.jobRequisitions[] with itemID → title = requisitionTitle; location =
  requisitionLocations[].nameCode.shortName joined with "; " (empty ones dropped); url =
  `https://<host>/mascsr/default/mdf/recruitment/recruitment.html?cid=<cid>&ccId=<ccid>&lang=en_US&jobId=<itemID>&source=CC2`
  (query in exactly that order, URL-encoded). Rows that are not objects or lack itemID are skipped.
- **paycom_config(page)** → [jwt, service_url] or null: reads the JSON between `var configsFromHost = ` and `; var Mountable`;
  needs sessionJWT and libConfig (a JSON string) with atsPortalMantleServiceUrl; the service URL must be https, its host
  paycomonline.net or a subdomain of it, with no query, fragment, user name or port other than 443; a trailing "/" is removed.
  Anything else → null.
- **parse_paylocity(page)**: JSON after `window.pageData = `; Jobs[] that are objects, have JobId and are not IsInternal →
  title JobTitle; location = JobLocation.City and .State joined ", ", else LocationName, else ""; url =
  `https://recruiting.paylocity.com/Recruiting/Jobs/Details/<JobId>`. No pageData → [].
- **parse_dayforce(d, tenant, board)**: d must be a list; items with Title and ReferenceNumber; url = JobDetailsUrl when its
  host is exactly jobs.dayforcehcm.com, else `https://jobs.dayforcehcm.com/en-US/<tenant>/<board>/jobs/<ReferenceNumber>`;
  location = City, State joined ", ".
- **brassring_session(page)** → [token, cookie_value] or null: token = value of the hidden input named
  `__RequestVerificationToken`; cookie_value = value of the hidden input with id `CookieValue`, HTML entities decoded. Both needed.
- **parse_brassring(d)**: d.Jobs.Job[]; Questions[] become {QuestionName lower-cased: Value}; title = jobtitle; location = the
  first non-empty value whose name contains "location" or "city" (tags removed), else ""; url = Link; jobs without a title or
  Link are skipped.
- **clearcompany_site_id(page)** → the `data-site-id="<36-char GUID>"` value, else null.
- **parse_clearcompany(d)**: d.results[] → title positionTitle, location `location` (or ""), url = applyLink with a trailing
  "/apply" removed; kept only when there is a title and the url starts with https://.

## Addition (2026-11-03, e): forms that had no search (JSA-117) and live checks of company-list hints (JSA-119)

### resolve_careers.detect_ats — new URL forms (ident in the result)
- **dover**: `app.dover.com/apply/<name>/<job uuid>` or `app.dover.com/<name>/careers/<client uuid>` (also `app.dover.io`;
  uuid = 8-4-4-4-12 lower-case hex) → ident = the path from "apply/" or from "<name>/" up to and including the uuid,
  lower-cased ("apply/diffuse%20bio/1dabee06-…", "dover/careers/545c34b3-…"). An `app.dover.com/apply/<slug>` link with no
  uuid after it → ident = the slug alone (recorded, not searched). A uuid link never also yields the bare-slug hit.
- **paycom**: `paycomonline.net/v4/ats/web.php/jobs?clientkey=<32 hex>` (other query keys may come before it, joined with
  "&", "&amp;" or "&#038;") → ident = that whole text from "paycomonline.net" to the end of the key, lower-cased.
- **taleo** Business Edition: `<x>.tbe.taleo.net/<dir>/ats/careers/…?…org=<ORG>` with an optional `&cws=<digits>` right after
  → ident = that text lower-cased. A Business Edition URL never yields the bare host "tbe.taleo.net".
- **successfactors**: `career<digits?>[preview].successfactors.com|.eu|sapsf.com|sapsf.eu/career?…company=<id>` → ident = host
  lower-cased + "/career?…company=<id>" with the id's case KEPT (the id is case-sensitive). The plain host hit is also
  returned as before.

### ats_search.clean_ident — new forms
- dover: "apply/<name>/<uuid>" → "job/<uuid>"; "<name>/careers/<uuid>" → "client/<uuid>"; anything else (a bare slug) → null.
- paycom: besides `/portal/<32 hex>` and `/jobs/<32 hex>` at the end, an ident with `/jobs?…clientkey=<32 hex>` (entities
  "&amp;" / "&#038;" decoded, key followed by a non-hex character or the end) → the 32-hex key lower-cased.
- taleo: a Business Edition ident → tbe_ident(); a bare "tbe.taleo.net" or any `.tbe.taleo.net` ident tbe_ident() rejects → null.
  Enterprise hosts (`<x>.taleo.net`) unchanged.
- successfactors: an ident `<career host>/career?…company=<id>` → "<host lower-cased>/career?company=<id>" (id case kept,
  other query keys dropped); any other ident → its host only (the part before the first "/", lower-cased; "@site" dropped).

### ats_search.tbe_ident(ident) → string or null
HTML entities decoded twice; host must be `<label>.tbe.taleo.net`; first path segment = dir (word characters / dashes);
query key `org` (letters, digits, "_", "-") required; `cws` digits, default "1" (non-digit → "1"). → "<host>/<dir lower>/<ORG upper>/<cws>".

### ats_search.site_hosts(ident, site) → list
The ident's own host (part before "@" and before the first "/", lower-cased) comes first when it is a company career
host, then career_hosts(site); no duplicates. Own host is NOT used when: it is not a dotted host name; it ends in a vendor
domain (successfactors.com / .eu, sapsf.com / .eu, jobs.sap.com, phenompeople.com); it is a `*.jobs2web.com` host with
more than one label before "jobs2web.com" or whose label is vendor infrastructure (www, cdn, api, app, careers, jobs,
rmkcdn …); or it is the company's root domain or "www." + root domain.

### ats_search.parse_tbe(page) → postings
Each `<h4 class="…oracletaleocwsv2-head-title…"><a href="…viewRequisition…">Title</a></h4>` followed by `<div>` lines up
to `</div> <!--/.accordion-head-info` → title = link text (tags removed), url = href (entities decoded; kept only when it
starts with https://; each url once), location = the non-empty div texts that are not all digits, joined ", "
("Houston", "US-TX", "77095" → "Houston, US-TX").

### ats_search.parse_dover(d, name) → postings
d.results[] objects with id and title; skipped when is_published is false or is_sample is true. url =
`https://app.dover.com/apply/<name URL-quoted (spaces → %20)>/<id>` ("company" when name is empty); location = each
entry of `locations[]`: its `name` (else location_option.display_name), empty ones dropped, duplicates once, joined "; ".

### ats_search.parse_rmk — two more page shapes
Job links may be `/job/…/<digits>/` or `/<site code>/job/…/<digits>/` (one extra path segment). Location: the
`class="jobLocation…"` text as before, else the text of the element whose id ends in `-section-location-value`.

### resolve_careers.rmk_site(url, page) → list
A page that is itself an RMK career site → [["successfactors", <url host lower-cased>]]. Markers (case-insensitive):
"ssoCompanyId", "j2w.init", "var j2w", "jobs2web.com", "rmkcdn.successfactors.com". Needs at least two DIFFERENT markers,
one of them "ssoCompanyId" or "j2w.init". [] when the host is a vendor host (see site_hosts), the url has no host, or the
markers are missing.

### resolve_careers.inventory_hints(company) — which company-list hints are kept
Every hint (first 8 from the company list) is kept only when a live check says its board lists something now:
workday → a Workday search with an empty text returns postings; greenhouse / lever / ashby → the board list is non-empty;
any other system ats_search reads (iCIMS, Oracle Cloud, Taleo incl. Business Edition, UltiPro, SuccessFactors, Phenom,
Eightfold, Avature, ADP, Paycom, Dover, …) → ats_search.live(system, ident) is true. A hint whose ident clean_ident
rejects, or of a system ats_search does not read, is dropped without a request. Order of the kept hints = list order.

### ats_search.live(system, ident) → bool
False without any request when the system is not one ats_search reads, the ident is not a string, or clean_ident rejects it.

## Addition (2026-11-04, f) — the rest of the ats-scrapers systems (JSA-137)

### resolve_careers.detect_ats(text) — new URL shapes (each [system, ident]; ident lower-cased)
- tiktok: `lifeattiktok.com` / `api.lifeattiktok.com` → ident that host; `careers.tiktokusds.com` → that host.
- bytedance: `joinbytedance.com` or `jobs.bytedance.com` → that host.
- cornerstone: `<slug>.csod.com`, keeping `/ux/ats/careersite/<digits>` when the URL has it ("henkel.csod.com/ux/ats/careersite/1").
  A host that is only the end of a longer name (the `api.csod.com` inside `na.api.csod.com`) is not taken.
- gem: `jobs.gem.com/<slug>` → slug. pageup: `careers.pageuppeople.com/<client digits>/<channel>/<locale>` → "client/channel/locale"
  (an optional leading "mob/" is kept). personio: `<slug>.jobs.personio.com` or `.jobs.personio.de` → that host.
- recruiterbox: `<slug>.recruiterbox.com` or `<slug>.hire.trakstar.com` → slug. softgarden: `<slug>.career.softgarden.de` → host.
- join: `join.com/companies/<slug>` → slug. keka: `<tenant>.keka.com/careers[/<one segment>]` → "tenant.keka.com/careers[/segment]".
- gupy: `<slug>.gupy.io` → host. hrmos: `hrmos.co/pages/<id>` → id. herp: `herp.careers/v1/<id>` → id. beisen: `<slug>.zhiye.com` → host.
- recorded only (no search): moka `app.mokahr.com` / `hire-r1.mokahr.com` + `/social-recruitment/<slug>/<digits>` (or campus-) → that
  path with host; darwinbox `<slug>.darwinbox.in` / `.darwinbox.com` → host.
- eightfold on the company's own domain: `apply.careers.<name>.<com|net|org|io>` → that host.
- avature on the company's own domain: a URL whose path is `/careers/SearchJobs` or `/careers/JobDetail` (optionally after one
  locale segment like `/en_US`) on a host with at least three labels that does not start with www. → "host" or "host/en_us".
- ultipro: `recruiting<digits?>.ultipro.com` and now also `.ultipro.ca` boards.

### ats_search.clean_ident(system, ident) — the new systems (input is lower-cased first)
- tiktok: "lifeattiktok.com", "api.lifeattiktok.com" or "tiktok" → "tiktok"; "careers.tiktokusds.com" or "usds" → "usds"; anything else → null.
- bytedance: "joinbytedance.com", "jobs.bytedance.com" or "bytedance" → "bytedance"; else null.
- cornerstone: "<slug>.csod.com[/ux/ats/careersite/<n>[/…]]" → "<slug>.csod.com/<n>" (n = 1 when absent); a vendor slug (www, api, cdn …) → null.
- pageup: "[mob/]<digits>/<channel>/<xx or xx-yy>[/…]" → "<digits>/<channel>/<locale>" (mob/ and any tail dropped); else null.
- keka: "<tenant>.keka.com[/careers[/<portal>]]" → "<tenant>.keka.com" or "<tenant>.keka.com/<portal>"; the segments api, applyjob,
  jobdetails, content are not portals (→ just the host); a vendor tenant (www, app …) → null.
- personio / softgarden / gupy / beisen: exactly "<slug>.jobs.personio.com|de" / "<slug>.career.softgarden.de" / "<slug>.gupy.io" /
  "<slug>.zhiye.com" → unchanged; a vendor slug (www, api, app, login, portal, portal-oss — Beisen's CDN …) → null.
- gem / recruiterbox / join / hrmos / herp: a slug of letters, digits, '_', '.', '-' starting with a letter or digit → unchanged;
  vendor words (www, api, app, jsapi, v1, pages …) → null.
- moka / darwinbox → null (recorded, not searched).
- eightfold / avature on a non-vendor host (custom_host): a host with at least three labels that is not the bare company domain
  ("acme.com", "www.acme.com") → the host; for avature a first path segment that is a locale ("en_us", "en-us", "en", "global", "us")
  is kept, a 5-character one written as "en_US"; any other path dropped. "<x>.eightfold.ai" / "<x>.avature.net" keep the old rule.

### resolve_careers.page_systems(url, page) → list of [system, ident]
rmk_site(url, page) first, then: an Eightfold page — it contains "window._EF_GROUP_ID =" or "_EF_PRODUCT" AND the word "eightfold"
(any case) → ["eightfold", custom_host of the url host]; an Avature page — the url path is /careers/SearchJobs… or /careers/JobDetail…
(optionally after one locale segment) AND the page contains "avature" (any case) → ["avature", custom_host of host + locale]. Hosts
custom_host rejects give nothing. Each pair once.

### resolve_careers.big_tech(company) — new names (matched from the start, case-insensitive)
"TikTok" (optionally + Inc / Inc. / Shop / US / USA, nothing else) → [["tiktok", "tiktok"]]; a name starting "TikTok" that contains
"USDS" or "U.S. Data Security" → [["tiktok", "usds"]]; "ByteDance" (optionally + Inc / Ltd) → [["bytedance", "bytedance"]].
"TikTok Creator Fund Partners" → [].

### Parsers (pure; every posting is {"title", "location", "url"}; whitespace collapsed, HTML entities decoded)
- throne_location(item): walk item.city_info → .parent → … collecting en_name (else name): "San Jose, California, United States of
  America"; without city_info, the city_list entries' en_name (else name) joined "; " (duplicates once); else "".
- parse_throne(d, tenant): d.data.job_post_list[] with id and title (else name). url = "https://lifeattiktok.com/search/<id>" (tiktok),
  "https://careers.tiktokusds.com/usds/position/<id>/detail" (usds), "https://joinbytedance.com/search/<id>" (bytedance).
- csod_session(page) → [token, api]: token from `csod.context.token = '…'` (or "…"), else from a `"token":"…"` field; api = the first
  "https://<x>.api.csod.com" in the page, else "https://na.api.csod.com"; no token → [null, null].
- parse_csod(d, host, site, slug): d.data.requisitions[] with requisitionId and displayJobTitle; location = the FIRST entry of
  locations: its city, state, country (string fields that are present) joined ", "; url =
  "https://<host>/ux/ats/careersite/<site>/job/<requisitionId>?c=<slug>".
- parse_gem(d, slug): d is a list; d[0].data.oatsExternalJobPostings.jobPostings[] with title and extId (else id); url =
  "https://jobs.gem.com/<slug>/<extId>"; location = each location's name, else its city, else "Remote" when isRemote, joined "; ".
- parse_pageup(page, base): each `<a class="job-link" href="…/job/<digits>/…">Title</a>`; location = the next `class="location"`
  element's text before the following job link; url = href joined to base; each job id once.
- parse_personio(d, host): d is a list of {id, name, office, offices}; url = "https://<host>/job/<id>"; location = office, else offices joined "; ".
- parse_recruiterbox(d): d.objects[] with title and hosted_url starting "https://"; location = location.city, .state, .country
  (non-empty) joined ", "; when all empty and allows_remote is true → "Remote".
- schema_location(loc): a schema.org Place or a list of them → per place address.addressLocality, addressRegion, addressCountry
  (non-empty strings) joined ", "; places joined "; ", duplicates once.
- parse_softgarden(d): d.dataFeedElement[].item with title and url starting "https://"; location = schema_location(item.jobLocation).
- join_company_id(page): the digits in `"company":{"id":N` (else `"companyId":N`, quotes around N allowed) → string; else null.
- parse_join(d, slug): d.items[] with id and title; url = item.url, else "https://join.com/companies/<slug>/jobs/<idParam or id>";
  location = city.cityName, city.regionName, city.countryName joined ", ".
- keka_identifier(page): the GUID in "/ats/documents/<guid>/careerportal/" or "/careers/api/embedjobs/js/<guid>", lower-cased; else null.
- parse_keka(d, host): d is a list of {id, title, jobLocations[{city, state, countryName}]}; url = "https://<host>/careers/jobdetails/<id>";
  location = per entry city, state, countryName joined ", ", entries joined "; ".
- parse_gupy(page, host): the JSON in `<script id="__NEXT_DATA__" …>…</script>` → props.pageProps.jobs[] with id and title; url =
  "https://<host>/jobs/<id>"; location = workplace.address city, stateShortName (else state), country joined ", ". Bad JSON → [].
- parse_hrmos(page): each `<li class="pg-list-cassette …">` card: link "https://hrmos.co/pages/<x>/jobs/<id>", title = its <h2> text,
  location = its `class="sg-tag-location"` <li> text (else "").
- parse_herp(page, slug): each `<a … requisition-list-card__header-anchor … href="/v1/<slug>/<id>"><h2 …>Title</h2>`; url =
  "https://herp.careers/v1/<slug>/<id>"; location ""; each link once; links of another slug ignored.
- beisen_portal(page): the object after `var BSGlobal =` parsed as JSON → its PortalId as a string; missing / bad JSON → null.
- parse_beisen(d, host): d.Data[] with JobAdId and JobAdName; url = "https://<host>/portal/jobs/<JobAdId>"; location = LocNames joined "; ".
