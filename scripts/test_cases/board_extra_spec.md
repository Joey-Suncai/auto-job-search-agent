# Two helpers for a job-board list file

1. parse_extra(text) reads a text file that lists company job boards, one per line, and returns a list of [kind, board] pairs
   in file order. kind is "lever" or "ashby"; board is lower-case.
   - A line is "lever:<site>" or "ashby:<org>" (spaces around the colon allowed; kind is case-insensitive), or a full board or
     job URL on jobs.lever.co (also jobs.eu.lever.co) or jobs.ashbyhq.com — the board is the first path segment.
   - "#" starts a comment (whole line or end of line); blank lines are skipped.
   - Lines with any other kind (e.g. "greenhouse:stripe"), other hosts, or a board name containing spaces or other characters
     than letters, digits, "-", "_", "." are dropped. A pair that already appeared is dropped (first one kept).
2. board_name(board) turns a board name into a display name: split on "-", "_" or ".", capitalize each part (first letter
   upper, rest lower), join with one space. Empty parts are dropped; an empty input returns "".
