# Three helpers of a Workday career-site search

1. parse_tenant(url) → [host, tenant, site] or null.
   - https://<tenant>.wdN.myworkdayjobs.com/[<locale>/]<site>/job/... → host = the full host name lower-cased, tenant = the
     first label of the host, site = the first path segment after an optional locale such as "en-US". A URL whose first
     segment is "wday" or "job" (no site) → null.
   - https://wdN.myworkdaysite.com/recruiting/<tenant>/<site>/... → host, tenant (lower-cased), site.
   - Anything else (greenhouse, lever, other domains, empty) → null.
2. keep_posting(title, location) → true when the posting is a summer-style internship in the U.S.:
   - the title says "intern", "interns", "internship" or "internships" as a word ("Internal Auditor" is not);
   - the title does not name a fall / autumn / spring / winter / co-op / coop / year-round / part-time term;
   - if the title contains any 4-digit year, the only year must be 2027;
   - the location must not be clearly outside the U.S. (a non-U.S. country or city such as India, Canada, UK, London,
     Toronto, Bangalore) unless it also says United States / USA / U.S.; "Remote", U.S. cities and "3 Locations" are fine.
3. job_key(external_path) → the Workday job id after the LAST underscore at the end of the path, lower-cased
   ("/job/Chicago-IL/Data-Intern_R-12345" → "r-12345", trailing slash ignored); no underscore-id → "".
