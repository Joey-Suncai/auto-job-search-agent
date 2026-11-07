# Gate JD readers for an employer and Google (eligibility_fetch.py, JSA-133)

`strip(h)` = script/style removed, tags → spaces, entities decoded, whitespace collapsed.

## js_string_after(page, marker)
Pure (tested). The double-quoted JavaScript string right after `marker` in `page`, still escaped (backslash + next character kept as a pair), without its quotes; None when the marker is missing or the string never ends.

apple_parse(page)
Pure (tested). A jobs.apple.com details page → {'title', 'text', 'loc'} from the page's `JSON.parse("…")` loader data (loaderData.jobDetails.jobsData: localizations en_US (else en_UK, else any) → posting with postingTitle, jobSummary, description, minimumQualifications, preferredQualifications; text = those four joined, HTML removed; loc = the jobsData.locations names with their countryName, "; "-joined). {'closed': True} when the loader data parses but holds no `jobDetails` (an employer's "Page not found … no longer available" page; that sentence alone is not enough — every page carries it in its translations). None when nothing can be read (after ats-scrapers apple.py).

google_parse(page)
Pure (tested). A Google Careers posting page → {'title', 'text', 'loc'} or None. title = og:title; the JD = the title, then the lines from the first "Minimum qualifications" or "Minimum qualifications:" (else "About the job[:]") up to (not including) the first line that starts with "Information collected and processed" or "Google is proud to be an equal opportunity" (else the end), script / style removed, tags → line breaks, entities decoded, blank lines dropped, joined with spaces; loc = the line after the first line exactly "place" (Material icon name) before the JD, else ''. None when no JD line is found.
