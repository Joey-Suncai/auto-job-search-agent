Return a JSON array. Each case is one of:
{"name": "snake_case", "fn": "parse_extra", "text": "file contents with \n line breaks", "expect": [["lever", "acme"], ...]}
{"name": "snake_case", "fn": "board_name", "board": "rhombus-systems", "expect": "Rhombus Systems"}
About 2/3 parse_extra (comments, blank lines, duplicates, URLs, wrong kinds, upper case, spaces around the colon), 1/3 board_name.
