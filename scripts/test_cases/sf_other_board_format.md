Return {"cases": [...]}. Each case: {"name": str, "args": {"picked": str, "job": {"source"?: str, "url"?: str}, "defaults"?: [str]}, "expect": {"board": str} | {"none": true}, "spec_quote": str, "ambiguous": false}.
"picked" = the list's answer; "job" = the job's record; "defaults" = the configured default boards (omit it = the standard default, LinkedIn).
Write 24 cases: rule 1 = 9 (sources and URL hosts, source winning over URL), rule 2 = 7 (incl. 2 with a non-standard "defaults"), rule 3 = 8.
