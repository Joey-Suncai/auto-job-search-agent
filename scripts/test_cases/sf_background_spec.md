# SuccessFactors background rows → values from the candidate's facts (2026-11-04)

A SuccessFactors application page has background sections with repeated rows. The resume parser pre-fills them, often
badly. A planner takes one section {head, rows} and decides, from the facts below, what every row must hold.

Facts (today = 2026-11):
- Work 1: Job Title "Business Analyst Intern", Company "Hyde Park Investment Services, Inc.", Location "Champaign, Illinois",
  from 08/2025 to 10/2025, not current; a row belongs to it when its Company contains "hyde park" (case-insensitive, any
  spacing/punctuation).
- Work 2: Job Title "Consulting Assistant Intern", Company "Frost & Sullivan", Location "Shanghai, China", from 06/2024 to
  08/2024; a row belongs to it when its Company contains "frost".
- Education 1: school "University of Chicago", level master, major "Applied Data Science", from 2026-09 to 2027-12,
  current (in progress); a row belongs to it when its School Name contains "chicago".
- Education 2: school "University of Illinois Urbana-Champaign", level bachelor, major "Economics", from 2024-08 to 2026-05,
  finished (graduated); a row belongs to it when its School Name contains "illinois".
- No division / department is on file for either job.

Rules:
- Section kind: heading "Previous Employment" / "Work Experience" / "Employment History" → work; "Formal Education" /
  "Education" → education; any other heading (e.g. "Professional References", "Language Skills", "Certifications/Licenses")
  → not handled (the planner returns nothing).
- Each non-empty row is matched to a fact (work by Company, education by School Name). The first row matching a fact is
  set from it; a later row matching the same fact is to be deleted; a non-empty row matching no fact is "unmatched"
  (left for a person). A row whose every box and date is empty takes the next fact (in the order above) that has no row
  yet. Facts left with no row are to be added (listed by Company / school name).
- Work row values: Job Title, Company, Location from the fact; Start Date = first day of the start month (MM/DD/YYYY,
  e.g. 08/01/2025); End Date = last day of the end month (e.g. 10/31/2025, 08/31/2024). "Summary of Work Performed" is
  only set when the row's summary is empty (then from the fact's description; otherwise left as is). Division is never
  set (no fact).
- Education row values: Type = the option starting with "Master" for the master's school, "Bachelor" for the bachelor's;
  Subject = the major; School Name = the school; Result = "In Progress" for the current school, "Graduated" for the
  finished one; From Date = first day of the start month (09/01/2026, 08/01/2024); End Date = last day of the end month
  (12/31/2027, 05/31/2026).
