Each case is one call: {"name": "...", "fn": "icims_read_url" | "wd_page_gone" | "clean_url" | "closed_on" |
"page_verdict" | "render_pick" | "render_merge",
 "args": {...},   // icims_read_url/clean_url: {"link"}; wd_page_gone: {"html"}; closed_on: {"text","today"};
                  // page_verdict: {"url","final_url","title","text","http","today"} — for long texts you may give
                  //   "text_repeat": {"chunk": "...", "times": N} instead of "text" (text = chunk repeated N times, joined by "\n");
                  // render_pick: {"lines","rows","cap"}; render_merge: {"x","v"}
 "expect": ...,   // the return value; for page_verdict only {"status": "..."}; for render_merge the fields to check
 "spec_quote": "...", "ambiguous": false}
Cover every function with 3-6 cases, including near misses.
