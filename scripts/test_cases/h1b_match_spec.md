# Spec: company name -> H-1B facts, and the company-table fix (JSA-098)

Postings name a brand ("Walmart Global Tech"); the H-1B data names legal entities ("WAL-MART ASSOCIATES, INC.").
One employer must resolve to one family of filings, and one employer must be one row in the company table.

## Data
Records: {"name", "fy25", "total", "first"} — fy25 = FY2025 LCA filings, total = filings FY2010–2026, first = first
fiscal year (null or 9999 = unknown). Several records may share one employer; their numbers add up.

## norm(name)
Lower case; "&" -> " and "; drop ".com" at a word end; every character that is not a-z / 0-9 / space becomes a space;
the token pair "n a" (from "N.A.") is dropped; then these whole words are dropped: inc, incorporated, llc, corp,
corporation, co, company, ltd, limited, plc, lp, llp, holding, holdings, group, the, usa, us, america, na, services,
technologies, technology, lab, labs, global, international; spaces collapse, ends trimmed.
Examples: "Amazon.com Services LLC" -> "amazon"; "Citibank, N.A." -> "citibank"; "The Home Depot" -> "home depot".

## How an employer record is indexed
- A record's name is split on " d/b/a " (also "dba", "d b a", "doing business as", "aka", "a/k/a", case-insensitive,
  with spaces around); each part is normalised and is a key. "Fidelity Technology Group, LLC d/b/a Fidelity
  Investments" -> keys "fidelity" and "fidelity investments".
- If a key has ≥ 2 words and its first word is ≤ 4 letters, the key with the first two words joined is also a key:
  "wal mart associates" -> also "walmart associates".
- The record's employer identity is its first key; records with the same first key are one employer (numbers add up).

## lookup(company) -> {fy25, total, first, names, match}
0. ENTITIES (checked first; JSA-103): if the lower-cased, punctuation-free name (suffixes kept) — else norm(company) —
   is an ENTITIES key, its list is the set of exact employer keys (each "that exact key only", no prefix family, no
   descriptor drop). An empty list means the employer has no filings: result 0, 0, null, [].
1. Root(s): if the lower-cased, punctuation-free name (suffixes kept) is in RAW_ALIASES, those roots; else
   ALIASES[norm(company)] if present; else norm(company). A root that starts with "=" means "that exact key only".
2. Hits of a root k: the employers indexed under k exactly, plus — only when k is longer than 3 characters, k is not
   in GENERIC and k has no "=" — every employer with a key that starts with k followed by a space, EXCEPT keys whose
   next word after k is "it" (an IT staffing firm sharing the word) and keys in NOT_FAMILY.
   One-word rule (JSA-103): when k is a single word and not in FAMILIES, the prefix family is kept only if every
   remaining candidate key has the same second word ("revel systems" + "revel consulting" -> no family, exact key only;
   "medline industries" + "medline industries holdings" -> kept). Words in FAMILIES keep the whole family.
3. No hit: drop trailing words that are in DESCRIPTORS (careers, jobs, hq, hiring, recruiting) while > 1 word is left,
   map through ALIASES again, and look again.
4. Result: fy25 and total = sums over the hit employers; first = smallest known first year (null when none);
   names = the hit employers' names, largest (fy25 + total) first, at most 4. No hit -> 0, 0, null, [], match "none".

Tables (fixed configuration):
- ALIASES: meta -> meta platforms; facebook -> meta platforms; alphabet -> google; aws -> amazon; amazon web services ->
  amazon; jp morgan / jpmorganchase / jpmorgan chase -> jpmorgan; ibm -> ("=ibm", "international business machines");
  pwc -> pricewaterhousecoopers; ey / ernst young -> ernst and young; deloitte consulting -> deloitte;
  walmart global tech / walmart tech / sam s club -> walmart; verizon communications / verizon wireless /
  cellco partnership -> ("verizon", "cellco partnership") (and "verizon" itself maps there too); telus digital -> telus; ul solutions -> ul; zt systems -> zt; veeam software -> veeam;
  virginia tech -> virginia polytechnic institute; hewlett packard -> hp; citi / citigroup -> citibank;
  bofa -> ("=bank of", "bofa"); applied -> applied intuition.
- RAW_ALIASES (matched before suffixes are dropped): "bank of america" -> ("=bank of", "bofa"); "us bank" ->
  ("u s bank"); "capital group" and "capital group companies" -> ("capital companies", "capital research and management").
- GENERIC (one word that never takes a prefix family): american, america, north, south, east, west, national, united,
  general, first, new, global, state, university, city, county, advanced, applied, integrated, digital, data, smart,
  premier, capital, central, pacific, atlantic, western, eastern, southern, northern, midwest, texas, california,
  virginia, florida, york, allied, advantage, building, ryan, parallel, realm, leland, bank, insurance, health, energy,
  financial, consulting.
