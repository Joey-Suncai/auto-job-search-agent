A JSON array of 36 cases of two kinds.
Kind 1: {"name": "<unique snake_case>", "fn": "bachelor_options", "opts": [strings], "expect": [list of strings in order]}.
Kind 2: {"name": "<unique snake_case>", "fn": "level_of", "value": "<text>", "expect": "phd"|"master"|"bachelor"|"other"|null}.
Make 20 of kind 1 and 16 of kind 2. Use the real lists in the spec (Micron, Entrust, a Workday employer) plus plausible Workday variants; include B.S.-only, specialty bachelor's, "or" combinations, empty list, order of ranking.
