Each case is one call: {"name": "...", "fn": "adp_wfn_api" | "gh_boards_in_page" | "job_url" | "parse_tenant" | "page_verdict" | "clearcompany_route" | "clearcompany_site_id" | "read_ids" | "pick",
 "args": {...},   // adp_wfn_api: {"link"}; gh_boards_in_page: {"page"}; job_url: {"host","tenant","site","path"};
                  // parse_tenant: {"url"}; clearcompany_route: {"link"}; clearcompany_site_id: {"page"}; read_ids: {"text"} (expect = sorted JSON array of ids);
                  // pick: {"jobs": [{"id": ...}], "due_ids": [...], "ids": [...] or null} (expect = the list of picked ids in order); page_verdict: {"url","final_url","title","text","http"} — for long texts you may give
                  //   "text_repeat": {"chunk": "...", "times": N} instead of "text" (text = chunk repeated N times, joined by "\n")
 "expect": ...,   // the return value (lists as JSON arrays, null for None); for page_verdict only {"status": "..."}
 "spec_quote": "...", "ambiguous": false}
Cover every function with 5-7 cases, including near misses.
