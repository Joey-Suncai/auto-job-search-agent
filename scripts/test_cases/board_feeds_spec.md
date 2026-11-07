# board_feeds.py — spec (JSA-139)

Cards from two job boards (Y Combinator startup jobs, We Work Remotely) become job rows for a student who wants Summer
2027 internships or 2027/2028 new-grad roles in the United States in data / analytics / BI / product / AI.
Several helpers come from indeed_search.py and dice_search.py; they are summarised here so the cases can be written.

Shared rules (from indeed_search):
- **base keep** (title, location) is True only when ALL hold: the title has a track word (data, any word starting with
  "analy", AI, A.I., machine learning, ML, LLM, GenAI, agent / agentic, product, business intelligence, BI, insight /
  insights); the title has no senior word (senior, sr, sr., staff, principal, lead, director, head of, VP, vice president,
  manager II, architect, PhD, Ph.D, postdoc, MBA); the location is not clearly outside the U.S. ("Toronto, ON",
  "London, UK" → out; "Remote", "", U.S. cities / states → fine); and the level is not None.
- **level**: a title with fall / autumn / spring / winter / co-op / year-round / part-time → None. A title with
  intern / internship (not "internal") → "Internship" unless it names a year other than 2027. Otherwise a year other
  than 2027 / 2028 → None. Otherwise a new-grad word (new grad, new graduate, recent grad, entry level, entry-level,
  junior, associate product manager, APM, early career, university grad, university graduate, graduate program,
  rotational, class of 2027 / 2028, 2027 start, 2028 start) → "New Grad / Entry". Anything else → None.
- **norm(company)**: lower case, "&" → " and ", ".com" dropped, punctuation → space, the words inc, llc, corp,
  corporation, co, company, ltd, plc, lp, llp, holdings, group, the, usa, us, services, technologies, technology, labs,
  global, international (and a few more) removed, spaces collapsed.
- **title_key(title)**: lower case; text in ( ) or [ ] removed; 20xx years, summer, intern(s), internship(s),
  new grad, new graduate, remote, us, usa removed; non-alphanumeric runs → one space; trimmed.

## alt_key(title) → str
Lower case; bracket text is KEPT (the brackets themselves become spaces); the words "start", "summer" and any 4-digit
year 20xx are removed; every run of non-alphanumeric characters becomes one space; trimmed.
Examples: "Data Engineer Graduate (Data Platform E-commerce) - 2027 Start" → "data engineer graduate data platform e commerce";
"Data Engineer Graduate - Data Platform E-commerce - 2027 Start" → the same.

## keep(title, location) → bool
base keep(title, location) AND the title has none of these whole words (case-insensitive): design, designer, sales,
marketing, security, cyber, soc, audit (and words starting with audit), quality, qa, fraud, aml, anti-money, credit,
investment, accounting, hardware, mechanical, electrical, creative, customer, recruit… (recruiter, recruiting), hr,
people, edi, helpdesk, help desk.
Examples: "Junior Data Analyst", "Detroit, Michigan" → true; "Entry Level AML Analyst", "Orlando, Florida" → false;
"Junior QA Analyst" → false; "Data Analyst" (no level word) → false; "Senior Data Analyst Intern" → false.

## parse_cards(html) → list of {"guid", "company", "title", "location"}

A card is {"board": "yc" | "wwr", "id", "company", "title", "location", "url", "type", "visa"}.

## parse_yc(page) → list of cards
The page has an attribute `data-page="…"`: its value, after HTML entities are decoded (&quot; → "), is JSON; the postings
are its `props.jobPostings` list. For each posting with a non-empty `title` and `url`: board "yc"; id = the last path
segment of `url` (a trailing "/" ignored); company = `companyName` (trimmed, "" when missing); title (trimmed); location
(trimmed, "" when missing); url = `url` when it starts with "http", else "https://www.ycombinator.com" + url; type = `type`
("" when missing); visa = `visa` ("" when missing). Missing attribute or JSON that does not parse → [].

## parse_wwr(xml) → list of cards
An RSS feed. Each `<item>…</item>`: title = the <title> text (a CDATA wrapper removed, HTML entities decoded), link =
<link>. Items without a title or a link are skipped. The title is "Company: Role": split at the FIRST ": " → company =
left part, title = right part (both trimmed); no ": " → company "", title = the whole title. id = the last path segment
of the link; location = the texts of <region>, <state>, <country> that are non-empty, in that order, joined ", "
("Anywhere in the World", "Virginia", "" → "Anywhere in the World, Virginia"); type = <type> text ("" when missing);
visa ""; board "wwr"; url = the link.

## known(rows) → (ids, pairs)
rows = store rows {"company", "title", "url", "ats_url"}. ids = the set of (board, id lower-cased) found in url or ats_url:
"ycombinator.com/companies/<slug>/jobs/<id>" → ("yc", id); "weworkremotely.com/remote-jobs/<id>" → ("wwr", id).
pairs = {(norm(company), title_key(title))} ∪ {(norm(company), alt_key(title))} for every row.

## pick_new(cards, ids, pairs) → list of cards
In card order, a card is kept when: (board, id lower-cased) is not in ids; neither (norm(company), title_key(title)) nor
(norm(company), alt_key(title)) is in pairs; keep(title, location) is true; and fewer than 2 cards of the same
norm(company) were kept before. A kept card's key and pairs are added, so a later duplicate is dropped.
