# Case format: form prefetch (JSA-237)

Return {"cases": [...]}; every case has "name" (unique, snake_case), "kind" (one of the kinds below), "input", "expect",
"spec_quote" (the spec sentence the expectation comes from) and optionally "ambiguous": true + "why".

## kind "route" — what happens to ONE form question of a prefetched job
input: {"question": "<label as the form wrote it>", "options": ["..."] (may be empty),
        "rule": "confident" | "uncertain" | "none",
        "second_opinion": "agree" | "disagree" | "error" | null   (only meaningful when rule = "uncertain"),
        "suggestion": {"answer": "<text or option>" | "ASK", "fact": "<name of the candidate fact used>" | null} | null
                      (DeepSeek's suggestion; only meaningful when rule = "none")}
expect: {"route": "used" | "joey" | "sheet",
         "high_risk": true | false,
         "derived_block": true | false}
  - "used" = the answer goes into the form without asking Joey; "joey" = Joey answers it himself, one by one, no
    suggestion is offered for one-click acceptance; "sheet" = it goes on the question sheet with DeepSeek's suggestion
    for Joey's confirmation (never used on its own).
  - "derived_block" = the question is listed in the top block of fact-derived suggestions that Joey can accept with one click.
  - high-risk categories: visa, sponsorship, citizenship, export control, EEO, GPA, dates.

## kind "rank" — the greedy order of the morning sheet
input: {"jobs": {"<job id>": {"tier": "A"|"B"|"C"|"D", "needs": ["<question id>", ...]}, ...}, "max_questions": <int>}
  "needs" = the questions this job still needs answered (each question id is the same question across jobs; a job with
  an empty list is already ready).
expect: {"sheet": ["<question id>", ...] (in sheet order), "ready_after": <number of jobs ready once every sheet question is answered>,
         "left_out": ["<question id>", ...] (sorted alphabetically: questions not on the sheet)}
  Tie-break when two questions would make the same number of jobs ready: the one more jobs ask comes first (tier A/B jobs
  counted before C/D), then the alphabetically smaller id.

## kind "stale" — is a job read on this run?
input: {"last": null | {"read_at": "YYYY-MM-DD", "status": "ok" | "closed" | "error" | "restricted"},
        "today": "YYYY-MM-DD", "recheck_days": <int>, "only_new": true | false}
  "last" = the job's previous prefetch (null = never read).
expect: {"read": true | false}

## kind "cache" — do two DeepSeek requests share one cached answer?
input: {"a": {"question": "...", "options": [...], "facts_version": "..."}, "b": {...}}
expect: {"same_answer_reused": true | false}

## kind "merge" — are two wordings counted as one question before any DeepSeek grouping?
input: {"a": "<wording>", "b": "<wording>"}
expect: {"same": true | false}
  (only the simple merge: case, numbering like "1." / "Q3.", punctuation and spacing are ignored; nothing else)

## kind "restriction" — a prefetched form question states an identity restriction
input: {"question": "<label>", "citizen_or_pr": true | false}
expect: {"job_ineligible": true | false}
