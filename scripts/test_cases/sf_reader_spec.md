# SuccessFactors job pages in the eligibility gate

## sf_url(url) -> bool
True for a SuccessFactors career-site job URL: it has the query parameter "ats=successfactors" (after ? or &), or the host
contains ".successfactors.com" / ".successfactors.eu", or "career<digits>.sapsf." (e.g. career4.sapsf.com), or it is
"jobs.sap.com/job/…", or its path is "/job/<slug>/<7 or more digits>" optionally followed by "/" and then the end, "?" or
"#". False for Workday, Greenhouse, Lever, LinkedIn and other URLs, and for "/job/<slug>/<6 or fewer digits>".

## sf_text(html) -> {"title", "text", "loc"} | null
html is the page source. If it has no `itemprop="description"` → null. title = the text right after the element carrying
itemprop="title" (up to the next "<"), stripped; loc = the text right after class="jobGeoLocation" (up to the next "<"),
stripped; text = everything after the description element's opening tag, up to the first of class="jobfooter",
id="footer" or "<footer" that comes after it (or 30000 characters), with <script>/<style> blocks and all tags removed and
whitespace collapsed. If that text is empty → null. Missing title / location → "".
