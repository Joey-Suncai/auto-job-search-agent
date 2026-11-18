kind "merge": {"name": "...", "kind": "merge", "lists": [["A","B"],["B","C"],[]], "expect": {"options": ["A","B","C"], "option_sets": [["A","B"],["B","C"]]}, "spec_quote": "..."}
 - lists = the option list each merged form showed (in order); expect.option_sets absent / null when not needed (use null).
kind "answerable": {"name": "...", "kind": "answerable", "lists": [["Berlin","Chicago"],["United States","Finland"]], "pick": "United States", "expect": true, "spec_quote": "..."}
 - pick = the plain option text the user chose; expect true when saving is allowed (answerable on at least one list).
