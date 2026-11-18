# JSA-420 — saving a batch of answers fast, and never losing one

The answers Joey gives for form questions are saved by `qa_add.py` into the `qa` list of the profile file. After saving, the
program re-answers every stored form (the "replay", about 30 seconds, read-only) to report what the new answer changes.
Before this change the replay ran after every single answer: 16 answers took about 8 minutes, and during that time a batch
session could not use the profile.

## What the program does now
1. **One writer at a time.** Every run of `qa_add.py` that saves an answer takes an exclusive lock on the profile
   (a lock file next to it) from before it reads the profile until the answer is written, the browser bundle rebuilt and
   the data home commit made. The lock is released BEFORE the replay. Two runs started at the same moment both succeed and
   BOTH answers are in the profile afterwards (no answer is lost, the file stays valid JSON). A run that only lists the
   table or checks overlaps takes no lock. A run that is killed never leaves the lock held.
2. **Replay once per batch.** `qa_add.py --batch answers.json` (a JSON list of answers) saves every answer exactly as a single
   run would (each with its own overlap check and answer check; a failing item is reported and skipped, the others are still
   saved), then runs ONE replay and makes ONE commit for the whole batch. The batch holds the profile lock for all items and
   releases it before the replay.
3. **The replay reason of a batch** names the entries the batch really changed. `changed_numbers(before, after)` takes two
   lists (the qa list before and after) and returns the 1-based numbers of the entries in `after` that are new or differ
   from the entry at the same position in `before`, in order; an unchanged entry is not listed; removed entries are ignored.
   `batch_reason_n(nums)` turns a list of numbers into text: the numbers joined by "," (e.g. "5,7,9"); when there are more
   than 12 only the first 12 are written, followed by " (+K more)" where K is the count minus 12; an empty list gives "?".
4. The profile file is written through a temporary file and renamed, so a reader never sees half a file.
