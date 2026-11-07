Each case is one of:
{"name": "...", "fn": "click_out_index", "args": {"labels": ["...", "..."]}, "expect": <integer index or null>, "spec_quote": "...", "ambiguous": false}
{"name": "...", "fn": "opened_stop", "args": {"info": {"url": "...", "title": "...", "text": "...", "password": false}}, "expect": "blocked" | "signin" | "", "spec_quote": "...", "ambiguous": false}
{"name": "...", "fn": "classify", "args": {"page": {<page record>}}, "expect": {"via": "...", "ats_url": "...", "apply_url": "..."}, "spec_quote": "...", "ambiguous": false}
Test only the "Click-out" section (click_out_index, opened_stop) and how a click-out result reaches classify: about 4
click_out_index cases (dialog labels like "Cancel", "Apply on website", "Send application"; case / space variants; near
misses), 4 opened_stop cases (a Workday / Greenhouse job page, a challenge page, a company sign-in page with a password
field, a Wellfound login URL) and 4 classify cases (a peeked outside-Wellfound dialog whose click-out put a company
posting URL into `opened`, one where it put a careers home page there, one with click_out_stop "signin", one with
click_out_stop "blocked"). Page urls are Wellfound job pages like https://wellfound.com/jobs/4964451-data-intern.
