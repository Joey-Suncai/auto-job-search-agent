# complete_jobs: fill the dashboard fields a job row is missing (data/store/jobs.jsonl)

Some writers (Workday search, LinkedIn / Built In import, Lever / Ashby board search, cert supply) add job rows with
only id, company, title, url, level, tier, score, elig… The dashboard needs more fields. `complete(rows, companies)`
returns the rows with the missing fields filled. Rules:

1. **Never overwrite.** A field that is present with a value (including 0, "", "No", False) is kept as it is. Only a
   field that is absent or null (None) is filled. Exception: rule 2 (`sources` given as a list is converted).
2. **sources** must be a string of labels joined by "; ". If `sources` is a list → map each item through the label table below (unknown items kept as is), then join with "; ".
   If absent/null → use the row's `source` key mapped to a label: workday_search → "Workday search",
   linkedin → "LinkedIn", builtin → "Built In", ashby_search → "Ashby boards", lever_search → "Lever boards",
   cert_supply → "Cert supply"; any other non-empty value is used as is; if `source` is also absent but the row has
   `cert_supply` set → "Cert supply"; otherwise "Unknown".
3. **n_sources** (if missing) = number of labels in the final `sources` string.
4. **Company facts** come from the companies table, matched on a normalized company name: lowercase, "&" → " and ",
   ".com" dropped, non-alphanumerics → space, the words inc, incorporated, llc, corp, corporation, co, company, ltd,
   limited, plc, lp, llp, holding(s), group, the, usa, us, america, na, services, technologies, technology, lab(s),
   global, international removed, spaces collapsed. So "Acme Corp." matches "ACME, Inc." Fields copied when missing:
   sponsorship, h1b_fy25, h1b_total, h1b_since, gc_sponsor, gc_perm, gc_months, referral, contacts, warm_path.
   No match → sponsorship "Unknown — verify", h1b_fy25 0, h1b_total 0, h1b_since "", gc_sponsor "", gc_perm "",
   gc_months "", referral "Cold", contacts "", warm_path "". A matched company whose own field is null/absent gives
   that same default.
5. **referral_detail** (if missing) = the final `referral` value. li_connections and li_alumni (if missing) = 0.
6. **remote** (if missing) = "Yes" when the location contains the word "remote" (any case), else "No".
   salary (if missing) = "". posted (if missing) = "".
7. **track** (if missing or null) = from the title, first match wins, case-insensitive whole words:
   AI words (ai, machine learning, ml, llm, genai, generative, agent, agentic, nlp, deep learning, computer vision,
   research engineer, mlops…) → "AI Agentic Eng"; data engineering words (data engineer, analytics engineer, etl,
   data pipeline, database, data warehouse…) → "Data Engineer"; analyst words (data analyst, business analyst,
   business intelligence, bi analyst, marketing analyst, operations analyst…) → "Data Analyst"; product words
   (product manager, product analyst, program manager, product…) → "Product Manager"; data science words (data
   scien, analytics, quantitative, quant, statistic, research analyst, data…) → "Data Sci / Analytics";
   nothing matches → "Other". A track already present (even "Other") is kept.
8. **Score parts** s_role, s_timing, s_sponsor, s_greencard, s_referral, s_fresh (if missing) = 0.
9. Other fields (elig_*, ats_*, notes, score, tier, rank…) are never added or changed. Input rows are not mutated;
   the number and order of rows is unchanged. Running complete twice gives the same result as once.
