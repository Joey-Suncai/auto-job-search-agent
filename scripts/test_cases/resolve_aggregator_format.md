Each case is a JSON object:
{"name": "short id",
 "row": {"url": "...", "company": "...", "title": "...", "ats_url": "" or absent},
 "follow": {"<url>": "<final url>" or null},          // follow(url) result; a url not listed → null
 "known": [["greenhouse", "acme"]], "guesses": [["lever", "acme"]], "tenants": [["acme.wd5.myworkdayjobs.com", "acme", "External"]],
 "boards": {"greenhouse:acme": [["Title", "https://..."]], ...},        // board(ats, token); missing → []
 "wd": {"acme:External": [["Title", "https://..."]]},                   // wd_search(..., tenant, site, ...); missing → []
 "expect": null or {"code": "...", "ats_url": "..." (only for redirect / board / workday)},
 "expect_follow_called": true | false | absent,
 "spec_quote": "...", "ambiguous": false}