- NOT_FAMILY: snap on, snap on business solutions, snap finance, blackrock microsystems, oracle robotics, aerospace testing engineering and certification, anchorage school district, blueprint medicines, cohere health, datalab infotech, ellipsis health, emerson college, flint healthcare, gallup mckinley county schools, guidepoint security, magna infotech, momentum consulting, mosaic health system, mutual of omaha insurance, nash county board of education, nomura research institute, penta engineering, radiance informations, rain drop foundation, rover resources, segra software solutions, seneca nursing home, shepherd university, spectral md, synergent tech solutions, tessera therapeutics, toyota technological institute at chicago, tyler independent school district, vast data, voyager therapeutics, wonder porcelain, yotta systems.
- FAMILIES (one-word brands whose whole prefix family is one employer): abbott, abbvie, acuity, alcon, ally, amazon, apple, ascension, barclays, blackrock, bosch, brookfield, bunge, cigna, cummins, danfoss, dell, deloitte, disney, emerson, evercore, fedex, globalfoundries, grainger, hearst, hitachi, hubbell, intel, ipsos, iqvia, koch, labcorp, lazard, leidos, lenovo, magna, marsh, meijer, merck, micron, morningstar, mufg, nike, nokia, nomura, novartis, optum, parsons, philips, point72, qualcomm, rapp, regeneron, rivian, rockstar, samsung, sanofi, scor, siemens, sony, stantec, telus, toyota, transunion, veolia, verizon, visa, zoom.
- ENTITIES (name -> exact employer keys; [] = no filings): frontier technology -> []; apex technology inc -> []; the loomis company -> []; murphy usa -> []; propel labs -> []; prudential plc -> []; millennium -> []; gemini -> []; spectrum -> []; genesis -> []; prolific -> []; armada -> []; maxima -> []; vantage -> []; citadel -> ['citadel americas', 'citadel enterprise americas', 'citadel information']; archer -> ['archer aviation', 'archer aviation operating']; harvey -> ['counsel ai']; cadence -> ['cadence design systems']; flex -> ['flextronics']; galaxy -> ['galaxy digital']; gallagher -> ['arthur j gallagher service']; hartford -> ['hartford fire insurance']; impact -> ['impact tech']; intuitive -> ['intuitive surgical', 'intuitive surgical operations']; kodiak -> ['kodiak robotics']; mohawk -> ['mohawk industries']; nationwide -> ['nationwide insurance']; parker -> ['parker hannifin']; pilot -> ['pilot travel centers']; planet -> ['planet', 'planet pbc']; polaris -> ['polaris', 'polaris industries']; unity -> ['unity sf']; viking global -> ['viking investors']; enova -> ['enova financial']; wing -> ['wing aviation'].

## sponsor_label(facts)
"Strong H-1B sponsor" if fy25 ≥ 100 or total ≥ 1000; else "Some H-1B history" if fy25 or total > 0; else
"Unknown — verify".

## group_key(company) — when two company rows are one employer
If the raw name is in RAW_ALIASES: its first root (without "="). Else the first root of ALIASES[norm] (or norm),
trailing DESCRIPTORS dropped, then ALIASES once more (first root, without "="). Two rows are one employer when their
group keys are equal — except a pair listed in NOT_SAME ({"Brunswick", "Brunswick Group"}, {"Sentinel Group", "Sentinel Technologies"}, {"Astera", "Astera Labs"}), which stays two rows.

## Store fix
- refresh(row, facts): sets h1b_fy25 = fy25 (0 when null), h1b_total = total, h1b_since = first or "" ; sets
  sponsorship = sponsor_label(facts) only when the row's sponsorship is missing, empty, or one of the three labels
  above. A posting-level label ("Blocked: no sponsorship", "Blocked: citizenship required", "Posting offers
  sponsorship") is kept. Every other field is unchanged.
- merge_companies(rows): rows with the same group key become one row. The kept row is the one with the most
  open_roles (tie: the shorter company name, then alphabetical); it keeps its company name. open_roles, internships,
  new_grad, a_roles are summed. best_score / best_role / best_tier come from the row with the highest best_score;
  gc_sponsor / gc_perm / gc_months from the row with the highest numeric gc_perm. referral / contacts / warm_path stay
  the kept row's unless they are empty or "Cold", then the first other row's non-empty, non-"Cold" value. tracks =
  the union of every row's "; "-separated tracks in order of first appearance. Every output row (merged or not) then
  gets refresh() with lookup(its company). The result also says which names were merged into which kept name.
