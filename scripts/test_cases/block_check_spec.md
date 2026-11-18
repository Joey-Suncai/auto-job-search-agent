# Profile-block check — spec (JSA-294)

Job application forms have repeat blocks: one **education** block per school and one **work** block per job. Their box
labels are short ("School or University", "Degree", "Field of Study", "Overall Result (GPA)", "From", "To (Actual or
Expected)", "Job Title", "Company", "Location", "I currently work here", "Role Description"). The check decides, by code,
whether every box of every block holds the right fact for the entry that block belongs to.

## The candidate's entries (fixed for the tests; today = 2026-11-11)
Education:
- E1 **University of Chicago** (also written "THE UNIVERSITY OF CHICAGO", "Chicago, U of", "UChicago"): master's level,
  "M.S. Applied Data Science", start 2026-09, end 2027-12, **in progress (current)**. Fields of study accepted: Applied Data
  Science, Data Science, Data Analytics, Computer Science, Information Systems, Applied Statistics, Statistics,
  "Data Analytics and Data Science", and any option containing Data / Statist / Analytic / Computer / Information
  (Joey's fallback list). **No GPA yet.**
- E2 **University of Illinois Urbana-Champaign** (also "University of Illinois at Urbana-Champaign", "UIUC", "Illinois, U of"):
  bachelor's level, "B.A. Economics", start 2024-08, end 2026-05, **completed**. Field: Economics ("Economics (B.A.)",
  "Other" accepted). GPA: overall / cumulative **3.60**; major GPA **3.85**; institution GPA **3.81**.
Work:
- W1 **Hyde Park Investment Services, Inc.** (also "HYDE PARK INVESTMENT SERVICES"): Job Title "Business Analyst Intern",
  Location "Champaign, Illinois", 08/2025 – 10/2025, ended. Description: "Designed a 0–5 scoring rubric for ChatGPT-assisted
  MD&A review, requiring cited evidence and senior analyst validation; contributed to a workflow that cut end-to-end review
  time by 70%. Cleaned Finviz and Yahoo Finance data and built standardized Excel forecast models for 14 companies …"
- W2 **Frost & Sullivan**: Job Title "Consulting Assistant Intern", Location "Shanghai, China", 06/2024 – 08/2024, ended.
  Description: "Created tables and charts for 60+ pages of client-ready decks using Think-cell and Excel … Co-built, with a
  consultant, a levelized-cost model for Fortune 500 clients to assess green methanol's cost competitiveness …"

## Input
A list of rows in page order. A row = {label, page (what the form shows), source, section (optional, e.g. "Education 2"),
kind (optional "education" / "work")}. Rows that belong to blocks are recognised by any of: a section; a kind; a source
"wd_profile:education" / "wd_profile:work" / "wd_answered:<section>"; a label prefix "Education (<school>): <box>" or
"Previous Employment (<company>): <box>"; or a rule source ("rules:school", "rules:degree", "rules:discipline",
"rules:start_month", "rules:start_year", "rules:end_month", "rules:end_year") on a short box label — such rule rows only
form a block when the block contains a School box. A lone question ("What is your GPA?") is not a block.

## Grouping
Rows of one block are consecutive. A new block starts when the section / prefix changes, when the kind changes, or (no
section) when a box repeats (a second "School or University", a second "Job Title"). "Start date month" and "Start date
year" are different boxes of the same block.

## Which entry a block belongs to
The entry named by the block's School / Company box (or its prefix / section entry); else, for a work block with no company,
the entry whose job title the block shows. A block whose school / company is not one of the entries above (e.g. "Xi'an
Jiaotong-Liverpool University", "Job Searching Agent" as the only text) → its School / Company box is wrong.

## Verdict per box: ok / bad / unknown
- empty page value → ok (another check handles empty boxes).
- School / Company: ok when it names the block's entry; bad otherwise.
- Degree: the level of the shown option (Master's / MS / M.S. / Masters / Post Graduate → master; Bachelor's / BA / B.A. /
  Bachelors / Undergraduate → bachelor; PhD / Doctorate; Associate / High School) must equal the entry's level → ok, else bad;
  an option with no level → unknown; "Other" → ok.
- Field of study: ok when it is one of the entry's accepted fields (or contains one); bad when it is the OTHER school's
  field (e.g. "Economics" in the UChicago block, "Data Science" in the UIUC block); otherwise unknown.
- GPA ("GPA", "Overall Result (GPA)", "Grade Point Average"): UIUC — a label with "major" wants 3.85, a label with
  "institution" wants 3.81, any other wants 3.60 (a band like "3.5 - 3.9" holding it is ok; "3.60/4.0" ok). N/A / none / empty
  → ok. UChicago has no GPA: any number → bad, N/A → ok.
- From / Start, To / End / Graduation date: compare year and, when both have it, month with the entry's start / end.
  Formats: "8/2025", "08/2025", "2026-09", "09/01/2026", "Sep 2026", "September", "2026". Different → bad. Not a date → unknown.
- "Still attending" / "I currently attend": Yes / checked ok for UChicago (current), bad for UIUC; No ok for UIUC.
  "Degree Achieved" / "Did you graduate": Yes ok for UIUC, bad for UChicago; "In Progress" ok for UChicago, bad for UIUC.
- Job Title: ok when it equals the entry's title (case-insensitive); bad otherwise (e.g. the other job's title, "Job
  Searching Agent").
- Location: ok when it contains the entry's city; otherwise unknown.
- "I currently work here": checked / Yes → bad (both jobs ended); No / unchecked → ok.
- Role Description: ok when it shares at least about a third of its words with the entry's description; clearly another
  text (e.g. "Personal project, built with Claude Code …") → bad.
- Any other box in a block (Minor, Division, Type of Business, City) → unknown.

## Output
problems(rows) = one line per bad box (page values only). judge(rows) gives every block row a verdict.
