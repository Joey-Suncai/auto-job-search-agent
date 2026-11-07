# dice_search.py — spec (JSA-111)

Dice search result cards become job rows for a student who wants Summer 2027 internships or 2027/2028 new-grad roles in
the United States in data / analytics / BI / product / AI. Several helpers come from indeed_search.py and are specified
there; they are summarised here so the cases can be written.

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
The page is split at every occurrence of the text `data-testid="job-card"`; each piece after the first is one card.
In a card:
- title and short id come from the first `aria-label="View Details for <TITLE> (<hex id>)"`; a card without it is skipped.
  HTML entities in the title are decoded (`&amp;` → `&`).
- guid = the value in the first `href="/job-detail/<guid>"` (hex digits and dashes), lower-cased; if missing, the hex id
  from the aria-label.
- The card's text nodes (text between tags, trimmed, empty ones dropped, entities decoded) are listed in order. The
  first text node is the rest of the split tag (it starts with `role=`, e.g. ` role="article">` trimmed to
  `role="article">`); company = the second text node, or "" when the first does not start with `role=`.
- location = the text node right after the first text node equal to the title; "" if none.
Example card: `<div data-testid="job-card" role="article"><a aria-label="View Details for Junior Data Analyst (abc123)" href="/job-detail/1f2e-33aa"> </a><span>Acme Corp</span><span>Apply Now</span><a>Junior Data Analyst</a><span>Austin, Texas</span></div>`
→ `{"guid": "1f2e-33aa", "company": "Acme Corp", "title": "Junior Data Analyst", "location": "Austin, Texas"}`.

## known(rows) → (ids, pairs) and pick_new(cards, ids, pairs) → list of cards
known: for every store row, a Dice job id is read from `url` or `ats_url` when it contains `dice.com/job-detail/<id>`
(lower-cased); pairs = (norm(company), title_key(title)) and (norm(company), alt_key(title)) for every row.
pick_new walks the cards in order and keeps a card only when: its guid is not in ids; neither (norm(company),
title_key(title)) nor (norm(company), alt_key(title)) is in pairs; keep(title, location) is true; and fewer than 2
cards of the same norm(company) were already kept. A kept card adds its guid and both pairs, so a repeat later in the
list is dropped.
