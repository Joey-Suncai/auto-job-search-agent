# Tasks only Joey can do: skip in test batches, keep in real ones (JSA-141, Joey 2026-11-04)

Joey: 「在测试的时候，如果要交视频的 intern 自动跳过，但是回头等我上线或者我自己正式开始投递的时候，遇到要我完成的不要跳过。」

## joey_tasks(plan) → list of labels
- `plan["needs_user"]` is a list of questions the agent could not answer, each with a "label".
- A question is a Joey-only task when its label asks him to record something: it contains (case-insensitive, as a
  whole word) "video", "Loom", "Vimeo", "HireVue", "VidCruiter", "Spark Hire" / "SparkHire", "Willo", or "record" /
  "recorded" / "recording" followed by "yourself", "a", "an" or "your" (e.g. "record a short introduction").
- Returns those labels in order. Text questions, ratings, document uploads (resume, transcript), GPA etc. are not.
  A missing or empty needs_user → [].
- Whole word: "videos" or "videography" do not count ("video" must stand alone); "Loom" inside "Bloomberg" does not count.

## is_test_batch(batch) → bool
- True when `batch["purpose"] == "cert"`, or the batch "name" contains "cert" (case-insensitive). Otherwise False
  (missing name / purpose → False).

## joey_gate(row, plan, test) → row
- Computes joey_tasks(plan). When non-empty: sets `row["joey_tasks"]` to the list; and when `test` is true and
  row["status"] is "ok" or "flagged", sets row["status"] = "skipped_joey_task". A real batch (test false) never
  changes the status. Rows with another status (e.g. "closed_or_unreadable") keep it.
- When there are no tasks the row is returned unchanged (no "joey_tasks" key added).
