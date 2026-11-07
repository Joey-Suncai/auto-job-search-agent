Return {"cases": [...]}. Each case:
{"name": "...", "fn": "parse_yc" | "parse_wwr" | "known" | "pick_new",
 "args": parse_yc {"page": str} · parse_wwr {"xml": str} · known {"rows": [...]} ·
   pick_new {"cards": [card, …], "rows": [store rows]}   (the harness computes ids / pairs with known(rows)),
 "expect": parse_yc / parse_wwr → list of cards (all 8 keys) · known → {"ids": [[board, id], …] sorted, "pairs_count": int} ·
   pick_new → list of the kept cards' ids in order,
 "spec_quote": "...", "ambiguous": false}
26 cases: parse_yc 6 (entities in data-page, relative and absolute url, missing companyName / visa, posting without url
skipped, no attribute, bad JSON), parse_wwr 6 (CDATA title, no colon, two colons, empty region / state / country parts, item
without link, entities), known 4, pick_new 10 (already in store by id, by company + title, by alt key; keep() false for a senior
or non-U.S. or no-level title; 3rd card of one company dropped; a duplicate later in the list; a YC "Product Manager Intern"
in New York kept). For pick_new give cards with all 8 keys. Keep the HTML / XML short.
