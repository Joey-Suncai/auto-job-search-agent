Return {"cases": [...]}. Each case:
{"name": "...", "fn": one of "detect_ats_e" | "clean_ident" | "tbe_ident" | "site_hosts" | "parse_tbe" | "parse_dover" |
 "parse_rmk" | "rmk_site" | "inventory_hints" | "live_offline",
 "args": detect_ats_e {"text": str} · clean_ident {"system": str, "ident": str} · tbe_ident {"ident": str} ·
   site_hosts {"ident": str, "site": str} · parse_tbe {"page": str} · parse_dover {"d": any, "name": str} ·
   parse_rmk {"page": str, "base": str} · rmk_site {"url": str, "page": str} ·
   inventory_hints {"company": str, "hints": [[system, ident], …], "live": [[system, ident], …]}
     (hints = what the company list returns; live = the boards whose live check is true — for workday give the ident as
      "host/tenant/site" text, e.g. "acme.wd5.myworkdayjobs.com/acme/External"; never use smartrecruiters) ·
   live_offline {"system": str, "ident": str} (the harness makes every request fail loudly),
 "expect": detect_ats_e → list of [system, ident] for ONLY the systems dover, paycom, taleo, successfactors (others ignored) ·
   clean_ident / tbe_ident → string or null · site_hosts → list of strings · parse_* → list of {"title", "location", "url"} ·
   rmk_site → list of [system, host] · inventory_hints → list of [system, ident] kept, in order · live_offline → false,
 "spec_quote": "...", "ambiguous": false}
Write only cases for "Addition (2026-11-03, e)": 30 cases — detect_ats_e 7 (dover job link, dover careers link, dover bare
slug, paycom clientkey with &#038;, taleo TBE, a TBE link that must not give "tbe.taleo.net", successfactors company= with
mixed-case id), clean_ident 7 (dover ×2 + bare slug, paycom clientkey, taleo bare tbe host, successfactors company= with extra
query keys, successfactors plain host with @site), tbe_ident 2, site_hosts 4 (jobs2web company host, vendor host, career
host with site, bare company domain), parse_tbe 2, parse_dover 2, parse_rmk 1 (site-coded link + location-value id),
rmk_site 2, inventory_hints 2, live_offline 1. Keep snippets short and realistic.
