# resolve_careers additions for Wellfound rows (2026-11-05, JSA-171 method A)
Context: resolve_careers.py finds the company's own posting for rows that only point at an aggregator, using the row's
company + title (the aggregator page itself is never fetched). Three additions; everything else is unchanged.

1. `kind(url)` → which aggregator a row's url is. Existing values: 'jobright' (url contains "jobright.ai/jobs/info/"),
   'handshake' (contains "joinhandshake.com"), 'linkedin' (matches "linkedin.com/jobs/view/" or "linkedin.com/comm/jobs/view/").
   New: 'wellfound' when the url (lower-cased) contains "wellfound.com/jobs/" followed by digits (a job page such as
   https://wellfound.com/jobs/4964451-sap-ixp-intern-ai-product-management), with "wellfound.com" either at the start, after
   "/" or after "." (www.wellfound.com). A Wellfound company page (wellfound.com/company/acme), a search page
   (wellfound.com/jobs?role=…) or another site → not 'wellfound'. Anything else → None (null).

2. `city_of(location)` → the row's city in lower case. Existing: "+ N" and everything after it is removed; the word "remote"
   (and a following "or") is removed; the text before the first comma is the city; the word "city" is removed from it;
   '' when nothing is left. New: a semicolon ends the city exactly like a comma: "New York; Recruiter recently active" →
   "new york"; "Syracuse; Fairborn" → "syracuse"; "Seattle; Recruiter recently active; icn_" → "seattle".

3. `title_companies(title, company)` → list of company names that the job title itself states and that differ from the
   row's company label (Wellfound's label is sometimes another company). Candidates, in this order:
   (a) after the LAST word "at" in the title: the rest of the title, when it starts with a capital letter and has at most
       5 words: "Data Scientist Intern - QuantumBlack, AI by McKinsey at McKinsey & Company" → "McKinsey & Company".
   (b) the part before the first separator — " - " or " – " (dash with spaces on both sides), ": " (colon + space) or " | " —
       when that part has at most 4 words, starts with a capital letter and contains no job word. Job words (whole words,
       any case): intern, interns, internship, internships, co-op, coop, summer, fall, spring, winter, any year 2000-2099,
       program, engineer, engineering, analyst, analytics, analysis, scientist, science, developer, manager, management,
       product, data, research, associate, student, graduate, college, junior, senior, business, finance, financial,
       marketing, sales, operations, strategy, technology, software, machine, learning, digital, investment, pricing, ai,
       ml, it, fellow, fellowship, apprentice, apprenticeship, trainee, remote, hybrid, onsite, on-site, full-time,
       part-time, entry-level, "new grad". "a Workday employer - AGI - AI Power Systems Intern" → "a Workday employer"; "Intern - Data Analytics" → nothing from (b).
   (c) the title's first word (a trailing , . : removed) when it is
       · CamelCase: a capital, lower-case letters, then another capital and at least one more letter ("an employer", "PepsiCo",
         "DoorDash") — but not one of these words (any case): GenAI, DevOps, MLOps, DataOps, AIOps, FinTech, PowerBI,
         SaaS, IoT, eCommerce, JavaScript, TypeScript, GitHub, LinkedIn, YouTube, ChatGPT, OpenAI; or
       · capitalised words joined by hyphens ("Georgia-Pacific", "Rolls-Royce") that contain no job word
         ("Full-Time" → nothing); or
       · all capitals, at least 3 letters, not one of AI ML IT PM BI US USA HR UX UI QA GTM SWE MBA MS BS PHD IP RF ERP
         CRM GIS FP NLP LLM GEN IOT EV HVAC PRODUCT DATA INTERN INTERNSHIP SUMMER MARKETING FINANCE SALES NEW SR JR, AND the
         title has a second word that is not a job word: "SAP iXp Intern - AI Product Management" → "SAP";
         "SAP Business Analyst Intern" → nothing ("Business" is a job word); "NIKE" alone → nothing (no second word).
   Then drop a candidate that is the same company as the label (same name ignoring case, punctuation, spaces and suffixes
   such as Inc / LLC / Corp / Co: label "a Workday employer" drops "a Workday employer"; label "Directv" drops "a Workday employer"), one that looks
   like a job title (contains intern / internship / co-op / "summer 20xx"), and a repeat of an earlier candidate. At most
   3 names are returned, in order. Nothing found → [].
   The resolver searches the label's careers system first; only when that finds no matching posting are the
   title_companies searched (a match still needs the same title-similarity rule as before).

Return {"cases": [...]}. Each case: {"name": str, "fn": "kind" | "city_of" | "title_companies", "args": kind {"url": str} ·
city_of {"location": str} · title_companies {"title": str, "company": str}, "expect": kind → str or null · city_of → str ·
title_companies → [str, ...], "spec_quote": str, "ambiguous": false}.
