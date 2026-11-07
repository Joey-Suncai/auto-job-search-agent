Each case is a JSON object with "fn" naming the function under test:
{"name": "short id", "fn": "detect_ats" | "names_company" | "is_challenge" | "norm_title" | "city_of" | "match_posting" | "decide",
 "args": ...,  // detect_ats: {"text": "..."}; names_company: {"page": "<html>", "company": "...", "final_url": "..." or ""};
               // is_challenge: {"status": 403, "page": "..."}; norm_title: {"t": "..."}; city_of: {"location": "..."};
               // match_posting: {"title": "...", "location": "...", "postings": [["title","url","location"]]};
               // decide: {"row": {"title": "...", "location": "...", "ats_url": ""}, "systems": [["greenhouse","acme"]],
               //          "postings": {"greenhouse:acme": [["title","url","location"]]}}   (key = system + ":" + ident; for
               //          workday ident is [host, tenant, site] and the key is "workday:<tenant>/<site>"); missing key → []
 "expect": ...,  // detect_ats: [[system, ident]] (workday ident = [host, tenant, site]); names_company / is_challenge: true/false;
                 // norm_title / city_of: string; match_posting: url string or null (only the URL is compared);
                 // decide: {"code": "...", "system": "...", "ats_url": "..." (only when code = match)}
 "spec_quote": "...", "ambiguous": false}
Write roughly: 6 detect_ats, 6 names_company, 4 is_challenge, 3 norm_title, 3 city_of, 6 match_posting, 5 decide.
