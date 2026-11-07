# Picking test internships from a public job board (platform certification)

Each posting: company, title, location, text (the job description), url, key, board (the board token, e.g. "dvgroup"). Context: `blocked` = company names that
must not be used, `blocked_boards` = board tokens already used (a company is blocked when its board token is in
blocked_boards, or when its normalized name — lower case, company suffixes like Inc / LLC / Labs /
Technologies removed — matches), `known` = posting keys or urls already in the store, `flags` = the list of offline
warning flags already computed for this posting (CLEAR = clearance / U.S. person / export control, NOSPON = no visa
sponsorship, DEG = PhD/MBA only, START = start date outside Summer 2027, STALE = unreadable, DEF = defense company,
OLD/TRACK/APPLIED = soft, ignored here).

Return [keep, reason], checking in this order (the first failing check gives the reason):
1. company blocked (by name, by board, or by a near match: with letters and digits only, lower case, a blocked name of
   4+ characters inside the company name or the board token — "doordashusa" contains "doordash" — or the company name /
   token of 4+ characters inside a blocked name) → [false, "company blocked (tier A/B, tracker or skip list)"]
2. key or url in known → [false, "already in the store"]
3. title is not an internship → [false, "not an internship"]. An internship title contains the word intern / interns /
   internship / internships / co-op / coop. "Internal", "International", "Internet" do not count.
3a. title says PhD / Ph.D / doctoral, undergraduate / undergrad, or "college fair" / "career fair" / "university fair"
   → [false, "not open to him (PhD / undergraduate only / one school's fair)"]
3b. title names a role that needs a professional degree — legal, law clerk, law student, paralegal, juris, J.D.,
   nursing, pharmacy, medical student, ministry, pastor, dental, veterinary → [false, "needs a professional degree (law / medicine / ministry)"]
4. location does not name a U.S. place → [false, "not a U.S. location"]. A U.S. place: "United States", "USA", "U.S.",
   "Remote - US", a U.S. state name, ", <two-letter state code>" (e.g. "Austin, TX"), or a major U.S. city (New York,
   NYC, San Francisco, Seattle, Chicago, Boston, Austin, Los Angeles, Atlanta, Denver, Miami, Philadelphia, Washington DC,
   Bay Area). A list naming a U.S. place and another country still counts. "Remote" alone does not.
5. not a Summer 2027 posting → [false, "not Summer 2027"]: the title has 2026 but not 2027; or the title names fall /
   autumn / winter / spring, or a month from January–April or September–December, without also saying summer; or "2027" appears in neither title nor text.
6. any of CLEAR, NOSPON, DEG, START, STALE, DEF in flags → [false, "flags " + those flags joined by ", " in the order
   CLEAR, NOSPON, DEG, START, STALE, DEF].
7. otherwise [true, "ok"].
