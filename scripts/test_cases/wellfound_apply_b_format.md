A JSON array of cases. Each case:
{"name": "<unique snake_case, prefix b_>", "fn": "clean_url" | "posting_like" | "pick_external" | "classify", "args": {...}, "expect": ...}
- clean_url: args {"url": <string or null>}; expect a string.
- posting_like: args {"url": <string>}; expect true / false.
- pick_external: args {"page": <page record>}; expect a string.
- classify: args {"page": <page record>}; expect {"via": ..., "ats_url": ..., "apply_url": ...} (reason is not checked).
Focus on what a first batch did not cover: classify rules 2 (a sign-in URL in `opened`), 3 (redirect to /company/…;
"/company/acme/jobs/123-x" is still a job page), 6 (sign in to apply text), 7 (Applied button), 8 (a Wellfound apply
link), 9 with `peeked` true, 10 (no Apply control); apply-label near misses ("Apply filters", "Send application");
posting_like for Workday /details/, Workable /j/<code>, iCIMS /jobs/<digits>/…, a SuccessFactors company-host
/job/<slug>/<digits>; a known ATS URL with a url= parameter that must not be unwrapped; tracking-parameter case
(UTM_Source); pick_external preferring an ATS posting found by rule (d) over a non-ATS "Apply" link. About 4 clean_url /
posting_like, 3 pick_external, 9 classify.
