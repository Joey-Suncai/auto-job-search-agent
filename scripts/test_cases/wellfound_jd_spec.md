# wellfound_parse(page) — spec (JSA-108, eligibility gate reader)

`page` is the HTML of a public Wellfound job page (wellfound.com/jobs/<id>-<slug>). Returns {"title", "text", "loc"} or
null (None).

1. Text lines: remove <script>…</script> and <style>…</style> blocks; replace every HTML tag with a line break; decode
   HTML entities (&amp; → &, &#39; → ' …); trim each line; drop empty lines.
2. If no line is exactly "About the job" → null.
3. The JD lines are the lines after the first "About the job" line up to (not including) the first later line that is
   exactly "About the company", or to the end when there is none. If the last JD line is exactly "Apply Now", drop it.
   text = the JD lines joined with single spaces, runs of whitespace collapsed to one space, trimmed. Empty text → null.
4. title: the text inside <title>…</title> (entities decoded, trimmed), cut before " at <Company> •" or
   " at <Company> |" (the first " at " that is followed by a name and then " •" or " |"), and before " | Wellfound";
   trimmed. No <title> → "".
5. loc: the line right after a line exactly "Job Location", when that line comes before "About the job" and the next line
   is also before "About the job"; otherwise "".
6. Lines such as "Visa Sponsorship", "Not Available", "Relocation" before "About the job" are never part of the text.
