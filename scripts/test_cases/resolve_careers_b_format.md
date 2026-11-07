Same case format as before, with two more functions:
{"name": "...", "fn": "norm_title" | "names_company" | "match_posting" | "domain_candidates" | "board_guesses",
 "args": norm_title: {"t": "..."}; names_company: {"page": "<html>", "company": "...", "final_url": "..." or ""};
         match_posting: {"title": "...", "location": "...", "postings": [["title","url","location"]]};
         domain_candidates: {"company": "..."}; board_guesses: {"company": "..."},
 "expect": norm_title: string; names_company: true/false; match_posting: url or null; domain_candidates: [domains];
           board_guesses: [[ats, slug]],
 "spec_quote": "...", "ambiguous": false}
Write only cases for the "Additions (2026-11-03)" section: 4 norm_title, 3 match_posting with abbreviations, 3 names_company,
6 domain_candidates, 4 board_guesses.
