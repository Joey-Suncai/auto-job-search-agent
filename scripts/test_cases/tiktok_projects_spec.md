# TikTok / ByteDance dry-run runner — project blocks (spec, JSA-100)

After the resume upload, the site's parser fills a "Project Experience" section with blocks. The parser makes mistakes:
it can turn a student-club role into a project (e.g. a block named "minister of the organization department") and it can
miss real projects. The candidate's real projects are listed in the config. The helper decides, without a browser, what
to do with each parsed block.

## project_plan(entries, projects) → (plan, problems)
- `entries`: the project blocks on the page, in page order: `[{"idx": "project[1]", "name": "<parsed project name>"}, ...]`.
  `name` may be empty, null, or have extra spaces / line breaks (count them as one space).
- `projects`: the config list: `[{"name", "match_re", "role", "start", "end", "description"}, ...]`.
  `match_re` is a case-insensitive regular expression searched in the parsed name; when `match_re` is missing, the config
  `name` itself is searched (literally, case-insensitive). `start` / `end` are months such as "2026-03", "03/2026" or
  "2026.3"; `end` null (or missing / empty) means the project is ongoing.
- Each config project is used at most once. Blocks are matched in page order: a block takes the first config project
  (in config order) that is not used yet and whose pattern is found in the block's name. A block with an empty name
  matches nothing.
- A matched block → one plan item `{"idx": <the block's idx>, "name": <config name>, "role": <config role, "" if missing>,
  "start": "YYYY-MM", "end": "YYYY-MM" or "Present" when ongoing, "desc": <config description, "" if missing>}`.
- A block that matches no config project → no plan item, and one problem string that contains the block's idx and the
  words "not in config" (the runner then removes that block from the form).
- Every config project that no block matched → a plan item with `"idx": null` (the runner adds a new block for it),
  after all the matched items, in config order. This is not a problem.
- Returns the plan list first, the problems list second. An empty config list → every block is a problem, plan empty.
