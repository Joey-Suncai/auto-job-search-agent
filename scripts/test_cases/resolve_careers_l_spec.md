# names_company additions (2026-11-04 night, JSA-149)
Context: names_company(page_html, company, final_url) decides whether a homepage belongs to the company. `ws` = the
company's distinctive words (lower case, generic words such as inc / group / services / health / financial / national
removed). `label` = the registrable label of the final host ("bcbsm" for www.bcbsm.com). `page names` = title + og tags +
JSON-LD name + copyright line + logo alt, lower case. These three additions are new; everything else is unchanged.

1. Initials without small words: the label may equal the initials of the company name with "of", "the", "and", "for"
   left out: "an employer" → "bcbsm" passes the host check (the page names must still name the
   company as before: e.g. contain all of the words squashed together, or its first two words).
2. Whole-name domain, empty names: when the label equals all distinctive words squashed together (or the whole name
   squashed) and the page names are empty (rendered by JavaScript), the page counts as the company
   ("Precision Castparts" on precisioncastparts.com with an empty page) — unless the host is foreign / parked (unchanged).
3. Lead-word domain (`lead_word(label, ws)`): true when the company has 2+ distinctive words, the label equals the FIRST
   word exactly, that word has ≥ 4 characters, is not all digits, and is not a common word (american, national, united,
   global, first, general, international, north, south, east, west, central, pacific, atlantic, new, great, state, city,
   county, university, health, bank, capital, financial, insurance, energy, data, digital, smart, tech, technology,
   technologies, systems, software, consulting, partners, medical, care, home, life, team, business, precision, advanced,
   applied, premier, quality, superior, summit, pioneer, liberty, apex, blue, green, red, black, white, gold).
   names_company then accepts the page only when ALL hold: lead_word is true; the first word appears as a whole word at
   least TWICE in the page names; and at least one OTHER distinctive word of the name with ≥ 3 letters appears as a whole
   word anywhere in the page HTML text (tags stripped). "IDEMIA Public Security" on idemia.com (names say "idemia" several
   times, body says "public security") → true; "Nissan Motor Corporation" on nissan.com whose page is "in loving memory of
   Uzi Nissan" twice and never "motor" → false; a page titled just "Nissan" → false.
