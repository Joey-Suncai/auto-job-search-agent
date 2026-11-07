# load_open_answers(text) — which drafted answers the plan may use

`open_answers.md` is written by the materials step. It holds blocks like:

    ## <question id> — <question label>
    limit: 1200 characters · length: 711 · uses: S6
    <answer body, one or more lines>

The loader returns a list of (label, body) pairs, in file order, one per block that has a usable answer:
- The `limit:` line is metadata and is never part of the body. Leading/trailing blank lines are trimmed.
- The header line before the first `## ` block (e.g. "# Open answers ...") is ignored.
- A block whose body (after removing the limit line and trimming) is empty, or is exactly the word `ASK`
  (any letter case), is the materials step saying "this cannot be answered from the candidate's facts" —
  that block is NOT returned, so the form field stays unanswered and goes to the candidate.
- A body that merely contains the word "ask" inside a sentence is a normal answer and is returned.
- Labels are returned with runs of whitespace collapsed to one space and trimmed; letter case is kept.
