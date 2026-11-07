# USAJOBS source + gate reader — spec (2026-11-03)

Helpers (from indeed_search.py): TRK = a whole-word match of data, analy* (analyst / analytics / analysis), AI, A.I., machine learning, ML, LLM, GenAI, agent / agentic, product, business intelligence, BI, insight(s). SENIOR = senior, sr, sr., staff, principal, lead, director, head of, VP, vice president, manager II, architect, PhD, Ph.D, postdoc, MBA. norm(company) = lower case, & → and, punctuation removed, words inc / llc / corp / company / ltd / group / the / services / technologies / labs / global / international / us / usa / america removed, spaces collapsed. title_key(title) = lower case, bracket text removed, 20xx years / summer / intern(s) / internship(s) / new grad / remote / us / usa removed, non-alphanumerics → one space, trimmed. GS-12 … GS-15 grades count as senior. In pick_new the position id is the last run of digits at the end of the url (else the item's id). strip(html) = tags removed, entities decoded, whitespace collapsed.

## items(payload)
Pure (tested). An API response → [{'id', 'title', 'org', 'location', 'url', 'posted', 'closes', 'who', 'grade'}]: SearchResult.SearchResultItems[].MatchedObjectDescriptor with PositionID, PositionTitle, OrganizationName (else DepartmentName), PositionLocationDisplay (else the PositionLocation names "; "-joined), PositionURI, the dates PublicationStartDate / ApplicationCloseDate cut to YYYY-MM-DD, UserArea.Details.WhoMayApply.Name (else ''), grade = "GS-<LowGrade>" from UserArea.Details when JobGrade[0].Code is "GS" (else ''). Items without an id, title or url are skipped.

## keep(item, today)
Pure (tested). His tracks (TRK on the title), not senior (SENIOR on the title, or grade GS-12 … GS-15), and not closed (closes empty or on / after `today`, ISO dates compared as text).

## known(rows)
Pure (tested). Store rows → (USAJOBS position ids, {(norm org/company, title_key)}).

## pick_new(found, ids, pairs, today)
Pure (tested). Kept items not in the store and not repeated, at most 2 per organisation, in order.

## usajobs_jd(d)
Pure (tested). One USAJOBS API MatchedObjectDescriptor → {'title', 'text', 'loc'} or None (no title). text = "Who may apply: <UserArea.Details.WhoMayApply.Name>." (when present), then QualificationSummary, UserArea.Details JobSummary, MajorDuties (a list, joined), Requirements, Education, and "Security clearance: <SecurityClearance>." (when present) — HTML removed, whitespace collapsed; loc = PositionLocationDisplay (else the PositionLocation names "; "-joined).
