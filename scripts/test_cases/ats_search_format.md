Return {"cases": [...]}. Each case:
{"name": "...", "fn": one of "root_domain" | "career_hosts" | "clean_ident" | "with_site" | "parse_icims" | "parse_rmk" |
 "parse_phenom" | "parse_oracle" | "parse_taleo" | "parse_jazz" | "parse_jobvite" | "parse_rss" | "postings_offline" | "decide",
 "args":
   root_domain {"host": str} · career_hosts {"site": str} · clean_ident {"system": str, "ident": str} ·
   with_site {"systems": [[system, ident], …], "site": str} ·
   parse_icims {"page": str, "host": str} · parse_rmk {"page": str, "base": str} · parse_phenom {"page": str} ·
   parse_oracle {"d": object, "host": str, "site": str} · parse_taleo {"d": object, "host": str, "cs": str} ·
   parse_jazz {"page": str, "host": str} · parse_jobvite {"page": str, "slug": str} · parse_rss {"xml": str} ·
   postings_offline {"system": str, "ident": str, "query": str}   (only cases that must return [] without a request) ·
   decide {"row": {"title": str, "location": str, "ats_url": ""}, "systems": [[system, ident], …],
           "postings": {"<system>:<ident>": [[title, url, location], …]}}   (a board missing from postings returns no postings),
 "expect":
   root_domain → string · career_hosts → list of strings · clean_ident → string or null · with_site → list of [system, ident] ·
   parse_* → list of {"title", "location", "url"} · postings_offline → [] ·
   decide → {"code": str, "system": str} plus "ats_url" when code is "match",
 "spec_quote": "...", "ambiguous": false}
Write 30 cases: clean_ident 9 (several systems, junk hosts, 2f prefix, @site suffix, ultipro with and without board id,
oracle dev host), root_domain / career_hosts 3, with_site 2, parsers 10 (each parser at least once, with a near miss —
a link to another host, a duplicate href, a phenom job with a non-ATS applyUrl), postings_offline 2, decide 4.
Keep page snippets short and realistic.
